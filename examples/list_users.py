#!/usr/bin/env python3
"""List all users (cursor-paginated) and summarize by status and provider.

    ./examples/run.sh examples/list_users.py
"""
from collections import Counter

from _common import get_client

from prisma_browser_sdk.api.users import list_users
from prisma_browser_sdk.extras import paginate


def main() -> int:
    client = get_client()

    by_status: Counter = Counter()
    by_provider: Counter = Counter()
    total = 0
    for user in paginate(list_users, client=client):
        total += 1
        by_status[str(getattr(user, "status", "?"))] += 1
        by_provider[str(getattr(user, "provider", "?"))] += 1

    print(f"users: {total}")
    print("  by status:   " + ", ".join(f"{k}={v}" for k, v in by_status.most_common()))
    print("  by provider: " + ", ".join(f"{k}={v}" for k, v in by_provider.most_common()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
