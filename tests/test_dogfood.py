from pathlib import Path
from northstar import NorthstarCatalog
from northstar.core.entities import CapabilitySpec, ComponentSpec, InvariantSpec
from northstar.core.models import RelationshipEdge, RelationalVerb


def test_northstar_self_dogfood():

    catalog = NorthstarCatalog()
    catalog.add(ComponentSpec(uri="component://northstar/catalog", name="Catalog", domain="northstar"))
    catalog.add(ComponentSpec(uri="component://northstar/validators", name="Validators", domain="northstar"))
    catalog.add(CapabilitySpec(
        uri="req://catalog/resolve-governing-intent",
        title="Resolve Governing Intent Closure",
        domain="northstar",
        component="catalog",
    ))
    catalog.add(CapabilitySpec(uri="req://validators/validate-code-ast", title="Validate Code AST", domain="northstar"))
    catalog.add(InvariantSpec(
        uri="constraint://northstar/no-direct-db-import",
        title="No Direct DB Import",
        rule_type="BOUNDARY",
        target_scope="*",
        description="Prevents direct database access bypassing repository tier",
    ))
    catalog.graph.add_edge(RelationshipEdge(

        source="csi://northstar/api.NorthstarCatalog.get_governing_intent",
        verb=RelationalVerb.SATISFIES,
        target="req://catalog/resolve-governing-intent",
    ))
    catalog.graph.add_edge(RelationshipEdge(
        source="component://northstar/catalog",
        verb=RelationalVerb.REQUIRES,
        target="req://catalog/resolve-governing-intent",
    ))

    assert catalog.graph.node_count >= 5
    assert catalog.graph.has_node("component://northstar/catalog")
    assert catalog.graph.has_node("component://northstar/validators")
    assert catalog.graph.has_node("req://catalog/resolve-governing-intent")
    assert catalog.graph.has_node("req://validators/validate-code-ast")
    assert catalog.graph.has_node("constraint://northstar/no-direct-db-import")

    # Test closure query on Northstar's own symbol
    closure = catalog.get_governing_intent("csi://northstar/api.NorthstarCatalog.get_governing_intent")
    assert len(closure.capabilities) == 1
    assert closure.capabilities[0].uri == "req://catalog/resolve-governing-intent"
    assert len(closure.components) >= 1
    assert closure.components[0].uri == "component://northstar/catalog"


    # Verify context markdown prompt generation
    md = closure.to_markdown_prompt_context()
    assert "Resolve Governing Intent Closure" in md

