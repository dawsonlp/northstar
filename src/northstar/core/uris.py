"""URI parser and validator for Northstar canonical addressing schemes."""

from dataclasses import dataclass
from enum import Enum
import re
from typing import Optional


class SchemeType(str, Enum):
    COMPONENT = "component"
    REQUIREMENT = "req"
    WORKFLOW = "workflow"
    DECISION = "decision"
    CONSTRAINT = "constraint"
    POLICY = "policy"
    QUALITY = "quality"


URI_PATTERN = re.compile(
    r"^(?P<scheme>component|req|workflow|decision|constraint|policy|quality)://"
    r"(?:(?P<domain>[a-z0-9_/-]+)/)?"
    r"(?P<identifier>[a-z0-9_-]+)"
    r"(?:#(?P<fragment>[a-zA-Z0-9_-]+))?$"
)

ADR_IDENTIFIER_PATTERN = re.compile(r"^adr-\d+-[a-z0-9_-]+$")


@dataclass(frozen=True)
class NorthstarURI:
    raw: str
    scheme: SchemeType
    domain: str
    identifier: str
    fragment: Optional[str] = None

    def __str__(self) -> str:
        if self.domain and self.domain != self.identifier:
            base = f"{self.scheme.value}://{self.domain}/{self.identifier}"
        else:
            base = f"{self.scheme.value}://{self.identifier}"
        if self.fragment:
            return f"{base}#{self.fragment}"
        return base

    @property
    def is_component(self) -> bool:
        return self.scheme == SchemeType.COMPONENT

    @property
    def is_requirement(self) -> bool:
        return self.scheme == SchemeType.REQUIREMENT

    @property
    def is_workflow(self) -> bool:
        return self.scheme == SchemeType.WORKFLOW

    @property
    def is_decision(self) -> bool:
        return self.scheme == SchemeType.DECISION

    @property
    def is_constraint(self) -> bool:
        return self.scheme == SchemeType.CONSTRAINT

    @property
    def is_policy(self) -> bool:
        return self.scheme == SchemeType.POLICY

    @property
    def is_quality(self) -> bool:
        return self.scheme == SchemeType.QUALITY


def parse_uri(uri_str: str) -> NorthstarURI:
    """Parse and validate a canonical Northstar URI."""
    match = URI_PATTERN.match(uri_str.strip())
    if not match:
        raise ValueError(
            f"Invalid Northstar URI: '{uri_str}'. Must match scheme://[domain/]slug "
            f"for schemes (component, req, workflow, decision, constraint, policy, quality)."
        )

    scheme_str = match.group("scheme")
    raw_domain = match.group("domain")
    identifier = match.group("identifier")
    fragment = match.group("fragment")

    domain = raw_domain.strip("/") if raw_domain else identifier
    scheme = SchemeType(scheme_str)

    # Specific check for ADR format
    if scheme == SchemeType.DECISION and not ADR_IDENTIFIER_PATTERN.match(identifier):
        raise ValueError(
            f"Invalid decision URI identifier: '{identifier}'. Must follow 'adr-###-slug' pattern."
        )

    return NorthstarURI(
        raw=uri_str,
        scheme=scheme,
        domain=domain,
        identifier=identifier,
        fragment=fragment,
    )
