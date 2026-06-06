from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..models.post_quantum_key_security_control_type_0_action import PostQuantumKeySecurityControlType0Action

T = TypeVar("T", bound="PostQuantumKeySecurityControlType0")


@_attrs_define
class PostQuantumKeySecurityControlType0:
    """Control whether to offer a post-quantum key agreement algorithm in TLS.

    Attributes:
        action (PostQuantumKeySecurityControlType0Action): Post Quantum Key Security action.
    """

    action: PostQuantumKeySecurityControlType0Action

    def to_dict(self) -> dict[str, Any]:
        action = self.action.value

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "action": action,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = PostQuantumKeySecurityControlType0Action(d.pop("action"))

        post_quantum_key_security_control_type_0 = cls(
            action=action,
        )

        return post_quantum_key_security_control_type_0
