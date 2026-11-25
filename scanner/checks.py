from dataclasses import dataclass
from enum import Enum
from typing import Any


class SEVERITY_LEVEL(Enum):
    CRITICAL = 0
    HIGH     = 1
    MEDIUM   = 2
    LOW      = 3


@dataclass(frozen=True)
class Finding:
    severity  : SEVERITY_LEVEL
    tool_name : str
    message   : str

    def __str__(self) -> str:
        return f"[{self.severity.name}] {self.tool_name}: {self.message}"


def missing_description(tool: Any) -> Finding | None:
    """Flag a tool whose description is empty or absent."""
    if not (tool.description or "").strip():
        return Finding(SEVERITY_LEVEL.MEDIUM, tool.name, "no description")
    return None


# Every check takes one tool and returns a Finding or None.
CHECKS = (missing_description,)


def run_test(tools: Any) -> list[Finding]:
    """Run all checks over the tools from tools/list and return the findings."""
    findings: list[Finding] = []
    for tool in tools.tools:
        for check in CHECKS:
            finding = check(tool)
            if finding is not None:
                findings.append(finding)
    findings.sort(key=lambda f: f.severity.value)
    return findings

# missing description, injection phrases, risky parameters