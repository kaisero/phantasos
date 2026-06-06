#!/usr/bin/env bash
# Run an OAG-SDK example against your tenant (reads ./.env). Read-only.
#   ./oag-examples/run.sh                                  # validate_live.py
#   ./oag-examples/run.sh oag-examples/sweep_get_endpoints.py
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
SCRIPT="${1:-oag-examples/validate_live.py}"
uv run --no-project \
  --with pydantic --with urllib3 --with python-dateutil --with typing_extensions \
  --python 3.12 python "$SCRIPT"
