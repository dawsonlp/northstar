"""Built-in executable AST and contract invariant validators."""

from abc import ABC, abstractmethod
import ast
from dataclasses import dataclass
from enum import Enum
import re
from typing import Any, Dict, List, Optional, Set

from northstar.core.entities import InvariantRuleType, InvariantSpec


class ViolationSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class ConstraintViolation:
    """A structured violation emitted when an invariant gate fails."""
    constraint_uri: str
    target_symbol: str
    message: str
    severity: ViolationSeverity = ViolationSeverity.ERROR
    line_number: Optional[int] = None
    remediation_hint: str = ""
    governing_adr: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "constraint_uri": self.constraint_uri,
            "target_symbol": self.target_symbol,
            "message": self.message,
            "severity": self.severity.value if isinstance(self.severity, ViolationSeverity) else self.severity,
            "line_number": self.line_number,
            "remediation_hint": self.remediation_hint,
            "governing_adr": self.governing_adr,
        }


class ConstraintValidator(ABC):
    """Abstract base class for all executable constraint validators."""

    @abstractmethod
    def validate(
        self,
        target_symbol: str,
        code_content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[ConstraintViolation]:
        pass


class ArchitecturalBoundaryValidator(ConstraintValidator):
    """Enforces that code does not import forbidden modules or cross architectural boundaries."""

    def __init__(
        self,
        constraint_uri: str,
        forbidden_import_prefixes: Optional[List[str]] = None,
        forbidden_import_patterns: Optional[List[str]] = None,
        target_pattern: Optional[str] = None,
        governing_adr: Optional[str] = None,
        remediation_hint: str = "",
        severity: ViolationSeverity = ViolationSeverity.ERROR,
    ):
        self.constraint_uri = constraint_uri
        self.forbidden_import_prefixes = forbidden_import_prefixes or []
        self.forbidden_import_patterns = [re.compile(p) for p in (forbidden_import_patterns or [])]
        self.target_pattern = re.compile(target_pattern) if target_pattern else None
        self.governing_adr = governing_adr
        self.remediation_hint = remediation_hint
        self.severity = severity

    def validate(
        self,
        target_symbol: str,
        code_content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[ConstraintViolation]:
        if self.target_pattern and not self.target_pattern.search(target_symbol):
            return []

        violations: List[ConstraintViolation] = []
        try:
            tree = ast.parse(code_content)
        except SyntaxError:
            return violations

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    is_forbidden = any(
                        alias.name == p or alias.name.startswith(f"{p}.")
                        for p in self.forbidden_import_prefixes
                    ) or any(
                        pattern.search(alias.name)
                        for pattern in self.forbidden_import_patterns
                    )
                    if is_forbidden:
                        violations.append(
                            ConstraintViolation(
                                constraint_uri=self.constraint_uri,
                                target_symbol=target_symbol,
                                message=f"Forbidden direct import of '{alias.name}' violates architectural boundary.",
                                line_number=node.lineno,
                                remediation_hint=self.remediation_hint or f"Remove '{alias.name}' and inject via interface.",
                                governing_adr=self.governing_adr,
                                severity=self.severity,
                            )
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    is_forbidden = any(
                        node.module == p or node.module.startswith(f"{p}.")
                        for p in self.forbidden_import_prefixes
                    ) or any(
                        pattern.search(node.module)
                        for pattern in self.forbidden_import_patterns
                    )
                    if is_forbidden:
                        violations.append(
                            ConstraintViolation(
                                constraint_uri=self.constraint_uri,
                                target_symbol=target_symbol,
                                message=f"Forbidden from-import of '{node.module}' violates architectural boundary.",
                                line_number=node.lineno,
                                remediation_hint=self.remediation_hint or f"Remove '{node.module}' and inject via interface.",
                                governing_adr=self.governing_adr,
                                severity=self.severity,
                            )
                        )
        return violations


class DecoratorInvariantValidator(ConstraintValidator):
    """Enforces that target methods carry mandatory decorators (e.g. @idempotent, @require_auth)."""

    def __init__(
        self,
        constraint_uri: str,
        required_decorator_name: str,
        remediation_hint: str = "",
        governing_adr: Optional[str] = None,
        severity: ViolationSeverity = ViolationSeverity.ERROR,
    ):
        self.constraint_uri = constraint_uri
        self.required_decorator_name = required_decorator_name
        self.remediation_hint = remediation_hint
        self.governing_adr = governing_adr
        self.severity = severity

    def validate(
        self,
        target_symbol: str,
        code_content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[ConstraintViolation]:
        violations: List[ConstraintViolation] = []
        try:
            tree = ast.parse(code_content)
        except SyntaxError:
            return violations

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check decorators
                decorator_names = set()
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Name):
                        decorator_names.add(dec.id)
                    elif isinstance(dec, ast.Call):
                        if isinstance(dec.func, ast.Name):
                            decorator_names.add(dec.func.id)
                        elif isinstance(dec.func, ast.Attribute):
                            decorator_names.add(dec.func.attr)

                if self.required_decorator_name not in decorator_names:
                    violations.append(
                        ConstraintViolation(
                            constraint_uri=self.constraint_uri,
                            target_symbol=target_symbol,
                            message=f"Method '{node.name}' is missing mandatory '@{self.required_decorator_name}' decorator.",
                            line_number=node.lineno,
                            remediation_hint=self.remediation_hint or f"Add '@{self.required_decorator_name}' decorator.",
                            governing_adr=self.governing_adr,
                            severity=self.severity,
                        )
                    )
        return violations


class PurityValidator(ConstraintValidator):
    """Enforces that domain calculations and entity methods are free of I/O side effects."""

    FORBIDDEN_CALLS = {"open", "print", "exec", "eval"}
    FORBIDDEN_MODULE_CALLS = {"requests", "httpx", "urllib", "sqlite3", "psycopg", "os", "sys"}

    def __init__(
        self,
        constraint_uri: str,
        remediation_hint: str = "",
        governing_adr: Optional[str] = None,
        severity: ViolationSeverity = ViolationSeverity.ERROR,
    ):
        self.constraint_uri = constraint_uri
        self.remediation_hint = remediation_hint
        self.governing_adr = governing_adr
        self.severity = severity

    def validate(
        self,
        target_symbol: str,
        code_content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[ConstraintViolation]:
        violations: List[ConstraintViolation] = []
        try:
            tree = ast.parse(code_content)
        except SyntaxError:
            return violations

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in self.FORBIDDEN_CALLS:
                    violations.append(
                        ConstraintViolation(
                            constraint_uri=self.constraint_uri,
                            target_symbol=target_symbol,
                            message=f"Impure call to built-in '{node.func.id}()' forbidden in domain entity.",
                            line_number=node.lineno,
                            remediation_hint=self.remediation_hint or "Perform I/O in infrastructure service.",
                            governing_adr=self.governing_adr,
                            severity=self.severity,
                        )
                    )
                elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                    if node.func.value.id in self.FORBIDDEN_MODULE_CALLS:
                        violations.append(
                            ConstraintViolation(
                                constraint_uri=self.constraint_uri,
                                target_symbol=target_symbol,
                                message=f"Impure call to '{node.func.value.id}.{node.func.attr}()' forbidden in domain entity.",
                                line_number=node.lineno,
                                remediation_hint=self.remediation_hint or "Delegate side-effects to repository.",
                                governing_adr=self.governing_adr,
                                severity=self.severity,
                            )
                        )
        return violations


class StateTransitionMatrixValidator(ConstraintValidator):
    """Enforces that code mutations adhere to declared valid state transitions."""

    def __init__(
        self,
        constraint_uri: str,
        forbidden_transitions: List[tuple[str, str]],
        remediation_hint: str = "",
        governing_adr: Optional[str] = None,
        severity: ViolationSeverity = ViolationSeverity.ERROR,
    ):
        self.constraint_uri = constraint_uri
        self.forbidden_transitions = set(forbidden_transitions)  # Set of (from_state, to_state)
        self.remediation_hint = remediation_hint
        self.governing_adr = governing_adr
        self.severity = severity

    def validate(
        self,
        target_symbol: str,
        code_content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[ConstraintViolation]:
        violations: List[ConstraintViolation] = []
        if metadata and "state_transition" in metadata:
            trans = metadata["state_transition"]
            from_st = trans.get("from_state")
            to_st = trans.get("to_state")
            if (from_st, to_st) in self.forbidden_transitions:
                violations.append(
                    ConstraintViolation(
                        constraint_uri=self.constraint_uri,
                        target_symbol=target_symbol,
                        message=f"Illegal state transition from '{from_st}' to '{to_st}'.",
                        remediation_hint=self.remediation_hint or f"State transition from {from_st} to {to_st} is prohibited by state machine.",
                        governing_adr=self.governing_adr,
                        severity=self.severity,
                    )
                )
        return violations


class TypeContractValidator(ConstraintValidator):
    """Enforces strict type annotations on public capability boundaries (forbidding missing/Any return types)."""

    def __init__(
        self,
        constraint_uri: str,
        remediation_hint: str = "",
        governing_adr: Optional[str] = None,
        severity: ViolationSeverity = ViolationSeverity.ERROR,
    ):
        self.constraint_uri = constraint_uri
        self.remediation_hint = remediation_hint
        self.governing_adr = governing_adr
        self.severity = severity

    def validate(
        self,
        target_symbol: str,
        code_content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[ConstraintViolation]:
        violations: List[ConstraintViolation] = []
        try:
            tree = ast.parse(code_content)
        except SyntaxError:
            return violations

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):  # Public function
                    if node.returns is None:
                        violations.append(
                            ConstraintViolation(
                                constraint_uri=self.constraint_uri,
                                target_symbol=target_symbol,
                                message=f"Public function '{node.name}' is missing a return type annotation.",
                                line_number=node.lineno,
                                remediation_hint=self.remediation_hint or f"Add explicit return type annotation to '{node.name}'.",
                                governing_adr=self.governing_adr,
                                severity=self.severity,
                            )
                        )
                    elif isinstance(node.returns, ast.Name) and node.returns.id == "Any":
                        violations.append(
                            ConstraintViolation(
                                constraint_uri=self.constraint_uri,
                                target_symbol=target_symbol,
                                message=f"Public function '{node.name}' uses loose 'Any' return type.",
                                line_number=node.lineno,
                                remediation_hint=self.remediation_hint or "Replace 'Any' with a specific typed domain model.",
                                governing_adr=self.governing_adr,
                                severity=self.severity,
                            )
                        )
        return violations
