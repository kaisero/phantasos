#!/usr/bin/env python3
"""Validate the OAG SDK against a LIVE tenant via the facade (read-only).

    ./oag-examples/run.sh oag-examples/validate_live.py
"""
from _common import get_client

from prisma_browser.extras import NotFoundException, error_message, paginate


def main() -> int:
    client = get_client()

    print("→ [1] list users (limit 5)")
    page = client.users.list_users(limit=5)
    users = page.data or []
    print(f"  ✓ authenticated; {len(users)} user(s); has_next_page="
          f"{getattr(page.page_info, 'has_next_page', '?')}")
    if users:
        u = users[0]
        print(f"  first: {u.name} <{u.email}> provider={u.provider}")

    print("→ [2] paginate users (cap 25)")
    count = 0
    for _ in paginate(client.users.list_users, limit=10):
        count += 1
        if count >= 25:
            break
    print(f"  ✓ iterated {count}")

    print("→ [3] read security policy")
    pol = client.security_policy.get_security_policy()
    print(f"  ✓ {len(pol.data or [])} policy item(s)")

    print("→ [4] typed error on bogus user id")
    try:
        client.users.get_user_by_id("00000000000000000000000000000000")
        print("  ? no error")
    except NotFoundException as exc:
        print(f"  ✓ NotFoundException: {error_message(exc)}")

    client.close()
    print("✓ live validation complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
