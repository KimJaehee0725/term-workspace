# Changelog

## 0.1.1 - 2026-02-06

- Fix: Linux/headless tmux environments no longer fail with `size missing`
- Session creation now sets explicit detached geometry via `tmux new-session -x/-y`
- Add fallback from `split-window -p` to absolute width `split-window -l`
- Suppress noisy `can't find session` message during session existence check

## 0.1.0 - 2026-02-06

- Initial release
- `term-workspace` launcher for macOS and Linux
- Right-side `Textual` panel with clickable directory tree
- GPU/VRAM/CPU monitor with multi-GPU color bars
- Per-session `tmux` interaction tuning:
  - border drag resize
  - pane drag overlap prevention
  - system clipboard integration (`pbcopy`, `wl-copy`, `xclip`, `xsel`)
