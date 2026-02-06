# term-workspace

`term-workspace` is a `tmux` workspace launcher with a right-side status panel for navigation and system monitoring.

## Features

- 3-pane layout by default:
  - left: main work terminal
  - right-top: status panel (directory tree + metrics)
  - right-bottom: dedicated command terminal for status panel actions
- Existing 2-pane sessions are auto-upgraded to add the right-bottom command pane.
- Clickable directory tree in the status panel.
- Clicking directories sends `cd` to the dedicated command pane (does not interrupt the main work pane).
- Clicking supported files opens the file in the dedicated command pane editor.
- Supported file extensions:
  - `.py`, `.pyi`, `.sh`, `.bash`, `.zsh`
  - `.json`, `.jsonl`, `.yaml`, `.yml`
  - `.toml`, `.ini`, `.cfg`, `.conf`
  - `.txt`, `.md`
- Editor selection for file-open:
  - `$VISUAL` or `$EDITOR` if set
  - fallback order: `nvim`, `vim`, `nano`, `vi`, `less`
- Real-time metrics panel:
  - CPU utilization
  - memory utilization
  - GPU utilization and VRAM usage
  - multi-GPU support via `nvidia-smi` (per-GPU bars)
- tmux interaction tuning:
  - pane border drag resize enabled
  - drag-copy restricted to active pane only (prevents cross-pane drag copy)
  - copy-mode clipboard integration
- Cross-platform clipboard support:
  - macOS: `pbcopy` / `pbpaste`
  - Linux Wayland: `wl-copy` / `wl-paste`
  - Linux X11: `xclip` or `xsel`
- Detached-session safety:
  - explicit tmux geometry and split fallback to avoid `size missing` issues in headless Linux environments.

## Requirements

- `tmux` (3.2+ recommended)
- Python 3.9+
- `nvidia-smi` (optional, only needed for NVIDIA GPU metrics)

## Install

### Option 1: pipx (recommended)

```bash
pipx install git+https://github.com/KimJaehee0725/term-workspace.git
```

### Option 2: pip user install

```bash
python3 -m pip install --user git+https://github.com/KimJaehee0725/term-workspace.git
```

### Option 3: release wheel

```bash
python3 -m pip install --user https://github.com/KimJaehee0725/term-workspace/releases/download/v0.2.2/term_workspace-0.2.2-py3-none-any.whl
```

## Screenshot

![term-workspace status panel](assets/status-panel.png)

## Run

```bash
term-workspace
```

### Common options

```bash
term-workspace --session devpanel --root ~/project
term-workspace --panel-width-percent 45
term-workspace --panel-command-height 6
term-workspace --no-attach
```

### Environment variables

- `PANEL_WIDTH_PERCENT` (default: `40`)
- `PANEL_COMMAND_HEIGHT` (default: `8`)

## Mouse and Clipboard

- Drag center border to resize left/right panes.
- Drag-copy works only in the active pane.
- Copy to system clipboard in copy mode:
  - `prefix` + `[`
  - select text
  - press `Enter` or `y`
- Paste system clipboard:
  - `prefix` + `v`

## Platform Notes

### Linux

- Wayland clipboard: install `wl-copy` and `wl-paste`
- X11 clipboard: install `xclip` or `xsel`

### macOS

- Uses `pbcopy` / `pbpaste` for clipboard integration.
- Apple GPU utilization may show as unavailable without privileged tools; VRAM may still be shown.

## Release

This repo includes GitHub Actions workflows:

- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`

Release flow:

1. Update version in `pyproject.toml` and `src/term_workspace/__init__.py`
2. Update `CHANGELOG.md`
3. Commit and push
4. Create and push tag (example `v0.2.2`)
5. Workflow builds `wheel` / `sdist` and publishes GitHub Release assets

