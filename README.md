# discord-game-spoof

make discord show games you're not playing to boost the game variety badge, i havent tested tho it does pull valid games and shows them in ur activity.
stuff counting towards ur badge probably depends on how long you keep up the fake game for.

> unofficial, not affiliated with discord. spoofing activity may go against discord's tos idek if it does, use at your own risk.

## layout

- `src/discord_game_spoof/process_spoof.py` - fake exes at the paths discord's detectable-games list expects, so discord detects them as running
- `src/discord_game_spoof/rpc_spoof.py` - talks to discord's local rich presence pipe and sends `SET_ACTIVITY` per game
- `tools/fakewin.cs` - source of the tiny idle window the process spoofer launches

## setup

```powershell
pip install -e .
```

## usage

```powershell
# process method
discord-fake-process --count 3
discord-fake-process --count 40 --rotate-minutes 30 --seed 1
discord-fake-process --list-only --count 10

# rpc method (canary is usually pipe 1)
discord-fake-rpc --pipe 1 --pool 20 --count 2 --interval 120
```

ctrl+c stops either one. the process method compiles `tools/fakewin.cs` on first run (into `build/`) using the csc that ships with windows, so no binaries live in the repo. set `FAKEWIN_EXE` to use your own idle exe.