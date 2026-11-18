from decimal import Decimal

import pytest

import functions as fn


def test_to_money_uses_decimal_without_float_error():
    assert fn.to_money(0.1) + fn.to_money(0.2) == Decimal("0.30")
    assert fn.to_money("1500000") == Decimal("1500000.00")


@pytest.mark.parametrize("bad", [None, True, "abc", -5, 0, float("nan"), "1e30"])
def test_to_money_rejects_invalid(bad):
    with pytest.raises(fn.FinanceError):
        fn.to_money(bad)


def test_sensitive_numbers_rejected():
    with pytest.raises(fn.FinanceError):
        fn.validate_text("tarjeta 4111 1111 1111 1111", "description")
    assert fn.validate_text("Pago 12345", "description") == "Pago 12345"


def test_period_helpers():
    assert fn.shift_period("2026-01", -1) == "2025-12"
    assert fn.shift_period("2026-11", 3) == "2027-02"
    with pytest.raises(fn.FinanceError):
        fn.validate_period("2026-13")


def test_cash_flow_and_savings_rate(populated):
    txs = populated.data["transactions"]
    flow = fn.calculate_cash_flow(txs, "2026-11")
    assert flow["income"] == Decimal("3200000.00")
    assert flow["expenses"] == Decimal("1400000.00")
    assert flow["cash_flow"] == Decimal("1800000.00")
    assert flow["savings_rate_pct"] == Decimal("56.25")
    assert flow["savings_status"] == "saludable"


def test_savings_rate_without_income_and_deficit():
    assert fn.calculate_savings_rate(Decimal(0), Decimal(10))["status"] == "sin_ingresos"
    assert fn.calculate_savings_rate(Decimal(100), Decimal(150))["status"] == "deficit"


def test_net_worth_formula(populated):
    d = populated.data
    nw = fn.calculate_net_worth(d["assets"], d["liabilities"], d["investments"])
    assert nw["total_assets"] == Decimal("10000000.00")  # 2M + 5M + 3M inversión
    assert nw["total_liabilities"] == Decimal("1000000.00")
    assert nw["net_worth"] == Decimal("9000000.00")
    assert nw["debt_to_assets_pct"] == Decimal("10.00")


def test_distributions_sum_to_100(populated):
    d = populated.data
    dist = fn.calculate_asset_distribution(d["assets"], d["investments"])
    assert sum(r["pct"] for r in dist["items"]) == Decimal("100.00")
    assert {r["type"] for r in dist["items"]} == {"ahorros", "bienes_muebles", "inversiones"}


def test_budget_execution_status(populated):
    budgets = {"Alimentación": "500000.00", "Vivienda": "1000000.00"}
    exe = fn.calculate_budget_execution(budgets, populated.data["transactions"], "2026-11")
    by = {r["category"]: r for r in exe["items"]}
    assert by["Alimentación"]["status"] == "excedido"
    assert by["Alimentación"]["remaining"] == Decimal("-100000.00")
    assert by["Vivienda"]["status"] == "alerta"  # 80 %


def test_monthly_variation(populated):
    var = fn.calculate_monthly_variation(populated.data["transactions"], "2026-11")
    assert var["previous_period"] == "2026-10"
    assert var["expenses"]["change"] == Decimal("200000.00")
    assert var["income"]["change_pct"] == Decimal("6.67")


def test_recurring_expenses(populated):
    rec = fn.recurring_expenses(populated.data["transactions"])
    assert {r["description"] for r in rec} == {"Arriendo", "Mercado"}


def test_savings_capacity_average(populated):
    cap = fn.calculate_savings_capacity(populated.data["transactions"], "2026-11", 3)
    assert cap["months_considered"] == 2
    assert cap["avg_monthly_saving"] == Decimal("1800000.00")  # (1.8M + 1.8M) / 2


def test_net_worth_variation_needs_two_snapshots():
    assert fn.calculate_net_worth_variation([{"date": "2026-10-01", "net_worth": "1"}])["available"] is False
    v = fn.calculate_net_worth_variation([
        {"date": "2026-10-01", "net_worth": "1000.00"}, {"date": "2026-11-01", "net_worth": "1500.00"}])
    assert v["since_first"]["change"] == Decimal("500.00")
    assert v["since_first"]["change_pct"] == Decimal("50.00")


def test_investment_allocation_concentration_warning():
    invs = [{"asset_class": "renta_variable", "value": "900.00"}, {"asset_class": "renta_fija", "value": "100.00"}]
    alloc = fn.calculate_investment_allocation(invs)
    assert alloc["largest_class_pct"] == Decimal("90.00")
    assert any("concentración" in w.lower() for w in alloc["warnings"])


def test_simulation_zero_rate_and_compounding():
    flat = fn.simulate_investment(1000, 100, 0, 1)
    assert flat["final_nominal"] == Decimal("2200.00")
    comp = fn.simulate_investment(1000, 0, 10, 2)
    assert comp["final_nominal"] == Decimal("1210.00")
    assert comp["hypothetical"] is True


def test_simulation_inflation_reduces_real_value():
    sim = fn.simulate_investment(1000, 0, 5, 10, inflation_pct=5)
    assert sim["final_real"] == Decimal("1000.00")


@pytest.mark.parametrize("kwargs", [dict(years=0), dict(years=51), dict(annual_rate_pct=500), dict(principal=0, monthly_contribution=0)])
def test_simulation_validation(kwargs):
    base = dict(principal=1000, monthly_contribution=0, annual_rate_pct=5, years=1)
    base.update(kwargs)
    with pytest.raises(fn.FinanceError):
        fn.simulate_investment(**base)


def test_goal_progress():
    g = {"target_amount": "1200.00", "current_amount": "300.00", "deadline": "2027-01-15"}
    from datetime import date
    p = fn.goal_progress(g, today=date(2026, 11, 17))
    assert p["progress_pct"] == Decimal("25.00") and p["months_left"] == 2
    assert p["monthly_needed"] == Decimal("450.00")


def test_report_contains_all_sections(populated):
    rep = fn.generate_financial_report(populated.data, "2026-11")
    for key in ("cash_flow", "net_worth", "budget", "asset_distribution", "investment_allocation", "recurring_expenses"):
        assert key in rep
