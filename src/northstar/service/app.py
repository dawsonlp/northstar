"""FastAPI Service and Solution Control Plane Web Portal for Northstar."""

from collections import defaultdict
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

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


def create_app(workspace_root: Optional[str | Path] = None) -> FastAPI:
    """Factory creating configured FastAPI application."""
    root_path = Path(workspace_root or os.getenv("NORTHSTAR_WORKSPACE_ROOT", "."))
    
    app = FastAPI(
        title="Northstar Intent & Governance Control Plane",
        description="The Intent, Requirements, and Governance Authority for the Tripartite Semantic Federation",
        version="0.1.0",
    )

    # Initialize catalog
    if (root_path / "intent").exists() or (root_path / "adrs").exists() or (root_path / ".northstar").exists():
        catalog = NorthstarCatalog.load(root_path)
    else:
        catalog = NorthstarCatalog()

    # Store catalog in app state
    app.state.catalog = catalog
    app.state.workspace_root = root_path

    # Pydantic Request Models
    class NodePayload(BaseModel):
        type: str  # CapabilitySpec, ComponentSpec, DecisionSpec, InvariantSpec, PolicySpec, QualitySpec, WorkflowSpec
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

    @app.get("/health")
    def health_check():
        return {
            "status": "ok",
            "workspace_root": str(app.state.workspace_root),
            "node_count": catalog.graph.node_count,
            "edge_count": catalog.graph.edge_count,
        }

    @app.get("/api/v1/graph")
    def get_graph():
        """Get the full serialized intent multi-graph."""
        return catalog.graph.to_dict()

    @app.get("/api/v1/nodes/{uri:path}")
    def get_node(uri: str):
        """Retrieve a specific intent node by canonical URI."""
        node = catalog.graph.get_node(uri)
        if not node:
            raise HTTPException(status_code=404, detail=f"Intent node '{uri}' not found")
        return {
            "uri": node.uri,
            "type": node.__class__.__name__,
            "data": node.to_dict(),
        }

    @app.post("/api/v1/nodes")
    def register_node(payload: NodePayload):
        """Register or update an intent node."""
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
            raise HTTPException(status_code=400, detail=f"Unsupported node type: {node_type}")

        catalog.add(node)
        return {"status": "registered", "uri": node.uri}

    @app.post("/api/v1/links")
    def register_link(payload: LinkPayload):
        """Register a typed relational edge."""
        try:
            verb = RelationalVerb(payload.verb)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid relational verb: {payload.verb}")

        edge = catalog.link(payload.source, verb, payload.target, payload.metadata)
        return {"status": "linked", "edge": edge.to_dict()}

    @app.get("/api/v1/closure")
    def get_closure(target_uri: str = Query(..., description="Target CSI or intent URI")):
        """Resolve the 2-hop governing intent closure for prompt context injection."""
        closure = catalog.get_governing_intent(target_uri)
        return {
            "target_symbol": closure.target_symbol,
            "capabilities": [c.to_dict() for c in closure.capabilities],
            "components": [c.to_dict() for c in closure.components],
            "decisions": [d.to_dict() for d in closure.decisions],
            "constraints": [c.to_dict() for c in closure.constraints],
            "policies": [p.to_dict() for p in closure.policies],
            "qualities": [q.to_dict() for q in closure.qualities],
            "markdown_prompt_context": closure.to_markdown_prompt_context(),
        }

    @app.post("/api/v1/validate")
    def validate_code(payload: ValidatePayload):
        """Validate proposed code AST against active invariants."""
        violations = catalog.validate_code(payload.target_symbol, payload.code_content, payload.metadata)
        return {
            "target_symbol": payload.target_symbol,
            "passed": len(violations) == 0,
            "violation_count": len(violations),
            "violations": [v.to_dict() for v in violations],
        }

    @app.get("/api/v1/solutions")
    def get_solutions():
        """Retrieve high-level solution stage visualizer metrics."""
        components = catalog.graph.get_nodes_by_type(ComponentSpec)
        capabilities = catalog.graph.get_nodes_by_type(CapabilitySpec)
        decisions = catalog.graph.get_nodes_by_type(DecisionSpec)
        invariants = catalog.graph.get_nodes_by_type(InvariantSpec)

        solutions: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "components": [],
            "capabilities": [],
            "decisions": [],
            "invariants": [],
            "unimplemented_capabilities": [],
        })

        for comp in components:
            sol_name = comp.domain or "general"
            solutions[sol_name]["components"].append(comp.to_dict())

        for cap in capabilities:
            sol_name = cap.component or "general"
            solutions[sol_name]["capabilities"].append(cap.to_dict())
            incoming = catalog.graph.get_incoming_edges(cap.uri, RelationalVerb.SATISFIES)
            if not incoming:
                solutions[sol_name]["unimplemented_capabilities"].append(cap.uri)

        for dec in decisions:
            # Domain from URI
            domain = dec.uri.replace("decision://", "").split("/")[0]
            solutions[domain]["decisions"].append(dec.to_dict())

        for inv in invariants:
            domain = inv.uri.replace("constraint://", "").split("/")[0]
            solutions[domain]["invariants"].append(inv.to_dict())

        # Determine stage for each solution
        result = []
        for sol_name, data in solutions.items():
            total_caps = len(data["capabilities"])
            unimplemented = len(data["unimplemented_capabilities"])
            implemented = total_caps - unimplemented

            if total_caps == 0:
                stage = "1. INTENT ELICITATION"
                progress = 15
            elif implemented == 0:
                stage = "2. DATA & ARCHITECTURE MODELING"
                progress = 40
            elif implemented < total_caps:
                stage = "3. CODE IMPLEMENTATION"
                progress = int(40 + (implemented / total_caps) * 45)
            else:
                stage = "4. INVARIANT CERTIFIED"
                progress = 100

            result.append({
                "solution_name": sol_name,
                "stage": stage,
                "progress_percentage": progress,
                "total_capabilities": total_caps,
                "implemented_capabilities": implemented,
                "unimplemented_capabilities": unimplemented,
                "total_components": len(data["components"]),
                "total_decisions": len(data["decisions"]),
                "total_invariants": len(data["invariants"]),
            })

        return {"solutions": result}

    @app.post("/api/v1/solutions/{solution_name}/project")
    def project_solution_docs(solution_name: str, target_dir: Optional[str] = None):
        """Project a solution's intent graph into a structured documentation suite on disk."""
        target_path = Path(target_dir or (app.state.workspace_root / solution_name / "docs" / "requirements"))
        generated = catalog.project_solution_docs(solution_name, target_path)
        return {
            "status": "projected",
            "solution_name": solution_name,
            "target_dir": str(target_path),
            "file_count": len(generated),
            "files": [str(p) for p in generated],
        }

    @app.get("/", response_class=HTMLResponse)
    @app.get("/dashboard", response_class=HTMLResponse)
    def render_dashboard():
        """Serve the Solution Control Plane Single-Page Web Dashboard."""
        return DASHBOARD_HTML

    return app



DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Northstar 🧭 Solution Control Plane</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0d1117;
      --card-bg: #161b22;
      --border: #30363d;
      --text: #c9d1d9;
      --text-muted: #8b949e;
      --text-bright: #f0f6fc;
      --accent-cyan: #58a6ff;
      --accent-green: #3fb950;
      --accent-yellow: #d29922;
      --accent-red: #f85149;
      --accent-purple: #bc8cff;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      color: var(--text);
      font-family: 'Plus Jakarta Sans', sans-serif;
      line-height: 1.5;
      padding-bottom: 40px;
    }
    header {
      background-color: var(--card-bg);
      border-bottom: 1px solid var(--border);
      padding: 16px 32px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: sticky;
      top: 0;
      z-index: 100;
    }
    .logo {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 20px;
      font-weight: 700;
      color: var(--text-bright);
    }
    .badge {
      font-size: 11px;
      font-family: 'JetBrains Mono', monospace;
      padding: 3px 8px;
      border-radius: 12px;
      background: rgba(88, 166, 255, 0.15);
      color: var(--accent-cyan);
      border: 1px solid rgba(88, 166, 255, 0.3);
    }
    .container {
      max-width: 1300px;
      margin: 32px auto;
      padding: 0 24px;
    }
    .tabs {
      display: flex;
      gap: 12px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 24px;
    }
    .tab-btn {
      background: none;
      border: none;
      color: var(--text-muted);
      font-size: 15px;
      font-weight: 600;
      padding: 12px 16px;
      cursor: pointer;
      position: relative;
    }
    .tab-btn.active {
      color: var(--accent-cyan);
    }
    .tab-btn.active::after {
      content: '';
      position: absolute;
      bottom: -1px;
      left: 0;
      right: 0;
      height: 2px;
      background: var(--accent-cyan);
    }
    .tab-content { display: none; }
    .tab-content.active { display: block; }
    
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
      gap: 20px;
      margin-bottom: 32px;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 20px;
    }
    .card-title {
      font-size: 16px;
      font-weight: 600;
      color: var(--text-bright);
      margin-bottom: 12px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .progress-bar-bg {
      background: rgba(255, 255, 255, 0.08);
      height: 8px;
      border-radius: 4px;
      overflow: hidden;
      margin: 12px 0;
    }
    .progress-fill {
      background: linear-gradient(90deg, var(--accent-cyan), var(--accent-green));
      height: 100%;
      transition: width 0.5s ease;
    }
    .metric-row {
      display: flex;
      justify-content: space-between;
      font-size: 13px;
      color: var(--text-muted);
      margin-top: 6px;
    }
    .metric-val {
      font-family: 'JetBrains Mono', monospace;
      font-weight: 600;
      color: var(--text-bright);
    }
    pre, code {
      font-family: 'JetBrains Mono', monospace;
      background: rgba(0,0,0,0.3);
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 13px;
    }
    .code-block {
      background: #090d13;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 16px;
      overflow-x: auto;
      margin-top: 12px;
    }
    .btn {
      background: var(--accent-cyan);
      color: #000;
      font-weight: 600;
      border: none;
      padding: 8px 16px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 13px;
    }
    .btn:hover { opacity: 0.9; }
    .form-group {
      margin-bottom: 14px;
    }
    label {
      display: block;
      font-size: 13px;
      font-weight: 600;
      margin-bottom: 6px;
      color: var(--text-bright);
    }
    input, textarea, select {
      width: 100%;
      background: #090d13;
      border: 1px solid var(--border);
      color: var(--text-bright);
      padding: 10px 12px;
      border-radius: 6px;
      font-family: inherit;
      font-size: 14px;
    }
    input:focus, textarea:focus, select:focus {
      outline: none;
      border-color: var(--accent-cyan);
    }
  </style>
</head>
<body>
  <header>
    <div class="logo">
      <span>🧭 Northstar Intent Authority</span>
      <span class="badge">Tripartite Semantic Federation</span>
    </div>
    <div id="health-status">
      <span class="badge" style="background: rgba(63,185,80,0.15); color: var(--accent-green); border-color: rgba(63,185,80,0.3);">
        ● Engine Live (<span id="node-count">0</span> Nodes)
      </span>
    </div>
  </header>

  <div class="container">
    <div class="tabs">
      <button class="tab-btn active" onclick="switchTab('solutions')">📊 Solutions & Stage Visualizer</button>
      <button class="tab-btn" onclick="switchTab('elicitation')">✍️ Stakeholder Elicitation</button>
      <button class="tab-btn" onclick="switchTab('graph')">🌐 Intent Knowledge Graph</button>
      <button class="tab-btn" onclick="switchTab('closure')">🔍 Context Slicer & Invariant Gate</button>
    </div>

    <!-- TAB 1: SOLUTIONS & STAGE VISUALIZER -->
    <div id="tab-solutions" class="tab-content active">
      <h2 style="font-size: 20px; color: var(--text-bright); margin-bottom: 16px;">Active Solutions Lifecycle Control Plane</h2>
      <div id="solutions-grid" class="grid">
        <div class="card"><p style="color: var(--text-muted);">Loading active solutions...</p></div>
      </div>
    </div>

    <!-- TAB 2: STAKEHOLDER ELICITATION -->
    <div id="tab-elicitation" class="tab-content">
      <div class="grid">
        <div class="card" style="grid-column: span 2;">
          <div class="card-title">
            <span>✍️ Elicit Capability Operational Contract</span>
            <span class="badge">req:// URI Generation</span>
          </div>
          <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 16px;">
            Capture formal operational contracts (preconditions, guarantees, failure modes) directly from human stakeholders.
          </p>
          <form id="elicit-form" onsubmit="submitCapability(event)">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
              <div class="form-group">
                <label>Component / Bounded Context</label>
                <input type="text" id="cap-component" placeholder="e.g. groundtruth/logical" required>
              </div>
              <div class="form-group">
                <label>Capability Slug</label>
                <input type="text" id="cap-slug" placeholder="e.g. verify-state-transition" required>
              </div>
            </div>
            <div class="form-group">
              <label>Human Purpose & Intent</label>
              <textarea id="cap-intent" rows="2" placeholder="e.g. Verifies finite state machine transitions against legal entity state graphs." required></textarea>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
              <div class="form-group">
                <label>Preconditions (Semicolon-separated)</label>
                <input type="text" id="cap-pre" placeholder="e.g. Entity exists; Current state is valid">
              </div>
              <div class="form-group">
                <label>Postconditions (Semicolon-separated)</label>
                <input type="text" id="cap-post" placeholder="e.g. State advanced; Transition audit log persisted">
              </div>
            </div>
            <div class="form-group">
              <label>Failure Modes (Error Name : Trigger Condition : Recovery Action)</label>
              <input type="text" id="cap-failure" placeholder="e.g. IllegalTransitionError : State from_state -> to_state invalid : Reject and return 409">
            </div>
            <button type="submit" class="btn">Register Intent Capability</button>
          </form>
        </div>
      </div>
    </div>

    <!-- TAB 3: GRAPH EXPLORER -->
    <div id="tab-graph" class="tab-content">
      <div class="card">
        <div class="card-title">
          <span>🌐 Raw Intent Multi-Graph Explorer</span>
          <button class="btn" onclick="fetchGraph()">Refresh Graph</button>
        </div>
        <pre id="graph-json" class="code-block" style="max-height: 500px;"></pre>
      </div>
    </div>

    <!-- TAB 4: CLOSURE & INVARIANT GATE -->
    <div id="tab-closure" class="tab-content">
      <div class="grid">
        <div class="card">
          <div class="card-title">🔍 Query 2-Hop Intent Closure</div>
          <div class="form-group">
            <label>Target Symbol CSI or Capability URI</label>
            <input type="text" id="closure-target" placeholder="e.g. csi://northstar/api.NorthstarCatalog.get_governing_intent">
          </div>
          <button class="btn" onclick="queryClosure()">Slice Intent Context</button>
          <pre id="closure-result" class="code-block" style="max-height: 350px; margin-top: 16px;"></pre>
        </div>

        <div class="card">
          <div class="card-title">🛡️ Pre-Commit AST Invariant Gate</div>
          <div class="form-group">
            <label>Code Snippet to Test</label>
            <textarea id="val-code" rows="6" placeholder="def my_function():\n    pass"></textarea>
          </div>
          <button class="btn" onclick="testInvariantGate()">Validate Invariants</button>
          <pre id="val-result" class="code-block" style="max-height: 250px; margin-top: 16px;"></pre>
        </div>
      </div>
    </div>
  </div>

  <script>
    function switchTab(tabId) {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      event.target.classList.add('active');
      document.getElementById('tab-' + tabId).classList.add('active');
      if (tabId === 'solutions') fetchSolutions();
      if (tabId === 'graph') fetchGraph();
    }

    async function fetchHealth() {
      const res = await fetch('/health');
      const data = await res.json();
      document.getElementById('node-count').innerText = data.node_count;
    }

    async function fetchSolutions() {
      const res = await fetch('/api/v1/solutions');
      const data = await res.json();
      const grid = document.getElementById('solutions-grid');
      grid.innerHTML = '';
      if (data.solutions.length === 0) {
        grid.innerHTML = '<div class="card"><p style="color: var(--text-muted);">No solutions loaded yet. Use the Elicitation portal to add intent!</p></div>';
        return;
      }
      data.solutions.forEach(s => {
        grid.innerHTML += `
          <div class="card">
            <div class="card-title">
              <span>📦 Solution: ${s.solution_name}</span>
              <span class="badge">${s.stage}</span>
            </div>
            <div class="progress-bar-bg">
              <div class="progress-fill" style="width: ${s.progress_percentage}%"></div>
            </div>
            <div class="metric-row"><span>Maturity Progress:</span><span class="metric-val">${s.progress_percentage}%</span></div>
            <div class="metric-row"><span>Total Capabilities:</span><span class="metric-val">${s.total_capabilities}</span></div>
            <div class="metric-row"><span>Implemented / Unimplemented:</span><span class="metric-val">${s.implemented_capabilities} / ${s.unimplemented_capabilities}</span></div>
            <div class="metric-row"><span>Architectural Decisions (ADRs):</span><span class="metric-val">${s.total_decisions}</span></div>
            <div class="metric-row"><span>Active Invariant Guardrails:</span><span class="metric-val">${s.total_invariants}</span></div>
          </div>
        `;
      });
    }

    async function submitCapability(e) {
      e.preventDefault();
      const comp = document.getElementById('cap-component').value.trim();
      const slug = document.getElementById('cap-slug').value.trim();
      const intent = document.getElementById('cap-intent').value.trim();
      const preRaw = document.getElementById('cap-pre').value.trim();
      const postRaw = document.getElementById('cap-post').value.trim();
      const failRaw = document.getElementById('cap-failure').value.trim();

      const pre = preRaw ? preRaw.split(';').map(d => ({ description: d.trim() })) : [];
      const post = postRaw ? postRaw.split(';').map(d => ({ description: d.trim() })) : [];
      const failures = [];
      if (failRaw) {
        const parts = failRaw.split(':').map(p => p.trim());
        if (parts.length >= 3) {
          failures.push({ error_name: parts[0], trigger_condition: parts[1], recovery_action: parts[2] });
        }
      }

      const uri = `req://${comp.replace('component://', '')}/${slug}`;
      const payload = {
        type: "CapabilitySpec",
        data: {
          uri: uri,
          title: slug.replace(/-/g, ' ').toUpperCase(),
          intent: intent,
          component: comp,
          contract: { preconditions: pre, postconditions: post, state_transitions: [] },
          failure_modes: failures,
        }
      };

      const res = await fetch('/api/v1/nodes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const result = await res.json();
      alert('✅ Registered Capability: ' + result.uri);
      fetchHealth();
      fetchSolutions();
    }

    async function fetchGraph() {
      const res = await fetch('/api/v1/graph');
      const data = await res.json();
      document.getElementById('graph-json').innerText = JSON.stringify(data, null, 2);
    }

    async function queryClosure() {
      const target = document.getElementById('closure-target').value.trim();
      if (!target) return;
      const res = await fetch('/api/v1/closure?target_uri=' + encodeURIComponent(target));
      const data = await res.json();
      document.getElementById('closure-result').innerText = data.markdown_prompt_context || JSON.stringify(data, null, 2);
    }

    async function testInvariantGate() {
      const code = document.getElementById('val-code').value;
      const res = await fetch('/api/v1/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_symbol: "csi://test/Service.method", code_content: code })
      });
      const data = await res.json();
      document.getElementById('val-result').innerText = JSON.stringify(data, null, 2);
    }

    fetchHealth();
    fetchSolutions();
  </script>
</body>
</html>
"""

app = create_app()

