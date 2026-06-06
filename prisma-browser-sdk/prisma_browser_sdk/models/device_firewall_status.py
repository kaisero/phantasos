from .._lenient import LenientStrEnum


class DeviceFirewallStatus(LenientStrEnum):
    FIREWALLSTATUSDISABLED = "FireWallStatusDisabled"
    FIREWALLSTATUSENABLED = "FireWallStatusEnabled"
    FIREWALLSTATUSUNKNOWN = "FireWallStatusUnknown"

    def __str__(self) -> str:
        return str(self.value)
