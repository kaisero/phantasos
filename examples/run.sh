#!/usr/bin/env bash
# Run a live-validation example against your tenant.
#   ./examples/run.sh                      # runs validate_live.py
#   ./examples/run.sh examples/foo.py      # runs another example
#
# Reads credentials from ./.env (see .env.example). Read-only.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"

SCRIPT="${1:-examples/validate_live.py}"

uv run --no-project \
  --with httpx --with attrs --with python-dateutil \
  --python 3.12 python "$SCRIPT"
