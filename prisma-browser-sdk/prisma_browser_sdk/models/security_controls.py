from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar
from typing import cast as _typing_cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.allow_block_control_type_0 import AllowBlockControlType0
    from ..models.allowed_or_blocked_extensions_control_type_0 import AllowedOrBlockedExtensionsControlType0
    from ..models.allowed_printers_control_type_0 import AllowedPrintersControlType0
    from ..models.authentication_factor_identity_provider_control import AuthenticationFactorIdentityProviderControl
    from ..models.authentication_factor_passkey_control import AuthenticationFactorPasskeyControl
    from ..models.authentication_factor_pin_code_control import AuthenticationFactorPinCodeControl
    from ..models.authentication_server_allowlist_control_type_0 import AuthenticationServerAllowlistControlType0
    from ..models.block_extensions_by_permissions_control_type_0 import BlockExtensionsByPermissionsControlType0
    from ..models.browser_history_control_type_0 import BrowserHistoryControlType0
    from ..models.browser_lock_control_type_0 import BrowserLockControlType0
    from ..models.browser_self_protection_control_type_0 import BrowserSelfProtectionControlType0
    from ..models.concurrent_number_of_devices_control_type_0 import ConcurrentNumberOfDevicesControlType0
    from ..models.cookies_control_type_0 import CookiesControlType0
    from ..models.dns_over_https_control_type_0 import DnsOverHttpsControlType0
    from ..models.enable_disable_control_type_0 import EnableDisableControlType0
    from ..models.enhanced_tracking_protection_control_type_0 import EnhancedTrackingProtectionControlType0
    from ..models.flush_browser_data_control_type_0 import FlushBrowserDataControlType0
    from ..models.force_https_control_type_0 import ForceHttpsControlType0
    from ..models.internet_explorer_compatibility_mode_control_type_0 import (
        InternetExplorerCompatibilityModeControlType0,
    )
    from ..models.java_script_v8_jit_and_web_assembly_control_type_0 import JavaScriptV8JitAndWebAssemblyControlType0
    from ..models.kerberos_delegation_allowlist_control_type_0 import KerberosDelegationAllowlistControlType0
    from ..models.keylogging_protection_control_type_0 import KeyloggingProtectionControlType0
    from ..models.launching_external_applications_control_type_0 import LaunchingExternalApplicationsControlType0
    from ..models.legacy_password_manager_control_type_0 import LegacyPasswordManagerControlType0
    from ..models.local_network_access_restrictions_control_type_0 import LocalNetworkAccessRestrictionsControlType0
    from ..models.native_messaging_hosts_control_type_0 import NativeMessagingHostsControlType0
    from ..models.notifications_control_type_0 import NotificationsControlType0
    from ..models.open_links_in_external_apps_control_type_0 import OpenLinksInExternalAppsControlType0
    from ..models.pages_with_insecure_content_control_type_0 import PagesWithInsecureContentControlType0
    from ..models.popups_control_type_0 import PopupsControlType0
    from ..models.post_quantum_key_security_control_type_0 import PostQuantumKeySecurityControlType0
    from ..models.restrict_extension_host_permissions_control_type_0 import RestrictExtensionHostPermissionsControlType0
    from ..models.session_refresh_control_type_0 import SessionRefreshControlType0
    from ..models.trusted_certificate_authorities_control_type_0 import TrustedCertificateAuthoritiesControlType0
    from ..models.web_rtc_control_type_0 import WebRtcControlType0


T = TypeVar("T", bound="SecurityControls")


@_attrs_define
class SecurityControls:
    """Controls for security rules.

    Attributes:
        developer_tools (AllowBlockControlType0 | None | Unset): A simple control with an allow or block action. Re-
            usable by any data control that only needs a binary allow/block decision.
        cast (AllowBlockControlType0 | None | Unset): A simple control with an allow or block action. Re-usable by any
            data control that only needs a binary allow/block decision.
        cookies_protection (EnableDisableControlType0 | None | Unset): A simple control with an enable or disable
            action. Re-usable by any control that only needs a binary enable/disable decision.
        browser_history (BrowserHistoryControlType0 | None | Unset): Control the ability to delete history from the
            browser.
        dns_over_https (DnsOverHttpsControlType0 | None | Unset): Set DNS resolving on top of the HTTPS protocol, for
            encrypting the requests and their resolutions. resolverUrl and adnsEnabled=true are mutually exclusive.
        browser_self_protection (BrowserSelfProtectionControlType0 | None | Unset): Enables a kernel-mode driver that
            provides advanced runtime security for the browser. This protection is available only on Windows and applies
            only to devices where Prisma Browser is installed with admin permissions and the user is running the browser as
            admin.
        keylogging_protection (KeyloggingProtectionControlType0 | None | Unset): Prevent keyloggers from capturing user
            input while using the browser (Windows only).
        browser_lock (BrowserLockControlType0 | None | Unset): Require the user to unlock their browser.
        authentication_factor (AuthenticationFactorIdentityProviderControl | AuthenticationFactorPasskeyControl |
            AuthenticationFactorPinCodeControl | None | Unset): The authentication factor is used to unlock the browser, or
            for step-up MFA.
        session_refresh (None | SessionRefreshControlType0 | Unset): Periodically require the user to re-authenticate.
        native_messaging_hosts (NativeMessagingHostsControlType0 | None | Unset): Control which native messaging hosts
            can communicate with Prisma Browser and its extensions.
        allowed_or_blocked_extensions (AllowedOrBlockedExtensionsControlType0 | None | Unset): Control browser extension
            availability to users based on extension ID or risk score.
        block_extensions_by_permissions (BlockExtensionsByPermissionsControlType0 | None | Unset): Prevent users from
            running extensions that require certain permissions.
        post_quantum_key_security (None | PostQuantumKeySecurityControlType0 | Unset): Control whether to offer a post-
            quantum key agreement algorithm in TLS.
        strict_origin_isolation (EnableDisableControlType0 | None | Unset): A simple control with an enable or disable
            action. Re-usable by any control that only needs a binary enable/disable decision.
        advanced_browser_protection (EnableDisableControlType0 | None | Unset): A simple control with an enable or
            disable action. Re-usable by any control that only needs a binary enable/disable decision.
        user_data_directory_protection (EnableDisableControlType0 | None | Unset): A simple control with an enable or
            disable action. Re-usable by any control that only needs a binary enable/disable decision.
        mobile_password_saving (AllowBlockControlType0 | None | Unset): A simple control with an allow or block action.
            Re-usable by any data control that only needs a binary allow/block decision.
        autofill_of_forms (AllowBlockControlType0 | None | Unset): A simple control with an allow or block action. Re-
            usable by any data control that only needs a binary allow/block decision.
        autofill_of_credit_cards (AllowBlockControlType0 | None | Unset): A simple control with an allow or block
            action. Re-usable by any data control that only needs a binary allow/block decision.
        java_script_running_from_omnibox (AllowBlockControlType0 | None | Unset): A simple control with an allow or
            block action. Re-usable by any data control that only needs a binary allow/block decision.
        pages_with_ssl_errors (AllowBlockControlType0 | None | Unset): A simple control with an allow or block action.
            Re-usable by any data control that only needs a binary allow/block decision.
        basic_authentication_over_http (AllowBlockControlType0 | None | Unset): A simple control with an allow or block
            action. Re-usable by any data control that only needs a binary allow/block decision.
        third_party_cookies (AllowBlockControlType0 | None | Unset): A simple control with an allow or block action. Re-
            usable by any data control that only needs a binary allow/block decision.
        print_preview (AllowBlockControlType0 | None | Unset): A simple control with an allow or block action. Re-usable
            by any data control that only needs a binary allow/block decision.
        google_cloud_print (AllowBlockControlType0 | None | Unset): A simple control with an allow or block action. Re-
            usable by any data control that only needs a binary allow/block decision.
        allowed_printers (AllowedPrintersControlType0 | None | Unset): Control which printers can be used when printing
            from Prisma Browser.
        open_links_in_external_apps (None | OpenLinksInExternalAppsControlType0 | Unset): Control the ability of other
            apps to open links from Prisma Browser.
        trusted_certificate_authorities (None | TrustedCertificateAuthoritiesControlType0 | Unset): Choose the
            certificate authorities trusted by Prisma Browser.
        remote_host_firewall_traversal (AllowBlockControlType0 | None | Unset): A simple control with an allow or block
            action. Re-usable by any data control that only needs a binary allow/block decision.
        end_process_via_task_manager (AllowBlockControlType0 | None | Unset): A simple control with an allow or block
            action. Re-usable by any data control that only needs a binary allow/block decision.
        pdfium (AllowBlockControlType0 | None | Unset): A simple control with an allow or block action. Re-usable by any
            data control that only needs a binary allow/block decision.
        web_gl_api (AllowBlockControlType0 | None | Unset): A simple control with an allow or block action. Re-usable by
            any data control that only needs a binary allow/block decision.
        file_system_api (AllowBlockControlType0 | None | Unset): A simple control with an allow or block action. Re-
            usable by any data control that only needs a binary allow/block decision.
        sensors_api (AllowBlockControlType0 | None | Unset): A simple control with an allow or block action. Re-usable
            by any data control that only needs a binary allow/block decision.
        web_serial_api (AllowBlockControlType0 | None | Unset): A simple control with an allow or block action. Re-
            usable by any data control that only needs a binary allow/block decision.
        web_bluetooth_api (AllowBlockControlType0 | None | Unset): A simple control with an allow or block action. Re-
            usable by any data control that only needs a binary allow/block decision.
        web_usb_api (AllowBlockControlType0 | None | Unset): A simple control with an allow or block action. Re-usable
            by any data control that only needs a binary allow/block decision.
        web_hid_api (AllowBlockControlType0 | None | Unset): A simple control with an allow or block action. Re-usable
            by any data control that only needs a binary allow/block decision.
        quic_protocol (AllowBlockControlType0 | None | Unset): A simple control with an allow or block action. Re-usable
            by any data control that only needs a binary allow/block decision.
        web_clipboard_api (AllowBlockControlType0 | None | Unset): A simple control with an allow or block action. Re-
            usable by any data control that only needs a binary allow/block decision.
        local_fonts (AllowBlockControlType0 | None | Unset): A simple control with an allow or block action. Re-usable
            by any data control that only needs a binary allow/block decision.
        flush_browser_data (FlushBrowserDataControlType0 | None | Unset): Set temporary browser sessions, so browser
            data will be cleaned upon close or time period.
        legacy_password_manager (LegacyPasswordManagerControlType0 | None | Unset): Enable the Prisma Access Browser
            legacy password manager for managing and securing company passwords and secrets.
        hide_sensitive_data_from_extensions (EnableDisableControlType0 | None | Unset): A simple control with an enable
            or disable action. Re-usable by any control that only needs a binary enable/disable decision.
        remote_debugging (AllowBlockControlType0 | None | Unset): A simple control with an allow or block action. Re-
            usable by any data control that only needs a binary allow/block decision.
        internet_explorer_compatibility_mode (InternetExplorerCompatibilityModeControlType0 | None | Unset): Configure
            websites that should open using Internet Explorer compatibility mode.
        launching_external_applications (LaunchingExternalApplicationsControlType0 | None | Unset): Control whether
            external applications may launch from Prisma Browser.
        cookies (CookiesControlType0 | None | Unset): Control the ability to store cookies on the browser.
        local_network_access_restrictions (LocalNetworkAccessRestrictionsControlType0 | None | Unset): Manage website
            access to local network endpoints.
        enhanced_tracking_protection (EnhancedTrackingProtectionControlType0 | None | Unset): Manage tracking protection
            and cross-site tracking.
        force_https (ForceHttpsControlType0 | None | Unset): Force using HTTPS instead of HTTP to reduce the risk of
            MitM attacks and sending sensitive information in cleartext.
        java_script_v8_jit_and_web_assembly (JavaScriptV8JitAndWebAssemblyControlType0 | None | Unset): Block JavaScript
            v8 JIT to reduce exploitation risks and to activate vulnerability mitigation techniques. Block WebAssembly
            (WASM) to reduce exploitation risks.
        restrict_extension_host_permissions (None | RestrictExtensionHostPermissionsControlType0 | Unset): Prevent
            extensions from running scripts and accessing content in websites.
        web_rtc (None | Unset | WebRtcControlType0): Control the use of WebRTC mechanism, which might be exploited.
            Disabling it might impact the usability of websites working with WebRTC functionalities, like call/video
            streaming.
        notifications (None | NotificationsControlType0 | Unset): Control the ability to display notifications in the
            browser.
        popups (None | PopupsControlType0 | Unset): Control the ability to display popups in the browser.
        pages_with_insecure_content (None | PagesWithInsecureContentControlType0 | Unset): Set whether pages with
            insecure content are available.
        kerberos_delegation_allowlist (KerberosDelegationAllowlistControlType0 | None | Unset): List the hosts that may
            forward a user's Kerberos ticket to downstream services.
        authentication_server_allowlist (AuthenticationServerAllowlistControlType0 | None | Unset): List the servers
            allowed to use Integrated Authentication.
        concurrent_number_of_devices (ConcurrentNumberOfDevicesControlType0 | None | Unset): Control the maximum number
            of devices users can be logged into at the same time.
    """

    developer_tools: AllowBlockControlType0 | None | Unset = UNSET
    cast: AllowBlockControlType0 | None | Unset = UNSET
    cookies_protection: EnableDisableControlType0 | None | Unset = UNSET
    browser_history: BrowserHistoryControlType0 | None | Unset = UNSET
    dns_over_https: DnsOverHttpsControlType0 | None | Unset = UNSET
    browser_self_protection: BrowserSelfProtectionControlType0 | None | Unset = UNSET
    keylogging_protection: KeyloggingProtectionControlType0 | None | Unset = UNSET
    browser_lock: BrowserLockControlType0 | None | Unset = UNSET
    authentication_factor: (
        AuthenticationFactorIdentityProviderControl
        | AuthenticationFactorPasskeyControl
        | AuthenticationFactorPinCodeControl
        | None
        | Unset
    ) = UNSET
    session_refresh: None | SessionRefreshControlType0 | Unset = UNSET
    native_messaging_hosts: NativeMessagingHostsControlType0 | None | Unset = UNSET
    allowed_or_blocked_extensions: AllowedOrBlockedExtensionsControlType0 | None | Unset = UNSET
    block_extensions_by_permissions: BlockExtensionsByPermissionsControlType0 | None | Unset = UNSET
    post_quantum_key_security: None | PostQuantumKeySecurityControlType0 | Unset = UNSET
    strict_origin_isolation: EnableDisableControlType0 | None | Unset = UNSET
    advanced_browser_protection: EnableDisableControlType0 | None | Unset = UNSET
    user_data_directory_protection: EnableDisableControlType0 | None | Unset = UNSET
    mobile_password_saving: AllowBlockControlType0 | None | Unset = UNSET
    autofill_of_forms: AllowBlockControlType0 | None | Unset = UNSET
    autofill_of_credit_cards: AllowBlockControlType0 | None | Unset = UNSET
    java_script_running_from_omnibox: AllowBlockControlType0 | None | Unset = UNSET
    pages_with_ssl_errors: AllowBlockControlType0 | None | Unset = UNSET
    basic_authentication_over_http: AllowBlockControlType0 | None | Unset = UNSET
    third_party_cookies: AllowBlockControlType0 | None | Unset = UNSET
    print_preview: AllowBlockControlType0 | None | Unset = UNSET
    google_cloud_print: AllowBlockControlType0 | None | Unset = UNSET
    allowed_printers: AllowedPrintersControlType0 | None | Unset = UNSET
    open_links_in_external_apps: None | OpenLinksInExternalAppsControlType0 | Unset = UNSET
    trusted_certificate_authorities: None | TrustedCertificateAuthoritiesControlType0 | Unset = UNSET
    remote_host_firewall_traversal: AllowBlockControlType0 | None | Unset = UNSET
    end_process_via_task_manager: AllowBlockControlType0 | None | Unset = UNSET
    pdfium: AllowBlockControlType0 | None | Unset = UNSET
    web_gl_api: AllowBlockControlType0 | None | Unset = UNSET
    file_system_api: AllowBlockControlType0 | None | Unset = UNSET
    sensors_api: AllowBlockControlType0 | None | Unset = UNSET
    web_serial_api: AllowBlockControlType0 | None | Unset = UNSET
    web_bluetooth_api: AllowBlockControlType0 | None | Unset = UNSET
    web_usb_api: AllowBlockControlType0 | None | Unset = UNSET
    web_hid_api: AllowBlockControlType0 | None | Unset = UNSET
    quic_protocol: AllowBlockControlType0 | None | Unset = UNSET
    web_clipboard_api: AllowBlockControlType0 | None | Unset = UNSET
    local_fonts: AllowBlockControlType0 | None | Unset = UNSET
    flush_browser_data: FlushBrowserDataControlType0 | None | Unset = UNSET
    legacy_password_manager: LegacyPasswordManagerControlType0 | None | Unset = UNSET
    hide_sensitive_data_from_extensions: EnableDisableControlType0 | None | Unset = UNSET
    remote_debugging: AllowBlockControlType0 | None | Unset = UNSET
    internet_explorer_compatibility_mode: InternetExplorerCompatibilityModeControlType0 | None | Unset = UNSET
    launching_external_applications: LaunchingExternalApplicationsControlType0 | None | Unset = UNSET
    cookies: CookiesControlType0 | None | Unset = UNSET
    local_network_access_restrictions: LocalNetworkAccessRestrictionsControlType0 | None | Unset = UNSET
    enhanced_tracking_protection: EnhancedTrackingProtectionControlType0 | None | Unset = UNSET
    force_https: ForceHttpsControlType0 | None | Unset = UNSET
    java_script_v8_jit_and_web_assembly: JavaScriptV8JitAndWebAssemblyControlType0 | None | Unset = UNSET
    restrict_extension_host_permissions: None | RestrictExtensionHostPermissionsControlType0 | Unset = UNSET
    web_rtc: None | Unset | WebRtcControlType0 = UNSET
    notifications: None | NotificationsControlType0 | Unset = UNSET
    popups: None | PopupsControlType0 | Unset = UNSET
    pages_with_insecure_content: None | PagesWithInsecureContentControlType0 | Unset = UNSET
    kerberos_delegation_allowlist: KerberosDelegationAllowlistControlType0 | None | Unset = UNSET
    authentication_server_allowlist: AuthenticationServerAllowlistControlType0 | None | Unset = UNSET
    concurrent_number_of_devices: ConcurrentNumberOfDevicesControlType0 | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.allow_block_control_type_0 import AllowBlockControlType0
        from ..models.allowed_or_blocked_extensions_control_type_0 import AllowedOrBlockedExtensionsControlType0
        from ..models.allowed_printers_control_type_0 import AllowedPrintersControlType0
        from ..models.authentication_factor_identity_provider_control import AuthenticationFactorIdentityProviderControl
        from ..models.authentication_factor_passkey_control import AuthenticationFactorPasskeyControl
        from ..models.authentication_factor_pin_code_control import AuthenticationFactorPinCodeControl
        from ..models.authentication_server_allowlist_control_type_0 import AuthenticationServerAllowlistControlType0
        from ..models.block_extensions_by_permissions_control_type_0 import BlockExtensionsByPermissionsControlType0
        from ..models.browser_history_control_type_0 import BrowserHistoryControlType0
        from ..models.browser_lock_control_type_0 import BrowserLockControlType0
        from ..models.browser_self_protection_control_type_0 import BrowserSelfProtectionControlType0
        from ..models.concurrent_number_of_devices_control_type_0 import ConcurrentNumberOfDevicesControlType0
        from ..models.cookies_control_type_0 import CookiesControlType0
        from ..models.dns_over_https_control_type_0 import DnsOverHttpsControlType0
        from ..models.enable_disable_control_type_0 import EnableDisableControlType0
        from ..models.enhanced_tracking_protection_control_type_0 import EnhancedTrackingProtectionControlType0
        from ..models.flush_browser_data_control_type_0 import FlushBrowserDataControlType0
        from ..models.force_https_control_type_0 import ForceHttpsControlType0
        from ..models.internet_explorer_compatibility_mode_control_type_0 import (
            InternetExplorerCompatibilityModeControlType0,
        )
        from ..models.java_script_v8_jit_and_web_assembly_control_type_0 import (
            JavaScriptV8JitAndWebAssemblyControlType0,
        )
        from ..models.kerberos_delegation_allowlist_control_type_0 import KerberosDelegationAllowlistControlType0
        from ..models.keylogging_protection_control_type_0 import KeyloggingProtectionControlType0
        from ..models.launching_external_applications_control_type_0 import LaunchingExternalApplicationsControlType0
        from ..models.legacy_password_manager_control_type_0 import LegacyPasswordManagerControlType0
        from ..models.local_network_access_restrictions_control_type_0 import LocalNetworkAccessRestrictionsControlType0
        from ..models.native_messaging_hosts_control_type_0 import NativeMessagingHostsControlType0
        from ..models.notifications_control_type_0 import NotificationsControlType0
        from ..models.open_links_in_external_apps_control_type_0 import OpenLinksInExternalAppsControlType0
        from ..models.pages_with_insecure_content_control_type_0 import PagesWithInsecureContentControlType0
        from ..models.popups_control_type_0 import PopupsControlType0
        from ..models.post_quantum_key_security_control_type_0 import PostQuantumKeySecurityControlType0
        from ..models.restrict_extension_host_permissions_control_type_0 import (
            RestrictExtensionHostPermissionsControlType0,
        )
        from ..models.session_refresh_control_type_0 import SessionRefreshControlType0
        from ..models.trusted_certificate_authorities_control_type_0 import TrustedCertificateAuthoritiesControlType0
        from ..models.web_rtc_control_type_0 import WebRtcControlType0

        developer_tools: dict[str, Any] | None | Unset
        if isinstance(self.developer_tools, Unset):
            developer_tools = UNSET
        elif isinstance(self.developer_tools, AllowBlockControlType0):
            developer_tools = self.developer_tools.to_dict()
        else:
            developer_tools = self.developer_tools

        cast: dict[str, Any] | None | Unset
        if isinstance(self.cast, Unset):
            cast = UNSET
        elif isinstance(self.cast, AllowBlockControlType0):
            cast = self.cast.to_dict()
        else:
            cast = self.cast

        cookies_protection: dict[str, Any] | None | Unset
        if isinstance(self.cookies_protection, Unset):
            cookies_protection = UNSET
        elif isinstance(self.cookies_protection, EnableDisableControlType0):
            cookies_protection = self.cookies_protection.to_dict()
        else:
            cookies_protection = self.cookies_protection

        browser_history: dict[str, Any] | None | Unset
        if isinstance(self.browser_history, Unset):
            browser_history = UNSET
        elif isinstance(self.browser_history, BrowserHistoryControlType0):
            browser_history = self.browser_history.to_dict()
        else:
            browser_history = self.browser_history

        dns_over_https: dict[str, Any] | None | Unset
        if isinstance(self.dns_over_https, Unset):
            dns_over_https = UNSET
        elif isinstance(self.dns_over_https, DnsOverHttpsControlType0):
            dns_over_https = self.dns_over_https.to_dict()
        else:
            dns_over_https = self.dns_over_https

        browser_self_protection: dict[str, Any] | None | Unset
        if isinstance(self.browser_self_protection, Unset):
            browser_self_protection = UNSET
        elif isinstance(self.browser_self_protection, BrowserSelfProtectionControlType0):
            browser_self_protection = self.browser_self_protection.to_dict()
        else:
            browser_self_protection = self.browser_self_protection

        keylogging_protection: dict[str, Any] | None | Unset
        if isinstance(self.keylogging_protection, Unset):
            keylogging_protection = UNSET
        elif isinstance(self.keylogging_protection, KeyloggingProtectionControlType0):
            keylogging_protection = self.keylogging_protection.to_dict()
        else:
            keylogging_protection = self.keylogging_protection

        browser_lock: dict[str, Any] | None | Unset
        if isinstance(self.browser_lock, Unset):
            browser_lock = UNSET
        elif isinstance(self.browser_lock, BrowserLockControlType0):
            browser_lock = self.browser_lock.to_dict()
        else:
            browser_lock = self.browser_lock

        authentication_factor: dict[str, Any] | None | Unset
        if isinstance(self.authentication_factor, Unset):
            authentication_factor = UNSET
        elif isinstance(self.authentication_factor, AuthenticationFactorPinCodeControl):
            authentication_factor = self.authentication_factor.to_dict()
        elif isinstance(self.authentication_factor, AuthenticationFactorPasskeyControl):
            authentication_factor = self.authentication_factor.to_dict()
        elif isinstance(self.authentication_factor, AuthenticationFactorIdentityProviderControl):
            authentication_factor = self.authentication_factor.to_dict()
        else:
            authentication_factor = self.authentication_factor

        session_refresh: dict[str, Any] | None | Unset
        if isinstance(self.session_refresh, Unset):
            session_refresh = UNSET
        elif isinstance(self.session_refresh, SessionRefreshControlType0):
            session_refresh = self.session_refresh.to_dict()
        else:
            session_refresh = self.session_refresh

        native_messaging_hosts: dict[str, Any] | None | Unset
        if isinstance(self.native_messaging_hosts, Unset):
            native_messaging_hosts = UNSET
        elif isinstance(self.native_messaging_hosts, NativeMessagingHostsControlType0):
            native_messaging_hosts = self.native_messaging_hosts.to_dict()
        else:
            native_messaging_hosts = self.native_messaging_hosts

        allowed_or_blocked_extensions: dict[str, Any] | None | Unset
        if isinstance(self.allowed_or_blocked_extensions, Unset):
            allowed_or_blocked_extensions = UNSET
        elif isinstance(self.allowed_or_blocked_extensions, AllowedOrBlockedExtensionsControlType0):
            allowed_or_blocked_extensions = self.allowed_or_blocked_extensions.to_dict()
        else:
            allowed_or_blocked_extensions = self.allowed_or_blocked_extensions

        block_extensions_by_permissions: dict[str, Any] | None | Unset
        if isinstance(self.block_extensions_by_permissions, Unset):
            block_extensions_by_permissions = UNSET
        elif isinstance(self.block_extensions_by_permissions, BlockExtensionsByPermissionsControlType0):
            block_extensions_by_permissions = self.block_extensions_by_permissions.to_dict()
        else:
            block_extensions_by_permissions = self.block_extensions_by_permissions

        post_quantum_key_security: dict[str, Any] | None | Unset
        if isinstance(self.post_quantum_key_security, Unset):
            post_quantum_key_security = UNSET
        elif isinstance(self.post_quantum_key_security, PostQuantumKeySecurityControlType0):
            post_quantum_key_security = self.post_quantum_key_security.to_dict()
        else:
            post_quantum_key_security = self.post_quantum_key_security

        strict_origin_isolation: dict[str, Any] | None | Unset
        if isinstance(self.strict_origin_isolation, Unset):
            strict_origin_isolation = UNSET
        elif isinstance(self.strict_origin_isolation, EnableDisableControlType0):
            strict_origin_isolation = self.strict_origin_isolation.to_dict()
        else:
            strict_origin_isolation = self.strict_origin_isolation

        advanced_browser_protection: dict[str, Any] | None | Unset
        if isinstance(self.advanced_browser_protection, Unset):
            advanced_browser_protection = UNSET
        elif isinstance(self.advanced_browser_protection, EnableDisableControlType0):
            advanced_browser_protection = self.advanced_browser_protection.to_dict()
        else:
            advanced_browser_protection = self.advanced_browser_protection

        user_data_directory_protection: dict[str, Any] | None | Unset
        if isinstance(self.user_data_directory_protection, Unset):
            user_data_directory_protection = UNSET
        elif isinstance(self.user_data_directory_protection, EnableDisableControlType0):
            user_data_directory_protection = self.user_data_directory_protection.to_dict()
        else:
            user_data_directory_protection = self.user_data_directory_protection

        mobile_password_saving: dict[str, Any] | None | Unset
        if isinstance(self.mobile_password_saving, Unset):
            mobile_password_saving = UNSET
        elif isinstance(self.mobile_password_saving, AllowBlockControlType0):
            mobile_password_saving = self.mobile_password_saving.to_dict()
        else:
            mobile_password_saving = self.mobile_password_saving

        autofill_of_forms: dict[str, Any] | None | Unset
        if isinstance(self.autofill_of_forms, Unset):
            autofill_of_forms = UNSET
        elif isinstance(self.autofill_of_forms, AllowBlockControlType0):
            autofill_of_forms = self.autofill_of_forms.to_dict()
        else:
            autofill_of_forms = self.autofill_of_forms

        autofill_of_credit_cards: dict[str, Any] | None | Unset
        if isinstance(self.autofill_of_credit_cards, Unset):
            autofill_of_credit_cards = UNSET
        elif isinstance(self.autofill_of_credit_cards, AllowBlockControlType0):
            autofill_of_credit_cards = self.autofill_of_credit_cards.to_dict()
        else:
            autofill_of_credit_cards = self.autofill_of_credit_cards

        java_script_running_from_omnibox: dict[str, Any] | None | Unset
        if isinstance(self.java_script_running_from_omnibox, Unset):
            java_script_running_from_omnibox = UNSET
        elif isinstance(self.java_script_running_from_omnibox, AllowBlockControlType0):
            java_script_running_from_omnibox = self.java_script_running_from_omnibox.to_dict()
        else:
            java_script_running_from_omnibox = self.java_script_running_from_omnibox

        pages_with_ssl_errors: dict[str, Any] | None | Unset
        if isinstance(self.pages_with_ssl_errors, Unset):
            pages_with_ssl_errors = UNSET
        elif isinstance(self.pages_with_ssl_errors, AllowBlockControlType0):
            pages_with_ssl_errors = self.pages_with_ssl_errors.to_dict()
        else:
            pages_with_ssl_errors = self.pages_with_ssl_errors

        basic_authentication_over_http: dict[str, Any] | None | Unset
        if isinstance(self.basic_authentication_over_http, Unset):
            basic_authentication_over_http = UNSET
        elif isinstance(self.basic_authentication_over_http, AllowBlockControlType0):
            basic_authentication_over_http = self.basic_authentication_over_http.to_dict()
        else:
            basic_authentication_over_http = self.basic_authentication_over_http

        third_party_cookies: dict[str, Any] | None | Unset
        if isinstance(self.third_party_cookies, Unset):
            third_party_cookies = UNSET
        elif isinstance(self.third_party_cookies, AllowBlockControlType0):
            third_party_cookies = self.third_party_cookies.to_dict()
        else:
            third_party_cookies = self.third_party_cookies

        print_preview: dict[str, Any] | None | Unset
        if isinstance(self.print_preview, Unset):
            print_preview = UNSET
        elif isinstance(self.print_preview, AllowBlockControlType0):
            print_preview = self.print_preview.to_dict()
        else:
            print_preview = self.print_preview

        google_cloud_print: dict[str, Any] | None | Unset
        if isinstance(self.google_cloud_print, Unset):
            google_cloud_print = UNSET
        elif isinstance(self.google_cloud_print, AllowBlockControlType0):
            google_cloud_print = self.google_cloud_print.to_dict()
        else:
            google_cloud_print = self.google_cloud_print

        allowed_printers: dict[str, Any] | None | Unset
        if isinstance(self.allowed_printers, Unset):
            allowed_printers = UNSET
        elif isinstance(self.allowed_printers, AllowedPrintersControlType0):
            allowed_printers = self.allowed_printers.to_dict()
        else:
            allowed_printers = self.allowed_printers

        open_links_in_external_apps: dict[str, Any] | None | Unset
        if isinstance(self.open_links_in_external_apps, Unset):
            open_links_in_external_apps = UNSET
        elif isinstance(self.open_links_in_external_apps, OpenLinksInExternalAppsControlType0):
            open_links_in_external_apps = self.open_links_in_external_apps.to_dict()
        else:
            open_links_in_external_apps = self.open_links_in_external_apps

        trusted_certificate_authorities: dict[str, Any] | None | Unset
        if isinstance(self.trusted_certificate_authorities, Unset):
            trusted_certificate_authorities = UNSET
        elif isinstance(self.trusted_certificate_authorities, TrustedCertificateAuthoritiesControlType0):
            trusted_certificate_authorities = self.trusted_certificate_authorities.to_dict()
        else:
            trusted_certificate_authorities = self.trusted_certificate_authorities

        remote_host_firewall_traversal: dict[str, Any] | None | Unset
        if isinstance(self.remote_host_firewall_traversal, Unset):
            remote_host_firewall_traversal = UNSET
        elif isinstance(self.remote_host_firewall_traversal, AllowBlockControlType0):
            remote_host_firewall_traversal = self.remote_host_firewall_traversal.to_dict()
        else:
            remote_host_firewall_traversal = self.remote_host_firewall_traversal

        end_process_via_task_manager: dict[str, Any] | None | Unset
        if isinstance(self.end_process_via_task_manager, Unset):
            end_process_via_task_manager = UNSET
        elif isinstance(self.end_process_via_task_manager, AllowBlockControlType0):
            end_process_via_task_manager = self.end_process_via_task_manager.to_dict()
        else:
            end_process_via_task_manager = self.end_process_via_task_manager

        pdfium: dict[str, Any] | None | Unset
        if isinstance(self.pdfium, Unset):
            pdfium = UNSET
        elif isinstance(self.pdfium, AllowBlockControlType0):
            pdfium = self.pdfium.to_dict()
        else:
            pdfium = self.pdfium

        web_gl_api: dict[str, Any] | None | Unset
        if isinstance(self.web_gl_api, Unset):
            web_gl_api = UNSET
        elif isinstance(self.web_gl_api, AllowBlockControlType0):
            web_gl_api = self.web_gl_api.to_dict()
        else:
            web_gl_api = self.web_gl_api

        file_system_api: dict[str, Any] | None | Unset
        if isinstance(self.file_system_api, Unset):
            file_system_api = UNSET
        elif isinstance(self.file_system_api, AllowBlockControlType0):
            file_system_api = self.file_system_api.to_dict()
        else:
            file_system_api = self.file_system_api

        sensors_api: dict[str, Any] | None | Unset
        if isinstance(self.sensors_api, Unset):
            sensors_api = UNSET
        elif isinstance(self.sensors_api, AllowBlockControlType0):
            sensors_api = self.sensors_api.to_dict()
        else:
            sensors_api = self.sensors_api

        web_serial_api: dict[str, Any] | None | Unset
        if isinstance(self.web_serial_api, Unset):
            web_serial_api = UNSET
        elif isinstance(self.web_serial_api, AllowBlockControlType0):
            web_serial_api = self.web_serial_api.to_dict()
        else:
            web_serial_api = self.web_serial_api

        web_bluetooth_api: dict[str, Any] | None | Unset
        if isinstance(self.web_bluetooth_api, Unset):
            web_bluetooth_api = UNSET
        elif isinstance(self.web_bluetooth_api, AllowBlockControlType0):
            web_bluetooth_api = self.web_bluetooth_api.to_dict()
        else:
            web_bluetooth_api = self.web_bluetooth_api

        web_usb_api: dict[str, Any] | None | Unset
        if isinstance(self.web_usb_api, Unset):
            web_usb_api = UNSET
        elif isinstance(self.web_usb_api, AllowBlockControlType0):
            web_usb_api = self.web_usb_api.to_dict()
        else:
            web_usb_api = self.web_usb_api

        web_hid_api: dict[str, Any] | None | Unset
        if isinstance(self.web_hid_api, Unset):
            web_hid_api = UNSET
        elif isinstance(self.web_hid_api, AllowBlockControlType0):
            web_hid_api = self.web_hid_api.to_dict()
        else:
            web_hid_api = self.web_hid_api

        quic_protocol: dict[str, Any] | None | Unset
        if isinstance(self.quic_protocol, Unset):
            quic_protocol = UNSET
        elif isinstance(self.quic_protocol, AllowBlockControlType0):
            quic_protocol = self.quic_protocol.to_dict()
        else:
            quic_protocol = self.quic_protocol

        web_clipboard_api: dict[str, Any] | None | Unset
        if isinstance(self.web_clipboard_api, Unset):
            web_clipboard_api = UNSET
        elif isinstance(self.web_clipboard_api, AllowBlockControlType0):
            web_clipboard_api = self.web_clipboard_api.to_dict()
        else:
            web_clipboard_api = self.web_clipboard_api

        local_fonts: dict[str, Any] | None | Unset
        if isinstance(self.local_fonts, Unset):
            local_fonts = UNSET
        elif isinstance(self.local_fonts, AllowBlockControlType0):
            local_fonts = self.local_fonts.to_dict()
        else:
            local_fonts = self.local_fonts

        flush_browser_data: dict[str, Any] | None | Unset
        if isinstance(self.flush_browser_data, Unset):
            flush_browser_data = UNSET
        elif isinstance(self.flush_browser_data, FlushBrowserDataControlType0):
            flush_browser_data = self.flush_browser_data.to_dict()
        else:
            flush_browser_data = self.flush_browser_data

        legacy_password_manager: dict[str, Any] | None | Unset
        if isinstance(self.legacy_password_manager, Unset):
            legacy_password_manager = UNSET
        elif isinstance(self.legacy_password_manager, LegacyPasswordManagerControlType0):
            legacy_password_manager = self.legacy_password_manager.to_dict()
        else:
            legacy_password_manager = self.legacy_password_manager

        hide_sensitive_data_from_extensions: dict[str, Any] | None | Unset
        if isinstance(self.hide_sensitive_data_from_extensions, Unset):
            hide_sensitive_data_from_extensions = UNSET
        elif isinstance(self.hide_sensitive_data_from_extensions, EnableDisableControlType0):
            hide_sensitive_data_from_extensions = self.hide_sensitive_data_from_extensions.to_dict()
        else:
            hide_sensitive_data_from_extensions = self.hide_sensitive_data_from_extensions

        remote_debugging: dict[str, Any] | None | Unset
        if isinstance(self.remote_debugging, Unset):
            remote_debugging = UNSET
        elif isinstance(self.remote_debugging, AllowBlockControlType0):
            remote_debugging = self.remote_debugging.to_dict()
        else:
            remote_debugging = self.remote_debugging

        internet_explorer_compatibility_mode: dict[str, Any] | None | Unset
        if isinstance(self.internet_explorer_compatibility_mode, Unset):
            internet_explorer_compatibility_mode = UNSET
        elif isinstance(self.internet_explorer_compatibility_mode, InternetExplorerCompatibilityModeControlType0):
            internet_explorer_compatibility_mode = self.internet_explorer_compatibility_mode.to_dict()
        else:
            internet_explorer_compatibility_mode = self.internet_explorer_compatibility_mode

        launching_external_applications: dict[str, Any] | None | Unset
        if isinstance(self.launching_external_applications, Unset):
            launching_external_applications = UNSET
        elif isinstance(self.launching_external_applications, LaunchingExternalApplicationsControlType0):
            launching_external_applications = self.launching_external_applications.to_dict()
        else:
            launching_external_applications = self.launching_external_applications

        cookies: dict[str, Any] | None | Unset
        if isinstance(self.cookies, Unset):
            cookies = UNSET
        elif isinstance(self.cookies, CookiesControlType0):
            cookies = self.cookies.to_dict()
        else:
            cookies = self.cookies

        local_network_access_restrictions: dict[str, Any] | None | Unset
        if isinstance(self.local_network_access_restrictions, Unset):
            local_network_access_restrictions = UNSET
        elif isinstance(self.local_network_access_restrictions, LocalNetworkAccessRestrictionsControlType0):
            local_network_access_restrictions = self.local_network_access_restrictions.to_dict()
        else:
            local_network_access_restrictions = self.local_network_access_restrictions

        enhanced_tracking_protection: dict[str, Any] | None | Unset
        if isinstance(self.enhanced_tracking_protection, Unset):
            enhanced_tracking_protection = UNSET
        elif isinstance(self.enhanced_tracking_protection, EnhancedTrackingProtectionControlType0):
            enhanced_tracking_protection = self.enhanced_tracking_protection.to_dict()
        else:
            enhanced_tracking_protection = self.enhanced_tracking_protection

        force_https: dict[str, Any] | None | Unset
        if isinstance(self.force_https, Unset):
            force_https = UNSET
        elif isinstance(self.force_https, ForceHttpsControlType0):
            force_https = self.force_https.to_dict()
        else:
            force_https = self.force_https

        java_script_v8_jit_and_web_assembly: dict[str, Any] | None | Unset
        if isinstance(self.java_script_v8_jit_and_web_assembly, Unset):
            java_script_v8_jit_and_web_assembly = UNSET
        elif isinstance(self.java_script_v8_jit_and_web_assembly, JavaScriptV8JitAndWebAssemblyControlType0):
            java_script_v8_jit_and_web_assembly = self.java_script_v8_jit_and_web_assembly.to_dict()
        else:
            java_script_v8_jit_and_web_assembly = self.java_script_v8_jit_and_web_assembly

        restrict_extension_host_permissions: dict[str, Any] | None | Unset
        if isinstance(self.restrict_extension_host_permissions, Unset):
            restrict_extension_host_permissions = UNSET
        elif isinstance(self.restrict_extension_host_permissions, RestrictExtensionHostPermissionsControlType0):
            restrict_extension_host_permissions = self.restrict_extension_host_permissions.to_dict()
        else:
            restrict_extension_host_permissions = self.restrict_extension_host_permissions

        web_rtc: dict[str, Any] | None | Unset
        if isinstance(self.web_rtc, Unset):
            web_rtc = UNSET
        elif isinstance(self.web_rtc, WebRtcControlType0):
            web_rtc = self.web_rtc.to_dict()
        else:
            web_rtc = self.web_rtc

        notifications: dict[str, Any] | None | Unset
        if isinstance(self.notifications, Unset):
            notifications = UNSET
        elif isinstance(self.notifications, NotificationsControlType0):
            notifications = self.notifications.to_dict()
        else:
            notifications = self.notifications

        popups: dict[str, Any] | None | Unset
        if isinstance(self.popups, Unset):
            popups = UNSET
        elif isinstance(self.popups, PopupsControlType0):
            popups = self.popups.to_dict()
        else:
            popups = self.popups

        pages_with_insecure_content: dict[str, Any] | None | Unset
        if isinstance(self.pages_with_insecure_content, Unset):
            pages_with_insecure_content = UNSET
        elif isinstance(self.pages_with_insecure_content, PagesWithInsecureContentControlType0):
            pages_with_insecure_content = self.pages_with_insecure_content.to_dict()
        else:
            pages_with_insecure_content = self.pages_with_insecure_content

        kerberos_delegation_allowlist: dict[str, Any] | None | Unset
        if isinstance(self.kerberos_delegation_allowlist, Unset):
            kerberos_delegation_allowlist = UNSET
        elif isinstance(self.kerberos_delegation_allowlist, KerberosDelegationAllowlistControlType0):
            kerberos_delegation_allowlist = self.kerberos_delegation_allowlist.to_dict()
        else:
            kerberos_delegation_allowlist = self.kerberos_delegation_allowlist

        authentication_server_allowlist: dict[str, Any] | None | Unset
        if isinstance(self.authentication_server_allowlist, Unset):
            authentication_server_allowlist = UNSET
        elif isinstance(self.authentication_server_allowlist, AuthenticationServerAllowlistControlType0):
            authentication_server_allowlist = self.authentication_server_allowlist.to_dict()
        else:
            authentication_server_allowlist = self.authentication_server_allowlist

        concurrent_number_of_devices: dict[str, Any] | None | Unset
        if isinstance(self.concurrent_number_of_devices, Unset):
            concurrent_number_of_devices = UNSET
        elif isinstance(self.concurrent_number_of_devices, ConcurrentNumberOfDevicesControlType0):
            concurrent_number_of_devices = self.concurrent_number_of_devices.to_dict()
        else:
            concurrent_number_of_devices = self.concurrent_number_of_devices

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if developer_tools is not UNSET:
            field_dict["developerTools"] = developer_tools
        if cast is not UNSET:
            field_dict["cast"] = cast
        if cookies_protection is not UNSET:
            field_dict["cookiesProtection"] = cookies_protection
        if browser_history is not UNSET:
            field_dict["browserHistory"] = browser_history
        if dns_over_https is not UNSET:
            field_dict["dnsOverHttps"] = dns_over_https
        if browser_self_protection is not UNSET:
            field_dict["browserSelfProtection"] = browser_self_protection
        if keylogging_protection is not UNSET:
            field_dict["keyloggingProtection"] = keylogging_protection
        if browser_lock is not UNSET:
            field_dict["browserLock"] = browser_lock
        if authentication_factor is not UNSET:
            field_dict["authenticationFactor"] = authentication_factor
        if session_refresh is not UNSET:
            field_dict["sessionRefresh"] = session_refresh
        if native_messaging_hosts is not UNSET:
            field_dict["nativeMessagingHosts"] = native_messaging_hosts
        if allowed_or_blocked_extensions is not UNSET:
            field_dict["allowedOrBlockedExtensions"] = allowed_or_blocked_extensions
        if block_extensions_by_permissions is not UNSET:
            field_dict["blockExtensionsByPermissions"] = block_extensions_by_permissions
        if post_quantum_key_security is not UNSET:
            field_dict["postQuantumKeySecurity"] = post_quantum_key_security
        if strict_origin_isolation is not UNSET:
            field_dict["strictOriginIsolation"] = strict_origin_isolation
        if advanced_browser_protection is not UNSET:
            field_dict["advancedBrowserProtection"] = advanced_browser_protection
        if user_data_directory_protection is not UNSET:
            field_dict["userDataDirectoryProtection"] = user_data_directory_protection
        if mobile_password_saving is not UNSET:
            field_dict["mobilePasswordSaving"] = mobile_password_saving
        if autofill_of_forms is not UNSET:
            field_dict["autofillOfForms"] = autofill_of_forms
        if autofill_of_credit_cards is not UNSET:
            field_dict["autofillOfCreditCards"] = autofill_of_credit_cards
        if java_script_running_from_omnibox is not UNSET:
            field_dict["javaScriptRunningFromOmnibox"] = java_script_running_from_omnibox
        if pages_with_ssl_errors is not UNSET:
            field_dict["pagesWithSslErrors"] = pages_with_ssl_errors
        if basic_authentication_over_http is not UNSET:
            field_dict["basicAuthenticationOverHttp"] = basic_authentication_over_http
        if third_party_cookies is not UNSET:
            field_dict["thirdPartyCookies"] = third_party_cookies
        if print_preview is not UNSET:
            field_dict["printPreview"] = print_preview
        if google_cloud_print is not UNSET:
            field_dict["googleCloudPrint"] = google_cloud_print
        if allowed_printers is not UNSET:
            field_dict["allowedPrinters"] = allowed_printers
        if open_links_in_external_apps is not UNSET:
            field_dict["openLinksInExternalApps"] = open_links_in_external_apps
        if trusted_certificate_authorities is not UNSET:
            field_dict["trustedCertificateAuthorities"] = trusted_certificate_authorities
        if remote_host_firewall_traversal is not UNSET:
            field_dict["remoteHostFirewallTraversal"] = remote_host_firewall_traversal
        if end_process_via_task_manager is not UNSET:
            field_dict["endProcessViaTaskManager"] = end_process_via_task_manager
        if pdfium is not UNSET:
            field_dict["pdfium"] = pdfium
        if web_gl_api is not UNSET:
            field_dict["webGlApi"] = web_gl_api
        if file_system_api is not UNSET:
            field_dict["fileSystemApi"] = file_system_api
        if sensors_api is not UNSET:
            field_dict["sensorsApi"] = sensors_api
        if web_serial_api is not UNSET:
            field_dict["webSerialApi"] = web_serial_api
        if web_bluetooth_api is not UNSET:
            field_dict["webBluetoothApi"] = web_bluetooth_api
        if web_usb_api is not UNSET:
            field_dict["webUsbApi"] = web_usb_api
        if web_hid_api is not UNSET:
            field_dict["webHidApi"] = web_hid_api
        if quic_protocol is not UNSET:
            field_dict["quicProtocol"] = quic_protocol
        if web_clipboard_api is not UNSET:
            field_dict["webClipboardApi"] = web_clipboard_api
        if local_fonts is not UNSET:
            field_dict["localFonts"] = local_fonts
        if flush_browser_data is not UNSET:
            field_dict["flushBrowserData"] = flush_browser_data
        if legacy_password_manager is not UNSET:
            field_dict["legacyPasswordManager"] = legacy_password_manager
        if hide_sensitive_data_from_extensions is not UNSET:
            field_dict["hideSensitiveDataFromExtensions"] = hide_sensitive_data_from_extensions
        if remote_debugging is not UNSET:
            field_dict["remoteDebugging"] = remote_debugging
        if internet_explorer_compatibility_mode is not UNSET:
            field_dict["internetExplorerCompatibilityMode"] = internet_explorer_compatibility_mode
        if launching_external_applications is not UNSET:
            field_dict["launchingExternalApplications"] = launching_external_applications
        if cookies is not UNSET:
            field_dict["cookies"] = cookies
        if local_network_access_restrictions is not UNSET:
            field_dict["localNetworkAccessRestrictions"] = local_network_access_restrictions
        if enhanced_tracking_protection is not UNSET:
            field_dict["enhancedTrackingProtection"] = enhanced_tracking_protection
        if force_https is not UNSET:
            field_dict["forceHttps"] = force_https
        if java_script_v8_jit_and_web_assembly is not UNSET:
            field_dict["javaScriptV8JitAndWebAssembly"] = java_script_v8_jit_and_web_assembly
        if restrict_extension_host_permissions is not UNSET:
            field_dict["restrictExtensionHostPermissions"] = restrict_extension_host_permissions
        if web_rtc is not UNSET:
            field_dict["webRtc"] = web_rtc
        if notifications is not UNSET:
            field_dict["notifications"] = notifications
        if popups is not UNSET:
            field_dict["popups"] = popups
        if pages_with_insecure_content is not UNSET:
            field_dict["pagesWithInsecureContent"] = pages_with_insecure_content
        if kerberos_delegation_allowlist is not UNSET:
            field_dict["kerberosDelegationAllowlist"] = kerberos_delegation_allowlist
        if authentication_server_allowlist is not UNSET:
            field_dict["authenticationServerAllowlist"] = authentication_server_allowlist
        if concurrent_number_of_devices is not UNSET:
            field_dict["concurrentNumberOfDevices"] = concurrent_number_of_devices

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.allow_block_control_type_0 import AllowBlockControlType0
        from ..models.allowed_or_blocked_extensions_control_type_0 import AllowedOrBlockedExtensionsControlType0
        from ..models.allowed_printers_control_type_0 import AllowedPrintersControlType0
        from ..models.authentication_factor_identity_provider_control import AuthenticationFactorIdentityProviderControl
        from ..models.authentication_factor_passkey_control import AuthenticationFactorPasskeyControl
        from ..models.authentication_factor_pin_code_control import AuthenticationFactorPinCodeControl
        from ..models.authentication_server_allowlist_control_type_0 import AuthenticationServerAllowlistControlType0
        from ..models.block_extensions_by_permissions_control_type_0 import BlockExtensionsByPermissionsControlType0
        from ..models.browser_history_control_type_0 import BrowserHistoryControlType0
        from ..models.browser_lock_control_type_0 import BrowserLockControlType0
        from ..models.browser_self_protection_control_type_0 import BrowserSelfProtectionControlType0
        from ..models.concurrent_number_of_devices_control_type_0 import ConcurrentNumberOfDevicesControlType0
        from ..models.cookies_control_type_0 import CookiesControlType0
        from ..models.dns_over_https_control_type_0 import DnsOverHttpsControlType0
        from ..models.enable_disable_control_type_0 import EnableDisableControlType0
        from ..models.enhanced_tracking_protection_control_type_0 import EnhancedTrackingProtectionControlType0
        from ..models.flush_browser_data_control_type_0 import FlushBrowserDataControlType0
        from ..models.force_https_control_type_0 import ForceHttpsControlType0
        from ..models.internet_explorer_compatibility_mode_control_type_0 import (
            InternetExplorerCompatibilityModeControlType0,
        )
        from ..models.java_script_v8_jit_and_web_assembly_control_type_0 import (
            JavaScriptV8JitAndWebAssemblyControlType0,
        )
        from ..models.kerberos_delegation_allowlist_control_type_0 import KerberosDelegationAllowlistControlType0
        from ..models.keylogging_protection_control_type_0 import KeyloggingProtectionControlType0
        from ..models.launching_external_applications_control_type_0 import LaunchingExternalApplicationsControlType0
        from ..models.legacy_password_manager_control_type_0 import LegacyPasswordManagerControlType0
        from ..models.local_network_access_restrictions_control_type_0 import LocalNetworkAccessRestrictionsControlType0
        from ..models.native_messaging_hosts_control_type_0 import NativeMessagingHostsControlType0
        from ..models.notifications_control_type_0 import NotificationsControlType0
        from ..models.open_links_in_external_apps_control_type_0 import OpenLinksInExternalAppsControlType0
        from ..models.pages_with_insecure_content_control_type_0 import PagesWithInsecureContentControlType0
        from ..models.popups_control_type_0 import PopupsControlType0
        from ..models.post_quantum_key_security_control_type_0 import PostQuantumKeySecurityControlType0
        from ..models.restrict_extension_host_permissions_control_type_0 import (
            RestrictExtensionHostPermissionsControlType0,
        )
        from ..models.session_refresh_control_type_0 import SessionRefreshControlType0
        from ..models.trusted_certificate_authorities_control_type_0 import TrustedCertificateAuthoritiesControlType0
        from ..models.web_rtc_control_type_0 import WebRtcControlType0

        d = dict(src_dict)

        def _parse_developer_tools(data: object) -> AllowBlockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allow_block_control_type_0 = AllowBlockControlType0.from_dict(data)

                return componentsschemas_allow_block_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowBlockControlType0 | None | Unset, data)

        developer_tools = _parse_developer_tools(d.pop("developerTools", UNSET))

        def _parse_cast(data: object) -> AllowBlockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allow_block_control_type_0 = AllowBlockControlType0.from_dict(data)

                return componentsschemas_allow_block_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowBlockControlType0 | None | Unset, data)

        cast = _parse_cast(d.pop("cast", UNSET))

        def _parse_cookies_protection(data: object) -> EnableDisableControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_enable_disable_control_type_0 = EnableDisableControlType0.from_dict(data)

                return componentsschemas_enable_disable_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(EnableDisableControlType0 | None | Unset, data)

        cookies_protection = _parse_cookies_protection(d.pop("cookiesProtection", UNSET))

        def _parse_browser_history(data: object) -> BrowserHistoryControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_browser_history_control_type_0 = BrowserHistoryControlType0.from_dict(data)

                return componentsschemas_browser_history_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(BrowserHistoryControlType0 | None | Unset, data)

        browser_history = _parse_browser_history(d.pop("browserHistory", UNSET))

        def _parse_dns_over_https(data: object) -> DnsOverHttpsControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_dns_over_https_control_type_0 = DnsOverHttpsControlType0.from_dict(data)

                return componentsschemas_dns_over_https_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(DnsOverHttpsControlType0 | None | Unset, data)

        dns_over_https = _parse_dns_over_https(d.pop("dnsOverHttps", UNSET))

        def _parse_browser_self_protection(data: object) -> BrowserSelfProtectionControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_browser_self_protection_control_type_0 = BrowserSelfProtectionControlType0.from_dict(
                    data
                )

                return componentsschemas_browser_self_protection_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(BrowserSelfProtectionControlType0 | None | Unset, data)

        browser_self_protection = _parse_browser_self_protection(d.pop("browserSelfProtection", UNSET))

        def _parse_keylogging_protection(data: object) -> KeyloggingProtectionControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_keylogging_protection_control_type_0 = KeyloggingProtectionControlType0.from_dict(
                    data
                )

                return componentsschemas_keylogging_protection_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(KeyloggingProtectionControlType0 | None | Unset, data)

        keylogging_protection = _parse_keylogging_protection(d.pop("keyloggingProtection", UNSET))

        def _parse_browser_lock(data: object) -> BrowserLockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_browser_lock_control_type_0 = BrowserLockControlType0.from_dict(data)

                return componentsschemas_browser_lock_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(BrowserLockControlType0 | None | Unset, data)

        browser_lock = _parse_browser_lock(d.pop("browserLock", UNSET))

        def _parse_authentication_factor(
            data: object,
        ) -> (
            AuthenticationFactorIdentityProviderControl
            | AuthenticationFactorPasskeyControl
            | AuthenticationFactorPinCodeControl
            | None
            | Unset
        ):
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_authentication_factor_control_type_0 = AuthenticationFactorPinCodeControl.from_dict(
                    data
                )

                return componentsschemas_authentication_factor_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_authentication_factor_control_type_1 = AuthenticationFactorPasskeyControl.from_dict(
                    data
                )

                return componentsschemas_authentication_factor_control_type_1
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_authentication_factor_control_type_2 = (
                    AuthenticationFactorIdentityProviderControl.from_dict(data)
                )

                return componentsschemas_authentication_factor_control_type_2
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(
                AuthenticationFactorIdentityProviderControl
                | AuthenticationFactorPasskeyControl
                | AuthenticationFactorPinCodeControl
                | None
                | Unset,
                data,
            )

        authentication_factor = _parse_authentication_factor(d.pop("authenticationFactor", UNSET))

        def _parse_session_refresh(data: object) -> None | SessionRefreshControlType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_session_refresh_control_type_0 = SessionRefreshControlType0.from_dict(data)

                return componentsschemas_session_refresh_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(None | SessionRefreshControlType0 | Unset, data)

        session_refresh = _parse_session_refresh(d.pop("sessionRefresh", UNSET))

        def _parse_native_messaging_hosts(data: object) -> NativeMessagingHostsControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_native_messaging_hosts_control_type_0 = NativeMessagingHostsControlType0.from_dict(
                    data
                )

                return componentsschemas_native_messaging_hosts_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(NativeMessagingHostsControlType0 | None | Unset, data)

        native_messaging_hosts = _parse_native_messaging_hosts(d.pop("nativeMessagingHosts", UNSET))

        def _parse_allowed_or_blocked_extensions(data: object) -> AllowedOrBlockedExtensionsControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allowed_or_blocked_extensions_control_type_0 = (
                    AllowedOrBlockedExtensionsControlType0.from_dict(data)
                )

                return componentsschemas_allowed_or_blocked_extensions_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowedOrBlockedExtensionsControlType0 | None | Unset, data)

        allowed_or_blocked_extensions = _parse_allowed_or_blocked_extensions(d.pop("allowedOrBlockedExtensions", UNSET))

        def _parse_block_extensions_by_permissions(
            data: object,
        ) -> BlockExtensionsByPermissionsControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_block_extensions_by_permissions_control_type_0 = (
                    BlockExtensionsByPermissionsControlType0.from_dict(data)
                )

                return componentsschemas_block_extensions_by_permissions_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(BlockExtensionsByPermissionsControlType0 | None | Unset, data)

        block_extensions_by_permissions = _parse_block_extensions_by_permissions(
            d.pop("blockExtensionsByPermissions", UNSET)
        )

        def _parse_post_quantum_key_security(data: object) -> None | PostQuantumKeySecurityControlType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_post_quantum_key_security_control_type_0 = (
                    PostQuantumKeySecurityControlType0.from_dict(data)
                )

                return componentsschemas_post_quantum_key_security_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(None | PostQuantumKeySecurityControlType0 | Unset, data)

        post_quantum_key_security = _parse_post_quantum_key_security(d.pop("postQuantumKeySecurity", UNSET))

        def _parse_strict_origin_isolation(data: object) -> EnableDisableControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_enable_disable_control_type_0 = EnableDisableControlType0.from_dict(data)

                return componentsschemas_enable_disable_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(EnableDisableControlType0 | None | Unset, data)

        strict_origin_isolation = _parse_strict_origin_isolation(d.pop("strictOriginIsolation", UNSET))

        def _parse_advanced_browser_protection(data: object) -> EnableDisableControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_enable_disable_control_type_0 = EnableDisableControlType0.from_dict(data)

                return componentsschemas_enable_disable_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(EnableDisableControlType0 | None | Unset, data)

        advanced_browser_protection = _parse_advanced_browser_protection(d.pop("advancedBrowserProtection", UNSET))

        def _parse_user_data_directory_protection(data: object) -> EnableDisableControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_enable_disable_control_type_0 = EnableDisableControlType0.from_dict(data)

                return componentsschemas_enable_disable_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(EnableDisableControlType0 | None | Unset, data)

        user_data_directory_protection = _parse_user_data_directory_protection(
            d.pop("userDataDirectoryProtection", UNSET)
        )

        def _parse_mobile_password_saving(data: object) -> AllowBlockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allow_block_control_type_0 = AllowBlockControlType0.from_dict(data)

                return componentsschemas_allow_block_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowBlockControlType0 | None | Unset, data)

        mobile_password_saving = _parse_mobile_password_saving(d.pop("mobilePasswordSaving", UNSET))

        def _parse_autofill_of_forms(data: object) -> AllowBlockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allow_block_control_type_0 = AllowBlockControlType0.from_dict(data)

                return componentsschemas_allow_block_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowBlockControlType0 | None | Unset, data)

        autofill_of_forms = _parse_autofill_of_forms(d.pop("autofillOfForms", UNSET))

        def _parse_autofill_of_credit_cards(data: object) -> AllowBlockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allow_block_control_type_0 = AllowBlockControlType0.from_dict(data)

                return componentsschemas_allow_block_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowBlockControlType0 | None | Unset, data)

        autofill_of_credit_cards = _parse_autofill_of_credit_cards(d.pop("autofillOfCreditCards", UNSET))

        def _parse_java_script_running_from_omnibox(data: object) -> AllowBlockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allow_block_control_type_0 = AllowBlockControlType0.from_dict(data)

                return componentsschemas_allow_block_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowBlockControlType0 | None | Unset, data)

        java_script_running_from_omnibox = _parse_java_script_running_from_omnibox(
            d.pop("javaScriptRunningFromOmnibox", UNSET)
        )

        def _parse_pages_with_ssl_errors(data: object) -> AllowBlockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allow_block_control_type_0 = AllowBlockControlType0.from_dict(data)

                return componentsschemas_allow_block_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowBlockControlType0 | None | Unset, data)

        pages_with_ssl_errors = _parse_pages_with_ssl_errors(d.pop("pagesWithSslErrors", UNSET))

        def _parse_basic_authentication_over_http(data: object) -> AllowBlockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allow_block_control_type_0 = AllowBlockControlType0.from_dict(data)

                return componentsschemas_allow_block_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowBlockControlType0 | None | Unset, data)

        basic_authentication_over_http = _parse_basic_authentication_over_http(
            d.pop("basicAuthenticationOverHttp", UNSET)
        )

        def _parse_third_party_cookies(data: object) -> AllowBlockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allow_block_control_type_0 = AllowBlockControlType0.from_dict(data)

                return componentsschemas_allow_block_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowBlockControlType0 | None | Unset, data)

        third_party_cookies = _parse_third_party_cookies(d.pop("thirdPartyCookies", UNSET))

        def _parse_print_preview(data: object) -> AllowBlockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allow_block_control_type_0 = AllowBlockControlType0.from_dict(data)

                return componentsschemas_allow_block_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowBlockControlType0 | None | Unset, data)

        print_preview = _parse_print_preview(d.pop("printPreview", UNSET))

        def _parse_google_cloud_print(data: object) -> AllowBlockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allow_block_control_type_0 = AllowBlockControlType0.from_dict(data)

                return componentsschemas_allow_block_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowBlockControlType0 | None | Unset, data)

        google_cloud_print = _parse_google_cloud_print(d.pop("googleCloudPrint", UNSET))

        def _parse_allowed_printers(data: object) -> AllowedPrintersControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allowed_printers_control_type_0 = AllowedPrintersControlType0.from_dict(data)

                return componentsschemas_allowed_printers_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowedPrintersControlType0 | None | Unset, data)

        allowed_printers = _parse_allowed_printers(d.pop("allowedPrinters", UNSET))

        def _parse_open_links_in_external_apps(data: object) -> None | OpenLinksInExternalAppsControlType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_open_links_in_external_apps_control_type_0 = (
                    OpenLinksInExternalAppsControlType0.from_dict(data)
                )

                return componentsschemas_open_links_in_external_apps_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(None | OpenLinksInExternalAppsControlType0 | Unset, data)

        open_links_in_external_apps = _parse_open_links_in_external_apps(d.pop("openLinksInExternalApps", UNSET))

        def _parse_trusted_certificate_authorities(
            data: object,
        ) -> None | TrustedCertificateAuthoritiesControlType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_trusted_certificate_authorities_control_type_0 = (
                    TrustedCertificateAuthoritiesControlType0.from_dict(data)
                )

                return componentsschemas_trusted_certificate_authorities_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(None | TrustedCertificateAuthoritiesControlType0 | Unset, data)

        trusted_certificate_authorities = _parse_trusted_certificate_authorities(
            d.pop("trustedCertificateAuthorities", UNSET)
        )

        def _parse_remote_host_firewall_traversal(data: object) -> AllowBlockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allow_block_control_type_0 = AllowBlockControlType0.from_dict(data)

                return componentsschemas_allow_block_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowBlockControlType0 | None | Unset, data)

        remote_host_firewall_traversal = _parse_remote_host_firewall_traversal(
            d.pop("remoteHostFirewallTraversal", UNSET)
        )

        def _parse_end_process_via_task_manager(data: object) -> AllowBlockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allow_block_control_type_0 = AllowBlockControlType0.from_dict(data)

                return componentsschemas_allow_block_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowBlockControlType0 | None | Unset, data)

        end_process_via_task_manager = _parse_end_process_via_task_manager(d.pop("endProcessViaTaskManager", UNSET))

        def _parse_pdfium(data: object) -> AllowBlockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allow_block_control_type_0 = AllowBlockControlType0.from_dict(data)

                return componentsschemas_allow_block_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowBlockControlType0 | None | Unset, data)

        pdfium = _parse_pdfium(d.pop("pdfium", UNSET))

        def _parse_web_gl_api(data: object) -> AllowBlockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allow_block_control_type_0 = AllowBlockControlType0.from_dict(data)

                return componentsschemas_allow_block_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowBlockControlType0 | None | Unset, data)

        web_gl_api = _parse_web_gl_api(d.pop("webGlApi", UNSET))

        def _parse_file_system_api(data: object) -> AllowBlockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allow_block_control_type_0 = AllowBlockControlType0.from_dict(data)

                return componentsschemas_allow_block_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowBlockControlType0 | None | Unset, data)

        file_system_api = _parse_file_system_api(d.pop("fileSystemApi", UNSET))

        def _parse_sensors_api(data: object) -> AllowBlockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allow_block_control_type_0 = AllowBlockControlType0.from_dict(data)

                return componentsschemas_allow_block_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowBlockControlType0 | None | Unset, data)

        sensors_api = _parse_sensors_api(d.pop("sensorsApi", UNSET))

        def _parse_web_serial_api(data: object) -> AllowBlockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allow_block_control_type_0 = AllowBlockControlType0.from_dict(data)

                return componentsschemas_allow_block_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowBlockControlType0 | None | Unset, data)

        web_serial_api = _parse_web_serial_api(d.pop("webSerialApi", UNSET))

        def _parse_web_bluetooth_api(data: object) -> AllowBlockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allow_block_control_type_0 = AllowBlockControlType0.from_dict(data)

                return componentsschemas_allow_block_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowBlockControlType0 | None | Unset, data)

        web_bluetooth_api = _parse_web_bluetooth_api(d.pop("webBluetoothApi", UNSET))

        def _parse_web_usb_api(data: object) -> AllowBlockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allow_block_control_type_0 = AllowBlockControlType0.from_dict(data)

                return componentsschemas_allow_block_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowBlockControlType0 | None | Unset, data)

        web_usb_api = _parse_web_usb_api(d.pop("webUsbApi", UNSET))

        def _parse_web_hid_api(data: object) -> AllowBlockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allow_block_control_type_0 = AllowBlockControlType0.from_dict(data)

                return componentsschemas_allow_block_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowBlockControlType0 | None | Unset, data)

        web_hid_api = _parse_web_hid_api(d.pop("webHidApi", UNSET))

        def _parse_quic_protocol(data: object) -> AllowBlockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allow_block_control_type_0 = AllowBlockControlType0.from_dict(data)

                return componentsschemas_allow_block_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowBlockControlType0 | None | Unset, data)

        quic_protocol = _parse_quic_protocol(d.pop("quicProtocol", UNSET))

        def _parse_web_clipboard_api(data: object) -> AllowBlockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allow_block_control_type_0 = AllowBlockControlType0.from_dict(data)

                return componentsschemas_allow_block_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowBlockControlType0 | None | Unset, data)

        web_clipboard_api = _parse_web_clipboard_api(d.pop("webClipboardApi", UNSET))

        def _parse_local_fonts(data: object) -> AllowBlockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allow_block_control_type_0 = AllowBlockControlType0.from_dict(data)

                return componentsschemas_allow_block_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowBlockControlType0 | None | Unset, data)

        local_fonts = _parse_local_fonts(d.pop("localFonts", UNSET))

        def _parse_flush_browser_data(data: object) -> FlushBrowserDataControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_flush_browser_data_control_type_0 = FlushBrowserDataControlType0.from_dict(data)

                return componentsschemas_flush_browser_data_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(FlushBrowserDataControlType0 | None | Unset, data)

        flush_browser_data = _parse_flush_browser_data(d.pop("flushBrowserData", UNSET))

        def _parse_legacy_password_manager(data: object) -> LegacyPasswordManagerControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_legacy_password_manager_control_type_0 = LegacyPasswordManagerControlType0.from_dict(
                    data
                )

                return componentsschemas_legacy_password_manager_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(LegacyPasswordManagerControlType0 | None | Unset, data)

        legacy_password_manager = _parse_legacy_password_manager(d.pop("legacyPasswordManager", UNSET))

        def _parse_hide_sensitive_data_from_extensions(data: object) -> EnableDisableControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_enable_disable_control_type_0 = EnableDisableControlType0.from_dict(data)

                return componentsschemas_enable_disable_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(EnableDisableControlType0 | None | Unset, data)

        hide_sensitive_data_from_extensions = _parse_hide_sensitive_data_from_extensions(
            d.pop("hideSensitiveDataFromExtensions", UNSET)
        )

        def _parse_remote_debugging(data: object) -> AllowBlockControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_allow_block_control_type_0 = AllowBlockControlType0.from_dict(data)

                return componentsschemas_allow_block_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AllowBlockControlType0 | None | Unset, data)

        remote_debugging = _parse_remote_debugging(d.pop("remoteDebugging", UNSET))

        def _parse_internet_explorer_compatibility_mode(
            data: object,
        ) -> InternetExplorerCompatibilityModeControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_internet_explorer_compatibility_mode_control_type_0 = (
                    InternetExplorerCompatibilityModeControlType0.from_dict(data)
                )

                return componentsschemas_internet_explorer_compatibility_mode_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(InternetExplorerCompatibilityModeControlType0 | None | Unset, data)

        internet_explorer_compatibility_mode = _parse_internet_explorer_compatibility_mode(
            d.pop("internetExplorerCompatibilityMode", UNSET)
        )

        def _parse_launching_external_applications(
            data: object,
        ) -> LaunchingExternalApplicationsControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_launching_external_applications_control_type_0 = (
                    LaunchingExternalApplicationsControlType0.from_dict(data)
                )

                return componentsschemas_launching_external_applications_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(LaunchingExternalApplicationsControlType0 | None | Unset, data)

        launching_external_applications = _parse_launching_external_applications(
            d.pop("launchingExternalApplications", UNSET)
        )

        def _parse_cookies(data: object) -> CookiesControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_cookies_control_type_0 = CookiesControlType0.from_dict(data)

                return componentsschemas_cookies_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(CookiesControlType0 | None | Unset, data)

        cookies = _parse_cookies(d.pop("cookies", UNSET))

        def _parse_local_network_access_restrictions(
            data: object,
        ) -> LocalNetworkAccessRestrictionsControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_local_network_access_restrictions_control_type_0 = (
                    LocalNetworkAccessRestrictionsControlType0.from_dict(data)
                )

                return componentsschemas_local_network_access_restrictions_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(LocalNetworkAccessRestrictionsControlType0 | None | Unset, data)

        local_network_access_restrictions = _parse_local_network_access_restrictions(
            d.pop("localNetworkAccessRestrictions", UNSET)
        )

        def _parse_enhanced_tracking_protection(data: object) -> EnhancedTrackingProtectionControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_enhanced_tracking_protection_control_type_0 = (
                    EnhancedTrackingProtectionControlType0.from_dict(data)
                )

                return componentsschemas_enhanced_tracking_protection_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(EnhancedTrackingProtectionControlType0 | None | Unset, data)

        enhanced_tracking_protection = _parse_enhanced_tracking_protection(d.pop("enhancedTrackingProtection", UNSET))

        def _parse_force_https(data: object) -> ForceHttpsControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_force_https_control_type_0 = ForceHttpsControlType0.from_dict(data)

                return componentsschemas_force_https_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(ForceHttpsControlType0 | None | Unset, data)

        force_https = _parse_force_https(d.pop("forceHttps", UNSET))

        def _parse_java_script_v8_jit_and_web_assembly(
            data: object,
        ) -> JavaScriptV8JitAndWebAssemblyControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_java_script_v8_jit_and_web_assembly_control_type_0 = (
                    JavaScriptV8JitAndWebAssemblyControlType0.from_dict(data)
                )

                return componentsschemas_java_script_v8_jit_and_web_assembly_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(JavaScriptV8JitAndWebAssemblyControlType0 | None | Unset, data)

        java_script_v8_jit_and_web_assembly = _parse_java_script_v8_jit_and_web_assembly(
            d.pop("javaScriptV8JitAndWebAssembly", UNSET)
        )

        def _parse_restrict_extension_host_permissions(
            data: object,
        ) -> None | RestrictExtensionHostPermissionsControlType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_restrict_extension_host_permissions_control_type_0 = (
                    RestrictExtensionHostPermissionsControlType0.from_dict(data)
                )

                return componentsschemas_restrict_extension_host_permissions_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(None | RestrictExtensionHostPermissionsControlType0 | Unset, data)

        restrict_extension_host_permissions = _parse_restrict_extension_host_permissions(
            d.pop("restrictExtensionHostPermissions", UNSET)
        )

        def _parse_web_rtc(data: object) -> None | Unset | WebRtcControlType0:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_web_rtc_control_type_0 = WebRtcControlType0.from_dict(data)

                return componentsschemas_web_rtc_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(None | Unset | WebRtcControlType0, data)

        web_rtc = _parse_web_rtc(d.pop("webRtc", UNSET))

        def _parse_notifications(data: object) -> None | NotificationsControlType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_notifications_control_type_0 = NotificationsControlType0.from_dict(data)

                return componentsschemas_notifications_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(None | NotificationsControlType0 | Unset, data)

        notifications = _parse_notifications(d.pop("notifications", UNSET))

        def _parse_popups(data: object) -> None | PopupsControlType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_popups_control_type_0 = PopupsControlType0.from_dict(data)

                return componentsschemas_popups_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(None | PopupsControlType0 | Unset, data)

        popups = _parse_popups(d.pop("popups", UNSET))

        def _parse_pages_with_insecure_content(data: object) -> None | PagesWithInsecureContentControlType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_pages_with_insecure_content_control_type_0 = (
                    PagesWithInsecureContentControlType0.from_dict(data)
                )

                return componentsschemas_pages_with_insecure_content_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(None | PagesWithInsecureContentControlType0 | Unset, data)

        pages_with_insecure_content = _parse_pages_with_insecure_content(d.pop("pagesWithInsecureContent", UNSET))

        def _parse_kerberos_delegation_allowlist(
            data: object,
        ) -> KerberosDelegationAllowlistControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_kerberos_delegation_allowlist_control_type_0 = (
                    KerberosDelegationAllowlistControlType0.from_dict(data)
                )

                return componentsschemas_kerberos_delegation_allowlist_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(KerberosDelegationAllowlistControlType0 | None | Unset, data)

        kerberos_delegation_allowlist = _parse_kerberos_delegation_allowlist(
            d.pop("kerberosDelegationAllowlist", UNSET)
        )

        def _parse_authentication_server_allowlist(
            data: object,
        ) -> AuthenticationServerAllowlistControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_authentication_server_allowlist_control_type_0 = (
                    AuthenticationServerAllowlistControlType0.from_dict(data)
                )

                return componentsschemas_authentication_server_allowlist_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(AuthenticationServerAllowlistControlType0 | None | Unset, data)

        authentication_server_allowlist = _parse_authentication_server_allowlist(
            d.pop("authenticationServerAllowlist", UNSET)
        )

        def _parse_concurrent_number_of_devices(data: object) -> ConcurrentNumberOfDevicesControlType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_concurrent_number_of_devices_control_type_0 = (
                    ConcurrentNumberOfDevicesControlType0.from_dict(data)
                )

                return componentsschemas_concurrent_number_of_devices_control_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return _typing_cast(ConcurrentNumberOfDevicesControlType0 | None | Unset, data)

        concurrent_number_of_devices = _parse_concurrent_number_of_devices(d.pop("concurrentNumberOfDevices", UNSET))

        security_controls = cls(
            developer_tools=developer_tools,
            cast=cast,
            cookies_protection=cookies_protection,
            browser_history=browser_history,
            dns_over_https=dns_over_https,
            browser_self_protection=browser_self_protection,
            keylogging_protection=keylogging_protection,
            browser_lock=browser_lock,
            authentication_factor=authentication_factor,
            session_refresh=session_refresh,
            native_messaging_hosts=native_messaging_hosts,
            allowed_or_blocked_extensions=allowed_or_blocked_extensions,
            block_extensions_by_permissions=block_extensions_by_permissions,
            post_quantum_key_security=post_quantum_key_security,
            strict_origin_isolation=strict_origin_isolation,
            advanced_browser_protection=advanced_browser_protection,
            user_data_directory_protection=user_data_directory_protection,
            mobile_password_saving=mobile_password_saving,
            autofill_of_forms=autofill_of_forms,
            autofill_of_credit_cards=autofill_of_credit_cards,
            java_script_running_from_omnibox=java_script_running_from_omnibox,
            pages_with_ssl_errors=pages_with_ssl_errors,
            basic_authentication_over_http=basic_authentication_over_http,
            third_party_cookies=third_party_cookies,
            print_preview=print_preview,
            google_cloud_print=google_cloud_print,
            allowed_printers=allowed_printers,
            open_links_in_external_apps=open_links_in_external_apps,
            trusted_certificate_authorities=trusted_certificate_authorities,
            remote_host_firewall_traversal=remote_host_firewall_traversal,
            end_process_via_task_manager=end_process_via_task_manager,
            pdfium=pdfium,
            web_gl_api=web_gl_api,
            file_system_api=file_system_api,
            sensors_api=sensors_api,
            web_serial_api=web_serial_api,
            web_bluetooth_api=web_bluetooth_api,
            web_usb_api=web_usb_api,
            web_hid_api=web_hid_api,
            quic_protocol=quic_protocol,
            web_clipboard_api=web_clipboard_api,
            local_fonts=local_fonts,
            flush_browser_data=flush_browser_data,
            legacy_password_manager=legacy_password_manager,
            hide_sensitive_data_from_extensions=hide_sensitive_data_from_extensions,
            remote_debugging=remote_debugging,
            internet_explorer_compatibility_mode=internet_explorer_compatibility_mode,
            launching_external_applications=launching_external_applications,
            cookies=cookies,
            local_network_access_restrictions=local_network_access_restrictions,
            enhanced_tracking_protection=enhanced_tracking_protection,
            force_https=force_https,
            java_script_v8_jit_and_web_assembly=java_script_v8_jit_and_web_assembly,
            restrict_extension_host_permissions=restrict_extension_host_permissions,
            web_rtc=web_rtc,
            notifications=notifications,
            popups=popups,
            pages_with_insecure_content=pages_with_insecure_content,
            kerberos_delegation_allowlist=kerberos_delegation_allowlist,
            authentication_server_allowlist=authentication_server_allowlist,
            concurrent_number_of_devices=concurrent_number_of_devices,
        )

        return security_controls
