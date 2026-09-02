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
from typing import Any, Dict, List, Optional
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
        # Sync in-memory loaded graph into Postgres
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
        nodes = list(catalog.graph._nodes.values())
        domains = sorted(list({n.domain for n in nodes}))
        
        solutions = []
        for d in domains:
            d_nodes = [n for n in nodes if n.domain == d]
            caps = [n for n in d_nodes if isinstance(n, CapabilitySpec)]
            decs = [n for n in d_nodes if isinstance(n, DecisionSpec)]
            comps = [n for n in d_nodes if isinstance(n, ComponentSpec)]
            invs = [n for n in d_nodes if isinstance(n, InvariantSpec)]

            solutions.append({
                "solution_name": d,
                "display_name": {
                    "northstar": "🧭 Northstar Intent Authority",
                    "groundtruth": "🏛️ GroundTruth Data Authority",
                    "codemesh": "🕸️ CodeMesh Computation Authority",
                    "ecommerce": "🛒 E-Commerce & Payments Domain",
                    "arch": "📐 Federation Architectural Decisions",
                }.get(d, f"📦 {d.capitalize()} Solution"),
                "total_nodes": len(d_nodes),
                "capabilities": len(caps),
                "decisions": len(decs),
                "components": len(comps),
                "invariants": len(invs),
            })

        return {"tenant": "tripartite", "solutions": solutions}

    @app.get("/api/v1/solutions/{solution_name}")
    def get_solution_details(solution_name: str):
        """Retrieve complete intent and governance specification for a solution."""
        all_nodes = list(catalog.graph._nodes.values())
        d_nodes = [n for n in all_nodes if n.domain == solution_name]

        return {
            "solution_name": solution_name,
            "display_name": {
                "northstar": "🧭 Northstar Intent Authority",
                "groundtruth": "🏛️ GroundTruth Data Authority",
                "codemesh": "🕸️ CodeMesh Computation Authority",
                "ecommerce": "🛒 E-Commerce & Payments Domain",
                "arch": "📐 Federation Architectural Decisions",
            }.get(solution_name, f"📦 {solution_name.capitalize()} Solution"),
            "nodes": [n.to_dict() for n in d_nodes],
            "capabilities": [n.to_dict() for n in d_nodes if isinstance(n, CapabilitySpec)],
            "decisions": [n.to_dict() for n in d_nodes if isinstance(n, DecisionSpec)],
            "components": [n.to_dict() for n in d_nodes if isinstance(n, ComponentSpec)],
            "invariants": [n.to_dict() for n in d_nodes if isinstance(n, InvariantSpec)],
        }

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
        all_nodes = list(catalog.graph._nodes.values())
        domains = sorted(list({n.domain for n in all_nodes}))


        solution_bundles = {}
        for d in domains:
            d_nodes = [n for n in all_nodes if n.domain == d]
            solution_bundles[d] = {
                "solution_name": d,
                "display_name": {
                    "northstar": "🧭 Northstar Intent Authority",
                    "groundtruth": "🏛️ GroundTruth Data Authority",
                    "codemesh": "🕸️ CodeMesh Computation Authority",
                    "ecommerce": "🛒 E-Commerce & Payments Domain",
                    "arch": "📐 Federation Architectural Decisions",
                }.get(d, f"📦 {d.capitalize()} Solution"),
                "nodes": [n.to_dict() for n in d_nodes],
                "capabilities": [n.to_dict() for n in d_nodes if isinstance(n, CapabilitySpec)],
                "decisions": [n.to_dict() for n in d_nodes if isinstance(n, DecisionSpec)],
                "components": [n.to_dict() for n in d_nodes if isinstance(n, ComponentSpec)],
                "invariants": [n.to_dict() for n in d_nodes if isinstance(n, InvariantSpec)],
            }

        embedded_json = json.dumps(solution_bundles)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Northstar | Intent & Requirements Authority</title>
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
          <option value="northstar">🧭 Northstar Intent Authority</option>
          <option value="groundtruth">🏛️ GroundTruth Data Authority</option>
          <option value="codemesh">🕸️ CodeMesh Computation Authority</option>
          <option value="ecommerce">🛒 E-Commerce & Payments Domain</option>
          <option value="arch">📐 Architectural Decisions (ADRs)</option>
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
    let currentSolution = 'northstar';
    let currentBundle = NS_BUNDLES[currentSolution] || NS_BUNDLES[Object.keys(NS_BUNDLES)[0]];
    let activeNodeId = 'overview';
    let renderCounter = 0;

    try {{
      if (window.mermaid) {{
        mermaid.initialize({{
          startOnLoad: false,
          theme: 'neutral',
          securityLevel: 'loose'
        }});
      }}
    }} catch (e) {{
      console.warn('Mermaid init warning:', e);
    }}

    function onSolutionChange(solutionName) {{
      activeNodeId = 'overview';
      currentSolution = solutionName;
      currentBundle = NS_BUNDLES[solutionName] || {{ solution_name: solutionName, nodes: [], capabilities: [], decisions: [], components: [], invariants: [] }};
      document.getElementById('solutionSelect').value = solutionName;
      renderTree();
      selectView(activeNodeId);
    }}

    function renderTree() {{
      if (!currentBundle) return;
      document.getElementById('treeSolutionHeader').textContent = currentBundle.solution_name;
      document.getElementById('treeStatsBadge').textContent = `${{currentBundle.nodes.length}} Nodes`;

      const container = document.getElementById('treeContainer');
      let html = '';

      // 1. Solution Overview
      html += `
        <div onclick="selectView('overview')" class="cursor-pointer flex items-center gap-2 px-3 py-2 rounded-lg text-slate-700 hover:bg-slate-100 ${{activeNodeId === 'overview' ? 'tree-node-active' : ''}}">
          <span>📊</span> <span>Intent Overview & Stats</span>
        </div>
      `;

      // 2. Decisions & ADRs
      if (currentBundle.decisions && currentBundle.decisions.length > 0) {{
        html += `
          <div class="pt-2">
            <div onclick="selectView('decisions_overview')" class="cursor-pointer flex items-center justify-between px-3 py-1.5 text-slate-600 hover:text-slate-900 font-semibold">
              <span class="flex items-center gap-2"><span>📜</span> <span>Architectural Decisions</span></span>
              <span class="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.2 rounded font-mono">${{currentBundle.decisions.length}}</span>
            </div>
            <div class="pl-6 space-y-0.5 mt-1 border-l border-slate-200 ml-4">
              ${{currentBundle.decisions.map(d => `
                <div onclick="selectDecision('${{d.uri}}')" class="cursor-pointer px-2 py-1 rounded text-slate-600 hover:text-slate-900 hover:bg-slate-100 truncate ${{activeNodeId === 'dec_' + d.uri ? 'tree-node-active' : ''}}">
                  ${{d.title || d.uri}}
                </div>
              `).join('')}}
            </div>
          </div>
        `;
      }}

      // 3. Capabilities
      if (currentBundle.capabilities && currentBundle.capabilities.length > 0) {{
        html += `
          <div class="pt-2">
            <div onclick="selectView('capabilities_overview')" class="cursor-pointer flex items-center justify-between px-3 py-1.5 text-slate-600 hover:text-slate-900 font-semibold">
              <span class="flex items-center gap-2"><span>⚡</span> <span>Functional Capabilities</span></span>
              <span class="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.2 rounded font-mono">${{currentBundle.capabilities.length}}</span>
            </div>
            <div class="pl-6 space-y-0.5 mt-1 border-l border-slate-200 ml-4">
              ${{currentBundle.capabilities.map(c => `
                <div onclick="selectCapability('${{c.uri}}')" class="cursor-pointer px-2 py-1 rounded text-slate-600 hover:text-slate-900 hover:bg-slate-100 truncate ${{activeNodeId === 'cap_' + c.uri ? 'tree-node-active' : ''}}">
                  ${{c.title || c.name || c.uri}}
                </div>
              `).join('')}}
            </div>
          </div>
        `;
      }}

      // 4. Invariants
      if (currentBundle.invariants && currentBundle.invariants.length > 0) {{
        html += `
          <div class="pt-2">
            <div onclick="selectView('invariants_overview')" class="cursor-pointer flex items-center justify-between px-3 py-1.5 text-slate-600 hover:text-slate-900 font-semibold">
              <span class="flex items-center gap-2"><span>🛡️</span> <span>Executable Invariants</span></span>
              <span class="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.2 rounded font-mono">${{currentBundle.invariants.length}}</span>
            </div>
            <div class="pl-6 space-y-0.5 mt-1 border-l border-slate-200 ml-4">
              ${{currentBundle.invariants.map(inv => `
                <div onclick="selectInvariant('${{inv.uri}}')" class="cursor-pointer px-2 py-1 rounded text-slate-600 hover:text-slate-900 hover:bg-slate-100 truncate ${{activeNodeId === 'inv_' + inv.uri ? 'tree-node-active' : ''}}">
                  ${{inv.title || inv.name || inv.uri}}
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
      }} else if (viewId === 'decisions_overview') {{
        renderDecisionsOverview(viewport);
      }} else if (viewId === 'capabilities_overview') {{
        renderCapabilitiesOverview(viewport);
      }} else if (viewId === 'invariants_overview') {{
        renderInvariantsOverview(viewport);
      }}
    }}

    function selectDecision(uri) {{
      activeNodeId = 'dec_' + uri;
      renderTree();
      const decision = currentBundle.decisions.find(d => d.uri === uri);
      if (!decision) return;
      renderDecisionDetailView(decision);
    }}

    function selectCapability(uri) {{
      activeNodeId = 'cap_' + uri;
      renderTree();
      const cap = currentBundle.capabilities.find(c => c.uri === uri);
      if (!cap) return;
      renderCapabilityDetailView(cap);
    }}

    function selectInvariant(uri) {{
      activeNodeId = 'inv_' + uri;
      renderTree();
      const inv = currentBundle.invariants.find(i => i.uri === uri);
      if (!inv) return;
      renderInvariantDetailView(inv);
    }}

    function renderOverviewView(container) {{
      container.innerHTML = `
        <div class="space-y-6">
          <div class="flex items-center justify-between border-b border-slate-200 pb-4">
            <div>
              <h2 class="text-xl font-bold text-slate-900 flex items-center gap-2">
                📊 ${{currentBundle.display_name || currentBundle.solution_name}}
              </h2>
              <p class="text-xs text-slate-500 mt-1">Intent and governance specification for ${{currentBundle.solution_name}}</p>
            </div>
            <span class="text-xs px-3 py-1 rounded bg-blue-50 text-blue-700 border border-blue-200 font-semibold shadow-sm">
              ${{currentBundle.nodes.length}} Authority Nodes
            </span>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div class="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
              <div class="text-xs text-slate-500 font-medium uppercase">Capabilities</div>
              <div class="text-2xl font-bold text-slate-900 mt-1">${{currentBundle.capabilities.length}}</div>
            </div>
            <div class="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
              <div class="text-xs text-slate-500 font-medium uppercase">Decisions (ADRs)</div>
              <div class="text-2xl font-bold text-blue-700 mt-1">${{currentBundle.decisions.length}}</div>
            </div>
            <div class="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
              <div class="text-xs text-slate-500 font-medium uppercase">Invariants</div>
              <div class="text-2xl font-bold text-emerald-700 mt-1">${{currentBundle.invariants.length}}</div>
            </div>
            <div class="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
              <div class="text-xs text-slate-500 font-medium uppercase">Components</div>
              <div class="text-2xl font-bold text-indigo-700 mt-1">${{currentBundle.components.length}}</div>
            </div>
          </div>

          <div class="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
            <h3 class="text-sm font-bold text-slate-900">Functional Capabilities & Intent</h3>
            <div class="space-y-3">
              ${{currentBundle.capabilities.map(c => `
                <div onclick="selectCapability('${{c.uri}}')" class="cursor-pointer border border-slate-100 hover:border-blue-300 rounded-lg p-3 hover:bg-slate-50 transition">
                  <div class="flex justify-between items-center">
                    <span class="font-bold text-slate-900 text-xs">${{c.title || c.name}}</span>
                    <span class="text-[10px] font-mono text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">${{c.uri}}</span>
                  </div>
                  <p class="text-xs text-slate-600 mt-1">${{c.intent || c.description || ''}}</p>
                </div>
              `).join('')}}
            </div>
          </div>
        </div>
      `;
    }}

    function renderDecisionDetailView(decision) {{
      const container = document.getElementById('mainViewport');
      container.innerHTML = `
        <div class="space-y-6">
          <div class="flex items-center justify-between border-b border-slate-200 pb-4">
            <div>
              <div class="flex items-center gap-3">
                <h2 class="text-2xl font-bold text-slate-900">${{decision.title || decision.uri}}</h2>
                <span class="text-xs px-2.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 font-mono">${{decision.uri}}</span>
              </div>
              <p class="text-xs text-slate-500 mt-1.5">Architectural Decision Record</p>
            </div>
            <button onclick="selectView('overview')" class="text-xs bg-white hover:bg-slate-50 text-slate-700 px-3 py-1.5 rounded-lg border border-slate-200 transition shadow-sm font-medium">
              ← Back to Overview
            </button>
          </div>

          <div class="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
            <div>
              <div class="text-xs uppercase tracking-wider text-slate-500 font-semibold">Context & Problem</div>
              <div class="text-xs text-slate-800 mt-1.5 bg-slate-50 p-4 rounded-lg border border-slate-200 whitespace-pre-line">${{decision.context_and_problem || 'No context provided.'}}</div>
            </div>

            <div>
              <div class="text-xs uppercase tracking-wider text-slate-500 font-semibold">Decision Outcome & Rationale</div>
              <div class="text-xs text-slate-800 mt-1.5 bg-slate-50 p-4 rounded-lg border border-slate-200 whitespace-pre-line">${{decision.decision_outcome || 'No outcome recorded.'}}</div>
            </div>
          </div>
        </div>
      `;
    }}

    function renderCapabilityDetailView(cap) {{
      const container = document.getElementById('mainViewport');
      container.innerHTML = `
        <div class="space-y-6">
          <div class="flex items-center justify-between border-b border-slate-200 pb-4">
            <div>
              <div class="flex items-center gap-3">
                <h2 class="text-2xl font-bold text-slate-900">${{cap.title || cap.name}}</h2>
                <span class="text-xs px-2.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-mono">${{cap.uri}}</span>
              </div>
              <p class="text-xs text-slate-500 mt-1.5">Functional Capability Contract</p>
            </div>
            <button onclick="selectView('overview')" class="text-xs bg-white hover:bg-slate-50 text-slate-700 px-3 py-1.5 rounded-lg border border-slate-200 transition shadow-sm font-medium">
              ← Back to Overview
            </button>
          </div>

          <div class="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
            <div>
              <div class="text-xs uppercase tracking-wider text-slate-500 font-semibold">Business Intent</div>
              <p class="text-xs text-slate-800 mt-1 bg-slate-50 p-4 rounded-lg border border-slate-200">${{cap.intent || cap.description || 'No intent provided.'}}</p>
            </div>

            ${{cap.contract ? `
              <div>
                <div class="text-xs uppercase tracking-wider text-slate-500 font-semibold">Preconditions & Postconditions</div>
                <div class="mt-2 space-y-2">
                  ${{cap.contract.preconditions ? cap.contract.preconditions.map(p => `<div class="text-xs bg-amber-50 text-amber-900 p-2.5 rounded border border-amber-200"><strong>PRE:</strong> ${{p.description || p}}</div>`).join('') : ''}}
                  ${{cap.contract.postconditions ? cap.contract.postconditions.map(p => `<div class="text-xs bg-emerald-50 text-emerald-900 p-2.5 rounded border border-emerald-200"><strong>POST:</strong> ${{p.description || p}}</div>`).join('') : ''}}
                </div>
              </div>
            ` : ''}}
          </div>
        </div>
      `;
    }}

    function renderInvariantDetailView(inv) {{
      const container = document.getElementById('mainViewport');
      container.innerHTML = `
        <div class="space-y-6">
          <div class="flex items-center justify-between border-b border-slate-200 pb-4">
            <div>
              <div class="flex items-center gap-3">
                <h2 class="text-2xl font-bold text-slate-900">${{inv.title || inv.name}}</h2>
                <span class="text-xs px-2.5 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200 font-mono">${{inv.uri}}</span>
              </div>
              <p class="text-xs text-slate-500 mt-1.5">Executable Architectural Invariant</p>
            </div>
            <button onclick="selectView('overview')" class="text-xs bg-white hover:bg-slate-50 text-slate-700 px-3 py-1.5 rounded-lg border border-slate-200 transition shadow-sm font-medium">
              ← Back to Overview
            </button>
          </div>

          <div class="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
            <div>
              <div class="text-xs uppercase tracking-wider text-slate-500 font-semibold">Invariant Policy Expression</div>
              <pre class="text-xs font-mono text-emerald-800 mt-1 bg-slate-50 p-4 rounded-lg border border-slate-200">${{inv.expression || inv.evaluator_class || 'Declared Policy Invariant'}}</pre>
            </div>
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
