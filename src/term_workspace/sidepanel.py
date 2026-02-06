from __future__ import annotations

import argparse
import os
import platform
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

import psutil
from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import DirectoryTree, Static


class StatsCollector:
    def __init__(self) -> None:
        self._platform = platform.system()
        self._mac_vram = self._read_macos_vram_total() if self._platform == "Darwin" else None
        self._first_cpu_read = True

    def _run(self, cmd: list[str], timeout: float = 1.0) -> Optional[str]:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            if result.returncode != 0:
                return None
            return result.stdout.strip()
        except Exception:
            return None

    def _read_macos_vram_total(self) -> Optional[str]:
        out = self._run(["system_profiler", "SPDisplaysDataType"], timeout=3.0)
        if not out:
            return None
        for raw in out.splitlines():
            line = raw.strip()
            if line.startswith("VRAM (Total):") or line.startswith("VRAM:"):
                return line.split(":", 1)[1].strip()
        return None

    def _to_float(self, value: str) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _read_nvidia(self) -> Optional[list[dict]]:
        if not shutil.which("nvidia-smi"):
            return None
        out = self._run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            timeout=1.0,
        )
        if not out:
            return None

        gpus: list[dict] = []
        for raw in out.splitlines():
            parts = [p.strip() for p in raw.split(",")]
            if len(parts) < 5:
                continue
            gpu_index = parts[0]
            gpu_name = parts[1]
            util = self._to_float(parts[2])
            mem_used = self._to_float(parts[3])
            mem_total = self._to_float(parts[4])
            if util is None or mem_used is None or mem_total is None:
                continue
            mem_pct = (mem_used / mem_total * 100.0) if mem_total > 0 else 0.0
            gpus.append(
                {
                    "index": gpu_index,
                    "name": gpu_name,
                    "util_pct": util,
                    "vram_pct": mem_pct,
                    "vram_text": f"{mem_used:.0f}/{mem_total:.0f} MiB",
                }
            )
        return gpus or None

    def snapshot(self) -> dict:
        if self._first_cpu_read:
            psutil.cpu_percent(interval=None)
            self._first_cpu_read = False
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()

        nvidia_gpus = self._read_nvidia()
        if nvidia_gpus:
            model_names = {gpu["name"] for gpu in nvidia_gpus}
            model_summary = next(iter(model_names)) if len(model_names) == 1 else "Mixed"
            gpu_info = {
                "source": "nvidia-smi",
                "count": len(nvidia_gpus),
                "model_summary": model_summary,
                "gpus": nvidia_gpus,
            }
        elif self._platform == "Darwin":
            gpu_info = {
                "source": "macOS (GPU util needs root powermetrics)",
                "count": 1,
                "model_summary": "Apple GPU",
                "gpus": [
                    {
                        "index": "0",
                        "name": "Apple GPU",
                        "util_pct": None,
                        "vram_pct": None,
                        "vram_text": self._mac_vram or "N/A",
                    }
                ],
            }
        else:
            gpu_info = {
                "source": "No supported GPU tool found",
                "count": 0,
                "model_summary": "Unknown",
                "gpus": [],
            }

        return {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "cpu_util": f"{cpu:.1f}%",
            "mem_util": f"{mem.percent:.1f}%",
            "gpu_source": gpu_info["source"],
            "gpu_count": gpu_info["count"],
            "gpu_model_summary": gpu_info["model_summary"],
            "gpus": gpu_info["gpus"],
        }


class SidePanelApp(App):
    OPENABLE_SUFFIXES = {
        ".py",
        ".pyi",
        ".sh",
        ".bash",
        ".zsh",
        ".json",
        ".jsonl",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".txt",
        ".md",
    }

    CSS = """
    Screen {
      layout: vertical;
    }

    #tree {
      height: 1fr;
      border: solid #5a7d9a;
    }

    #stats {
      height: 22;
      border: solid #6e8f72;
      padding: 0 1;
      overflow-y: auto;
    }
    """

    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, root_path: Path, target_pane: Optional[str]) -> None:
        super().__init__()
        self.root_path = root_path
        self.target_pane = target_pane
        self.collector = StatsCollector()
        self.last_selected_dir = str(root_path)
        self.last_selected_file = ""
        self.editor_cmd = self._resolve_editor_cmd()

    def compose(self) -> ComposeResult:
        yield DirectoryTree(str(self.root_path), id="tree")
        yield Static("", id="stats")

    def on_mount(self) -> None:
        self.query_one(DirectoryTree).focus()
        self.set_interval(1.0, self._refresh_stats)
        self.set_interval(3.0, self._refresh_tree)
        self._refresh_stats()

    def _refresh_tree(self) -> None:
        self.query_one(DirectoryTree).reload()

    def _bar_style(self, percent: float) -> str:
        if percent >= 90.0:
            return "bold red"
        if percent >= 70.0:
            return "yellow"
        return "green"

    def _render_bar(self, percent: float, width: int = 10) -> Text:
        clamped = max(0.0, min(100.0, percent))
        filled = int(round((clamped / 100.0) * width))
        filled = max(0, min(width, filled))
        text = Text("[")
        text.append("#" * filled, style=self._bar_style(clamped))
        text.append("-" * (width - filled), style="grey50")
        text.append("]")
        text.append(f" {clamped:5.1f}%")
        return text

    def _refresh_stats(self) -> None:
        data = self.collector.snapshot()
        text = Text()
        text.append(f"{data['time']}\n", style="bold")
        text.append(f"CPU Util: {data['cpu_util']} | Mem Util: {data['mem_util']}\n")
        text.append(
            f"GPU Source: {data['gpu_source']} | Count: {data['gpu_count']} | Model: {data['gpu_model_summary']}\n"
        )

        if data["gpus"]:
            for gpu in data["gpus"]:
                util_pct = gpu["util_pct"]
                vram_pct = gpu["vram_pct"]
                text.append(f"GPU{gpu['index']:>2} U ")
                if util_pct is None:
                    text.append("N/A")
                else:
                    text.append_text(self._render_bar(util_pct))
                text.append("  V ")
                if vram_pct is None:
                    text.append(f"N/A ({gpu['vram_text']})")
                else:
                    text.append_text(self._render_bar(vram_pct))
                    text.append(f"  {gpu['vram_text']}")
                text.append("\n")
        else:
            text.append("GPU metrics unavailable\n")

        text.append(f"Selected Dir: {self.last_selected_dir}")
        if self.last_selected_file:
            text.append(f"\nSelected File: {self.last_selected_file}")
        text.append(f"\nEditor: {self.editor_cmd}")
        self.query_one("#stats", Static).update(text)

    def _resolve_editor_cmd(self) -> str:
        env_editor = (os.environ.get("VISUAL") or os.environ.get("EDITOR") or "").strip()
        if env_editor:
            return env_editor
        for candidate in ("nvim", "vim", "nano", "vi", "less"):
            if shutil.which(candidate):
                return candidate
        return "vi"

    def _send_command_to_target(self, command: str) -> None:
        if not self.target_pane:
            return
        try:
            subprocess.run(
                ["tmux", "send-keys", "-t", self.target_pane, command, "C-m"],
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception:
            return

    def _send_cd_to_target(self, path: Path) -> None:
        self._send_command_to_target(f"cd {shlex.quote(str(path))}")

    def _is_openable_file(self, path: Path) -> bool:
        return path.suffix.lower() in self.OPENABLE_SUFFIXES

    def _send_open_file_to_target(self, path: Path) -> None:
        try:
            editor_parts = shlex.split(self.editor_cmd)
        except ValueError:
            editor_parts = []
        if not editor_parts:
            editor_parts = ["vi"]
        cmd = shlex.join([*editor_parts, str(path)])
        self._send_command_to_target(cmd)

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        path = event.path.resolve()
        self.last_selected_dir = str(path)
        self._send_cd_to_target(path)
        self._refresh_stats()

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        path = event.path.resolve()
        self.last_selected_file = str(path)
        if self._is_openable_file(path):
            self._send_open_file_to_target(path)
        self._refresh_stats()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Right-side terminal panel")
    parser.add_argument("--root", default=os.getcwd(), help="Root path for directory tree")
    parser.add_argument("--target-pane", default="", help="tmux pane id for cd sync")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    target = args.target_pane.strip() or None
    app = SidePanelApp(root_path=root, target_pane=target)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
