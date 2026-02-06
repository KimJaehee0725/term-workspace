#!/usr/bin/env bash
set -euo pipefail

METHOD="${METHOD:-pipx}"       # pipx | pip
REPO="${REPO:-KimJaehee0725/term-workspace}"
VERSION="${VERSION:-latest}"   # latest | vX.Y.Z
LOCAL=0

usage() {
  echo "Usage: install.sh [--local] [--method pipx|pip] [--repo OWNER/REPO] [--version latest|vX.Y.Z]"
  echo "Examples:"
  echo "  ./scripts/install.sh --local"
  echo "  ./scripts/install.sh --repo myname/tmux-devpanel --version v0.1.0"
  echo "  METHOD=pip ./scripts/install.sh --repo myname/tmux-devpanel"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --local)
      LOCAL=1
      shift
      ;;
    --method)
      METHOD="${2:-}"
      shift 2
      ;;
    --repo)
      REPO="${2:-}"
      shift 2
      ;;
    --version)
      VERSION="${2:-}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required." >&2
  exit 1
fi

if ! command -v tmux >/dev/null 2>&1; then
  echo "Warning: tmux is not installed yet. Install tmux before running term-workspace." >&2
fi

if [ "$LOCAL" -eq 1 ]; then
  SOURCE="."
elif [ "$VERSION" = "latest" ]; then
  SOURCE="git+https://github.com/${REPO}.git"
else
  SOURCE="https://github.com/${REPO}/archive/refs/tags/${VERSION}.tar.gz"
fi

case "$METHOD" in
  pipx)
    if ! command -v pipx >/dev/null 2>&1; then
      echo "Installing pipx (user mode)..."
      python3 -m pip install --user pipx
    fi
    pipx install --force "$SOURCE"
    ;;
  pip)
    python3 -m pip install --user --upgrade "$SOURCE"
    ;;
  *)
    echo "Unsupported --method: $METHOD" >&2
    exit 1
    ;;
esac

echo "Installed. Try: term-workspace"
