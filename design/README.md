# sisyphus + Ghostty CRT setup (exact same visual as nakedlunch)

This makes `sisyphus` command open Ghostty with **identical** visual treatment:
- same shaders (in-game-crt + bloom + glow-rgbsplit-twitchy)
- same 4:3 centered padding
- same JetBrains Mono 22pt, amber orange retro CRT
- fullscreen
- transparent titlebar etc.

## Setup (already done by the AI)

The wrapper is at:
- ~/.local/bin/sisyphus   (the launch command)
- sisyphus/design/sisyphus-ghostty-wrapper

Config:
- ~/.config/ghostty/sisyphus   (copy of nakedlunch visual, title updated)

Shaders are shared in ~/.ghostty-shaders/

## Usage

Just type in terminal:

```bash
sisyphus
```

It will launch Ghostty with the full nakedlunch-style CRT visual and run sisyphus inside.

To restore on another machine, copy the wrapper to ~/.local/bin/sisyphus , the config, ensure shaders and ~/.local/bin in PATH.

The inner command cds to the sisyphus source and runs `python3 -m sisyphus`.

