from __future__ import annotations

import argparse
import atexit
import json
import os
import random
import shutil
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DETECTABLE_URL = "https://discord.com/api/v9/applications/detectable"
IDLE_SOURCE = Path(os.environ.get("FAKEWIN_EXE") or Path(__file__).resolve().parents[2] / "build" / "fakewin.exe")
IDLE_ARGS: list[str] = []
CREATE_NO_WINDOW = 0

FORBIDDEN_CHARS = set('<>:"|?*')


@dataclass(frozen=True)
class Game:
    app_id: str
    name: str
    exe_rel: Path


def fetch_detectable() -> list[dict]:
    req = urllib.request.Request(DETECTABLE_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if not isinstance(data, list) or not data:
        raise RuntimeError("detectable list came back empty or in an unexpected shape")
    return data


def safe_rel_path(raw: str) -> Path | None:
    """Turn a registered exe string into a safe relative path, or None."""
    raw = raw.lstrip(">").replace("\\", "/").strip("/")
    if not raw or any(c in FORBIDDEN_CHARS for c in raw):
        return None
    parts = raw.split("/")
    if any(p in ("", ".", "..") for p in parts) or not parts[-1].lower().endswith(".exe"):
        return None
    return Path(*parts)


def load_played(path: Path) -> dict[str, dict]:
    """app_id -> {name, last_run (unix seconds), runs}. a missing or corrupt file means nothing played yet."""
    try:
        data = json.loads(path.read_text(encoding="utf8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_played(path: Path, played: dict[str, dict]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(played, indent=1), encoding="utf8")
    tmp.replace(path)


def mark_played(played: dict[str, dict], game: Game) -> None:
    rec = played.get(game.app_id, {})
    played[game.app_id] = {"name": game.name, "last_run": int(time.time()), "runs": int(rec.get("runs", 0)) + 1}


def pick_games(entries: list[dict], count: int, rng: random.Random,
               played: dict[str, dict] | None = None) -> list[Game]:
    pool: list[Game] = []
    for e in entries:
        for ex in e.get("executables") or []:
            if ex.get("os") != "win32" or ex.get("is_launcher"):
                continue
            rel = safe_rel_path(str(ex.get("name", "")))
            if rel is None:
                continue
            pool.append(Game(str(e.get("id")), str(e.get("name")), rel))
            break
    if not pool:
        raise RuntimeError("no usable win32 executables found in the list")
    rng.shuffle(pool)
    if played:
        # unplayed first; once those run out, the games played longest ago (sort is stable, so ties stay shuffled)
        pool.sort(key=lambda g: played[g.app_id].get("last_run", 0) if g.app_id in played else -1)
    return pool[:count]


def materialize(game: Game, workdir: Path) -> Path:
    target = (workdir / game.exe_rel).resolve()
    if workdir.resolve() not in target.parents:
        raise RuntimeError(f"refusing path outside work dir: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copyfile(IDLE_SOURCE, target)
    return target


class Fleet:
    def __init__(self) -> None:
        self.procs: dict[str, tuple[Game, Path, subprocess.Popen]] = {}

    def start(self, game: Game, exe: Path) -> None:
        p = subprocess.Popen(
            [str(exe), *IDLE_ARGS],
            cwd=str(exe.parent),
            creationflags=CREATE_NO_WINDOW,
        )
        self.procs[game.app_id] = (game, exe, p)

    def stop_one(self, app_id: str) -> None:
        entry = self.procs.pop(app_id, None)
        if entry and entry[2].poll() is None:
            entry[2].terminate()

    def stop_all(self) -> None:
        for app_id in list(self.procs):
            self.stop_one(app_id)

    def revive_dead(self) -> None:
        for game, exe, p in list(self.procs.values()):
            if p.poll() is not None:
                print(f"[restart] {game.name}")
                self.start(game, exe)


def build_idle_exe() -> bool:
    """compile tools/fakewin.cs into IDLE_SOURCE with the csc that ships with windows."""
    src = Path(__file__).resolve().parents[2] / "tools" / "fakewin.cs"
    csc = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET" / "Framework64" / "v4.0.30319" / "csc.exe"
    if not src.is_file() or not csc.is_file():
        return False
    IDLE_SOURCE.parent.mkdir(parents=True, exist_ok=True)
    print("building idle program from tools/fakewin.cs ...")
    r = subprocess.run([str(csc), "/nologo", "/target:winexe", f"/out:{IDLE_SOURCE}",
                        "/reference:System.Windows.Forms.dll", "/reference:System.Drawing.dll", str(src)])
    if r.returncode != 0 or not IDLE_SOURCE.is_file():
        return False
    # pad to ~3 MB: discord seems to ignore tiny exes (trailing zeros don't affect the pe)
    with open(IDLE_SOURCE, "ab") as f:
        f.write(b"\0" * max(0, 3_000_000 - IDLE_SOURCE.stat().st_size))
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=3, help="games running at the same time")
    ap.add_argument("--rotate-minutes", type=int, default=0,
                    help="0 = keep the same games; N = swap the whole set every N minutes")
    ap.add_argument("--workdir", default=str(Path(os.environ.get("LOCALAPPDATA", ".")) / "fake_games"))
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--allow-repeats", action="store_true",
                    help="ignore played.json and pick games without remembering them")
    ap.add_argument("--list-only", action="store_true", help="print the chosen games and exit")
    args = ap.parse_args()

    if os.name != "nt":
        print("Windows only.")
        return 2
    if not IDLE_SOURCE.is_file() and not build_idle_exe():
        print(f"idle program not found: {IDLE_SOURCE} (set FAKEWIN_EXE or install .NET framework csc)")
        return 2
    if not 1 <= args.count <= 200:
        print("--count must be 1..200")
        return 2

    rng = random.Random(args.seed)
    entries = fetch_detectable()
    print(f"detectable apps in list: {len(entries)}")
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    fleet = Fleet()
    atexit.register(fleet.stop_all)

    played_path = workdir / "played.json"
    played = {} if args.allow_repeats else load_played(played_path)

    def launch_set() -> None:
        for game in pick_games(entries, args.count, rng, played):
            exe = materialize(game, workdir)
            fleet.start(game, exe)
            print(f"[start] {game.name}  ->  {game.exe_rel}")
            if not args.allow_repeats:
                mark_played(played, game)
                save_played(played_path, played)

    if args.list_only:
        for game in pick_games(entries, args.count, rng, played):
            print(f"{game.app_id}  {game.name}  {game.exe_rel}")
        return 0

    launch_set()
    next_rotation = time.monotonic() + args.rotate_minutes * 60
    try:
        while True:
            time.sleep(5)
            fleet.revive_dead()
            if args.rotate_minutes and time.monotonic() >= next_rotation:
                print("[rotate] swapping game set")
                fleet.stop_all()
                launch_set()
                next_rotation = time.monotonic() + args.rotate_minutes * 60
    except KeyboardInterrupt:
        print("stopping")
    finally:
        fleet.stop_all()
    return 0


if __name__ == "__main__":
    sys.exit(main())
