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


class TenantIsolationValidator(ConstraintValidator):
    """Enforces that multi-tenant API endpoints and repositories explicitly declare tenant context parameters."""

    def __init__(
        self,
        constraint_uri: str = "constraint://arch/tenant-information-boundary",
        remediation_hint: str = "Accept 'tenant_slug: str' or 'tenant_id: UUID' parameter in multi-tenant signature.",
        governing_adr: Optional[str] = "decision://arch/adr-0005-hierarchical-multi-tenant-api-segmentation-and-global-inheritance",
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
                if "tenant" in node.name.lower() or (metadata and metadata.get("is_tenant_scoped")):
                    arg_names = [a.arg for a in node.args.args]
                    if not any("tenant" in a.lower() for a in arg_names):
                        violations.append(
                            ConstraintViolation(
                                constraint_uri=self.constraint_uri,
                                target_symbol=target_symbol,
                                message=f"Tenant-scoped function '{node.name}' is missing a tenant context parameter.",
                                line_number=node.lineno,
                                remediation_hint=self.remediation_hint,
                                governing_adr=self.governing_adr,
                                severity=self.severity,
                            )
                        )
        return violations


class ZeroDatabaseCredentialsValidator(ConstraintValidator):
    """Enforces that presentation layer and UI code never embed database connection strings or direct DB drivers."""

    def __init__(
        self,
        constraint_uri: str = "constraint://portal/zero-db-credentials",
        remediation_hint: str = "Route all data access through the GroundTruth and NorthStar REST APIs instead of direct DB access.",
        governing_adr: Optional[str] = "decision://arch/adr-0002-three-tier-decomposition-data-domain-first-capability-api-and-zero-logic-presentation",
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
        forbidden_tokens = ["postgres://", "postgresql://", "mysql://", "mongodb://", "psycopg", "larnet_dev"]
        for idx, line in enumerate(code_content.splitlines(), start=1):
            for token in forbidden_tokens:
                if token in line:
                    violations.append(
                        ConstraintViolation(
                            constraint_uri=self.constraint_uri,
                            target_symbol=target_symbol,
                            message=f"Direct database connection pattern or credential '{token}' detected in presentation code.",
                            line_number=idx,
                            remediation_hint=self.remediation_hint,
                            governing_adr=self.governing_adr,
                            severity=self.severity,
                        )
                    )
        return violations


class CanonicalURIComplianceValidator(ConstraintValidator):
    """Enforces that URI strings declared or parsed adhere to Option B grammar."""

    def __init__(
        self,
        constraint_uri: str = "constraint://arch/canonical-uri-compliance",
        remediation_hint: str = "Format URIs as scheme://[tenant:][solution]/[path][@version][#fragment].",
        governing_adr: Optional[str] = "decision://arch/adr-0004-canonical-uri-grammar-and-versioning-topology",
        severity: ViolationSeverity = ViolationSeverity.ERROR,
    ):
        self.constraint_uri = constraint_uri
        self.remediation_hint = remediation_hint
        self.governing_adr = governing_adr
        self.severity = severity
        self.uri_pattern = re.compile(r'^(req|component|decision|constraint|policy|quality|workflow|data|csi)://([a-z0-9_-]+:)?([a-z0-9_-]+)/([a-zA-Z0-9_.-]+)(/[a-zA-Z0-9_.-]+)*(@[a-zA-Z0-9_.-]+)?(#[a-zA-Z0-9_.-]+)?$')

    def validate(
        self,
        target_symbol: str,
        code_content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[ConstraintViolation]:
        violations: List[ConstraintViolation] = []
        if metadata and "uri_to_validate" in metadata:
            uri = metadata["uri_to_validate"]
            if not self.uri_pattern.match(uri):
                violations.append(
                    ConstraintViolation(
                        constraint_uri=self.constraint_uri,
                        target_symbol=target_symbol,
                        message=f"URI '{uri}' violates Option B Canonical URI grammar.",
                        remediation_hint=self.remediation_hint,
                        governing_adr=self.governing_adr,
                        severity=self.severity,
                    )
                )
        return violations


class DeterministicDDLPurityValidator(ConstraintValidator):
    """Enforces that physical DDL projection engines are pure string transformation functions free of IO."""

    def __init__(
        self,
        constraint_uri: str = "constraint://groundtruth/deterministic-ddl-purity",
        remediation_hint: str = "Ensure DDL generator only performs pure string formatting and returns deterministic SQL.",
        governing_adr: Optional[str] = "decision://arch/adr-0002-three-tier-decomposition-data-domain-first-capability-api-and-zero-logic-presentation",
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
                if isinstance(node.func, ast.Name) and node.func.id in ("open", "exec", "eval"):
                    violations.append(
                        ConstraintViolation(
                            constraint_uri=self.constraint_uri,
                            target_symbol=target_symbol,
                            message=f"Impure call '{node.func.id}()' detected in DDL projection engine.",
                            line_number=node.lineno,
                            remediation_hint=self.remediation_hint,
                            governing_adr=self.governing_adr,
                            severity=self.severity,
                        )
                    )
        return violations


