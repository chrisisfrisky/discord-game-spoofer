from __future__ import annotations

import argparse
import json
import os
import random
import struct
import time
import urllib.request
import uuid

DETECTABLE_URL = "https://discord.com/api/v9/applications/detectable"


def fetch_detectable() -> list[dict]:
    req = urllib.request.Request(DETECTABLE_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


class Session:
    def __init__(self, app: dict, pipe_no: int | None) -> None:
        self.app = app
        self.pipe_no = pipe_no
        self.pipe = None

    @property
    def name(self) -> str:
        return str(self.app.get("name"))

    def _send(self, op: int, payload: dict) -> None:
        data = json.dumps(payload).encode()
        self.pipe.write(struct.pack("<II", op, len(data)) + data)
        self.pipe.flush()

    def _recv(self) -> dict:
        _, ln = struct.unpack("<II", self.pipe.read(8))
        return json.loads(self.pipe.read(ln).decode() or "{}")

    def _open(self) -> int | None:
        for n in ([self.pipe_no] if self.pipe_no is not None else range(10)):
            try:
                self.pipe = open(rf"\\?\pipe\discord-ipc-{n}", "r+b", buffering=0)
                return n
            except OSError:
                continue
        return None

    def start(self) -> bool:
        n = self._open()
        if n is None:
            print(f"[{self.name}] no discord pipe")
            return False
        try:
            self._send(0, {"v": 1, "client_id": str(self.app["id"])})
            ev = self._recv()
            if ev.get("evt") != "READY":
                print(f"[{self.name}] handshake failed: {ev}")
                self.stop()
                return False
            self._send(1, {
                "cmd": "SET_ACTIVITY",
                "args": {"pid": os.getpid(), "activity": {"timestamps": {"start": int(time.time())}}},
                "nonce": str(uuid.uuid4()),
            })
            resp = self._recv()
            if resp.get("evt") == "ERROR":
                print(f"[{self.name}] SET_ACTIVITY error: {resp}")
                self.stop()
                return False
            user = ev.get("data", {}).get("user", {}).get("username")
            print(f"[start] {self.name} (pipe {n}, user {user})")
            return True
        except Exception as e:
            print(f"[{self.name}] failed: {e!r}")
            self.stop()
            return False

    def alive(self) -> bool:
        return self.pipe is not None

    def stop(self) -> None:
        if self.pipe is not None:
            try:
                self.pipe.close()
            except Exception:
                pass
            self.pipe = None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=1, help="games shown at the same time")
    ap.add_argument("--pool", type=int, default=10, help="how many different games to cycle through")
    ap.add_argument("--interval", type=int, default=60, help="seconds before swapping to the next games")
    ap.add_argument("--pipe", type=int, default=None, help="discord-ipc-N (0=first client, 1=second...)")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    pool = random.Random(args.seed).sample(fetch_detectable(), max(args.pool, args.count))
    print(f"cycling {len(pool)} games, {args.count} at a time, every {args.interval}s")

    active: list[Session] = []
    i = 0
    try:
        while True:
            for s in active:
                s.stop()
            active = []
            tries = 0
            while len(active) < args.count and tries < len(pool):
                s = Session(pool[i % len(pool)], args.pipe)
                i += 1
                tries += 1
                if s.start():
                    active.append(s)
            if not active:
                print("nothing connected, is discord open? retrying in 10s")
                time.sleep(10)
                continue
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("stopping")
    finally:
        for s in active:
            s.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())