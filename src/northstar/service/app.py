"""FastAPI Service and Solution Control Plane Web Portal for Northstar.

Adheres strictly to ADR 0002:
1. Intent Domain First (Multi-tenant, solution-scoped intent graphs)
2. Equalized Capability API (Non-CRUD intent, verification, and closure queries)
3. Zero-Logic Access Layer (Ultra-thin presentation, crisp Light Theme, no dark mode)
"""

from collections import defaultdict
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from northstar.adapters.git_file import GitFileAdapter
from northstar.adapters.postgres import PostgresAdapter
from northstar.api import NorthstarCatalog
from northstar.core.entities import (
    CapabilitySpec,
    ComponentSpec,
    DecisionSpec,
    InvariantSpec,
    PolicySpec,
    QualitySpec,
    WorkflowSpec,
)
from northstar.core.models import RelationalVerb, RelationshipEdge
from northstar.query.closure import resolve_intent_closure
from northstar.query.lineage import (
    get_component_dependencies,
    get_decision_lineage,
    get_impact_radius,
)


import re


def sanitize_mermaid_id(text: str) -> str:
    """Sanitize identifier for Mermaid graph nodes."""
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", str(text))
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean or "node"


def sanitize_mermaid_label(text: str) -> str:
    """Sanitize text inside Mermaid node brackets to prevent parse errors."""
    clean = re.sub(r'["\'\[\]\(\)\{\}:;<>|#]', "", str(text))
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def resolve_solution_bundles(catalog: NorthstarCatalog) -> Dict[str, Dict[str, Any]]:
    """Resolve complete, principled solution bundles across components, capabilities, ADRs, and invariants."""
    all_nodes = list(catalog.graph._nodes.values())
    all_edges = [edge for edge_set in catalog.graph._outgoing_edges.values() for edge in edge_set]

    # Pre-index governing relationships
    node_to_governing_adrs: Dict[str, Set[str]] = defaultdict(set)
    adr_to_governed_nodes: Dict[str, Set[str]] = defaultdict(set)

    for edge in all_edges:
        if edge.verb == RelationalVerb.GOVERNED_BY:
            node_to_governing_adrs[edge.source].add(edge.target)
            adr_to_governed_nodes[edge.target].add(edge.source)
        elif edge.verb in (RelationalVerb.CONSTRAINS, RelationalVerb.ENFORCES):
            pass

    # Core predefined solutions
    known_solutions = {
        "ecommerce": {
            "solution_name": "ecommerce",
            "display_name": "🛒 E-Commerce & Payments Domain",
            "description": "Omnichannel retail, checkout orchestration, orders, customer profiles, and idempotent payments.",
        },
        "groundtruth": {
            "solution_name": "groundtruth",
            "display_name": "🏛️ GroundTruth Data Authority",
            "description": "Four-tier semantic data authority, conceptual ontologies, normalized logical schemas, and DDL projections.",
        },
        "codemesh": {
            "solution_name": "codemesh",
            "display_name": "🕸️ CodeMesh Computation Authority",
            "description": "Canonical symbol graph, type contracts, multi-hop context slicing, and AST mutation engines.",
        },
        "northstar": {
            "solution_name": "northstar",
            "display_name": "🧭 Northstar Intent Authority",
            "description": "First-principles requirements, decision lineage, executable invariants, and prompt context slicing.",
        },
        "arch": {
            "solution_name": "arch",
            "display_name": "📐 Architectural Decisions (Global ADRs)",
            "description": "Foundational architectural decisions and universal invariants governing the Tripartite Federation.",
        },
    }

    # Discover any extra domains
    for n in all_nodes:
        if n.domain and n.domain not in known_solutions and n.domain not in ("catalog", "logical", "physical", "orders", "payments"):
            known_solutions[n.domain] = {
                "solution_name": n.domain,
                "display_name": f"📦 {n.domain.capitalize()} Solution",
                "description": f"Domain solution package for {n.domain}.",
            }

    bundles: Dict[str, Dict[str, Any]] = {}

    for sol_key, sol_meta in known_solutions.items():
        # 1. Components
        comps = [
            n for n in all_nodes
            if isinstance(n, ComponentSpec) and (
                n.domain == sol_key or
                n.uri.startswith(f"component://{sol_key}/") or
                (sol_key == "ecommerce" and n.domain in ("orders", "payments")) or
                (sol_key == "groundtruth" and n.domain in ("catalog", "logical", "physical", "groundtruth_meta"))
            )
        ]
        comp_uris = {c.uri for c in comps}
        comp_names = {c.name.lower() for c in comps} | {c.uri.split("/")[-1].lower() for c in comps}

        # 2. Capabilities
        caps = [
            n for n in all_nodes
            if isinstance(n, CapabilitySpec) and (
                n.domain == sol_key or
                n.uri.startswith(f"req://{sol_key}/") or
                (n.component and n.component.lower() in comp_names) or
                any(c_uri in n.uri for c_uri in comp_names) or
                (sol_key == "ecommerce" and n.domain in ("orders", "payments")) or
                (sol_key == "groundtruth" and n.domain in ("catalog", "logical", "physical"))
            )
        ]
        cap_uris = {c.uri for c in caps}

        # 3. Decisions / ADRs applying to this solution
        if sol_key == "arch":
            decs = [n for n in all_nodes if isinstance(n, DecisionSpec)]
        else:
            decs = [
                n for n in all_nodes
                if isinstance(n, DecisionSpec) and (
                    n.domain == sol_key or
                    any(governed in comp_uris or governed in cap_uris for governed in adr_to_governed_nodes.get(n.uri, set())) or
                    (sol_key in ("groundtruth", "northstar", "codemesh") and any(k in n.uri for k in ("0001", "0002", "0003")))
                )
            ]

        # 4. Invariants / Constraints applying to this solution
        invs = [
            n for n in all_nodes
            if isinstance(n, InvariantSpec) and (
                n.domain == sol_key or
                n.uri.startswith(f"constraint://{sol_key}/") or
                sol_key in n.target_scope or
                n.target_scope == "*" or
                any(dec.uri == n.governing_adr for dec in decs)
            )
        ]

        # 5. Policies & Qualities
        pols = [n for n in all_nodes if isinstance(n, PolicySpec) and (n.domain == sol_key or sol_key == "arch")]
        quals = [n for n in all_nodes if isinstance(n, QualitySpec) and (n.domain == sol_key or sol_key == "arch")]

        # 6. Generate Mermaid Topological Flowchart for this solution
        mermaid_lines = ["graph TD"]
        mermaid_lines.append("    classDef decNode fill:#eff6ff,stroke:#3b82f6,stroke-width:1.5px,color:#1e3a8a,font-weight:bold;")
        mermaid_lines.append("    classDef compNode fill:#f5f3ff,stroke:#8b5cf6,stroke-width:1.5px,color:#4c1d95,font-weight:bold;")
        mermaid_lines.append("    classDef capNode fill:#ecfdf5,stroke:#10b981,stroke-width:1.5px,color:#064e3b,font-weight:bold;")
        mermaid_lines.append("    classDef invNode fill:#fff1f2,stroke:#f43f5e,stroke-width:1.5px,color:#881337,font-weight:bold;")

        # Render Decisions
        for d in decs[:4]:
            d_id = "DEC_" + sanitize_mermaid_id(d.uri.split("/")[-1])
            d_title = sanitize_mermaid_label((d.title or d.uri)[:30])
            mermaid_lines.append(f'    {d_id}["📜 {d_title}"]:::decNode')

        # Render Components
        for c in comps[:6]:
            c_id = "COMP_" + sanitize_mermaid_id(c.uri.split("/")[-1])
            c_name = sanitize_mermaid_label(c.name or c.uri.split("/")[-1])
            mermaid_lines.append(f'    {c_id}["📦 {c_name}"]:::compNode')
            # Connect governing ADRs
            for d in decs:
                if c.uri in adr_to_governed_nodes.get(d.uri, set()):
                    d_id = "DEC_" + sanitize_mermaid_id(d.uri.split("/")[-1])
                    mermaid_lines.append(f"    {d_id} -.->|governs| {c_id}")

        # Render Capabilities & Connect to Components
        for cap in caps[:8]:
            cap_id = "CAP_" + sanitize_mermaid_id(cap.uri.split("/")[-1])
            cap_title = sanitize_mermaid_label((cap.title or cap.uri)[:26])
            mermaid_lines.append(f'    {cap_id}["⚡ {cap_title}"]:::capNode')
            # Link to component
            if cap.component:
                for c in comps:
                    if c.name.lower() == cap.component.lower() or c.uri.split("/")[-1].lower() == cap.component.lower():
                        c_id = "COMP_" + sanitize_mermaid_id(c.uri.split("/")[-1])
                        mermaid_lines.append(f"    {c_id} -->|exports| {cap_id}")

        # Render Invariants
        for inv in invs[:4]:
            inv_id = "INV_" + sanitize_mermaid_id(inv.uri.split("/")[-1])
            inv_title = sanitize_mermaid_label((inv.title or inv.uri)[:28])
            mermaid_lines.append(f'    {inv_id}["🛡️ {inv_title}"]:::invNode')

        if len(mermaid_lines) == 5:
            mermaid_lines.append('    EMPTY["ℹ️ No explicit topology graph declared for this solution"]:::decNode')

        mermaid_graph = "\n".join(mermaid_lines)

        bundles[sol_key] = {
            "solution_name": sol_key,
            "display_name": sol_meta["display_name"],
            "description": sol_meta["description"],
            "components": [c.to_dict() for c in comps],
            "capabilities": [c.to_dict() for c in caps],
            "decisions": [d.to_dict() for d in decs],
            "invariants": [i.to_dict() for i in invs],
            "policies": [p.to_dict() for p in pols],
            "qualities": [q.to_dict() for q in quals],
            "mermaid_graph": mermaid_graph,
            "total_nodes": len(comps) + len(caps) + len(decs) + len(invs) + len(pols) + len(quals),
        }

    return bundles



def create_app(workspace_root: Optional[str | Path] = None) -> FastAPI:
    root_path = Path(workspace_root or os.getenv("NORTHSTAR_WORKSPACE_ROOT", "."))
    
    app = FastAPI(
        title="Northstar Intent & Governance Control Plane",
        description="The Intent, Requirements, and Governance Authority for the Tripartite Semantic Federation",
        version="0.2.0",
    )

    # 1. Initialize catalog from Git/YAML manifests
    if (root_path / "intent").exists() or (root_path / "adrs").exists() or (root_path / ".northstar").exists():
        catalog = NorthstarCatalog.load(root_path)
    else:
        catalog = NorthstarCatalog()

    # 2. Sync / Connect to Larnet PostgreSQL if available
    postgres_adapter = None
    try:
        pg_host = os.getenv("POSTGRES_HOST", "localhost")
        pg_port = int(os.getenv("POSTGRES_PORT", "15432"))
        postgres_adapter = PostgresAdapter(host=pg_host, port=pg_port)
        postgres_adapter.save_graph(catalog.graph)
    except Exception as e:
        print(f"[Northstar] Notice: Running in hybrid memory/git mode (Postgres sync deferred: {e})")

    app.state.catalog = catalog
    app.state.postgres = postgres_adapter
    app.state.workspace_root = root_path

    # Pydantic Request Models
    class NodePayload(BaseModel):
        type: str
        data: Dict[str, Any]

    class LinkPayload(BaseModel):
        source: str
        verb: str
        target: str
        metadata: Optional[Dict[str, Any]] = None

    class ValidatePayload(BaseModel):
        target_symbol: str
        code_content: str
        metadata: Optional[Dict[str, Any]] = None

    # =========================================================================
    # CAPABILITY API ENDPOINTS
    # =========================================================================

    @app.get("/health")
    def health_check():
        return {
            "status": "ok",
            "service": "northstar",
            "workspace_root": str(app.state.workspace_root),
            "node_count": catalog.graph.node_count,
            "edge_count": catalog.graph.edge_count,
        }

    @app.get("/api/v1/solutions")
    def list_solutions():
        """Discover all solution domain packages partitioned under tenants."""
        bundles = resolve_solution_bundles(catalog)
        solutions = []
        for sol_key, bundle in bundles.items():
            solutions.append({
                "solution_name": sol_key,
                "display_name": bundle["display_name"],
                "description": bundle["description"],
                "total_nodes": bundle["total_nodes"],
                "components": len(bundle["components"]),
                "capabilities": len(bundle["capabilities"]),
                "decisions": len(bundle["decisions"]),
                "invariants": len(bundle["invariants"]),
            })
        return {"tenant": "tripartite", "solutions": solutions}

    @app.get("/api/v1/solutions/{solution_name}")
    def get_solution_details(solution_name: str):
        """Retrieve complete intent and governance specification for a solution."""
        bundles = resolve_solution_bundles(catalog)
        if solution_name not in bundles:
            raise HTTPException(status_code=404, detail=f"Solution '{solution_name}' not found")
        return bundles[solution_name]

    @app.get("/api/v1/graph")
    def get_graph():
        return catalog.graph.to_dict()

    @app.get("/api/v1/nodes/{uri:path}")
    def get_node(uri: str):
        node = catalog.graph.get_node(uri)
        if not node:
            raise HTTPException(status_code=404, detail=f"Intent node '{uri}' not found")
        return {"uri": node.uri, "type": node.__class__.__name__, "data": node.to_dict()}

    @app.post("/api/v1/nodes")
    def register_node(payload: NodePayload):
        node_type = payload.type
        data = payload.data
        if node_type == "CapabilitySpec":
            node = CapabilitySpec.from_dict(data)
        elif node_type == "ComponentSpec":
            node = ComponentSpec.from_dict(data)
        elif node_type == "WorkflowSpec":
            node = WorkflowSpec.from_dict(data)
        elif node_type == "DecisionSpec":
            node = DecisionSpec.from_dict(data)
        elif node_type == "InvariantSpec":
            node = InvariantSpec.from_dict(data)
        elif node_type == "PolicySpec":
            node = PolicySpec.from_dict(data)
        elif node_type == "QualitySpec":
            node = QualitySpec.from_dict(data)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown node type: {node_type}")

        catalog.graph.add_node(node)
        if app.state.postgres:
            try:
                app.state.postgres.save_node(node)
            except Exception as e:
                print(f"[Northstar] Postgres save failed: {e}")

        return {"status": "created", "uri": node.uri}

    @app.post("/api/v1/links")
    def register_link(payload: LinkPayload):
        try:
            verb = RelationalVerb(payload.verb)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid verb: {payload.verb}")

        edge = RelationshipEdge(
            source=payload.source,
            verb=verb,
            target=payload.target,
            metadata=payload.metadata or {},
        )
        catalog.graph.add_edge(edge)
        if app.state.postgres:
            try:
                app.state.postgres.save_edge(edge)
            except Exception as e:
                print(f"[Northstar] Postgres edge save failed: {e}")

        return {"status": "linked", "source": payload.source, "verb": payload.verb, "target": payload.target}

    @app.get("/api/v1/closure")
    def get_closure(target_uri: str = Query(...)):
        """Compute the full semantic closure for a code or data URI."""
        closure = resolve_intent_closure(catalog.graph, target_uri)
        return closure.to_dict()

    @app.post("/api/v1/validate")
    def validate_code(payload: ValidatePayload):
        """Execute invariant engines against submitted code snippet."""
        violations = catalog.invariant_engine.validate(
            symbol_uri=payload.target_symbol,
            code=payload.code_content,
            metadata=payload.metadata or {},
        )
        return {
            "valid": len(violations) == 0,
            "target_symbol": payload.target_symbol,
            "violations": [
                {
                    "rule_name": v.rule_name,
                    "description": v.description,
                    "severity": v.severity.value,
                    "line_number": v.line_number,
                }
                for v in violations
            ],
        }

    @app.get("/api/v1/lineage/decisions/{uri:path}")
    def get_decision_lineage_endpoint(uri: str):
        return get_decision_lineage(catalog.graph, uri)

    @app.get("/api/v1/lineage/impact/{uri:path}")
    def get_impact_radius_endpoint(uri: str):
        return get_impact_radius(catalog.graph, uri)

    @app.get("/api/v1/lineage/components/{uri:path}")
    def get_component_dependencies_endpoint(uri: str):
        return get_component_dependencies(catalog.graph, uri)

    # =========================================================================
    # LIGHT-THEMED WEB EXPLORER DASHBOARD
    # =========================================================================

    @app.get("/", response_class=HTMLResponse)
    @app.get("/dashboard", response_class=HTMLResponse)
    def render_dashboard():
        """Render the clean light-mode Northstar Intent Explorer."""
        bundles = resolve_solution_bundles(catalog)
        embedded_json = json.dumps(bundles)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Northstar | Intent & Governance Authority</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.0/dist/mermaid.min.js"></script>
  <style>
    body {{ background-color: #f8fafc; color: #0f172a; }}
    .tree-node-active {{ background-color: #eff6ff; color: #1d4ed8; font-weight: 600; border-left: 3px solid #3b82f6; }}
    ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    ::-webkit-scrollbar-track {{ background: #f1f5f9; }}
    ::-webkit-scrollbar-thumb {{ background: #cbd5e1; border-radius: 3px; }}
  </style>
</head>
<body class="bg-slate-50 text-slate-900 font-sans min-h-screen flex flex-col antialiased">

  <!-- Light Theme Header -->
  <header class="border-b border-slate-200 bg-white sticky top-0 z-50 px-6 py-3.5 flex items-center justify-between shadow-sm">
    <div class="flex items-center space-x-4">
      <div class="h-9 w-9 bg-blue-600 rounded-lg flex items-center justify-center font-bold text-white text-lg shadow-sm">NS</div>
      <div>
        <h1 class="text-base font-bold tracking-tight text-slate-900 flex items-center gap-2">
          Northstar <span class="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">Intent & Governance Authority</span>
        </h1>
        <p class="text-[11px] text-slate-500">Solution Control Plane • First-Principles Requirements • Decision Lineage • Executable Invariants</p>
      </div>
    </div>

    <!-- Tenant & Solution Selection Hierarchy -->
    <div class="flex items-center space-x-3 text-xs">
      <div class="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 shadow-sm">
        <span class="text-slate-500 font-medium">Tenant:</span>
        <select class="bg-transparent text-slate-800 font-semibold focus:outline-none cursor-pointer">
          <option value="tripartite" selected>🏢 Tripartite Enterprise</option>
        </select>
      </div>

      <div class="flex items-center gap-2 bg-white border border-blue-300 rounded-lg px-3 py-1.5 shadow-sm">
        <span class="text-blue-700 font-semibold">Active Solution:</span>
        <select id="solutionSelect" onchange="onSolutionChange(this.value)" class="bg-slate-50 text-slate-900 font-bold rounded px-2 py-0.5 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer border border-slate-200">
          <option value="ecommerce">🛒 E-Commerce & Payments Domain</option>
          <option value="groundtruth">🏛️ GroundTruth Data Authority</option>
          <option value="codemesh">🕸️ CodeMesh Computation Authority</option>
          <option value="northstar">🧭 Northstar Intent Authority</option>
          <option value="arch">📐 Architectural Decisions (Global ADRs)</option>
        </select>
      </div>

      <span class="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-blue-50 border border-blue-200 text-blue-800 font-medium shadow-sm">
        <span class="h-2 w-2 rounded-full bg-blue-500 animate-pulse"></span>
        PostgreSQL: <strong>localhost:15432</strong>
      </span>
    </div>
  </header>

  <!-- Workspace: Left Tree Sidebar + Right Main Viewport -->
  <div class="flex-1 flex overflow-hidden">
    
    <!-- LEFT SIDEBAR: Solution Tree Navigation -->
    <aside class="w-72 border-r border-slate-200 bg-white flex flex-col overflow-y-auto p-4 space-y-4 shadow-sm">
      <div class="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-500 px-2">
        <span id="treeSolutionHeader">Solution Intent</span>
        <span id="treeStatsBadge" class="text-[10px] bg-slate-100 px-2 py-0.5 rounded text-slate-600 font-mono">...</span>
      </div>

      <!-- Tree Nodes Container -->
      <nav id="treeContainer" class="space-y-1 text-xs font-medium">
        <!-- Dynamically rendered tree -->
      </nav>
    </aside>

    <!-- RIGHT MAIN VIEWPORT: Solution-Scoped Focus Content -->
    <main id="mainViewport" class="flex-1 overflow-y-auto p-8 space-y-6 bg-slate-50">
      <!-- Dynamically rendered detail view -->
    </main>
  </div>

  <script id="nsDataScript" type="application/json">
{embedded_json}
  </script>

  <script>
    const NS_BUNDLES = JSON.parse(document.getElementById('nsDataScript').textContent);
    let currentSolution = 'ecommerce';
    let currentBundle = NS_BUNDLES[currentSolution] || NS_BUNDLES[Object.keys(NS_BUNDLES)[0]];
    let activeNodeId = 'overview';
    let renderCounter = 0;

    try {{
      if (window.mermaid) {{
        mermaid.initialize({{
          startOnLoad: false,
          theme: 'neutral',
          securityLevel: 'loose',
          suppressErrorRendering: true
        }});
      }}
    }} catch (e) {{
      console.warn('Mermaid init warning:', e);
    }}


    function onSolutionChange(solutionName) {{
      activeNodeId = 'overview';
      currentSolution = solutionName;
      currentBundle = NS_BUNDLES[solutionName] || {{ solution_name: solutionName, display_name: solutionName, description: '', components: [], capabilities: [], decisions: [], invariants: [], policies: [], qualities: [], mermaid_graph: '' }};
      document.getElementById('solutionSelect').value = solutionName;
      renderTree();
      selectView(activeNodeId);
    }}

    function renderTree() {{
      if (!currentBundle) return;
      document.getElementById('treeSolutionHeader').textContent = currentBundle.solution_name;
      document.getElementById('treeStatsBadge').textContent = `${{currentBundle.total_nodes}} Nodes`;

      const container = document.getElementById('treeContainer');
      let html = '';

      // 1. Solution Overview
      html += `
        <div onclick="selectView('overview')" class="cursor-pointer flex items-center gap-2 px-3 py-2 rounded-lg text-slate-700 hover:bg-slate-100 ${{activeNodeId === 'overview' ? 'tree-node-active' : ''}}">
          <span>📊</span> <span>Solution Intent Topology</span>
        </div>
      `;

      // 2. Components
      if (currentBundle.components && currentBundle.components.length > 0) {{
        html += `
          <div class="pt-2">
            <div onclick="selectView('components_overview')" class="cursor-pointer flex items-center justify-between px-3 py-1.5 text-slate-600 hover:text-slate-900 font-semibold">
              <span class="flex items-center gap-2"><span>📦</span> <span>Components</span></span>
              <span class="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.2 rounded font-mono">${{currentBundle.components.length}}</span>
            </div>
            <div class="pl-6 space-y-0.5 mt-1 border-l border-slate-200 ml-4">
              ${{currentBundle.components.map(c => `
                <div onclick="selectComponent('${{c.uri}}')" class="cursor-pointer px-2 py-1 rounded text-slate-600 hover:text-slate-900 hover:bg-slate-100 truncate ${{activeNodeId === 'comp_' + c.uri ? 'tree-node-active' : ''}}">
                  ${{c.name || c.uri.split('/').pop()}}
                </div>
              `).join('')}}
            </div>
          </div>
        `;
      }}

      // 3. Functional Capabilities
      if (currentBundle.capabilities && currentBundle.capabilities.length > 0) {{
        html += `
          <div class="pt-2">
            <div onclick="selectView('capabilities_overview')" class="cursor-pointer flex items-center justify-between px-3 py-1.5 text-slate-600 hover:text-slate-900 font-semibold">
              <span class="flex items-center gap-2"><span>⚡</span> <span>Capabilities</span></span>
              <span class="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.2 rounded font-mono">${{currentBundle.capabilities.length}}</span>
            </div>
            <div class="pl-6 space-y-0.5 mt-1 border-l border-slate-200 ml-4">
              ${{currentBundle.capabilities.map(c => `
                <div onclick="selectCapability('${{c.uri}}')" class="cursor-pointer px-2 py-1 rounded text-slate-600 hover:text-slate-900 hover:bg-slate-100 truncate ${{activeNodeId === 'cap_' + c.uri ? 'tree-node-active' : ''}}">
                  ${{c.title || c.name || c.uri.split('/').pop()}}
                </div>
              `).join('')}}
            </div>
          </div>
        `;
      }}

      // 4. Decisions & ADRs
      if (currentBundle.decisions && currentBundle.decisions.length > 0) {{
        html += `
          <div class="pt-2">
            <div onclick="selectView('decisions_overview')" class="cursor-pointer flex items-center justify-between px-3 py-1.5 text-slate-600 hover:text-slate-900 font-semibold">
              <span class="flex items-center gap-2"><span>📜</span> <span>Governing ADRs</span></span>
              <span class="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.2 rounded font-mono">${{currentBundle.decisions.length}}</span>
            </div>
            <div class="pl-6 space-y-0.5 mt-1 border-l border-slate-200 ml-4">
              ${{currentBundle.decisions.map(d => `
                <div onclick="selectDecision('${{d.uri}}')" class="cursor-pointer px-2 py-1 rounded text-slate-600 hover:text-slate-900 hover:bg-slate-100 truncate ${{activeNodeId === 'dec_' + d.uri ? 'tree-node-active' : ''}}">
                  ${{d.title || d.uri.split('/').pop()}}
                </div>
              `).join('')}}
            </div>
          </div>
        `;
      }}

      // 5. Invariants & Constraints
      if (currentBundle.invariants && currentBundle.invariants.length > 0) {{
        html += `
          <div class="pt-2">
            <div onclick="selectView('invariants_overview')" class="cursor-pointer flex items-center justify-between px-3 py-1.5 text-slate-600 hover:text-slate-900 font-semibold">
              <span class="flex items-center gap-2"><span>🛡️</span> <span>Invariants & Rules</span></span>
              <span class="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.2 rounded font-mono">${{currentBundle.invariants.length}}</span>
            </div>
            <div class="pl-6 space-y-0.5 mt-1 border-l border-slate-200 ml-4">
              ${{currentBundle.invariants.map(inv => `
                <div onclick="selectInvariant('${{inv.uri}}')" class="cursor-pointer px-2 py-1 rounded text-slate-600 hover:text-slate-900 hover:bg-slate-100 truncate ${{activeNodeId === 'inv_' + inv.uri ? 'tree-node-active' : ''}}">
                  ${{inv.title || inv.name || inv.uri.split('/').pop()}}
                </div>
              `).join('')}}
            </div>
          </div>
        `;
      }}

      container.innerHTML = html;
    }}

    function selectView(viewId) {{
      activeNodeId = viewId;
      renderTree();
      const viewport = document.getElementById('mainViewport');

      if (viewId === 'overview') {{
        renderOverviewView(viewport);
      }} else if (viewId === 'components_overview') {{
        renderComponentsOverview(viewport);
      }} else if (viewId === 'capabilities_overview') {{
        renderCapabilitiesOverview(viewport);
      }} else if (viewId === 'decisions_overview') {{
        renderDecisionsOverview(viewport);
      }} else if (viewId === 'invariants_overview') {{
        renderInvariantsOverview(viewport);
      }}
    }}

    function selectComponent(uri) {{
      activeNodeId = 'comp_' + uri;
      renderTree();
      const comp = currentBundle.components.find(c => c.uri === uri);
      if (!comp) return;
      renderComponentDetailView(comp);
    }}

    function selectCapability(uri) {{
      activeNodeId = 'cap_' + uri;
      renderTree();
      const cap = currentBundle.capabilities.find(c => c.uri === uri);
      if (!cap) return;
      renderCapabilityDetailView(cap);
    }}

    function selectDecision(uri) {{
      activeNodeId = 'dec_' + uri;
      renderTree();
      const decision = currentBundle.decisions.find(d => d.uri === uri);
      if (!decision) return;
      renderDecisionDetailView(decision);
    }}

    function selectInvariant(uri) {{
      activeNodeId = 'inv_' + uri;
      renderTree();
      const inv = currentBundle.invariants.find(i => i.uri === uri);
      if (!inv) return;
      renderInvariantDetailView(inv);
    }}

    async function renderChartSafely(targetElementId, chartDefinition) {{
      const el = document.getElementById(targetElementId);
      if (!el) return;
      if (!chartDefinition || !chartDefinition.trim()) {{
        el.innerHTML = '<div class="p-4 text-xs text-slate-400 text-center font-mono">No topology chart declared for this view</div>';
        return;
      }}

      renderCounter++;
      const uniqueId = 'mermaid_svg_ns_' + renderCounter;

      try {{
        if (window.mermaid && window.mermaid.render) {{
          const cleanDef = chartDefinition.replace(/\\n/g, '\n').trim();
          const {{ svg }} = await window.mermaid.render(uniqueId, cleanDef);
          el.innerHTML = svg;
        }} else {{
          el.innerHTML = `<pre class="text-xs font-mono text-slate-800">${{chartDefinition}}</pre>`;
        }}
      }} catch (err) {{
        console.warn('Mermaid render fallback:', err);
        document.querySelectorAll('[id^="dmermaid"]').forEach(e => e.remove());
        document.querySelectorAll('.error-icon').forEach(e => e.closest('div')?.remove());
        el.innerHTML = `<div class="p-4 bg-white border border-slate-200 rounded-lg text-xs font-mono text-slate-700 overflow-x-auto"><div class="font-bold text-slate-500 mb-2">Topology Map (Text Definition)</div><pre>${{chartDefinition}}</pre></div>`;
      }}
    }}



    // --- VIEW RENDERERS ---

    function renderOverviewView(container) {{
      container.innerHTML = `
        <div class="space-y-6">
          <div class="flex items-center justify-between border-b border-slate-200 pb-4">
            <div>
              <h2 class="text-xl font-bold text-slate-900 flex items-center gap-2">
                📊 ${{currentBundle.display_name}}
              </h2>
              <p class="text-xs text-slate-500 mt-1">${{currentBundle.description}}</p>
            </div>
            <span class="text-xs px-3 py-1 rounded bg-blue-50 text-blue-700 border border-blue-200 font-semibold shadow-sm">
              ${{currentBundle.total_nodes}} Total Scoped Nodes
            </span>
          </div>

          <!-- Summary Metric Cards -->
          <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div onclick="selectView('components_overview')" class="cursor-pointer bg-white border border-slate-200 hover:border-purple-300 rounded-xl p-4 shadow-sm transition hover:shadow">
              <div class="text-xs text-slate-500 font-medium uppercase">Components</div>
              <div class="text-2xl font-bold text-purple-700 mt-1">${{currentBundle.components.length}}</div>
            </div>
            <div onclick="selectView('capabilities_overview')" class="cursor-pointer bg-white border border-slate-200 hover:border-emerald-300 rounded-xl p-4 shadow-sm transition hover:shadow">
              <div class="text-xs text-slate-500 font-medium uppercase">Capabilities</div>
              <div class="text-2xl font-bold text-emerald-700 mt-1">${{currentBundle.capabilities.length}}</div>
            </div>
            <div onclick="selectView('decisions_overview')" class="cursor-pointer bg-white border border-slate-200 hover:border-blue-300 rounded-xl p-4 shadow-sm transition hover:shadow">
              <div class="text-xs text-slate-500 font-medium uppercase">Governing ADRs</div>
              <div class="text-2xl font-bold text-blue-700 mt-1">${{currentBundle.decisions.length}}</div>
            </div>
            <div onclick="selectView('invariants_overview')" class="cursor-pointer bg-white border border-slate-200 hover:border-rose-300 rounded-xl p-4 shadow-sm transition hover:shadow">
              <div class="text-xs text-slate-500 font-medium uppercase">Invariants</div>
              <div class="text-2xl font-bold text-rose-700 mt-1">${{currentBundle.invariants.length}}</div>
            </div>
          </div>

          <!-- Mermaid Topological Diagram Card -->
          <div class="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-3">
            <div class="flex justify-between items-center border-b border-slate-100 pb-2">
              <h3 class="text-xs font-bold uppercase tracking-wider text-slate-800">Topological Governance Map</h3>
              <span class="text-[10px] text-slate-500 font-mono">Decisions ➔ Components ➔ Capabilities ➔ Invariants</span>
            </div>
            <div id="solutionTopologyChart" class="flex justify-center overflow-x-auto min-h-[160px] items-center">
              <span class="text-slate-400 text-xs animate-pulse">Rendering topology...</span>
            </div>
          </div>

          <!-- Quick Access Cards -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <!-- Capabilities Column -->
            <div class="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
              <div class="flex justify-between items-center border-b border-slate-100 pb-2">
                <h4 class="font-bold text-slate-900 text-xs uppercase tracking-wider">Functional Capabilities</h4>
                <span class="text-[10px] text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded font-mono font-semibold">${{currentBundle.capabilities.length}} Active</span>
              </div>
              <div class="space-y-2 max-h-64 overflow-y-auto">
                ${{currentBundle.capabilities.map(c => `
                  <div onclick="selectCapability('${{c.uri}}')" class="cursor-pointer p-2.5 rounded-lg border border-slate-100 hover:border-emerald-300 hover:bg-slate-50 transition">
                    <div class="flex justify-between items-center">
                      <span class="font-bold text-slate-900 text-xs">${{c.title || c.name}}</span>
                      <span class="text-[9px] font-mono text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded">${{c.uri.split('/').pop()}}</span>
                    </div>
                    <p class="text-xs text-slate-600 mt-1 line-clamp-1">${{c.intent || c.description || 'Declared capability'}}</p>
                  </div>
                `).join('')}}
              </div>
            </div>

            <!-- Invariants Column -->
            <div class="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
              <div class="flex justify-between items-center border-b border-slate-100 pb-2">
                <h4 class="font-bold text-slate-900 text-xs uppercase tracking-wider">Active Invariant Guardrails</h4>
                <span class="text-[10px] text-rose-700 bg-rose-50 px-2 py-0.5 rounded font-mono font-semibold">${{currentBundle.invariants.length}} Active</span>
              </div>
              <div class="space-y-2 max-h-64 overflow-y-auto">
                ${{currentBundle.invariants.map(inv => `
                  <div onclick="selectInvariant('${{inv.uri}}')" class="cursor-pointer p-2.5 rounded-lg border border-slate-100 hover:border-rose-300 hover:bg-slate-50 transition">
                    <div class="flex justify-between items-center">
                      <span class="font-bold text-slate-900 text-xs">${{inv.title || inv.name}}</span>
                      <span class="text-[9px] font-mono text-rose-700 bg-rose-50 px-1.5 py-0.5 rounded">${{inv.rule_type || 'GUARDRAIL'}}</span>
                    </div>
                    <p class="text-xs text-slate-600 mt-1 line-clamp-1">${{inv.description || inv.remediation_hint || 'Executable boundary rule'}}</p>
                  </div>
                `).join('')}}
              </div>
            </div>
          </div>
        </div>
      `;

      renderChartSafely('solutionTopologyChart', currentBundle.mermaid_graph);
    }}

    // --- DETAIL VIEW: INVARIANT / CONSTRAINT ---
    function renderInvariantDetailView(inv) {{
      const container = document.getElementById('mainViewport');
      container.innerHTML = `
        <div class="space-y-6">
          <div class="flex items-center justify-between border-b border-slate-200 pb-4">
            <div>
              <div class="flex items-center gap-3">
                <h2 class="text-2xl font-bold text-slate-900">${{inv.title || inv.name}}</h2>
                <span class="text-xs px-2.5 py-0.5 rounded bg-rose-50 text-rose-700 border border-rose-200 font-mono font-semibold">${{inv.rule_type || 'INVARIANT'}}</span>
                <span class="text-xs px-2.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-mono font-semibold">${{inv.status || 'ACTIVE'}}</span>
              </div>
              <p class="text-xs text-slate-500 mt-1.5 font-mono">${{inv.uri}}</p>
            </div>
            <button onclick="selectView('overview')" class="text-xs bg-white hover:bg-slate-50 text-slate-700 px-3 py-1.5 rounded-lg border border-slate-200 transition shadow-sm font-medium">
              ← Back to Solution Map
            </button>
          </div>

          <!-- 1. Formal Description Box -->
          <div class="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-3">
            <div class="text-xs uppercase tracking-wider text-slate-700 font-bold">Constraint Description & Verification Scope</div>
            <p class="text-sm text-slate-800 leading-relaxed bg-slate-50 p-4 rounded-lg border border-slate-200">
              ${{inv.description || 'No description provided.'}}
            </p>
          </div>

          <!-- 2. Actionable Remediation Hint -->
          <div class="bg-amber-50 border border-amber-200 rounded-xl p-6 shadow-sm space-y-2">
            <div class="text-xs uppercase tracking-wider text-amber-800 font-bold flex items-center gap-1.5">
              <span>💡</span> <span>Actionable Remediation Guidance</span>
            </div>
            <p class="text-xs text-amber-950 font-medium leading-relaxed">
              ${{inv.remediation_hint || 'Adhere strictly to boundary contracts. No automatic fix specified.'}}
            </p>
          </div>

          <!-- 3. Target Scope & Governance Metadata -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-2">
              <div class="text-xs uppercase tracking-wider text-slate-500 font-bold">Target AST / Domain Scope</div>
              <code class="text-xs font-mono text-purple-700 bg-purple-50 px-2 py-1 rounded border border-purple-200 block">${{inv.target_scope || '*'}}</code>
            </div>

            <div class="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-2">
              <div class="text-xs uppercase tracking-wider text-slate-500 font-bold">Governing Architectural Decision</div>
              ${{inv.governing_adr ? `
                <div onclick="selectDecision('${{inv.governing_adr}}')" class="cursor-pointer text-xs font-mono text-blue-700 bg-blue-50 hover:bg-blue-100 px-2 py-1 rounded border border-blue-200 truncate transition">
                  📜 ${{inv.governing_adr}}
                </div>
              ` : '<span class="text-xs text-slate-400">Global Architectural Principle</span>'}}
            </div>
          </div>

          <!-- 4. Executable Rule Expression -->
          <div class="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-3">
            <div class="text-xs uppercase tracking-wider text-slate-700 font-bold">Executable Invariant Policy Expression</div>
            <pre class="text-xs font-mono text-emerald-800 bg-slate-50 p-4 rounded-lg border border-slate-200 overflow-x-auto">${{inv.executable_expression || inv.expression || '# AST Invariant Engine evaluator class: DynamicASTBoundaryValidator'}}</pre>
          </div>
        </div>
      `;
    }}

    // --- DETAIL VIEW: DECISION (ADR) ---
    function renderDecisionDetailView(decision) {{
      const container = document.getElementById('mainViewport');
      container.innerHTML = `
        <div class="space-y-6">
          <div class="flex items-center justify-between border-b border-slate-200 pb-4">
            <div>
              <div class="flex items-center gap-3">
                <h2 class="text-2xl font-bold text-slate-900">${{decision.title || decision.uri}}</h2>
                <span class="text-xs px-2.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 font-mono font-semibold">${{decision.status || 'ACTIVE'}}</span>
              </div>
              <p class="text-xs text-slate-500 mt-1.5 font-mono">${{decision.uri}}</p>
            </div>
            <button onclick="selectView('overview')" class="text-xs bg-white hover:bg-slate-50 text-slate-700 px-3 py-1.5 rounded-lg border border-slate-200 transition shadow-sm font-medium">
              ← Back to Solution Map
            </button>
          </div>

          <!-- Decision Outcome Card -->
          <div class="bg-emerald-50 border border-emerald-200 rounded-xl p-6 shadow-sm space-y-2">
            <div class="text-xs uppercase tracking-wider text-emerald-800 font-bold flex items-center gap-1.5">
              <span>🎯</span> <span>Authoritative Decision Outcome</span>
            </div>
            <div class="text-sm text-emerald-950 font-medium leading-relaxed whitespace-pre-line">
              ${{decision.decision_outcome || 'No outcome recorded.'}}
            </div>
          </div>

          <!-- Context & Problem Card -->
          <div class="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-3">
            <div class="text-xs uppercase tracking-wider text-slate-700 font-bold">Context & Business Drivers</div>
            <div class="text-xs text-slate-800 leading-relaxed bg-slate-50 p-4 rounded-lg border border-slate-200 whitespace-pre-line">
              ${{decision.context_and_problem || 'No context provided.'}}
            </div>
          </div>

          <!-- Positive & Negative Consequences Grid -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-2">
              <div class="text-xs uppercase tracking-wider text-emerald-700 font-bold flex items-center gap-1">
                <span>✅</span> <span>Positive Consequences & Gains</span>
              </div>
              <ul class="text-xs text-slate-700 space-y-1.5 pl-4 list-disc">
                ${{decision.positive_consequences && decision.positive_consequences.length > 0 ? decision.positive_consequences.map(p => `<li>${{p}}</li>`).join('') : '<li class="text-slate-400 list-none">None specified</li>'}}
              </ul>
            </div>

            <div class="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-2">
              <div class="text-xs uppercase tracking-wider text-amber-700 font-bold flex items-center gap-1">
                <span>⚠️</span> <span>Trade-offs & Mitigations</span>
              </div>
              <ul class="text-xs text-slate-700 space-y-1.5 pl-4 list-disc">
                ${{decision.negative_consequences && decision.negative_consequences.length > 0 ? decision.negative_consequences.map(n => `<li>${{n}}</li>`).join('') : '<li class="text-slate-400 list-none">No negative trade-offs documented</li>'}}
              </ul>
            </div>
          </div>
        </div>
      `;
    }}

    // --- DETAIL VIEW: CAPABILITY SPEC ---
    function renderCapabilityDetailView(cap) {{
      const container = document.getElementById('mainViewport');
      container.innerHTML = `
        <div class="space-y-6">
          <div class="flex items-center justify-between border-b border-slate-200 pb-4">
            <div>
              <div class="flex items-center gap-3">
                <h2 class="text-2xl font-bold text-slate-900">${{cap.title || cap.name}}</h2>
                <span class="text-xs px-2.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-mono font-semibold">${{cap.lifecycle || 'ACTIVE'}}</span>
              </div>
              <p class="text-xs text-slate-500 mt-1.5 font-mono">${{cap.uri}}</p>
            </div>
            <button onclick="selectView('overview')" class="text-xs bg-white hover:bg-slate-50 text-slate-700 px-3 py-1.5 rounded-lg border border-slate-200 transition shadow-sm font-medium">
              ← Back to Solution Map
            </button>
          </div>

          <!-- Business Intent -->
          <div class="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-3">
            <div class="text-xs uppercase tracking-wider text-slate-700 font-bold">Business Intent & Goal</div>
            <p class="text-sm text-slate-800 leading-relaxed bg-slate-50 p-4 rounded-lg border border-slate-200">
              ${{cap.intent || cap.description || 'No intent declared.'}}
            </p>
          </div>

          <!-- Preconditions & Postconditions -->
          ${{cap.contract ? `
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div class="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-2">
                <div class="text-xs uppercase tracking-wider text-amber-700 font-bold flex items-center gap-1">
                  <span>🔒</span> <span>Preconditions</span>
                </div>
                <div class="space-y-1.5">
                  ${{cap.contract.preconditions && cap.contract.preconditions.length > 0 ? cap.contract.preconditions.map(p => `
                    <div class="text-xs bg-amber-50 text-amber-900 p-2.5 rounded border border-amber-200 font-medium">${{p.description || p}}</div>
                  `).join('') : '<span class="text-xs text-slate-400">No explicit preconditions required</span>'}}
                </div>
              </div>

              <div class="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-2">
                <div class="text-xs uppercase tracking-wider text-emerald-700 font-bold flex items-center gap-1">
                  <span>✨</span> <span>Postconditions</span>
                </div>
                <div class="space-y-1.5">
                  ${{cap.contract.postconditions && cap.contract.postconditions.length > 0 ? cap.contract.postconditions.map(p => `
                    <div class="text-xs bg-emerald-50 text-emerald-900 p-2.5 rounded border border-emerald-200 font-medium">${{p.description || p}}</div>
                  `).join('') : '<span class="text-xs text-slate-400">No explicit postconditions recorded</span>'}}
                </div>
              </div>
            </div>
          ` : ''}}

          <!-- Failure Modes & Recovery Actions Table -->
          ${{cap.failure_modes && cap.failure_modes.length > 0 ? `
            <div class="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
              <div class="px-5 py-3 border-b border-slate-200 bg-slate-50">
                <h3 class="text-xs font-bold uppercase tracking-wider text-slate-700">Failure Modes & Recovery Runbooks</h3>
              </div>
              <table class="w-full text-left text-xs border-collapse">
                <thead>
                  <tr class="border-b border-slate-200 text-slate-500 bg-slate-50">
                    <th class="py-2.5 px-4">Error Name</th>
                    <th class="py-2.5 px-4">Trigger Condition</th>
                    <th class="py-2.5 px-4 text-emerald-700">Actionable Recovery Action</th>
                  </tr>
                </thead>
                <tbody>
                  ${{cap.failure_modes.map(fm => `
                    <tr class="border-b border-slate-100 hover:bg-slate-50">
                      <td class="py-2.5 px-4 font-mono font-bold text-rose-700">${{fm.error_name}}</td>
                      <td class="py-2.5 px-4 text-slate-700">${{fm.trigger_condition}}</td>
                      <td class="py-2.5 px-4 text-emerald-800 font-medium bg-emerald-50">${{fm.recovery_action || 'Report error'}}</td>
                    </tr>
                  `).join('')}}
                </tbody>
              </table>
            </div>
          ` : ''}}
        </div>
      `;
    }}

    // --- DETAIL VIEW: COMPONENT SPEC ---
    function renderComponentDetailView(comp) {{
      const container = document.getElementById('mainViewport');
      container.innerHTML = `
        <div class="space-y-6">
          <div class="flex items-center justify-between border-b border-slate-200 pb-4">
            <div>
              <div class="flex items-center gap-3">
                <h2 class="text-2xl font-bold text-slate-900">${{comp.name || comp.uri}}</h2>
                <span class="text-xs px-2.5 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200 font-mono font-semibold">${{comp.lifecycle || 'ACTIVE'}}</span>
              </div>
              <p class="text-xs text-slate-500 mt-1.5 font-mono">${{comp.uri}}</p>
            </div>
            <button onclick="selectView('overview')" class="text-xs bg-white hover:bg-slate-50 text-slate-700 px-3 py-1.5 rounded-lg border border-slate-200 transition shadow-sm font-medium">
              ← Back to Solution Map
            </button>
          </div>

          <!-- Exported Capabilities Table -->
          <div class="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-3">
            <div class="text-xs uppercase tracking-wider text-slate-700 font-bold">Exported Public Capabilities</div>
            <div class="space-y-2">
              ${{comp.exported_capabilities && comp.exported_capabilities.length > 0 ? comp.exported_capabilities.map(capUri => `
                <div onclick="selectCapability('${{capUri}}')" class="cursor-pointer p-3 rounded-lg border border-slate-100 hover:border-blue-300 hover:bg-slate-50 transition flex justify-between items-center">
                  <span class="text-xs font-mono font-bold text-blue-700">${{capUri}}</span>
                  <span class="text-xs text-slate-400">➔</span>
                </div>
              `).join('') : '<span class="text-xs text-slate-400">No exported capabilities declared</span>'}}
            </div>
          </div>
        </div>
      `;
    }}

    function renderComponentsOverview(container) {{
      container.innerHTML = `
        <div class="space-y-6">
          <div class="border-b border-slate-200 pb-4">
            <h2 class="text-xl font-bold text-slate-900">📦 Components in ${{currentBundle.display_name}}</h2>
            <p class="text-xs text-slate-500 mt-1">Autonomous functional units encapsulated by this solution</p>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            ${{currentBundle.components.map(c => `
              <div onclick="selectComponent('${{c.uri}}')" class="cursor-pointer bg-white border border-slate-200 rounded-xl p-5 hover:border-purple-400 transition shadow-sm hover:shadow">
                <h3 class="font-bold text-slate-900 text-base">${{c.name}}</h3>
                <span class="text-xs font-mono text-purple-700 bg-purple-50 px-2 py-0.5 rounded border border-purple-200 font-semibold block mt-1">${{c.uri}}</span>
                <p class="text-xs text-slate-600 mt-2 line-clamp-2">${{c.description || 'Exported capabilities: ' + (c.exported_capabilities ? c.exported_capabilities.length : 0)}}</p>
              </div>
            `).join('')}}
          </div>
        </div>
      `;
    }}

    function renderCapabilitiesOverview(container) {{
      container.innerHTML = `
        <div class="space-y-6">
          <div class="border-b border-slate-200 pb-4">
            <h2 class="text-xl font-bold text-slate-900">⚡ Functional Capabilities in ${{currentBundle.display_name}}</h2>
            <p class="text-xs text-slate-500 mt-1">Authoritative contract specifications and failure recovery modes</p>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            ${{currentBundle.capabilities.map(c => `
              <div onclick="selectCapability('${{c.uri}}')" class="cursor-pointer bg-white border border-slate-200 rounded-xl p-5 hover:border-emerald-400 transition shadow-sm hover:shadow">
                <div class="flex justify-between items-center">
                  <h3 class="font-bold text-slate-900 text-base">${{c.title || c.name}}</h3>
                  <span class="text-xs font-mono text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 font-semibold">${{c.uri.split('/').pop()}}</span>
                </div>
                <p class="text-xs text-slate-600 mt-2">${{c.intent || c.description || 'Declared capability'}}</p>
              </div>
            `).join('')}}
          </div>
        </div>
      `;
    }}

    function renderDecisionsOverview(container) {{
      container.innerHTML = `
        <div class="space-y-6">
          <div class="border-b border-slate-200 pb-4">
            <h2 class="text-xl font-bold text-slate-900">📜 Architectural Decisions (ADRs) for ${{currentBundle.display_name}}</h2>
            <p class="text-xs text-slate-500 mt-1">Foundational design decisions governing the design and behavior of this solution</p>
          </div>
          <div class="grid grid-cols-1 gap-4">
            ${{currentBundle.decisions.map(d => `
              <div onclick="selectDecision('${{d.uri}}')" class="cursor-pointer bg-white border border-slate-200 rounded-xl p-5 hover:border-blue-400 transition shadow-sm hover:shadow space-y-2">
                <div class="flex justify-between items-center">
                  <h3 class="font-bold text-slate-900 text-base">${{d.title || d.uri}}</h3>
                  <span class="text-xs font-mono text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200 font-semibold">${{d.status || 'ACTIVE'}}</span>
                </div>
                <p class="text-xs text-slate-700 font-medium">${{d.decision_outcome || 'No outcome statement'}}</p>
                <div class="text-[10px] font-mono text-slate-400">${{d.uri}}</div>
              </div>
            `).join('')}}
          </div>
        </div>
      `;
    }}

    function renderInvariantsOverview(container) {{
      container.innerHTML = `
        <div class="space-y-6">
          <div class="border-b border-slate-200 pb-4">
            <h2 class="text-xl font-bold text-slate-900">🛡️ Invariant Rules for ${{currentBundle.display_name}}</h2>
            <p class="text-xs text-slate-500 mt-1">Executable policies and structural constraints verified across the domain</p>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            ${{currentBundle.invariants.map(inv => `
              <div onclick="selectInvariant('${{inv.uri}}')" class="cursor-pointer bg-white border border-slate-200 rounded-xl p-5 hover:border-rose-400 transition shadow-sm hover:shadow space-y-2">
                <div class="flex justify-between items-center">
                  <h3 class="font-bold text-slate-900 text-sm">${{inv.title || inv.name}}</h3>
                  <span class="text-[10px] font-mono text-rose-700 bg-rose-50 px-2 py-0.5 rounded border border-rose-200 font-semibold">${{inv.rule_type || 'RULE'}}</span>
                </div>
                <p class="text-xs text-slate-600 line-clamp-2">${{inv.description || inv.remediation_hint || 'Executable boundary rule'}}</p>
                <div class="text-[10px] font-mono text-slate-400 truncate">${{inv.target_scope || '*'}}</div>
              </div>
            `).join('')}}
          </div>
        </div>
      `;
    }}

    renderTree();
    selectView('overview');
  </script>
</body>
</html>"""
        return HTMLResponse(content=html_content)

    return app


app = create_app()
