#!/usr/bin/env bash
# Run an example against your tenant (reads ./.env). Read-only.
#   ./examples/run.sh                                  # validate_live.py
#   ./examples/run.sh examples/sweep_get_endpoints.py
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
SCRIPT="${1:-examples/validate_live.py}"
uv run --no-project \
  --with pydantic --with urllib3 --with python-dateutil --with typing_extensions \
  --python 3.12 python "$SCRIPT"
