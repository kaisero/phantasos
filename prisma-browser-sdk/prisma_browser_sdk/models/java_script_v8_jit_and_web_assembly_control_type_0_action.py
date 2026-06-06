from .._lenient import LenientStrEnum


class JavaScriptV8JitAndWebAssemblyControlType0Action(LenientStrEnum):
    DISABLEADVANCEDOPTIMIZATIONS = "disableAdvancedOptimizations"
    DISABLEJITANDWEBASSEMBLY = "disableJitAndWebAssembly"
    ENABLE = "enable"

    def __str__(self) -> str:
        return str(self.value)
