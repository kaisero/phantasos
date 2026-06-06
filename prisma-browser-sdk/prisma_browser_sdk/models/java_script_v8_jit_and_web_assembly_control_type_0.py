from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..models.java_script_v8_jit_and_web_assembly_control_type_0_action import (
    JavaScriptV8JitAndWebAssemblyControlType0Action,
)
from ..types import UNSET, Unset

T = TypeVar("T", bound="JavaScriptV8JitAndWebAssemblyControlType0")


@_attrs_define
class JavaScriptV8JitAndWebAssemblyControlType0:
    """Block JavaScript v8 JIT to reduce exploitation risks and to activate vulnerability mitigation techniques. Block
    WebAssembly (WASM) to reduce exploitation risks.

        Attributes:
            action (JavaScriptV8JitAndWebAssemblyControlType0Action): JavaScript v8 JIT and WebAssembly protection level.
            excluded_domains (list[str] | Unset): Domains excluded from the restriction.
    """

    action: JavaScriptV8JitAndWebAssemblyControlType0Action
    excluded_domains: list[str] | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        action = self.action.value

        excluded_domains: list[str] | Unset = UNSET
        if not isinstance(self.excluded_domains, Unset):
            excluded_domains = self.excluded_domains

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "action": action,
            }
        )
        if excluded_domains is not UNSET:
            field_dict["excludedDomains"] = excluded_domains

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = JavaScriptV8JitAndWebAssemblyControlType0Action(d.pop("action"))

        excluded_domains = cast(list[str], d.pop("excludedDomains", UNSET))

        java_script_v8_jit_and_web_assembly_control_type_0 = cls(
            action=action,
            excluded_domains=excluded_domains,
        )

        return java_script_v8_jit_and_web_assembly_control_type_0
