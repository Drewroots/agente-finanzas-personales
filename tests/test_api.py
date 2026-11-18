"""Pruebas de la API REST, el dashboard y los gráficos (Capa 1 y 5)."""
import pytest

import app as app_mod
import charts
from scripts import load_demo
from storage import DataStore
from test_agent import FakeClient, text


@pytest.fixture
def client(store):
    agent_client = FakeClient([text("Respuesta de prueba")] * 5)
    from agent import FinanceAgent
    app = app_mod.create_app(store, agent_factory=lambda s: FinanceAgent(s, client=agent_client))
    return app.test_client()


def test_pages_render(client):
    for path in ("/", "/dashboard", "/transactions"):
        r = client.get(path)
        assert r.status_code == 200 and b"Finanzas" in r.data


def test_transaction_crud(client):
    r = client.post("/api/transactions", json={"type": "expense", "amount": 25000, "category": "Transporte", "description": "Bus"})
    assert r.status_code == 201
    tid = r.get_json()["transaction"]["id"]
    assert client.get("/api/transactions").get_json()["matched"] == 1
    assert client.put(f"/api/transactions/{tid}", json={"amount": 30000}).get_json()["transaction"]["amount"] == "30000.00"
    assert client.delete(f"/api/transactions/{tid}").status_code == 200
    assert client.delete(f"/api/transactions/{tid}").status_code == 404


def test_validation_errors_are_400(client):
    assert client.post("/api/transactions", json={"type": "expense", "amount": -1}).status_code == 400
    assert client.post("/api/transactions", json={}).status_code == 400
    assert client.get("/api/summary?period=2026-99").status_code == 400
    assert client.get("/api/nope").status_code == 404


def test_assets_liabilities_investments_and_summary(client):
    assert client.post("/api/assets", json={"name": "Cuenta", "type": "ahorros", "value": 1000}).status_code == 201
    liab = client.post("/api/liabilities", json={"name": "Préstamo", "type": "prestamo", "value": 400}).get_json()["item"]
    assert client.post("/api/investments", json={"name": "CDT", "asset_class": "renta_fija", "value": 600}).status_code == 201
    s = client.get("/api/summary").get_json()
    assert s["net_worth"]["net_worth"] == "1200.00"
    assert client.put(f"/api/liabilities/{liab['id']}", json={"value": 100}).status_code == 200
    assert client.get("/api/networth").get_json()["result"]["net_worth"] == "1500.00"
    assert client.delete(f"/api/liabilities/{liab['id']}").status_code == 200


def test_budget_goal_and_simulation_endpoints(client):
    assert client.put("/api/budgets/Alimentación", json={"amount": 500000}).status_code == 200
    assert client.get("/api/budgets").status_code == 200
    g = client.post("/api/goals", json={"name": "Meta", "target_amount": 1000}).get_json()["goal"]
    assert client.delete(f"/api/goals/{g['id']}").status_code == 200
    r = client.post("/api/investments/simulate", json={"principal": 1000, "annual_rate_pct": 5, "years": 2})
    assert r.get_json()["hypothetical"] is True


def test_chat_endpoint(client):
    r = client.post("/api/chat", json={"message": "Hola"})
    assert r.status_code == 200 and r.get_json()["answer"] == "Respuesta de prueba"
    assert client.post("/api/chat", json={"message": ""}).status_code == 400


def test_chat_without_api_key_returns_503(store, monkeypatch):
    import agent as agent_mod
    monkeypatch.setattr(agent_mod.config, "PROVIDER", "anthropic")
    monkeypatch.setattr(agent_mod.config, "ANTHROPIC_API_KEY", None)
    app = app_mod.create_app(store)
    assert app.test_client().post("/api/chat", json={"message": "Hola"}).status_code == 503


def test_all_charts_render_png_with_and_without_data(store):
    for name in charts.CHARTS:  # sin datos -> marcador de posición
        assert charts.render_png(name, store.snapshot(), "2026-11")[:8] == b"\x89PNG\r\n\x1a\n"
    demo = load_demo.build()
    for name in charts.CHARTS:
        assert len(charts.render_png(name, demo)) > 3000


def test_chart_endpoint_and_unknown_chart(client):
    assert client.get("/api/charts/income_vs_expenses.png").mimetype == "image/png"
    assert client.get("/api/charts/zzz.png").status_code == 404


def test_demo_data_is_valid_and_flagged(tmp_path):
    p = tmp_path / "demo.json"
    import json
    p.write_text(json.dumps(load_demo.build()), encoding="utf-8")
    s = DataStore(p)
    assert s.data["profile"]["demo"] is True and s.data["transactions"]
