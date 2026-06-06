from enum import Enum


class DeviceFirewallStatus(str, Enum):
    FIREWALLSTATUSDISABLED = "FireWallStatusDisabled"
    FIREWALLSTATUSENABLED = "FireWallStatusEnabled"
    FIREWALLSTATUSUNKNOWN = "FireWallStatusUnknown"

    def __str__(self) -> str:
        return str(self.value)
