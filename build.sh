#!/usr/bin/env bash
#
# Idempotent build of the Prisma Browser Python SDK.
#
#   ./build.sh
#
# Re-running reproduces the complete SDK from source and loses no progress:
#   1. preprocess the OpenAPI spec        (preprocess_spec.py  -> deterministic)
#   2. generate the client                (openapi-python-client --overwrite)
#   3. re-apply the hand-written overlay   (apply_overlay.py    -> idempotent)
#
# The only hand-maintained code lives OUTSIDE the generated package:
#   preprocess_spec.py, overlay/, apply_overlay.py. The generated package is
#   disposable. Edit the overlay in overlay/, never in prisma_browser_sdk/extras/.
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$PATH"

SPEC_SRC="prismaBrowserAPIspecWithSecurityPolicy.yaml"
SPEC_PP="prismaBrowserAPIspec.preprocessed.yaml"
PYV="3.12"

echo "==> [1/4] Preprocess spec"
uv run --no-project --with ruamel.yaml --python "$PYV" python preprocess_spec.py

echo "==> [2/4] Generate SDK from preprocessed spec"
uvx --python "$PYV" --from openapi-python-client openapi-python-client generate \
  --path "$SPEC_PP" --config opc-config.yaml --meta uv --overwrite

echo "==> [3/4] Apply overlay + idempotent patches"
uv run --no-project --python "$PYV" python apply_overlay.py

echo "==> [4/4] Smoke test (compile + import)"
uv run --no-project --with httpx --with attrs --with python-dateutil --python "$PYV" python - <<'PY'
import importlib, pkgutil, sys
sys.path.insert(0, "prisma-browser-sdk")
import prisma_browser_sdk
ok = err = 0
errs = []
for mod in pkgutil.walk_packages(prisma_browser_sdk.__path__, "prisma_browser_sdk."):
    try:
        importlib.import_module(mod.name); ok += 1
    except Exception as e:
        err += 1; errs.append((mod.name, repr(e)[:120]))
# confirm the overlay public API is importable
from prisma_browser_sdk.extras import build_client, paginate, paginate_async, unwrap, ApiException  # noqa
print(f"imported {ok} modules, {err} failures; overlay API OK")
for n, e in errs[:10]:
    print("  FAIL", n, e)
sys.exit(1 if err else 0)
PY

echo "==> Build complete."
