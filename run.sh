#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/.venv"
CONFIG="$DIR/projector-bridge.yaml"

# Create/activate venv and install if needed
if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -e "$DIR"
fi

exec "$VENV/bin/python" -m projector_bridge --config "$CONFIG" --log-level "${1:-DEBUG}"
