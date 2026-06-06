#!/usr/bin/env python3
"""List devices (paginated) via the facade; summarize by status/OS."""
from collections import Counter
from _common import get_client
from prisma_browser.extras import paginate

def main() -> int:
    client = get_client()
    by_status, by_os, n = Counter(), Counter(), 0
    for d in paginate(client.devices.list_devices):
        n += 1; by_status[str(getattr(d, "status", "?"))] += 1; by_os[str(getattr(d, "os_type", "?"))] += 1
    print(f"devices: {n}")
    print("  by status:", ", ".join(f"{k}={v}" for k, v in by_status.most_common()))
    print("  by OS:    ", ", ".join(f"{k}={v}" for k, v in by_os.most_common(10)))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
