"""Unit and integration tests for Northstar Documentation Projection Engine."""

import tempfile
from pathlib import Path
import pytest

from northstar import (
    CapabilitySpec,
    ComponentSpec,
    DecisionSpec,
    DocumentationProjector,
    InvariantRuleType,
    InvariantSpec,
    NorthstarCatalog,
    OperationalContract,
    Postcondition,
    Precondition,
)


def test_documentation_projection_engine():
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_dir = Path(tmp_dir) / "docs"

        catalog = NorthstarCatalog()

        # Add Component
        comp = ComponentSpec(
            uri="component://groundtruth/logical",
            name="GroundTruth Logical Data Model",
            domain="groundtruth",
            description="DAMA logical entity models and state machines.",
            exported_capabilities=["req://logical/define-entity-schema"],
            boundary_invariants=["constraint://groundtruth/state-machine-validity"],
        )
        catalog.add(comp)

        # Add Capability
        cap = CapabilitySpec(
            uri="req://logical/define-entity-schema",
            title="Define Logical Entity Schema",
            intent="Defines DAMA-compliant logical entity schemas.",
            component="logical",
            contract=OperationalContract(
                preconditions=[Precondition("Entity links to conceptual term", "term.exists()")],
                postconditions=[Postcondition("Entity is registered", "catalog.has_entity()")],
            ),
            governed_by=["decision://groundtruth/adr-0001-mof"],
            constraints=["constraint://groundtruth/state-machine-validity"],
        )
        catalog.add(cap)

        # Add ADR
        dec = DecisionSpec(
            uri="decision://groundtruth/adr-0001-mof",
            title="ADR 0001: MOF & DAMA Conformance",
            context_and_problem="Need formal meta-model.",
            decision_outcome="Use MOF 4-layer architecture.",
            positive_consequences=["Lossless schema generation"],
        )
        catalog.add(dec)

        # Add Invariant
        inv = InvariantSpec(
            uri="constraint://groundtruth/state-machine-validity",
            title="State Machine Validity",
            rule_type=InvariantRuleType.STATE_MACHINE,
            remediation_hint="Ensure transition is valid.",
            governing_adr="decision://groundtruth/adr-0001-mof",
        )
        catalog.add(inv)

        # Execute Projection
        generated = catalog.project_solution_docs("groundtruth", out_dir)

        assert len(generated) >= 5
        assert (out_dir / "README.md").exists()
        assert (out_dir / "components" / "logical.md").exists()
        assert (out_dir / "capabilities" / "logical" / "define-entity-schema.md").exists()
        assert (out_dir / "adrs" / "adr-0001-mof.md").exists()
        assert (out_dir / "invariants" / "catalog.md").exists()
        assert (out_dir / "traceability_matrix.md").exists()

        # Check README content
        readme_text = (out_dir / "README.md").read_text()
        assert "GROUNDTRUTH Requirements & Intent Specification" in readme_text
        assert "GroundTruth Logical Data Model" in readme_text
        assert "Define Logical Entity Schema" in readme_text

        # Check Capability content
        cap_text = (out_dir / "capabilities" / "logical" / "define-entity-schema.md").read_text()
        assert "Preconditions" in cap_text
        assert "Entity links to conceptual term" in cap_text
        assert "Postconditions" in cap_text
        assert "ADR 0001: MOF & DAMA Conformance" in cap_text

