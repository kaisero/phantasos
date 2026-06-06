#!/usr/bin/env python3
"""List all users (paginated) via the facade; summarize by status/provider."""
from collections import Counter
from _common import get_client
from prisma_browser.extras import paginate

def main() -> int:
    client = get_client()
    by_status, by_provider, n = Counter(), Counter(), 0
    for u in paginate(client.users.list_users):
        n += 1; by_status[str(u.status)] += 1; by_provider[str(u.provider)] += 1
    print(f"users: {n}")
    print("  by status:  ", ", ".join(f"{k}={v}" for k, v in by_status.most_common()))
    print("  by provider:", ", ".join(f"{k}={v}" for k, v in by_provider.most_common()))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
