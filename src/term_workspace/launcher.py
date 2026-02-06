from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


def run_cmd(
    args: list[str],
    *,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=check,
        text=True,
        capture_output=capture,
    )


def tmux(
    args: list[str],
    *,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    return run_cmd(["tmux", *args], check=check, capture=capture)


def tmux_capture(args: list[str]) -> str:
    out = tmux(args, capture=True).stdout.strip()
    return out


def tmux_capture_optional(args: list[str]) -> Optional[str]:
    result = tmux(args, check=False, capture=True)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def session_exists(session_name: str) -> bool:
    result = tmux(["has-session", "-t", session_name], check=False, capture=True)
    return result.returncode == 0


def detect_clipboard_cmds() -> tuple[Optional[str], Optional[str]]:
    if shutil.which("pbcopy") and shutil.which("pbpaste"):
        return "pbcopy", "pbpaste"
    if shutil.which("wl-copy") and shutil.which("wl-paste"):
        return "wl-copy", "wl-paste -n"
    if shutil.which("xclip"):
        return "xclip -selection clipboard -in", "xclip -selection clipboard -out"
    if shutil.which("xsel"):
        return "xsel --clipboard --input", "xsel --clipboard --output"
    return None, None


def configure_interaction(session_name: str) -> None:
    tmux(["set-option", "-t", session_name, "mouse", "on"], check=False)

    # Keep single click pass-through to pane applications (Textual tree click support).
    tmux(
        [
            "bind-key",
            "-T",
            "root",
            "MouseDown1Pane",
            "select-pane",
            "-t=",
            "\\;",
            "send-keys",
            "-M",
        ],
        check=False,
    )

    # Restrict drag-based selection to the currently active pane only.
    drag_copy_cmd = 'if-shell -F "#{||:#{pane_in_mode},#{mouse_any_flag}}" "send-keys -M" "copy-mode -M"'
    tmux(
        [
            "bind-key",
            "-T",
            "root",
            "MouseDrag1Pane",
            "if-shell",
            "-F",
            "#{pane_active}",
            drag_copy_cmd,
            "",
        ],
        check=False,
    )

    # In copy-mode, ignore drag events that originate from non-active panes.
    tmux(
        [
            "bind-key",
            "-T",
            "copy-mode-vi",
            "MouseDrag1Pane",
            "if-shell",
            "-F",
            "#{pane_active}",
            r"select-pane \; send-keys -X begin-selection",
            "",
        ],
        check=False,
    )

    # Dragging border resizes pane widths.
    tmux(["bind-key", "-T", "root", "MouseDown1Border", "select-pane", "-t="], check=False)
    tmux(["bind-key", "-T", "root", "MouseDrag1Border", "resize-pane", "-M"], check=False)


def configure_clipboard(session_name: str) -> None:
    copy_cmd, paste_cmd = detect_clipboard_cmds()

    tmux(["set-option", "-s", "set-clipboard", "on"], check=False)
    tmux(["set-window-option", "-t", session_name, "mode-keys", "vi"], check=False)

    if copy_cmd:
        tmux(["set-option", "-s", "copy-command", copy_cmd], check=False)
        tmux(
            [
                "bind-key",
                "-T",
                "copy-mode-vi",
                "Enter",
                "send-keys",
                "-X",
                "copy-pipe-and-cancel",
                copy_cmd,
            ],
            check=False,
        )
        tmux(
            [
                "bind-key",
                "-T",
                "copy-mode-vi",
                "y",
                "send-keys",
                "-X",
                "copy-pipe-and-cancel",
                copy_cmd,
            ],
            check=False,
        )
        tmux(
            [
                "bind-key",
                "-T",
                "copy-mode-vi",
                "MouseDragEnd1Pane",
                "if-shell",
                "-F",
                "#{pane_active}",
                f"send-keys -X copy-pipe-and-cancel {shlex.quote(copy_cmd)}",
                "",
            ],
            check=False,
        )

    if paste_cmd:
        paste_pipe = f"{paste_cmd} | tmux load-buffer - ; tmux paste-buffer"
        tmux(["bind-key", "-T", "prefix", "v", "run-shell", paste_pipe], check=False)


def sidepanel_command(root_dir: str, left_pane: str) -> str:
    sidepanel_bin = shutil.which("term-sidepanel")
    if sidepanel_bin:
        cmd = [sidepanel_bin, "--root", root_dir, "--target-pane", left_pane]
    else:
        sidepanel_script = str(Path(__file__).with_name("sidepanel.py"))
        cmd = [sys.executable, sidepanel_script, "--root", root_dir, "--target-pane", left_pane]
    return shlex.join(cmd)


def _int_or_default(value: Optional[str], default: int) -> int:
    try:
        parsed = int(value or "")
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def initial_tmux_size() -> tuple[int, int]:
    # Detached tmux sessions may not have a known client size on some Linux setups.
    # Provide explicit geometry so split-window can always compute sizes.
    width = _int_or_default(os.environ.get("COLUMNS"), 200)
    height = _int_or_default(os.environ.get("LINES"), 60)
    width = max(80, min(width, 500))
    height = max(24, min(height, 200))
    return width, height


def _clean_tmux_option(value: Optional[str]) -> str:
    if not value:
        return ""
    return value.strip().strip('"').strip("'")


def pane_exists(pane_id: str) -> bool:
    if not pane_id:
        return False
    result = tmux(["display-message", "-p", "-t", pane_id, "#{pane_id}"], check=False, capture=True)
    return result.returncode == 0


def read_session_option(session_name: str, option_name: str) -> str:
    value = tmux_capture_optional(["show-options", "-t", session_name, "-v", option_name])
    return _clean_tmux_option(value)


def find_status_pane(session_name: str) -> str:
    configured = read_session_option(session_name, "@term_workspace_status_pane")
    if pane_exists(configured):
        return configured

    panes = tmux_capture_optional(
        [
            "list-panes",
            "-t",
            f"{session_name}:0",
            "-F",
            "#{pane_id}\t#{pane_start_command}\t#{pane_current_command}\t#{pane_left}",
        ]
    )
    if not panes:
        return ""

    rows: list[tuple[str, str, str, int]] = []
    for raw in panes.splitlines():
        parts = raw.split("\t")
        if len(parts) != 4:
            continue
        pane_id, start_cmd, current_cmd, pane_left_raw = parts
        try:
            pane_left = int(pane_left_raw)
        except ValueError:
            pane_left = 0
        rows.append((pane_id, start_cmd, current_cmd, pane_left))

    for pane_id, start_cmd, _, _ in rows:
        if "sidepanel.py" in start_cmd or "term-sidepanel" in start_cmd:
            return pane_id

    if not rows:
        return ""
    rows.sort(key=lambda row: row[3], reverse=True)
    return rows[0][0]


def ensure_command_pane(
    session_name: str,
    root_dir: str,
    panel_command_height: int,
) -> None:
    existing_command_pane = read_session_option(session_name, "@term_workspace_command_pane")
    if pane_exists(existing_command_pane):
        return

    status_pane = find_status_pane(session_name)
    if not pane_exists(status_pane):
        return

    command_height = max(3, min(panel_command_height, 20))
    command_pane = tmux_capture_optional(
        [
            "split-window",
            "-v",
            "-t",
            status_pane,
            "-l",
            str(command_height),
            "-c",
            root_dir,
            "-P",
            "-F",
            "#{pane_id}",
        ]
    )
    if not command_pane:
        return

    panel_cmd = sidepanel_command(root_dir, command_pane)
    tmux(["respawn-pane", "-k", "-t", status_pane, panel_cmd], check=False)
    tmux(["set-option", "-t", session_name, "@term_workspace_command_pane", command_pane], check=False)
    tmux(["set-option", "-t", session_name, "@term_workspace_status_pane", status_pane], check=False)


def create_session(
    session_name: str,
    root_dir: str,
    panel_width_percent: int,
    panel_command_height: int,
) -> None:
    width, height = initial_tmux_size()
    tmux(["new-session", "-d", "-s", session_name, "-c", root_dir, "-x", str(width), "-y", str(height)])

    status_pane = ""
    try:
        status_pane = tmux_capture(
            [
                "split-window",
                "-h",
                "-t",
                f"{session_name}:0",
                "-p",
                str(panel_width_percent),
                "-c",
                root_dir,
                "-P",
                "-F",
                "#{pane_id}",
            ]
        )
    except subprocess.CalledProcessError:
        # Fallback for tmux environments that reject percent-based sizing.
        right_width = max(30, int(width * (panel_width_percent / 100.0)))
        status_pane = tmux_capture(
            [
                "split-window",
                "-h",
                "-t",
                f"{session_name}:0",
                "-l",
                str(right_width),
                "-c",
                root_dir,
                "-P",
                "-F",
                "#{pane_id}",
            ]
        )

    command_height = max(3, min(panel_command_height, max(3, height // 2)))
    command_pane = tmux_capture(
        [
            "split-window",
            "-v",
            "-t",
            status_pane,
            "-l",
            str(command_height),
            "-c",
            root_dir,
            "-P",
            "-F",
            "#{pane_id}",
        ]
    )

    left_pane = tmux_capture(["display-message", "-p", "-t", f"{session_name}:0.0", "#{pane_id}"])

    panel_cmd = sidepanel_command(root_dir, command_pane)
    tmux(["respawn-pane", "-k", "-t", status_pane, panel_cmd], check=False)
    tmux(["set-option", "-t", session_name, "@term_workspace_command_pane", command_pane], check=False)
    tmux(["set-option", "-t", session_name, "@term_workspace_status_pane", status_pane], check=False)
    tmux(["select-pane", "-t", left_pane], check=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Open tmux workspace with right monitoring panel")
    parser.add_argument("--session", default="devpanel", help="tmux session name")
    parser.add_argument("--root", default=os.getcwd(), help="root working directory")
    parser.add_argument("--no-attach", action="store_true", help="create/sync session without attaching")
    parser.add_argument(
        "--panel-width-percent",
        type=int,
        default=int(os.environ.get("PANEL_WIDTH_PERCENT", "40")),
        help="right pane width percent",
    )
    parser.add_argument(
        "--panel-command-height",
        type=int,
        default=int(os.environ.get("PANEL_COMMAND_HEIGHT", "8")),
        help="height (rows) of right-bottom command pane used by side panel actions",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if shutil.which("tmux") is None:
        print("tmux is required. Install tmux first.", file=sys.stderr)
        return 1

    root_dir = str(Path(args.root).expanduser().resolve())
    if not Path(root_dir).is_dir():
        print(f"root directory not found: {root_dir}", file=sys.stderr)
        return 1

    panel_width = max(20, min(70, int(args.panel_width_percent)))
    panel_command_height = max(3, min(20, int(args.panel_command_height)))

    if not session_exists(args.session):
        create_session(args.session, root_dir, panel_width, panel_command_height)
    else:
        ensure_command_pane(args.session, root_dir, panel_command_height)

    configure_interaction(args.session)
    configure_clipboard(args.session)

    if args.no_attach:
        return 0

    if os.environ.get("TMUX"):
        tmux(["switch-client", "-t", args.session], check=False)
    else:
        tmux(["attach", "-t", args.session], check=False)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
