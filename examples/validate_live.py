#!/usr/bin/env python3
"""
Validate the generated SDK against a LIVE Prisma Browser tenant.

Reads credentials from ../.env (CLIENT_ID / CLIENT_SECRET / SCOPE), then exercises
the real API read-only:
  1. authenticate (OAuth2 client-credentials, token fetched lazily)
  2. list users (single page)
  3. paginate users (capped, to prove cursor-following)
  4. trigger a typed error (GET a bogus user id -> NotFoundError/ClientError)

Run it with:  ./examples/run.sh     (handles deps + the package path)

Everything here is read-only — it creates/modifies nothing in your tenant.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# --- make the generated package importable (it isn't pip-installed) ----------
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "prisma-browser-sdk"))


def load_dotenv(path: Path) -> None:
    """Minimal .env loader (no third-party dep). Does not override real env vars."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    load_dotenv(ROOT / ".env")

    from prisma_browser_sdk.extras import (
        client_from_env,
        paginate,
        unwrap,
        ApiException,
        NotFoundError,
        ClientError,
        DEFAULT_BASE_URL,
    )
    from prisma_browser_sdk.api.users import list_users, get_user_by_id

    try:
        client = client_from_env()
    except RuntimeError as exc:
        print(f"✗ {exc}\n  Populate {ROOT / '.env'} (CLIENT_ID, CLIENT_SECRET, SCOPE).")
        return 2

    print(f"Base URL : {client._base_url}")
    print(f"Scope    : {client._httpx_args['auth']._scope}")
    print(f"(default : {DEFAULT_BASE_URL})\n")

    # 1 + 2. authenticate + list a single page -------------------------------
    print("→ [1] listing users (limit=5) ...")
    try:
        page = unwrap(list_users.sync_detailed(client=client, limit=5))
    except ApiException as exc:
        print(f"✗ list_users failed: {exc}")
        return 1
    users = page.data or []
    print(f"  ✓ authenticated; got {len(users)} user(s); has_next_page="
          f"{getattr(page.page_info, 'has_next_page', '?')}")
    if users:
        u = users[0]
        print(f"  first user: id={u.id!r} name={u.name!r} email={u.email!r} status={u.status}")

    # 3. paginate (capped) ----------------------------------------------------
    print("\n→ [2] paginating users (cap 25) ...")
    count = 0
    for _ in paginate(list_users, client=client, limit=10):
        count += 1
        if count >= 25:
            break
    print(f"  ✓ iterated {count} user(s) across pages")

    # 4. typed error path -----------------------------------------------------
    print("\n→ [3] fetching a bogus user id (expect a typed error) ...")
    try:
        unwrap(get_user_by_id.sync_detailed(client=client, id="00000000000000000000000000000000"))
        print("  ? no error raised (id unexpectedly existed)")
    except NotFoundError as exc:
        print(f"  ✓ NotFoundError raised as expected: {exc}")
    except ClientError as exc:
        print(f"  ✓ typed ClientError raised: {exc}")

    print("\n✓ live validation complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
