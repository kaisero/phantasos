from enum import Enum


class JavaScriptV8JitAndWebAssemblyControlType0Action(str, Enum):
    DISABLEADVANCEDOPTIMIZATIONS = "disableAdvancedOptimizations"
    DISABLEJITANDWEBASSEMBLY = "disableJitAndWebAssembly"
    ENABLE = "enable"

    def __str__(self) -> str:
        return str(self.value)
