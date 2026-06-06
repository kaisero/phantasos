from enum import Enum


class RegistryValueType(str, Enum):
    BINARY = "Binary"
    DWORD = "DWORD"
    EXPANDABLESTRING = "ExpandableString"
    MULTISTRING = "MultiString"
    QWORD = "QWORD"
    STRING = "String"

    def __str__(self) -> str:
        return str(self.value)
