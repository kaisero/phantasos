#!/usr/bin/env python3
"""List applications (cursor-paginated) and group them by type.

    ./examples/run.sh examples/list_applications.py
"""
from collections import Counter

from _common import get_client

from prisma_browser_sdk.api.applications import list_applications
from prisma_browser_sdk.extras import paginate


def main() -> int:
    client = get_client()

    by_type: Counter = Counter()
    sample: dict[str, str] = {}
    total = 0
    for app in paginate(list_applications, client=client):
        total += 1
        app_type = str(getattr(app, "type_", None) or getattr(app, "type", "?"))
        by_type[app_type] += 1
        sample.setdefault(app_type, str(getattr(app, "name", "?")))

    print(f"applications: {total}")
    for app_type, n in by_type.most_common():
        print(f"  {app_type:20s} {n:4d}   e.g. {sample.get(app_type, '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
