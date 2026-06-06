from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.attribute_object_browser_brand import AttributeObjectBrowserBrand
    from ..models.attribute_object_browser_eol import AttributeObjectBrowserEol
    from ..models.attribute_object_client_certificate import AttributeObjectClientCertificate
    from ..models.attribute_object_cs_zta_score import AttributeObjectCsZtaScore
    from ..models.attribute_object_device_management import AttributeObjectDeviceManagement
    from ..models.attribute_object_device_manufacturer import AttributeObjectDeviceManufacturer
    from ..models.attribute_object_device_type import AttributeObjectDeviceType
    from ..models.attribute_object_disk_encryption import AttributeObjectDiskEncryption
    from ..models.attribute_object_endpoint_protection import AttributeObjectEndpointProtection
    from ..models.attribute_object_file_existence import AttributeObjectFileExistence
    from ..models.attribute_object_firewall import AttributeObjectFirewall
    from ..models.attribute_object_location_services import AttributeObjectLocationServices
    from ..models.attribute_object_mobile_device_management import AttributeObjectMobileDeviceManagement
    from ..models.attribute_object_mobile_device_manufacturers import AttributeObjectMobileDeviceManufacturers
    from ..models.attribute_object_mobile_device_type import AttributeObjectMobileDeviceType
    from ..models.attribute_object_mobile_os_version import AttributeObjectMobileOsVersion
    from ..models.attribute_object_mobile_root_jail_break_status import AttributeObjectMobileRootJailBreakStatus
    from ..models.attribute_object_mobile_screen_lock import AttributeObjectMobileScreenLock
    from ..models.attribute_object_normal_os_boot_mode import AttributeObjectNormalOSBootMode
    from ..models.attribute_object_os_password import AttributeObjectOsPassword
    from ..models.attribute_object_os_version import AttributeObjectOsVersion
    from ..models.attribute_object_privileged_process import AttributeObjectPrivilegedProcess
    from ..models.attribute_object_registry import AttributeObjectRegistry
    from ..models.attribute_object_remote_connection import AttributeObjectRemoteConnection
    from ..models.attribute_object_running_processes import AttributeObjectRunningProcesses
    from ..models.attribute_object_screen_lock import AttributeObjectScreenLock
    from ..models.attribute_object_serial_number import AttributeObjectSerialNumber
    from ..models.attribute_object_system_integrity import AttributeObjectSystemIntegrity


T = TypeVar("T", bound="AttributeObject")


@_attrs_define
class AttributeObject:
    """
    Attributes:
        screen_lock (AttributeObjectScreenLock | Unset): Check if the device has automatic screen lock enabled
        endpoint_protection (AttributeObjectEndpointProtection | Unset): Check if the device has endpoint protection
            software installed and running
        firewall (AttributeObjectFirewall | Unset): Check if the device has firewall protection installed and running
        disk_encryption (AttributeObjectDiskEncryption | Unset): Check if the device has disk encryption software
            installed and running
        os_version (AttributeObjectOsVersion | Unset): Check if the device is running a specific operating system
            version
        serial_number (AttributeObjectSerialNumber | Unset): Check if the device's serial number is included in the
            provided list
        client_certificate (AttributeObjectClientCertificate | Unset): Check if the device's client certificate is
            signed by the provided issuer certificate
        device_type (AttributeObjectDeviceType | Unset): Check if the device matches specific device types (e.g.,
            desktop, laptop, virtual machine)
        cs_zta_score (AttributeObjectCsZtaScore | Unset): Check if the device meets minimum CrowdStrike Zero Trust
            Assessment score requirements.
            If multiple score types are provided (basicScore, overallScore, breakdownScores), the latest one will be used.
        mobile_root_jail_break_status (AttributeObjectMobileRootJailBreakStatus | Unset): Check if the mobile device has
            been rooted (Android) or jailbroken (iOS)
        mobile_screen_lock (AttributeObjectMobileScreenLock | Unset): Check if the mobile device has screen lock
            protection enabled
        mobile_device_manufacturers (AttributeObjectMobileDeviceManufacturers | Unset): Check if the mobile device is
            from specific manufacturers (e.g., Apple, Samsung)
        mobile_os_version (AttributeObjectMobileOsVersion | Unset): Check if the mobile device is running a specific iOS
            or Android version
        mobile_device_type (AttributeObjectMobileDeviceType | Unset): Check if the mobile device matches specific types
            (e.g., phone, tablet)
        mobile_device_management (AttributeObjectMobileDeviceManagement | Unset): Check if the mobile device is managed
            by specific mobile device management systems
        os_password (AttributeObjectOsPassword | Unset): Check if the device has an OS authentication password
            configured with specific requirements
        normal_os_boot_mode (AttributeObjectNormalOSBootMode | Unset): Check if a device is running in OS normal boot
            mode (not safe mode, recovery mode or a pre-installation environment)
        privileged_process (AttributeObjectPrivilegedProcess | Unset): Include only devices on which Prisma Browser is
            running with elevated/root permissions
        device_manufacturer (AttributeObjectDeviceManufacturer | Unset): Check if the device is from specific
            manufacturers (e.g., Dell, HP, Lenovo)
        device_management (AttributeObjectDeviceManagement | Unset): Check if the device is managed by specific device
            management systems (e.g., Microsoft Intune, Jamf, Active Directory)
        system_integrity (AttributeObjectSystemIntegrity | Unset): Check if the device has advanced system integrity
            protection enabled
        browser_brand (AttributeObjectBrowserBrand | Unset): Check if the device has specific browser brands and
            versions installed
        remote_connection (AttributeObjectRemoteConnection | Unset): Check if the device has an active remote connection
            (RDP, Citrix ICA, etc.)
        registry (AttributeObjectRegistry | Unset): Check if the device has all of the specified registry key
            configurations (Windows only)
        location_services (AttributeObjectLocationServices | Unset): Check if the device's location services can be
            accessed by Prisma Browser
        running_processes (AttributeObjectRunningProcesses | Unset): Check if the device has all of the specified
            processes running
        file_existence (AttributeObjectFileExistence | Unset): Check if the device has all of the specified files
            present
        browser_eol (AttributeObjectBrowserEol | Unset): Check if the device has browser versions that are end-of-life
    """

    screen_lock: AttributeObjectScreenLock | Unset = UNSET
    endpoint_protection: AttributeObjectEndpointProtection | Unset = UNSET
    firewall: AttributeObjectFirewall | Unset = UNSET
    disk_encryption: AttributeObjectDiskEncryption | Unset = UNSET
    os_version: AttributeObjectOsVersion | Unset = UNSET
    serial_number: AttributeObjectSerialNumber | Unset = UNSET
    client_certificate: AttributeObjectClientCertificate | Unset = UNSET
    device_type: AttributeObjectDeviceType | Unset = UNSET
    cs_zta_score: AttributeObjectCsZtaScore | Unset = UNSET
    mobile_root_jail_break_status: AttributeObjectMobileRootJailBreakStatus | Unset = UNSET
    mobile_screen_lock: AttributeObjectMobileScreenLock | Unset = UNSET
    mobile_device_manufacturers: AttributeObjectMobileDeviceManufacturers | Unset = UNSET
    mobile_os_version: AttributeObjectMobileOsVersion | Unset = UNSET
    mobile_device_type: AttributeObjectMobileDeviceType | Unset = UNSET
    mobile_device_management: AttributeObjectMobileDeviceManagement | Unset = UNSET
    os_password: AttributeObjectOsPassword | Unset = UNSET
    normal_os_boot_mode: AttributeObjectNormalOSBootMode | Unset = UNSET
    privileged_process: AttributeObjectPrivilegedProcess | Unset = UNSET
    device_manufacturer: AttributeObjectDeviceManufacturer | Unset = UNSET
    device_management: AttributeObjectDeviceManagement | Unset = UNSET
    system_integrity: AttributeObjectSystemIntegrity | Unset = UNSET
    browser_brand: AttributeObjectBrowserBrand | Unset = UNSET
    remote_connection: AttributeObjectRemoteConnection | Unset = UNSET
    registry: AttributeObjectRegistry | Unset = UNSET
    location_services: AttributeObjectLocationServices | Unset = UNSET
    running_processes: AttributeObjectRunningProcesses | Unset = UNSET
    file_existence: AttributeObjectFileExistence | Unset = UNSET
    browser_eol: AttributeObjectBrowserEol | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        screen_lock: dict[str, Any] | Unset = UNSET
        if not isinstance(self.screen_lock, Unset):
            screen_lock = self.screen_lock.to_dict()

        endpoint_protection: dict[str, Any] | Unset = UNSET
        if not isinstance(self.endpoint_protection, Unset):
            endpoint_protection = self.endpoint_protection.to_dict()

        firewall: dict[str, Any] | Unset = UNSET
        if not isinstance(self.firewall, Unset):
            firewall = self.firewall.to_dict()

        disk_encryption: dict[str, Any] | Unset = UNSET
        if not isinstance(self.disk_encryption, Unset):
            disk_encryption = self.disk_encryption.to_dict()

        os_version: dict[str, Any] | Unset = UNSET
        if not isinstance(self.os_version, Unset):
            os_version = self.os_version.to_dict()

        serial_number: dict[str, Any] | Unset = UNSET
        if not isinstance(self.serial_number, Unset):
            serial_number = self.serial_number.to_dict()

        client_certificate: dict[str, Any] | Unset = UNSET
        if not isinstance(self.client_certificate, Unset):
            client_certificate = self.client_certificate.to_dict()

        device_type: dict[str, Any] | Unset = UNSET
        if not isinstance(self.device_type, Unset):
            device_type = self.device_type.to_dict()

        cs_zta_score: dict[str, Any] | Unset = UNSET
        if not isinstance(self.cs_zta_score, Unset):
            cs_zta_score = self.cs_zta_score.to_dict()

        mobile_root_jail_break_status: dict[str, Any] | Unset = UNSET
        if not isinstance(self.mobile_root_jail_break_status, Unset):
            mobile_root_jail_break_status = self.mobile_root_jail_break_status.to_dict()

        mobile_screen_lock: dict[str, Any] | Unset = UNSET
        if not isinstance(self.mobile_screen_lock, Unset):
            mobile_screen_lock = self.mobile_screen_lock.to_dict()

        mobile_device_manufacturers: dict[str, Any] | Unset = UNSET
        if not isinstance(self.mobile_device_manufacturers, Unset):
            mobile_device_manufacturers = self.mobile_device_manufacturers.to_dict()

        mobile_os_version: dict[str, Any] | Unset = UNSET
        if not isinstance(self.mobile_os_version, Unset):
            mobile_os_version = self.mobile_os_version.to_dict()

        mobile_device_type: dict[str, Any] | Unset = UNSET
        if not isinstance(self.mobile_device_type, Unset):
            mobile_device_type = self.mobile_device_type.to_dict()

        mobile_device_management: dict[str, Any] | Unset = UNSET
        if not isinstance(self.mobile_device_management, Unset):
            mobile_device_management = self.mobile_device_management.to_dict()

        os_password: dict[str, Any] | Unset = UNSET
        if not isinstance(self.os_password, Unset):
            os_password = self.os_password.to_dict()

        normal_os_boot_mode: dict[str, Any] | Unset = UNSET
        if not isinstance(self.normal_os_boot_mode, Unset):
            normal_os_boot_mode = self.normal_os_boot_mode.to_dict()

        privileged_process: dict[str, Any] | Unset = UNSET
        if not isinstance(self.privileged_process, Unset):
            privileged_process = self.privileged_process.to_dict()

        device_manufacturer: dict[str, Any] | Unset = UNSET
        if not isinstance(self.device_manufacturer, Unset):
            device_manufacturer = self.device_manufacturer.to_dict()

        device_management: dict[str, Any] | Unset = UNSET
        if not isinstance(self.device_management, Unset):
            device_management = self.device_management.to_dict()

        system_integrity: dict[str, Any] | Unset = UNSET
        if not isinstance(self.system_integrity, Unset):
            system_integrity = self.system_integrity.to_dict()

        browser_brand: dict[str, Any] | Unset = UNSET
        if not isinstance(self.browser_brand, Unset):
            browser_brand = self.browser_brand.to_dict()

        remote_connection: dict[str, Any] | Unset = UNSET
        if not isinstance(self.remote_connection, Unset):
            remote_connection = self.remote_connection.to_dict()

        registry: dict[str, Any] | Unset = UNSET
        if not isinstance(self.registry, Unset):
            registry = self.registry.to_dict()

        location_services: dict[str, Any] | Unset = UNSET
        if not isinstance(self.location_services, Unset):
            location_services = self.location_services.to_dict()

        running_processes: dict[str, Any] | Unset = UNSET
        if not isinstance(self.running_processes, Unset):
            running_processes = self.running_processes.to_dict()

        file_existence: dict[str, Any] | Unset = UNSET
        if not isinstance(self.file_existence, Unset):
            file_existence = self.file_existence.to_dict()

        browser_eol: dict[str, Any] | Unset = UNSET
        if not isinstance(self.browser_eol, Unset):
            browser_eol = self.browser_eol.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if screen_lock is not UNSET:
            field_dict["screenLock"] = screen_lock
        if endpoint_protection is not UNSET:
            field_dict["endpointProtection"] = endpoint_protection
        if firewall is not UNSET:
            field_dict["firewall"] = firewall
        if disk_encryption is not UNSET:
            field_dict["diskEncryption"] = disk_encryption
        if os_version is not UNSET:
            field_dict["osVersion"] = os_version
        if serial_number is not UNSET:
            field_dict["serialNumber"] = serial_number
        if client_certificate is not UNSET:
            field_dict["clientCertificate"] = client_certificate
        if device_type is not UNSET:
            field_dict["deviceType"] = device_type
        if cs_zta_score is not UNSET:
            field_dict["csZtaScore"] = cs_zta_score
        if mobile_root_jail_break_status is not UNSET:
            field_dict["mobileRootJailBreakStatus"] = mobile_root_jail_break_status
        if mobile_screen_lock is not UNSET:
            field_dict["mobileScreenLock"] = mobile_screen_lock
        if mobile_device_manufacturers is not UNSET:
            field_dict["mobileDeviceManufacturers"] = mobile_device_manufacturers
        if mobile_os_version is not UNSET:
            field_dict["mobileOsVersion"] = mobile_os_version
        if mobile_device_type is not UNSET:
            field_dict["mobileDeviceType"] = mobile_device_type
        if mobile_device_management is not UNSET:
            field_dict["mobileDeviceManagement"] = mobile_device_management
        if os_password is not UNSET:
            field_dict["osPassword"] = os_password
        if normal_os_boot_mode is not UNSET:
            field_dict["normalOSBootMode"] = normal_os_boot_mode
        if privileged_process is not UNSET:
            field_dict["privilegedProcess"] = privileged_process
        if device_manufacturer is not UNSET:
            field_dict["deviceManufacturer"] = device_manufacturer
        if device_management is not UNSET:
            field_dict["deviceManagement"] = device_management
        if system_integrity is not UNSET:
            field_dict["systemIntegrity"] = system_integrity
        if browser_brand is not UNSET:
            field_dict["browserBrand"] = browser_brand
        if remote_connection is not UNSET:
            field_dict["remoteConnection"] = remote_connection
        if registry is not UNSET:
            field_dict["registry"] = registry
        if location_services is not UNSET:
            field_dict["locationServices"] = location_services
        if running_processes is not UNSET:
            field_dict["runningProcesses"] = running_processes
        if file_existence is not UNSET:
            field_dict["fileExistence"] = file_existence
        if browser_eol is not UNSET:
            field_dict["browserEol"] = browser_eol

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.attribute_object_browser_brand import AttributeObjectBrowserBrand
        from ..models.attribute_object_browser_eol import AttributeObjectBrowserEol
        from ..models.attribute_object_client_certificate import AttributeObjectClientCertificate
        from ..models.attribute_object_cs_zta_score import AttributeObjectCsZtaScore
        from ..models.attribute_object_device_management import AttributeObjectDeviceManagement
        from ..models.attribute_object_device_manufacturer import AttributeObjectDeviceManufacturer
        from ..models.attribute_object_device_type import AttributeObjectDeviceType
        from ..models.attribute_object_disk_encryption import AttributeObjectDiskEncryption
        from ..models.attribute_object_endpoint_protection import AttributeObjectEndpointProtection
        from ..models.attribute_object_file_existence import AttributeObjectFileExistence
        from ..models.attribute_object_firewall import AttributeObjectFirewall
        from ..models.attribute_object_location_services import AttributeObjectLocationServices
        from ..models.attribute_object_mobile_device_management import AttributeObjectMobileDeviceManagement
        from ..models.attribute_object_mobile_device_manufacturers import AttributeObjectMobileDeviceManufacturers
        from ..models.attribute_object_mobile_device_type import AttributeObjectMobileDeviceType
        from ..models.attribute_object_mobile_os_version import AttributeObjectMobileOsVersion
        from ..models.attribute_object_mobile_root_jail_break_status import AttributeObjectMobileRootJailBreakStatus
        from ..models.attribute_object_mobile_screen_lock import AttributeObjectMobileScreenLock
        from ..models.attribute_object_normal_os_boot_mode import AttributeObjectNormalOSBootMode
        from ..models.attribute_object_os_password import AttributeObjectOsPassword
        from ..models.attribute_object_os_version import AttributeObjectOsVersion
        from ..models.attribute_object_privileged_process import AttributeObjectPrivilegedProcess
        from ..models.attribute_object_registry import AttributeObjectRegistry
        from ..models.attribute_object_remote_connection import AttributeObjectRemoteConnection
        from ..models.attribute_object_running_processes import AttributeObjectRunningProcesses
        from ..models.attribute_object_screen_lock import AttributeObjectScreenLock
        from ..models.attribute_object_serial_number import AttributeObjectSerialNumber
        from ..models.attribute_object_system_integrity import AttributeObjectSystemIntegrity

        d = dict(src_dict)
        _screen_lock = d.pop("screenLock", UNSET)
        screen_lock: AttributeObjectScreenLock | Unset
        if isinstance(_screen_lock, Unset):
            screen_lock = UNSET
        else:
            screen_lock = AttributeObjectScreenLock.from_dict(_screen_lock)

        _endpoint_protection = d.pop("endpointProtection", UNSET)
        endpoint_protection: AttributeObjectEndpointProtection | Unset
        if isinstance(_endpoint_protection, Unset):
            endpoint_protection = UNSET
        else:
            endpoint_protection = AttributeObjectEndpointProtection.from_dict(_endpoint_protection)

        _firewall = d.pop("firewall", UNSET)
        firewall: AttributeObjectFirewall | Unset
        if isinstance(_firewall, Unset):
            firewall = UNSET
        else:
            firewall = AttributeObjectFirewall.from_dict(_firewall)

        _disk_encryption = d.pop("diskEncryption", UNSET)
        disk_encryption: AttributeObjectDiskEncryption | Unset
        if isinstance(_disk_encryption, Unset):
            disk_encryption = UNSET
        else:
            disk_encryption = AttributeObjectDiskEncryption.from_dict(_disk_encryption)

        _os_version = d.pop("osVersion", UNSET)
        os_version: AttributeObjectOsVersion | Unset
        if isinstance(_os_version, Unset):
            os_version = UNSET
        else:
            os_version = AttributeObjectOsVersion.from_dict(_os_version)

        _serial_number = d.pop("serialNumber", UNSET)
        serial_number: AttributeObjectSerialNumber | Unset
        if isinstance(_serial_number, Unset):
            serial_number = UNSET
        else:
            serial_number = AttributeObjectSerialNumber.from_dict(_serial_number)

        _client_certificate = d.pop("clientCertificate", UNSET)
        client_certificate: AttributeObjectClientCertificate | Unset
        if isinstance(_client_certificate, Unset):
            client_certificate = UNSET
        else:
            client_certificate = AttributeObjectClientCertificate.from_dict(_client_certificate)

        _device_type = d.pop("deviceType", UNSET)
        device_type: AttributeObjectDeviceType | Unset
        if isinstance(_device_type, Unset):
            device_type = UNSET
        else:
            device_type = AttributeObjectDeviceType.from_dict(_device_type)

        _cs_zta_score = d.pop("csZtaScore", UNSET)
        cs_zta_score: AttributeObjectCsZtaScore | Unset
        if isinstance(_cs_zta_score, Unset):
            cs_zta_score = UNSET
        else:
            cs_zta_score = AttributeObjectCsZtaScore.from_dict(_cs_zta_score)

        _mobile_root_jail_break_status = d.pop("mobileRootJailBreakStatus", UNSET)
        mobile_root_jail_break_status: AttributeObjectMobileRootJailBreakStatus | Unset
        if isinstance(_mobile_root_jail_break_status, Unset):
            mobile_root_jail_break_status = UNSET
        else:
            mobile_root_jail_break_status = AttributeObjectMobileRootJailBreakStatus.from_dict(
                _mobile_root_jail_break_status
            )

        _mobile_screen_lock = d.pop("mobileScreenLock", UNSET)
        mobile_screen_lock: AttributeObjectMobileScreenLock | Unset
        if isinstance(_mobile_screen_lock, Unset):
            mobile_screen_lock = UNSET
        else:
            mobile_screen_lock = AttributeObjectMobileScreenLock.from_dict(_mobile_screen_lock)

        _mobile_device_manufacturers = d.pop("mobileDeviceManufacturers", UNSET)
        mobile_device_manufacturers: AttributeObjectMobileDeviceManufacturers | Unset
        if isinstance(_mobile_device_manufacturers, Unset):
            mobile_device_manufacturers = UNSET
        else:
            mobile_device_manufacturers = AttributeObjectMobileDeviceManufacturers.from_dict(
                _mobile_device_manufacturers
            )

        _mobile_os_version = d.pop("mobileOsVersion", UNSET)
        mobile_os_version: AttributeObjectMobileOsVersion | Unset
        if isinstance(_mobile_os_version, Unset):
            mobile_os_version = UNSET
        else:
            mobile_os_version = AttributeObjectMobileOsVersion.from_dict(_mobile_os_version)

        _mobile_device_type = d.pop("mobileDeviceType", UNSET)
        mobile_device_type: AttributeObjectMobileDeviceType | Unset
        if isinstance(_mobile_device_type, Unset):
            mobile_device_type = UNSET
        else:
            mobile_device_type = AttributeObjectMobileDeviceType.from_dict(_mobile_device_type)

        _mobile_device_management = d.pop("mobileDeviceManagement", UNSET)
        mobile_device_management: AttributeObjectMobileDeviceManagement | Unset
        if isinstance(_mobile_device_management, Unset):
            mobile_device_management = UNSET
        else:
            mobile_device_management = AttributeObjectMobileDeviceManagement.from_dict(_mobile_device_management)

        _os_password = d.pop("osPassword", UNSET)
        os_password: AttributeObjectOsPassword | Unset
        if isinstance(_os_password, Unset):
            os_password = UNSET
        else:
            os_password = AttributeObjectOsPassword.from_dict(_os_password)

        _normal_os_boot_mode = d.pop("normalOSBootMode", UNSET)
        normal_os_boot_mode: AttributeObjectNormalOSBootMode | Unset
        if isinstance(_normal_os_boot_mode, Unset):
            normal_os_boot_mode = UNSET
        else:
            normal_os_boot_mode = AttributeObjectNormalOSBootMode.from_dict(_normal_os_boot_mode)

        _privileged_process = d.pop("privilegedProcess", UNSET)
        privileged_process: AttributeObjectPrivilegedProcess | Unset
        if isinstance(_privileged_process, Unset):
            privileged_process = UNSET
        else:
            privileged_process = AttributeObjectPrivilegedProcess.from_dict(_privileged_process)

        _device_manufacturer = d.pop("deviceManufacturer", UNSET)
        device_manufacturer: AttributeObjectDeviceManufacturer | Unset
        if isinstance(_device_manufacturer, Unset):
            device_manufacturer = UNSET
        else:
            device_manufacturer = AttributeObjectDeviceManufacturer.from_dict(_device_manufacturer)

        _device_management = d.pop("deviceManagement", UNSET)
        device_management: AttributeObjectDeviceManagement | Unset
        if isinstance(_device_management, Unset):
            device_management = UNSET
        else:
            device_management = AttributeObjectDeviceManagement.from_dict(_device_management)

        _system_integrity = d.pop("systemIntegrity", UNSET)
        system_integrity: AttributeObjectSystemIntegrity | Unset
        if isinstance(_system_integrity, Unset):
            system_integrity = UNSET
        else:
            system_integrity = AttributeObjectSystemIntegrity.from_dict(_system_integrity)

        _browser_brand = d.pop("browserBrand", UNSET)
        browser_brand: AttributeObjectBrowserBrand | Unset
        if isinstance(_browser_brand, Unset):
            browser_brand = UNSET
        else:
            browser_brand = AttributeObjectBrowserBrand.from_dict(_browser_brand)

        _remote_connection = d.pop("remoteConnection", UNSET)
        remote_connection: AttributeObjectRemoteConnection | Unset
        if isinstance(_remote_connection, Unset):
            remote_connection = UNSET
        else:
            remote_connection = AttributeObjectRemoteConnection.from_dict(_remote_connection)

        _registry = d.pop("registry", UNSET)
        registry: AttributeObjectRegistry | Unset
        if isinstance(_registry, Unset):
            registry = UNSET
        else:
            registry = AttributeObjectRegistry.from_dict(_registry)

        _location_services = d.pop("locationServices", UNSET)
        location_services: AttributeObjectLocationServices | Unset
        if isinstance(_location_services, Unset):
            location_services = UNSET
        else:
            location_services = AttributeObjectLocationServices.from_dict(_location_services)

        _running_processes = d.pop("runningProcesses", UNSET)
        running_processes: AttributeObjectRunningProcesses | Unset
        if isinstance(_running_processes, Unset):
            running_processes = UNSET
        else:
            running_processes = AttributeObjectRunningProcesses.from_dict(_running_processes)

        _file_existence = d.pop("fileExistence", UNSET)
        file_existence: AttributeObjectFileExistence | Unset
        if isinstance(_file_existence, Unset):
            file_existence = UNSET
        else:
            file_existence = AttributeObjectFileExistence.from_dict(_file_existence)

        _browser_eol = d.pop("browserEol", UNSET)
        browser_eol: AttributeObjectBrowserEol | Unset
        if isinstance(_browser_eol, Unset):
            browser_eol = UNSET
        else:
            browser_eol = AttributeObjectBrowserEol.from_dict(_browser_eol)

        attribute_object = cls(
            screen_lock=screen_lock,
            endpoint_protection=endpoint_protection,
            firewall=firewall,
            disk_encryption=disk_encryption,
            os_version=os_version,
            serial_number=serial_number,
            client_certificate=client_certificate,
            device_type=device_type,
            cs_zta_score=cs_zta_score,
            mobile_root_jail_break_status=mobile_root_jail_break_status,
            mobile_screen_lock=mobile_screen_lock,
            mobile_device_manufacturers=mobile_device_manufacturers,
            mobile_os_version=mobile_os_version,
            mobile_device_type=mobile_device_type,
            mobile_device_management=mobile_device_management,
            os_password=os_password,
            normal_os_boot_mode=normal_os_boot_mode,
            privileged_process=privileged_process,
            device_manufacturer=device_manufacturer,
            device_management=device_management,
            system_integrity=system_integrity,
            browser_brand=browser_brand,
            remote_connection=remote_connection,
            registry=registry,
            location_services=location_services,
            running_processes=running_processes,
            file_existence=file_existence,
            browser_eol=browser_eol,
        )

        return attribute_object
