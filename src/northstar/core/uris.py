"""URI parser and validator for Northstar canonical Option B addressing schemes.

Grammar: scheme://[tenant:][solution]/[identifier][@version][#fragment]
"""

from dataclasses import dataclass
from enum import Enum
import re
from typing import Optional, Tuple


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
    r"(?:(?P<tenant>[a-z0-9_-]+):)?"
    r"(?:(?P<domain>[a-z0-9_/-]+)/)?"
    r"(?P<identifier>[a-z0-9_-]+)"
    r"(?:@(?P<version>[a-zA-Z0-9_.-]+))?"
    r"(?:#(?P<fragment>[a-zA-Z0-9_-]+))?$"
)

ADR_IDENTIFIER_PATTERN = re.compile(r"^adr-\d+-[a-z0-9_-]+$")


@dataclass(frozen=True)
class NorthstarURI:
    raw: str
    scheme: SchemeType
    domain: str
    identifier: str
    tenant: Optional[str] = None
    version: Optional[str] = None
    fragment: Optional[str] = None

    def __str__(self) -> str:
        return self.to_scoped()


    def to_canonical(self, default_tenant: str = "tripartite", default_version: Optional[str] = None) -> str:
        """Format as a fully qualified canonical Option B URI."""
        tenant_part = f"{self.tenant or default_tenant}:"
        domain_part = f"{self.domain}/" if self.domain else ""
        ver_part = f"@{self.version}" if self.version else (f"@{default_version}" if default_version else "")
        frag_part = f"#{self.fragment}" if self.fragment else ""
        return f"{self.scheme.value}://{tenant_part}{domain_part}{self.identifier}{ver_part}{frag_part}"

    def to_scoped(self) -> str:
        """Format as a human-friendly scoped URI without tenant/version prefix if redundant."""
        domain_part = f"{self.domain}/" if self.domain and self.domain != self.identifier else ""
        ver_part = f"@{self.version}" if self.version else ""
        frag_part = f"#{self.fragment}" if self.fragment else ""
        return f"{self.scheme.value}://{domain_part}{self.identifier}{ver_part}{frag_part}"

    def to_coordinate_tuple(self, default_tenant: str = "tripartite") -> Tuple[str, str, str, str, str]:
        """Return 5-tuple: (scheme, tenant, solution, version, identifier)."""
        tenant_val = self.tenant or ("global" if self.scheme == SchemeType.DECISION else default_tenant)
        version_val = self.version or "latest"
        return (self.scheme.value, tenant_val, self.domain, version_val, self.identifier)

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
    """Parse and validate a canonical Option B Northstar URI."""
    match = URI_PATTERN.match(uri_str.strip())
    if not match:
        raise ValueError(
            f"Invalid Northstar URI: '{uri_str}'. Must match scheme://[tenant:][domain/]slug[@version][#fragment] "
            f"for schemes (component, req, workflow, decision, constraint, policy, quality)."
        )

    scheme_str = match.group("scheme")
    raw_tenant = match.group("tenant")
    raw_domain = match.group("domain")
    identifier = match.group("identifier")
    version = match.group("version")
    fragment = match.group("fragment")

    domain = raw_domain.strip("/") if raw_domain else identifier
    scheme = SchemeType(scheme_str)

    # Specific check for ADR format
    if scheme == SchemeType.DECISION and not ADR_IDENTIFIER_PATTERN.match(identifier):
        raise ValueError(
            f"Invalid decision URI identifier: '{identifier}'. Must follow 'adr-###-slug' pattern."
        )

    tenant = raw_tenant if raw_tenant else ("global" if scheme == SchemeType.DECISION and domain == "arch" else None)

    return NorthstarURI(
        raw=uri_str,
        scheme=scheme,
        domain=domain,
        identifier=identifier,
        tenant=tenant,
        version=version,
        fragment=fragment,
    )
