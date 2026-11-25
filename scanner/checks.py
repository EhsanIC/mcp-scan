import re
import unicodedata
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


_WHITESPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Fold a description into a comparable form: NFKC, straight quotes, single spaces, casefolded."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    return _WHITESPACE.sub(" ", text).casefold()


def missing_description(tool: Any) -> Finding | None:
    """Flag a tool whose description is empty or absent."""
    if not (tool.description or "").strip():
        return Finding(SEVERITY_LEVEL.MEDIUM, tool.name, "no description")
    return None


# Phrases are stored already normalized (lowercase, single spaces).
INJECTION_PHRASES = (
    (SEVERITY_LEVEL.HIGH,   "ignore previous instructions"),
    (SEVERITY_LEVEL.HIGH,   "ignore all previous instructions"),
    (SEVERITY_LEVEL.HIGH,   "disregard previous instructions"),
    (SEVERITY_LEVEL.HIGH,   "forget previous instructions"),
    (SEVERITY_LEVEL.HIGH,   "do not tell the user"),
    (SEVERITY_LEVEL.HIGH,   "don't tell the user"),
    (SEVERITY_LEVEL.HIGH,   "without telling the user"),
    (SEVERITY_LEVEL.HIGH,   "hide this from the user"),
    (SEVERITY_LEVEL.MEDIUM, "you are now"),
    (SEVERITY_LEVEL.MEDIUM, "new instructions:"),
    (SEVERITY_LEVEL.MEDIUM, "system prompt"),
    (SEVERITY_LEVEL.MEDIUM, "<secret>"),
)


def injection_phrases(tool: Any) -> Finding | None:
    """Flag prompt-injection wording in a tool description."""
    text = normalize(tool.description or "")
    if not text:
        return None

    hits = [(severity, phrase) for severity, phrase in INJECTION_PHRASES if phrase in text]
    if not hits:
        return None

    severity = min((hit_severity for hit_severity, _ in hits), key=lambda level: level.value)
    phrases = ", ".join(f'"{phrase}"' for _, phrase in hits)
    return Finding(severity, tool.name, f"injection phrase(s): {phrases}")


# Every check takes one tool and returns a Finding or None.
CHECKS = (missing_description, injection_phrases)


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
