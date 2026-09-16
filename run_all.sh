#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON="$SCRIPT_DIR/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
  printf '%s\n' "Project environment not found. Create it with: python3 -m venv .venv" >&2
  exit 1
fi

exec "$PYTHON" "$SCRIPT_DIR/run_all.py" "$@"
