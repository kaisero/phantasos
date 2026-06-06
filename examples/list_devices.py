#!/usr/bin/env python3
"""List devices (cursor-paginated) and summarize by status and OS.

    ./examples/run.sh examples/list_devices.py
"""
from collections import Counter

from _common import get_client

from prisma_browser_sdk.api.devices import list_devices
from prisma_browser_sdk.extras import paginate


def main() -> int:
    client = get_client()

    by_status: Counter = Counter()
    by_os: Counter = Counter()
    total = 0
    for device in paginate(list_devices, client=client):
        total += 1
        by_status[str(getattr(device, "status", "?"))] += 1
        by_os[str(getattr(device, "os_type", "?"))] += 1

    print(f"devices: {total}")
    print("  by status: " + ", ".join(f"{k}={v}" for k, v in by_status.most_common()))
    print("  by OS:     " + ", ".join(f"{k}={v}" for k, v in by_os.most_common(10)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
