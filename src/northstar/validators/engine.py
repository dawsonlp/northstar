"""Executable invariant validation engine and diagnostic generator."""

import ast
from dataclasses import dataclass
from enum import Enum
import re
from typing import Any, Dict, List, Optional


class DiagnosticSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    BLOCKER = "BLOCKER"


@dataclass
class ViolationLocation:
    file: Optional[str] = None
    line: Optional[int] = None
    symbol: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"file": self.file, "line": self.line, "symbol": self.symbol}


@dataclass
class ConstraintViolation:
    constraint_uri: str
    violation_target: str
    message: str
    remediation_hint: str
    severity: DiagnosticSeverity = DiagnosticSeverity.ERROR
    governing_adr: Optional[str] = None
    location: Optional[ViolationLocation] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "constraint_uri": self.constraint_uri,
            "severity": self.severity.value if isinstance(self.severity, DiagnosticSeverity) else self.severity,
            "violation_target": self.violation_target,
            "message": self.message,
            "governing_adr": self.governing_adr,
            "remediation_hint": self.remediation_hint,
            "location": self.location.to_dict() if self.location else None,
        }


class ConstraintValidator:
    """Base class for executable invariant validators."""

    def __init__(
        self,
        constraint_uri: str,
        governing_adr: Optional[str] = None,
        severity: DiagnosticSeverity = DiagnosticSeverity.ERROR,
    ):
        self.constraint_uri = constraint_uri
        self.governing_adr = governing_adr
        self.severity = severity

    def validate(
        self, target_symbol: str, code_content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> List[ConstraintViolation]:
        raise NotImplementedError


class LayerBoundaryValidator(ConstraintValidator):
    """Validates that a symbol's implementation does not import disallowed modules (e.g. domain importing DB)."""

    def __init__(
        self,
        constraint_uri: str,
        target_pattern: str,
        forbidden_import_patterns: List[str],
        governing_adr: Optional[str] = None,
        remediation_hint: str = "",
    ):
        super().__init__(constraint_uri, governing_adr, DiagnosticSeverity.ERROR)
        self.target_pattern = re.compile(target_pattern)
        self.forbidden_import_patterns = [re.compile(p) for p in forbidden_import_patterns]
        self.remediation_hint = remediation_hint

    def validate(
        self, target_symbol: str, code_content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> List[ConstraintViolation]:
        if not self.target_pattern.search(target_symbol):
            return []

        violations: List[ConstraintViolation] = []
        try:
            tree = ast.parse(code_content)
        except SyntaxError:
            # If code has syntax errors, defer to syntax linters
            return []

        for node in ast.walk(tree):
            imported_names: List[str] = []
            if isinstance(node, ast.Import):
                imported_names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_names.append(node.module)

            for mod_name in imported_names:
                for pattern in self.forbidden_import_patterns:
                    if pattern.search(mod_name):
                        violations.append(
                            ConstraintViolation(
                                constraint_uri=self.constraint_uri,
                                severity=self.severity,
                                violation_target=target_symbol,
                                message=f"Symbol '{target_symbol}' imports forbidden module '{mod_name}'.",
                                governing_adr=self.governing_adr,
                                remediation_hint=self.remediation_hint
                                or f"Remove direct import of '{mod_name}' and inject interface dependency instead.",
                                location=ViolationLocation(
                                    line=getattr(node, "lineno", None),
                                    symbol=target_symbol,
                                ),
                            )
                        )
        return violations


class InvariantEngine:
    """Executes registered invariant validators against proposed code mutations."""

    def __init__(self):
        self._validators: List[ConstraintValidator] = []

    def register_validator(self, validator: ConstraintValidator) -> None:
        self._validators.append(validator)

    def validate_code(
        self,
        target_symbol: str,
        code_content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[ConstraintViolation]:
        violations: List[ConstraintViolation] = []
        for validator in self._validators:
            results = validator.validate(target_symbol, code_content, metadata)
            violations.extend(results)
        return violations

