"""Formal operational contracts, preconditions, postconditions, and error primitives."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Precondition:
    """A condition that must be guaranteed prior to capability execution."""
    description: str
    expression: Optional[str] = None
    error_on_violation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"description": self.description}
        if self.expression:
            data["expression"] = self.expression
        if self.error_on_violation:
            data["error_on_violation"] = self.error_on_violation
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Precondition":
        return cls(
            description=data.get("description", ""),
            expression=data.get("expression"),
            error_on_violation=data.get("error_on_violation"),
        )


@dataclass
class Postcondition:
    """A state guarantee established upon successful capability execution."""
    description: str
    expression: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"description": self.description}
        if self.expression:
            data["expression"] = self.expression
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Postcondition":
        return cls(
            description=data.get("description", ""),
            expression=data.get("expression"),
        )


@dataclass
class StateTransition:
    """A formal state transition on an operated entity."""
    entity: str
    attribute: str
    from_state: str
    to_state: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity": self.entity,
            "attribute": self.attribute,
            "from_state": self.from_state,
            "to_state": self.to_state,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateTransition":
        return cls(
            entity=data.get("entity", ""),
            attribute=data.get("attribute", "status"),
            from_state=str(data.get("from_state", "")),
            to_state=str(data.get("to_state", "")),
        )



@dataclass
class OperationalContract:
    """Combined operational contract specifying pre/postconditions and state transitions."""
    preconditions: List[Precondition] = field(default_factory=list)
    postconditions: List[Postcondition] = field(default_factory=list)
    state_transitions: List[StateTransition] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "preconditions": [p.to_dict() for p in self.preconditions],
            "postconditions": [p.to_dict() for p in self.postconditions],
            "state_transitions": [s.to_dict() for s in self.state_transitions],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OperationalContract":
        return cls(
            preconditions=[Precondition.from_dict(p) for p in data.get("preconditions", [])],
            postconditions=[Postcondition.from_dict(p) for p in data.get("postconditions", [])],
            state_transitions=[StateTransition.from_dict(s) for s in data.get("state_transitions", [])],
        )


@dataclass
class FailureMode:
    """An explicit domain error branch, trigger condition, and recovery action."""
    error_name: str
    trigger_condition: str
    recovery_action: str
    domain_error_code: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_name": self.error_name,
            "trigger_condition": self.trigger_condition,
            "recovery_action": self.recovery_action,
            "domain_error_code": self.domain_error_code,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FailureMode":
        return cls(
            error_name=data["error_name"],
            trigger_condition=data["trigger_condition"],
            recovery_action=data["recovery_action"],
            domain_error_code=data.get("domain_error_code", ""),
        )


@dataclass
class ActorGrant:
    """Authorization grant defining which actor role may invoke a capability."""
    role: str
    tenancy_constraint: Optional[str] = None
    policy_ref: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"role": self.role}
        if self.tenancy_constraint:
            data["tenancy_constraint"] = self.tenancy_constraint
        if self.policy_ref:
            data["policy_ref"] = self.policy_ref
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActorGrant":
        return cls(
            role=data["role"],
            tenancy_constraint=data.get("tenancy_constraint"),
            policy_ref=data.get("policy_ref"),
        )


@dataclass
class OperatedEntities:
    """Explicit references to GroundTruth logical entities operated on by a capability."""
    creates: List[str] = field(default_factory=list)
    reads: List[str] = field(default_factory=list)
    mutates: List[str] = field(default_factory=list)
    deletes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "creates": self.creates,
            "reads": self.reads,
            "mutates": self.mutates,
            "deletes": self.deletes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OperatedEntities":
        return cls(
            creates=data.get("creates", []),
            reads=data.get("reads", []),
            mutates=data.get("mutates", []),
            deletes=data.get("deletes", []),
        )

