"""Unit tests for Northstar URI parsing and validation."""

import pytest
from northstar.core.uris import NorthstarURI, SchemeType, parse_uri


def test_parse_requirement_uri():
    uri = parse_uri("req://payments/idempotent-charge-execution")
    assert uri.scheme == SchemeType.REQUIREMENT
    assert uri.domain == "payments"
    assert uri.identifier == "idempotent-charge-execution"
    assert uri.is_requirement is True
    assert str(uri) == "req://payments/idempotent-charge-execution"


def test_parse_decision_uri():
    uri = parse_uri("decision://payments/adr-004-stripe-idempotency-keys")
    assert uri.scheme == SchemeType.DECISION
    assert uri.domain == "payments"
    assert uri.identifier == "adr-004-stripe-idempotency-keys"
    assert uri.is_decision is True


def test_parse_constraint_uri():
    uri = parse_uri("constraint://architecture/domain-service-isolation")
    assert uri.scheme == SchemeType.CONSTRAINT
    assert uri.domain == "architecture"
    assert uri.identifier == "domain-service-isolation"
    assert uri.is_constraint is True


def test_parse_policy_uri():
    uri = parse_uri("policy://compliance/pci-dss-card-data-isolation")
    assert uri.scheme == SchemeType.POLICY
    assert uri.domain == "compliance"
    assert uri.identifier == "pci-dss-card-data-isolation"
    assert uri.is_policy is True


def test_parse_quality_uri():
    uri = parse_uri("quality://checkout/p99-latency-under-200ms")
    assert uri.scheme == SchemeType.QUALITY
    assert uri.domain == "checkout"
    assert uri.identifier == "p99-latency-under-200ms"
    assert uri.is_quality is True


def test_invalid_scheme():
    with pytest.raises(ValueError, match="Invalid Northstar URI"):
        parse_uri("invalid://payments/test")


def test_invalid_adr_identifier():
    with pytest.raises(ValueError, match="Must follow 'adr-###-slug' pattern"):
        parse_uri("decision://payments/bad-identifier")


def test_parse_option_b_canonical_uri():
    uri = parse_uri("req://tripartite:payments/idempotent-charge-execution@v1#preconditions")
    assert uri.scheme == SchemeType.REQUIREMENT
    assert uri.tenant == "tripartite"
    assert uri.domain == "payments"
    assert uri.identifier == "idempotent-charge-execution"
    assert uri.version == "v1"
    assert uri.fragment == "preconditions"
    assert uri.to_canonical() == "req://tripartite:payments/idempotent-charge-execution@v1#preconditions"
    assert uri.to_coordinate_tuple() == ("req", "tripartite", "payments", "v1", "idempotent-charge-execution")


def test_parse_global_adr_option_b():
    uri = parse_uri("decision://global:arch/adr-0004-canonical-uri-grammar@v1")
    assert uri.scheme == SchemeType.DECISION
    assert uri.tenant == "global"
    assert uri.domain == "arch"
    assert uri.identifier == "adr-0004-canonical-uri-grammar"
    assert uri.version == "v1"
