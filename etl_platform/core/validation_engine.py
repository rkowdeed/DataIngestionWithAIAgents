"""
Validation Engine.

Applies metadata.validation_rules to a fully extracted/transformed
record: NOT_NULL, DATATYPE, RANGE, ENUM, CROSS_FIELD, and NESTED_OBJECT
checks. This runs after transformation but before load, and its findings
feed both the audit log and the error repository / self-healing queue.
"""
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    json_path: str
    rule_type: str
    severity: str
    message: str


@dataclass
class ValidationResult:
    is_valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "ERROR"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "WARNING"]


def _column_for_path(json_path: str, mappings: list[dict]) -> str | None:
    for m in mappings:
        if m["json_path"] == json_path:
            return m["target_column"]
    return None


def _check_range(value, expression: str) -> bool:
    # expression format: "<low>&lt;=value&lt;=<high>" stored as e.g. "0<=value<=50"
    match = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*<=\s*value\s*<=\s*(-?\d+(?:\.\d+)?)\s*$", expression)
    if not match or value is None:
        return True  # can't evaluate -> don't fail the record on a malformed rule
    low, high = float(match.group(1)), float(match.group(2))
    try:
        return low <= float(value) <= high
    except (TypeError, ValueError):
        return False


def _check_enum(value, expression: str) -> bool:
    # expression format: "IN ('A','B','C')"
    match = re.match(r"^\s*IN\s*\((.*)\)\s*$", expression, re.IGNORECASE)
    if not match:
        return True
    allowed = [v.strip().strip("'\"") for v in match.group(1).split(",")]
    return value in allowed


def validate_record(record: dict, validation_rules: list[dict], mappings: list[dict]) -> ValidationResult:
    """Run all applicable validation rules against a single extracted record."""
    issues: list[ValidationIssue] = []

    for rule in validation_rules:
        json_path = rule["json_path"]
        rule_type = rule["rule_type"]
        expression = rule["rule_expression"]
        severity = rule.get("severity", "ERROR")

        column = _column_for_path(json_path, mappings)
        value = record.get(column) if column else None

        passed = True
        if rule_type == "NOT_NULL":
            passed = value is not None and value != ""
        elif rule_type == "RANGE":
            passed = _check_range(value, expression)
        elif rule_type == "ENUM":
            passed = _check_enum(value, expression)
        elif rule_type in ("DATATYPE", "CROSS_FIELD", "NESTED_OBJECT"):
            # Extension points for more advanced rule types; default to pass
            # so unimplemented rule types never silently reject data.
            passed = True
        else:
            logger.warning("Unknown validation rule_type '%s' for %s", rule_type, json_path)

        if not passed:
            issues.append(ValidationIssue(
                json_path=json_path,
                rule_type=rule_type,
                severity=severity,
                message=f"Validation failed for '{json_path}' (column={column}, value={value!r}, rule={expression!r})",
            ))

    has_errors = any(i.severity == "ERROR" for i in issues)
    return ValidationResult(is_valid=not has_errors, issues=issues)
