"""Executable invariant validation engine and diagnostic generator."""

import ast
from dataclasses import dataclass
from enum import Enum
import re
from typing import Any, Dict, List, Optional

from northstar.core.entities import InvariantRuleType, InvariantSpec
from northstar.validators.rules import (
    ArchitecturalBoundaryValidator,
    CanonicalURIComplianceValidator,
    ConstraintValidator,
    ConstraintViolation,
    DecoratorInvariantValidator,
    DeterministicDDLPurityValidator,
    PurityValidator,
    StateTransitionMatrixValidator,
    TenantIsolationValidator,
    TypeContractValidator,
    ViolationSeverity,
    ZeroDatabaseCredentialsValidator,
)

# Compatibility aliases
DiagnosticSeverity = ViolationSeverity
LayerBoundaryValidator = ArchitecturalBoundaryValidator


@dataclass
class ViolationLocation:
    file: Optional[str] = None
    line: Optional[int] = None
    symbol: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"file": self.file, "line": self.line, "symbol": self.symbol}


class InvariantEngine:
    """Orchestrates execution of bound invariant validators against proposed code changes."""

    def __init__(self):
        self.validators: List[ConstraintValidator] = []

    def register_validator(self, validator: ConstraintValidator) -> None:
        self.validators.append(validator)

    def register_from_spec(self, spec: InvariantSpec) -> None:
        """Create and register a validator automatically from an InvariantSpec."""
        uri_lower = spec.uri.lower()
        if spec.rule_type == InvariantRuleType.DECORATOR_INVARIANT or "idempotent" in uri_lower:
            dec_name = spec.executable_expression or "idempotent"
            self.register_validator(
                DecoratorInvariantValidator(
                    constraint_uri=spec.uri,
                    required_decorator_name=dec_name,
                    remediation_hint=spec.remediation_hint,
                )
            )
        elif spec.rule_type == InvariantRuleType.PURITY_BOUND or "ddl-purity" in uri_lower:
            if "ddl" in uri_lower:
                self.register_validator(DeterministicDDLPurityValidator(constraint_uri=spec.uri, remediation_hint=spec.remediation_hint))
            else:
                self.register_validator(PurityValidator(constraint_uri=spec.uri, remediation_hint=spec.remediation_hint))
        elif spec.rule_type == InvariantRuleType.TYPE_CONTRACT:
            self.register_validator(
                TypeContractValidator(
                    constraint_uri=spec.uri,
                    remediation_hint=spec.remediation_hint,
                )
            )
        elif "tenant" in uri_lower:
            self.register_validator(TenantIsolationValidator(constraint_uri=spec.uri, remediation_hint=spec.remediation_hint))
        elif "zero-db" in uri_lower or "no-db" in uri_lower:
            self.register_validator(ZeroDatabaseCredentialsValidator(constraint_uri=spec.uri, remediation_hint=spec.remediation_hint))
        elif "canonical-uri" in uri_lower or "uri" in uri_lower:
            self.register_validator(CanonicalURIComplianceValidator(constraint_uri=spec.uri, remediation_hint=spec.remediation_hint))

    def validate_code(
        self,
        target_symbol: str,
        code_content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[ConstraintViolation]:
        """Run all registered validators against code content and return all violations."""
        all_violations: List[ConstraintViolation] = []
        for validator in self.validators:
            violations = validator.validate(target_symbol, code_content, metadata)
            all_violations.extend(violations)
        return all_violations


__all__ = [
    "InvariantEngine",
    "ConstraintValidator",
    "ConstraintViolation",
    "ViolationSeverity",
    "DiagnosticSeverity",
    "ViolationLocation",
    "ArchitecturalBoundaryValidator",
    "LayerBoundaryValidator",
    "DecoratorInvariantValidator",
    "PurityValidator",
    "StateTransitionMatrixValidator",
    "TypeContractValidator",
    "TenantIsolationValidator",
    "ZeroDatabaseCredentialsValidator",
    "CanonicalURIComplianceValidator",
    "DeterministicDDLPurityValidator",
]

