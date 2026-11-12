# discord-game-spoof

make discord show games you're not playing to boost the game variety badge, i havent tested tho it does pull valid games and shows them in ur activity.
stuff counting towards ur badge probably depends on how long you keep up the fake game for.

> unofficial, not affiliated with discord. spoofing activity may go against discord's tos idek if it does, use at your own risk.

## layout

- `src/discord_game_spoof/process_spoof.py` - fake exes at the paths discord's detectable-games list expects, so discord detects them as running
- `tools/fakewin.cs` - source of the tiny idle window the process spoofer launches

## setup

```powershell
pip install -e .
```

## usage

```powershell
discord-fake-process --count 3
discord-fake-process --count 40 --rotate-minutes 30 --seed 1
discord-fake-process --list-only --count 10
```

it remembers every game it has run in `played.json` inside the workdir and picks unplayed ones first (oldest-played once all are used). `--allow-repeats` turns that off, delete the file to reset.

note: discord only shows one detected game as "playing", and a real running game (like roblox) takes priority over the fake.

ctrl+c stops it. it compiles `tools/fakewin.cs` on first run (into `build/`) using the csc that ships with windows, so no binaries live in the repo. set `FAKEWIN_EXE` to use your own idle exe.