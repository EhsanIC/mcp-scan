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


DANGEROUS_PARAMETERS = {
    # execution / query power
    "command": SEVERITY_LEVEL.HIGH,
    "cmd": SEVERITY_LEVEL.HIGH,
    "shell": SEVERITY_LEVEL.HIGH,
    "exec": SEVERITY_LEVEL.HIGH,
    "execute": SEVERITY_LEVEL.HIGH,
    "eval": SEVERITY_LEVEL.HIGH,
    "script": SEVERITY_LEVEL.HIGH,
    "sql": SEVERITY_LEVEL.HIGH,
    # ambiguous: "promo_code", "zip code"
    "code": SEVERITY_LEVEL.MEDIUM,
    # filesystem
    "path": SEVERITY_LEVEL.MEDIUM,
    "file": SEVERITY_LEVEL.MEDIUM,
    "filename": SEVERITY_LEVEL.MEDIUM,
    "filepath": SEVERITY_LEVEL.MEDIUM,
    "pathname": SEVERITY_LEVEL.MEDIUM,
    "dir": SEVERITY_LEVEL.MEDIUM,
    "directory": SEVERITY_LEVEL.MEDIUM,
    # network
    "url": SEVERITY_LEVEL.MEDIUM,
    "uri": SEVERITY_LEVEL.MEDIUM,
    "host": SEVERITY_LEVEL.MEDIUM,
    "hostname": SEVERITY_LEVEL.MEDIUM,
    "endpoint": SEVERITY_LEVEL.MEDIUM,
}

# Keywords that actually narrow the accepted input. "default" and "title" do not.
CONSTRAINTS = (
    "enum", "const", "pattern", "format",
    "maximum", "minimum", "maxLength", "minLength", "multipleOf",
    "exclusiveMaximum", "exclusiveMinimum",
)

_DOWNGRADE = {
    SEVERITY_LEVEL.HIGH: SEVERITY_LEVEL.MEDIUM,
    SEVERITY_LEVEL.MEDIUM: SEVERITY_LEVEL.LOW,
    SEVERITY_LEVEL.LOW: SEVERITY_LEVEL.LOW,
}


def _schema(tool: Any) -> dict:
    """The tool's input schema; the SDK field name varies between versions."""
    schema = getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None) or {}
    return schema if isinstance(schema, dict) else {}


def _tokens(name: str) -> set[str]:
    """Split a parameter name into lowercase words, handling snake_case and camelCase."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    return {token for token in re.split(r"[^a-z0-9]+", spaced.casefold()) if token}


def risky_parameters(tool: Any) -> Finding | None:
    """Flag parameters whose name implies shell/file/network/SQL power."""
    schema = _schema(tool)
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return None

    required = schema.get("required")
    required = set(required) if isinstance(required, list) else set()

    hits = []
    for name, prop in properties.items():
        if not isinstance(prop, dict):
            continue
        matches = _tokens(name) & DANGEROUS_PARAMETERS.keys()
        if not matches:
            continue

        severity = min((DANGEROUS_PARAMETERS[token] for token in matches), key=lambda level: level.value)
        constrained = any(keyword in prop for keyword in CONSTRAINTS)
        if constrained:
            severity = _DOWNGRADE[severity]
        hits.append((severity, name, prop.get("type", "?"), name in required, constrained))

    if not hits:
        return None

    hits.sort(key=lambda hit: (hit[0].value, hit[1]))
    details = ", ".join(
        f"'{name}' ({param_type}, {'required' if is_required else 'optional'}, "
        f"{'constrained' if is_constrained else 'unconstrained'})"
        for _, name, param_type, is_required, is_constrained in hits
    )
    return Finding(hits[0][0], tool.name, f"risky parameter(s): {details}")


# Every check takes one tool and returns a Finding or None.
CHECKS = (missing_description, injection_phrases, risky_parameters)


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
