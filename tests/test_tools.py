import json

import pytest

from storage import DataStore, StorageError
from tools import TOOL_DEFINITIONS, execute_tool


def call(store, tool_name, /, **params):
    return execute_tool(store, tool_name, params)


def test_four_tools_registered_with_valid_schemas():
    names = {t["name"] for t in TOOL_DEFINITIONS}
    assert names == {"manage_transaction", "calculate_net_worth", "analyze_finances", "investment_analysis"}
    for t in TOOL_DEFINITIONS:
        assert t["input_schema"]["required"] == ["action"]


def test_add_and_list_transactions(store):
    r = call(store, "manage_transaction", action="add", type="income", amount=3500000, category="salario", date="2026-11-01")
    assert r["status"] == "ok" and r["transaction"]["category"] == "Salario"
    call(store, "manage_transaction", action="add", type="expense", amount=45000.5, category="alimentacion", date="2026-11-03")
    lst = call(store, "manage_transaction", action="list", period="2026-11")
    assert lst["matched"] == 2 and lst["total_expenses"] == "45000.50"


def test_persistence_roundtrip(store):
    call(store, "manage_transaction", action="add", type="expense", amount=100, category="Salud")
    again = DataStore(store.path)
    assert len(again.data["transactions"]) == 1


@pytest.mark.parametrize("params", [
    dict(action="add", type="expense"),                         # falta monto
    dict(action="add", type="expense", amount=-5),
    dict(action="add", type="otro", amount=5),
    dict(action="add", type="expense", amount=5, category="Viajes"),
    dict(action="add", type="expense", amount=5, date="31/12/2026"),
    dict(action="add", type="expense", amount=5, description="tarjeta 4111111111111111"),
    dict(action="zzz"),
])
def test_invalid_inputs_return_error_and_store_nothing(store, params):
    assert call(store, "manage_transaction", **params)["status"] == "error"
    assert store.data["transactions"] == []


def test_delete_requires_confirmation(store):
    tid = call(store, "manage_transaction", action="add", type="expense", amount=10)["transaction"]["id"]
    r = call(store, "manage_transaction", action="delete", transaction_id=tid)
    assert r["status"] == "needs_confirmation" and len(store.data["transactions"]) == 1
    assert call(store, "manage_transaction", action="delete", transaction_id=tid, confirm=True)["status"] == "ok"
    assert store.data["transactions"] == []


def test_update_requires_confirmation_and_applies(store):
    tid = call(store, "manage_transaction", action="add", type="expense", amount=10, category="Salud")["transaction"]["id"]
    r = call(store, "manage_transaction", action="update", transaction_id=tid, amount=99)
    assert r["status"] == "needs_confirmation" and store.data["transactions"][0]["amount"] == "10.00"
    call(store, "manage_transaction", action="update", transaction_id=tid, amount=99, confirm=True)
    assert store.data["transactions"][0]["amount"] == "99.00"


def test_not_found(store):
    r = call(store, "manage_transaction", action="delete", transaction_id="t_zzz", confirm=True)
    assert r["status"] == "error" and r["code"] == "not_found"


def test_net_worth_flow(store):
    call(store, "calculate_net_worth", action="add_asset", name="Cuenta", item_type="ahorros", value=2000000)
    call(store, "calculate_net_worth", action="add_liability", name="Préstamo", item_type="prestamo", value=500000)
    call(store, "investment_analysis", action="add_investment", name="CDT", asset_class="renta_fija", value=1000000)
    r = call(store, "calculate_net_worth", action="calculate", save_snapshot=True)
    assert r["result"]["net_worth"] == "2500000.00"
    assert r["snapshot"]["net_worth"] == "2500000.00" and len(store.data["history"]) == 1


def test_net_worth_empty_warns(store):
    assert "warning" in call(store, "calculate_net_worth", action="calculate")


def test_remove_asset_needs_confirm(store):
    aid = call(store, "calculate_net_worth", action="add_asset", name="X", item_type="otros", value=1)["item"]["id"]
    assert call(store, "calculate_net_worth", action="remove_item", item_id=aid)["status"] == "needs_confirmation"
    assert call(store, "calculate_net_worth", action="remove_item", item_id=aid, confirm=True)["status"] == "ok"


def test_analyze_summary_and_budget(populated):
    s = call(populated, "analyze_finances", action="summary", period="2026-11")
    assert s["cash_flow"]["cash_flow"] == "1800000.00" and s["interpretation"]
    assert call(populated, "analyze_finances", action="set_budget", category="Alimentación", amount=500000)["status"] == "ok"
    # cambiar un presupuesto existente exige confirmación
    r = call(populated, "analyze_finances", action="set_budget", category="Alimentación", amount=700000)
    assert r["status"] == "needs_confirmation"
    b = call(populated, "analyze_finances", action="budget_status", period="2026-11")
    assert b["budget"]["items"][0]["status"] == "excedido"


def test_analyze_compare_recurring_report(populated):
    assert call(populated, "analyze_finances", action="compare_periods", period="2026-11")["status"] == "ok"
    assert len(call(populated, "analyze_finances", action="recurring")["recurring"]) == 2
    assert call(populated, "analyze_finances", action="report", period="2026-11")["report"]["period"] == "2026-11"


def test_goals_lifecycle(store):
    g = call(store, "analyze_finances", action="goal_add", name="Viaje", target_amount=1000000, current_amount=100000)
    gid = g["goal"]["id"]
    assert g["goal"]["progress_pct"] == "10.00"
    assert call(store, "analyze_finances", action="goal_update", goal_id=gid, current_amount=500000)["status"] == "needs_confirmation"
    r = call(store, "analyze_finances", action="goal_update", goal_id=gid, current_amount=500000, confirm=True)
    assert r["goal"]["progress_pct"] == "50.00"


def test_investment_simulation_is_labeled_hypothetical(store):
    r = call(store, "investment_analysis", action="simulate", principal=1000000, monthly_contribution=0, annual_rate_pct=10, years=2)
    assert r["hypothetical"] is True and r["simulation"]["final_nominal"] == "1210000.00"
    assert r["disclaimer"] and r["warnings"]


def test_compare_scenarios_and_explain(store):
    r = call(store, "investment_analysis", action="compare_scenarios", principal=1000, years=3,
             scenarios=[{"label": "Bajo", "annual_rate_pct": 2}, {"label": "Alto", "annual_rate_pct": 9}])
    assert [s["label"] for s in r["scenarios"]] == ["Bajo", "Alto"]
    assert "diversificar" in call(store, "investment_analysis", action="explain", concept="Diversificación")["explanation"].lower()
    assert call(store, "investment_analysis", action="compare_scenarios", years=3, principal=1, scenarios=[{"annual_rate_pct": 1}])["status"] == "error"


def test_unknown_tool_and_bad_input(store):
    assert execute_tool(store, "nope", {})["code"] == "unknown_tool"
    assert execute_tool(store, "manage_transaction", None)["status"] == "error"


def test_results_are_json_serializable(populated):
    for name, params in [("analyze_finances", dict(action="report", period="2026-11")),
                         ("calculate_net_worth", dict(action="calculate")),
                         ("investment_analysis", dict(action="allocation"))]:
        json.dumps(execute_tool(populated, name, params))


def test_backup_created_and_corruption_recovery(store):
    call(store, "manage_transaction", action="add", type="expense", amount=10)
    call(store, "manage_transaction", action="add", type="expense", amount=20)
    assert list(store.backup_dir.glob("finanzas_*.json"))
    store.path.write_text("{ esto no es json", encoding="utf-8")
    recovered = DataStore(store.path)  # recupera desde la última copia válida
    assert len(recovered.data["transactions"]) >= 1


def test_corruption_without_backup_raises(tmp_path):
    p = tmp_path / "f.json"
    p.write_text("[]", encoding="utf-8")
    with pytest.raises(StorageError):
        DataStore(p)
