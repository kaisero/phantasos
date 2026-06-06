#!/usr/bin/env python3
"""List applications (paginated) via the facade; group by type (oneOf-unwrapped)."""
from collections import Counter
from _common import get_client
from prisma_browser.extras import paginate

def main() -> int:
    client = get_client()
    by_type, n = Counter(), 0
    for item in paginate(client.applications.list_applications):
        app = getattr(item, "actual_instance", item)  # unwrap ApplicationItem oneOf
        n += 1; by_type[str(getattr(app, "type", "?"))] += 1
    print(f"applications: {n}")
    for t, c in by_type.most_common():
        print(f"  {t:20s} {c}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
