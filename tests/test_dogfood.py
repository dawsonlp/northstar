"""Unit test verifying Northstar's self-dogfooded intent manifests."""

from pathlib import Path
from northstar import NorthstarCatalog


def test_northstar_self_dogfood():
    repo_root = Path(__file__).parent.parent
    catalog = NorthstarCatalog.load(repo_root)

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
