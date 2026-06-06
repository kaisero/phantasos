from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.device_browser_brand import DeviceBrowserBrand
from ..models.device_device_type import DeviceDeviceType
from ..models.device_disk_encryption_status import DeviceDiskEncryptionStatus
from ..models.device_firewall_status import DeviceFirewallStatus
from ..models.device_os_type import DeviceOsType
from ..models.device_platform import DevicePlatform
from ..models.device_screen_lock_status import DeviceScreenLockStatus
from ..models.device_status import DeviceStatus
from ..models.location_method import LocationMethod
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.browser_self_protection_module import BrowserSelfProtectionModule
    from ..models.crowdstrike_zta_posture import CrowdstrikeZTAPosture
    from ..models.device_disk_encryption_details import DeviceDiskEncryptionDetails
    from ..models.device_epp import DeviceEPP
    from ..models.device_firewall_details import DeviceFirewallDetails
    from ..models.device_management import DeviceManagement
    from ..models.device_password_posture import DevicePasswordPosture
    from ..models.system_integrity_posture import SystemIntegrityPosture
    from ..models.user import User


T = TypeVar("T", bound="Device")


@_attrs_define
class Device:
    """
    Attributes:
        id (str): Unique identifier
        external_id (str): External identifier
        status (DeviceStatus): Device status
        first_seen (datetime.datetime): First seen time
        last_seen (datetime.datetime): Last seen time
        os_type (DeviceOsType): Operating System type
        os_version (str): OS Version
        os_display_name (str): OS Display Name
        arch (str): Architecture
        native_arch (str): Native Architecture
        hostname (str): Hostname
        model (str): Device Model
        serial_number (str): Serial Number
        mac_addresses (list[str]): MAC Addresses
        screen_lock_status (DeviceScreenLockStatus): Screen Lock Status
        disk_encryption_status (DeviceDiskEncryptionStatus): Disk Encryption Status
        firewall_status (DeviceFirewallStatus): Firewall Status
        user_agent (str): User Agent
        talon_extension_version (str): Talon Extension Version
        browser_version (str): Browser Version
        browser_brand (DeviceBrowserBrand): Browser brand
        device_type (DeviceDeviceType): Device Type
        platform (DevicePlatform): Device platform
        is_browser_installed_as_admin (bool): Browser installed as admin
        chromeos_version (str | Unset): ChromeOS version (only for ChromeOS devices)
        location_method (LocationMethod | Unset): Location detection method
        mobile_vendor (str | Unset): Mobile device vendor/manufacturer (e.g., Samsung, Apple)
        mobile_hardware (str | Unset): Mobile device hardware identifier (e.g., iPhone14,2, SM-G998B)
        mobile_is_rooted (bool | Unset): Whether the mobile device is rooted/jailbroken
        disk_encryption_details (DeviceDiskEncryptionDetails | Unset): Disk encryption details for the device
        firewall_details (DeviceFirewallDetails | Unset): Firewall details for the device
        ip (None | str | Unset): IP Address
        device_epp (DeviceEPP | Unset):
        device_password (DevicePasswordPosture | Unset):
        crowdstrike_zta (CrowdstrikeZTAPosture | Unset):
        system_integrity (SystemIntegrityPosture | Unset):
        is_running_on_remote_session (bool | Unset): Whether the device is running on a remote session (e.g., RDP, VNC)
        device_management (DeviceManagement | Unset):
        browser_self_protection_module (BrowserSelfProtectionModule | Unset): Browser self-protection module
        is_os_user_admin (bool | Unset): OS user is admin
        user (User | Unset):
    """

    id: str
    external_id: str
    status: DeviceStatus
    first_seen: datetime.datetime
    last_seen: datetime.datetime
    os_type: DeviceOsType
    os_version: str
    os_display_name: str
    arch: str
    native_arch: str
    hostname: str
    model: str
    serial_number: str
    mac_addresses: list[str]
    screen_lock_status: DeviceScreenLockStatus
    disk_encryption_status: DeviceDiskEncryptionStatus
    firewall_status: DeviceFirewallStatus
    user_agent: str
    talon_extension_version: str
    browser_version: str
    browser_brand: DeviceBrowserBrand
    device_type: DeviceDeviceType
    platform: DevicePlatform
    is_browser_installed_as_admin: bool
    chromeos_version: str | Unset = UNSET
    location_method: LocationMethod | Unset = UNSET
    mobile_vendor: str | Unset = UNSET
    mobile_hardware: str | Unset = UNSET
    mobile_is_rooted: bool | Unset = UNSET
    disk_encryption_details: DeviceDiskEncryptionDetails | Unset = UNSET
    firewall_details: DeviceFirewallDetails | Unset = UNSET
    ip: None | str | Unset = UNSET
    device_epp: DeviceEPP | Unset = UNSET
    device_password: DevicePasswordPosture | Unset = UNSET
    crowdstrike_zta: CrowdstrikeZTAPosture | Unset = UNSET
    system_integrity: SystemIntegrityPosture | Unset = UNSET
    is_running_on_remote_session: bool | Unset = UNSET
    device_management: DeviceManagement | Unset = UNSET
    browser_self_protection_module: BrowserSelfProtectionModule | Unset = UNSET
    is_os_user_admin: bool | Unset = UNSET
    user: User | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        external_id = self.external_id

        status = self.status.value

        first_seen = self.first_seen.isoformat()

        last_seen = self.last_seen.isoformat()

        os_type = self.os_type.value

        os_version = self.os_version

        os_display_name = self.os_display_name

        arch = self.arch

        native_arch = self.native_arch

        hostname = self.hostname

        model = self.model

        serial_number = self.serial_number

        mac_addresses = self.mac_addresses

        screen_lock_status = self.screen_lock_status.value

        disk_encryption_status = self.disk_encryption_status.value

        firewall_status = self.firewall_status.value

        user_agent = self.user_agent

        talon_extension_version = self.talon_extension_version

        browser_version = self.browser_version

        browser_brand = self.browser_brand.value

        device_type = self.device_type.value

        platform = self.platform.value

        is_browser_installed_as_admin = self.is_browser_installed_as_admin

        chromeos_version = self.chromeos_version

        location_method: str | Unset = UNSET
        if not isinstance(self.location_method, Unset):
            location_method = self.location_method.value

        mobile_vendor = self.mobile_vendor

        mobile_hardware = self.mobile_hardware

        mobile_is_rooted = self.mobile_is_rooted

        disk_encryption_details: dict[str, Any] | Unset = UNSET
        if not isinstance(self.disk_encryption_details, Unset):
            disk_encryption_details = self.disk_encryption_details.to_dict()

        firewall_details: dict[str, Any] | Unset = UNSET
        if not isinstance(self.firewall_details, Unset):
            firewall_details = self.firewall_details.to_dict()

        ip: None | str | Unset
        if isinstance(self.ip, Unset):
            ip = UNSET
        else:
            ip = self.ip

        device_epp: dict[str, Any] | Unset = UNSET
        if not isinstance(self.device_epp, Unset):
            device_epp = self.device_epp.to_dict()

        device_password: dict[str, Any] | Unset = UNSET
        if not isinstance(self.device_password, Unset):
            device_password = self.device_password.to_dict()

        crowdstrike_zta: dict[str, Any] | Unset = UNSET
        if not isinstance(self.crowdstrike_zta, Unset):
            crowdstrike_zta = self.crowdstrike_zta.to_dict()

        system_integrity: dict[str, Any] | Unset = UNSET
        if not isinstance(self.system_integrity, Unset):
            system_integrity = self.system_integrity.to_dict()

        is_running_on_remote_session = self.is_running_on_remote_session

        device_management: dict[str, Any] | Unset = UNSET
        if not isinstance(self.device_management, Unset):
            device_management = self.device_management.to_dict()

        browser_self_protection_module: dict[str, Any] | Unset = UNSET
        if not isinstance(self.browser_self_protection_module, Unset):
            browser_self_protection_module = self.browser_self_protection_module.to_dict()

        is_os_user_admin = self.is_os_user_admin

        user: dict[str, Any] | Unset = UNSET
        if not isinstance(self.user, Unset):
            user = self.user.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "externalId": external_id,
                "status": status,
                "firstSeen": first_seen,
                "lastSeen": last_seen,
                "osType": os_type,
                "osVersion": os_version,
                "osDisplayName": os_display_name,
                "arch": arch,
                "nativeArch": native_arch,
                "hostname": hostname,
                "model": model,
                "serialNumber": serial_number,
                "macAddresses": mac_addresses,
                "screenLockStatus": screen_lock_status,
                "diskEncryptionStatus": disk_encryption_status,
                "firewallStatus": firewall_status,
                "userAgent": user_agent,
                "talonExtensionVersion": talon_extension_version,
                "browserVersion": browser_version,
                "browserBrand": browser_brand,
                "deviceType": device_type,
                "platform": platform,
                "isBrowserInstalledAsAdmin": is_browser_installed_as_admin,
            }
        )
        if chromeos_version is not UNSET:
            field_dict["chromeosVersion"] = chromeos_version
        if location_method is not UNSET:
            field_dict["locationMethod"] = location_method
        if mobile_vendor is not UNSET:
            field_dict["mobileVendor"] = mobile_vendor
        if mobile_hardware is not UNSET:
            field_dict["mobileHardware"] = mobile_hardware
        if mobile_is_rooted is not UNSET:
            field_dict["mobileIsRooted"] = mobile_is_rooted
        if disk_encryption_details is not UNSET:
            field_dict["diskEncryptionDetails"] = disk_encryption_details
        if firewall_details is not UNSET:
            field_dict["firewallDetails"] = firewall_details
        if ip is not UNSET:
            field_dict["ip"] = ip
        if device_epp is not UNSET:
            field_dict["deviceEPP"] = device_epp
        if device_password is not UNSET:
            field_dict["devicePassword"] = device_password
        if crowdstrike_zta is not UNSET:
            field_dict["crowdstrikeZTA"] = crowdstrike_zta
        if system_integrity is not UNSET:
            field_dict["systemIntegrity"] = system_integrity
        if is_running_on_remote_session is not UNSET:
            field_dict["isRunningOnRemoteSession"] = is_running_on_remote_session
        if device_management is not UNSET:
            field_dict["deviceManagement"] = device_management
        if browser_self_protection_module is not UNSET:
            field_dict["browserSelfProtectionModule"] = browser_self_protection_module
        if is_os_user_admin is not UNSET:
            field_dict["isOSUserAdmin"] = is_os_user_admin
        if user is not UNSET:
            field_dict["user"] = user

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.browser_self_protection_module import BrowserSelfProtectionModule
        from ..models.crowdstrike_zta_posture import CrowdstrikeZTAPosture
        from ..models.device_disk_encryption_details import DeviceDiskEncryptionDetails
        from ..models.device_epp import DeviceEPP
        from ..models.device_firewall_details import DeviceFirewallDetails
        from ..models.device_management import DeviceManagement
        from ..models.device_password_posture import DevicePasswordPosture
        from ..models.system_integrity_posture import SystemIntegrityPosture
        from ..models.user import User

        d = dict(src_dict)
        id = d.pop("id")

        external_id = d.pop("externalId")

        status = DeviceStatus(d.pop("status"))

        first_seen = datetime.datetime.fromisoformat(d.pop("firstSeen"))

        last_seen = datetime.datetime.fromisoformat(d.pop("lastSeen"))

        os_type = DeviceOsType(d.pop("osType"))

        os_version = d.pop("osVersion")

        os_display_name = d.pop("osDisplayName")

        arch = d.pop("arch")

        native_arch = d.pop("nativeArch")

        hostname = d.pop("hostname")

        model = d.pop("model")

        serial_number = d.pop("serialNumber")

        mac_addresses = cast(list[str], d.pop("macAddresses"))

        screen_lock_status = DeviceScreenLockStatus(d.pop("screenLockStatus"))

        disk_encryption_status = DeviceDiskEncryptionStatus(d.pop("diskEncryptionStatus"))

        firewall_status = DeviceFirewallStatus(d.pop("firewallStatus"))

        user_agent = d.pop("userAgent")

        talon_extension_version = d.pop("talonExtensionVersion")

        browser_version = d.pop("browserVersion")

        browser_brand = DeviceBrowserBrand(d.pop("browserBrand"))

        device_type = DeviceDeviceType(d.pop("deviceType"))

        platform = DevicePlatform(d.pop("platform"))

        is_browser_installed_as_admin = d.pop("isBrowserInstalledAsAdmin")

        chromeos_version = d.pop("chromeosVersion", UNSET)

        _location_method = d.pop("locationMethod", UNSET)
        location_method: LocationMethod | Unset
        if isinstance(_location_method, Unset):
            location_method = UNSET
        else:
            location_method = LocationMethod(_location_method)

        mobile_vendor = d.pop("mobileVendor", UNSET)

        mobile_hardware = d.pop("mobileHardware", UNSET)

        mobile_is_rooted = d.pop("mobileIsRooted", UNSET)

        _disk_encryption_details = d.pop("diskEncryptionDetails", UNSET)
        disk_encryption_details: DeviceDiskEncryptionDetails | Unset
        if isinstance(_disk_encryption_details, Unset):
            disk_encryption_details = UNSET
        else:
            disk_encryption_details = DeviceDiskEncryptionDetails.from_dict(_disk_encryption_details)

        _firewall_details = d.pop("firewallDetails", UNSET)
        firewall_details: DeviceFirewallDetails | Unset
        if isinstance(_firewall_details, Unset):
            firewall_details = UNSET
        else:
            firewall_details = DeviceFirewallDetails.from_dict(_firewall_details)

        def _parse_ip(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        ip = _parse_ip(d.pop("ip", UNSET))

        _device_epp = d.pop("deviceEPP", UNSET)
        device_epp: DeviceEPP | Unset
        if isinstance(_device_epp, Unset):
            device_epp = UNSET
        else:
            device_epp = DeviceEPP.from_dict(_device_epp)

        _device_password = d.pop("devicePassword", UNSET)
        device_password: DevicePasswordPosture | Unset
        if isinstance(_device_password, Unset):
            device_password = UNSET
        else:
            device_password = DevicePasswordPosture.from_dict(_device_password)

        _crowdstrike_zta = d.pop("crowdstrikeZTA", UNSET)
        crowdstrike_zta: CrowdstrikeZTAPosture | Unset
        if isinstance(_crowdstrike_zta, Unset):
            crowdstrike_zta = UNSET
        else:
            crowdstrike_zta = CrowdstrikeZTAPosture.from_dict(_crowdstrike_zta)

        _system_integrity = d.pop("systemIntegrity", UNSET)
        system_integrity: SystemIntegrityPosture | Unset
        if isinstance(_system_integrity, Unset):
            system_integrity = UNSET
        else:
            system_integrity = SystemIntegrityPosture.from_dict(_system_integrity)

        is_running_on_remote_session = d.pop("isRunningOnRemoteSession", UNSET)

        _device_management = d.pop("deviceManagement", UNSET)
        device_management: DeviceManagement | Unset
        if isinstance(_device_management, Unset):
            device_management = UNSET
        else:
            device_management = DeviceManagement.from_dict(_device_management)

        _browser_self_protection_module = d.pop("browserSelfProtectionModule", UNSET)
        browser_self_protection_module: BrowserSelfProtectionModule | Unset
        if isinstance(_browser_self_protection_module, Unset):
            browser_self_protection_module = UNSET
        else:
            browser_self_protection_module = BrowserSelfProtectionModule.from_dict(_browser_self_protection_module)

        is_os_user_admin = d.pop("isOSUserAdmin", UNSET)

        _user = d.pop("user", UNSET)
        user: User | Unset
        if isinstance(_user, Unset):
            user = UNSET
        else:
            user = User.from_dict(_user)

        device = cls(
            id=id,
            external_id=external_id,
            status=status,
            first_seen=first_seen,
            last_seen=last_seen,
            os_type=os_type,
            os_version=os_version,
            os_display_name=os_display_name,
            arch=arch,
            native_arch=native_arch,
            hostname=hostname,
            model=model,
            serial_number=serial_number,
            mac_addresses=mac_addresses,
            screen_lock_status=screen_lock_status,
            disk_encryption_status=disk_encryption_status,
            firewall_status=firewall_status,
            user_agent=user_agent,
            talon_extension_version=talon_extension_version,
            browser_version=browser_version,
            browser_brand=browser_brand,
            device_type=device_type,
            platform=platform,
            is_browser_installed_as_admin=is_browser_installed_as_admin,
            chromeos_version=chromeos_version,
            location_method=location_method,
            mobile_vendor=mobile_vendor,
            mobile_hardware=mobile_hardware,
            mobile_is_rooted=mobile_is_rooted,
            disk_encryption_details=disk_encryption_details,
            firewall_details=firewall_details,
            ip=ip,
            device_epp=device_epp,
            device_password=device_password,
            crowdstrike_zta=crowdstrike_zta,
            system_integrity=system_integrity,
            is_running_on_remote_session=is_running_on_remote_session,
            device_management=device_management,
            browser_self_protection_module=browser_self_protection_module,
            is_os_user_admin=is_os_user_admin,
            user=user,
        )

        device.additional_properties = d
        return device

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
