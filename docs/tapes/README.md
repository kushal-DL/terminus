# GIF Recording Scripts

This directory contains [VHS](https://github.com/charmbracelet/vhs) tape files for recording animated GIFs of Terminus gameplay.

## Prerequisites

Install VHS (requires Go):
```bash
# macOS
brew install charmbracelet/tap/vhs

# Windows (scoop)
scoop install vhs

# Linux
go install github.com/charmbracelet/vhs@latest
```

## Recording

Run each tape to generate the corresponding GIF:

```bash
vhs docs/tapes/main-menu.tape
vhs docs/tapes/colony.tape
vhs docs/tapes/build.tape
vhs docs/tapes/catastrophe.tape
vhs docs/tapes/market.tape
vhs docs/tapes/lobby.tape
vhs docs/tapes/dev-panel.tape
```

Output GIFs are saved to `docs/gifs/`.

## Manual Recording Alternative

If VHS is not available, use `asciinema` + `agg`:

```bash
# Record
asciinema rec docs/recordings/main-menu.cast

# Convert to GIF
agg docs/recordings/main-menu.cast docs/gifs/main-menu.gif --cols 100 --rows 30
```
