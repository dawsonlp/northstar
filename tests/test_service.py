"""Unit and integration tests for Northstar FastAPI service and Web Control Plane."""

import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from northstar.service.app import create_app


def test_service_endpoints_and_lifecycle():
    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace_root = Path(tmp_dir)
        app = create_app(workspace_root)
        client = TestClient(app)

        # 1. Health check
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["node_count"] == 0

        # 2. Register Component via API
        comp_payload = {
            "type": "ComponentSpec",
            "data": {
                "uri": "component://ecommerce/payments",
                "name": "Payments Engine",
                "domain": "ecommerce",
                "exported_capabilities": ["req://payments/charge-card"],
            },
        }
        res = client.post("/api/v1/nodes", json=comp_payload)
        assert res.status_code == 200
        assert res.json()["uri"] == "component://ecommerce/payments"

        # 3. Register Capability via API
        cap_payload = {
            "type": "CapabilitySpec",
            "data": {
                "uri": "req://payments/charge-card",
                "title": "Charge Card",
                "intent": "Charges customer credit card.",
                "component": "payments",
                "contract": {
                    "preconditions": [{"description": "Account is active"}],
                    "postconditions": [{"description": "Payment recorded"}],
                    "state_transitions": [],
                },
            },
        }
        res = client.post("/api/v1/nodes", json=cap_payload)
        assert res.status_code == 200
        assert res.json()["uri"] == "req://payments/charge-card"

        # 4. Register Link
        link_payload = {
            "source": "csi://ecommerce/services/PaymentService.charge",
            "verb": "SATISFIES",
            "target": "req://payments/charge-card",
        }
        res = client.post("/api/v1/links", json=link_payload)
        assert res.status_code == 200

        # 5. Query Graph
        res = client.get("/api/v1/graph")
        assert res.status_code == 200
        graph_data = res.json()
        assert "component://ecommerce/payments" in graph_data["nodes"]
        assert "req://payments/charge-card" in graph_data["nodes"]
        assert len(graph_data["edges"]) == 1

        # 6. Query Closure
        res = client.get("/api/v1/closure?target_uri=csi://ecommerce/services/PaymentService.charge")
        assert res.status_code == 200
        closure_data = res.json()
        assert len(closure_data["capabilities"]) == 1
        assert "Charge Card" in closure_data["markdown_prompt_context"]

        # 7. Query Solutions Stage Breakdown
        res = client.get("/api/v1/solutions")
        assert res.status_code == 200
        solutions_data = res.json()["solutions"]
        assert len(solutions_data) >= 1
        assert any(s["solution_name"] == "payments" or s["solution_name"] == "ecommerce" for s in solutions_data)

        # 8. Test Dashboard HTML
        res = client.get("/dashboard")
        assert res.status_code == 200
        assert "Northstar Intent Authority" in res.text
        assert "Solution Control Plane" in res.text
