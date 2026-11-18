"""Capa 4 - Lógica de negocio financiera.

Todas las funciones son puras (no leen ni escriben archivos, no llaman al LLM),
operan con ``Decimal`` y devuelven estructuras serializables. Los montos se
guardan como cadenas (``"1500000.00"``) para no perder precisión.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, getcontext
from typing import Any, Iterable, Mapping, Sequence

getcontext().prec = 28

CENT = Decimal("0.01")
MAX_AMOUNT = Decimal("1000000000000000")  # 1e15, evita entradas absurdas
HUNDRED = Decimal(100)

EXPENSE_CATEGORIES = [
    "Alimentación", "Transporte", "Educación", "Vivienda",
    "Entretenimiento", "Salud", "Servicios", "Otros",
]
INCOME_CATEGORIES = ["Salario", "Negocio", "Rendimientos", "Otros ingresos"]
ASSET_TYPES = ["efectivo", "ahorros", "bienes_muebles", "bienes_inmuebles", "otros"]
LIABILITY_TYPES = ["prestamo", "deuda_personal", "tarjeta_credito", "obligacion_financiera", "otros"]
INVESTMENT_CLASSES = [
    "renta_fija", "renta_variable", "fondos", "inmobiliario", "criptoactivos", "otros",
]

ASSET_LABELS = {
    "efectivo": "Dinero disponible", "ahorros": "Cuentas de ahorro",
    "inversiones": "Inversiones declaradas", "bienes_muebles": "Bienes muebles",
    "bienes_inmuebles": "Bienes inmuebles", "otros": "Otros activos",
}
LIABILITY_LABELS = {
    "prestamo": "Préstamos", "deuda_personal": "Deudas personales",
    "tarjeta_credito": "Tarjetas de crédito",
    "obligacion_financiera": "Obligaciones financieras", "otros": "Otros pasivos",
}
INVESTMENT_LABELS = {
    "renta_fija": "Renta fija", "renta_variable": "Renta variable", "fondos": "Fondos",
    "inmobiliario": "Inmobiliario", "criptoactivos": "Criptoactivos", "otros": "Otros",
}

_PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
# Secuencias de 13 a 19 dígitos (posibles números de tarjeta o cuenta).
_SENSITIVE_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")


class FinanceError(ValueError):
    """Error de validación o de regla de negocio."""

    code = "validation"


class NotFoundError(FinanceError):
    """El registro solicitado no existe."""

    code = "not_found"


# --------------------------------------------------------------------------
# Validación y utilidades
# --------------------------------------------------------------------------
def quantize(value: Decimal) -> Decimal:
    """Redondea a centavos (mitad hacia arriba)."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def to_money(value: Any, field: str = "monto", allow_zero: bool = False) -> Decimal:
    """Convierte ``value`` en un Decimal monetario positivo y validado."""
    if value is None or isinstance(value, bool):
        raise FinanceError(f"El campo '{field}' es obligatorio y debe ser numérico.")
    try:
        dec = Decimal(repr(value) if isinstance(value, float) else str(value).strip())
    except (InvalidOperation, ValueError):
        raise FinanceError(f"El campo '{field}' no es un número válido: {value!r}.") from None
    if not dec.is_finite():
        raise FinanceError(f"El campo '{field}' debe ser un número finito.")
    if dec < 0 or (dec == 0 and not allow_zero):
        raise FinanceError(f"El campo '{field}' debe ser mayor que cero.")
    if dec > MAX_AMOUNT:
        raise FinanceError(f"El campo '{field}' excede el máximo permitido.")
    return quantize(dec)


def to_decimal_pct(value: Any, field: str, low: Decimal, high: Decimal) -> Decimal:
    """Convierte un porcentaje (puede ser negativo) validando el rango."""
    if value is None or isinstance(value, bool):
        raise FinanceError(f"El campo '{field}' es obligatorio y debe ser numérico.")
    try:
        dec = Decimal(repr(value) if isinstance(value, float) else str(value).strip())
    except (InvalidOperation, ValueError):
        raise FinanceError(f"El campo '{field}' no es un número válido: {value!r}.") from None
    if not dec.is_finite() or dec < low or dec > high:
        raise FinanceError(f"El campo '{field}' debe estar entre {low} y {high}.")
    return dec


def money_str(value: Decimal) -> str:
    """Representación de un monto con dos decimales ('1500000.00')."""
    return f"{quantize(value):.2f}"


def _fold(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text.strip().lower())
        if unicodedata.category(c) != "Mn"
    )


def normalize_choice(value: Any, valid: Sequence[str], field: str, default: str | None = None) -> str:
    """Normaliza (sin tildes ni mayúsculas) un valor contra una lista válida."""
    if value is None or str(value).strip() == "":
        if default is not None:
            return default
        raise FinanceError(f"El campo '{field}' es obligatorio. Valores válidos: {', '.join(valid)}.")
    folded = _fold(str(value)).replace(" ", "_")
    for option in valid:
        if _fold(option).replace(" ", "_") == folded:
            return option
    raise FinanceError(f"'{value}' no es un valor válido para '{field}'. Opciones: {', '.join(valid)}.")


def validate_text(value: Any, field: str, max_len: int = 120, required: bool = False) -> str:
    """Valida un texto libre y rechaza datos bancarios sensibles."""
    text = "" if value is None else str(value).strip()
    if required and not text:
        raise FinanceError(f"El campo '{field}' es obligatorio.")
    if len(text) > max_len:
        raise FinanceError(f"El campo '{field}' no puede superar {max_len} caracteres.")
    if _SENSITIVE_RE.search(text):
        raise FinanceError(
            f"El campo '{field}' parece contener un número de tarjeta o cuenta. "
            "Por seguridad no se almacenan datos bancarios sensibles."
        )
    return text


def validate_date(value: Any = None) -> str:
    """Devuelve una fecha ISO (AAAA-MM-DD); por defecto, hoy."""
    if value is None or str(value).strip() == "":
        return date.today().isoformat()
    try:
        return datetime.strptime(str(value).strip()[:10], "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise FinanceError(f"Fecha inválida: {value!r}. Use el formato AAAA-MM-DD.") from None


def validate_period(value: Any = None) -> str:
    """Valida un periodo mensual 'AAAA-MM'; por defecto, el mes actual."""
    if value is None or str(value).strip() == "":
        return current_period()
    text = str(value).strip()
    if not _PERIOD_RE.match(text):
        raise FinanceError(f"Periodo inválido: {value!r}. Use el formato AAAA-MM.")
    return text


def current_period() -> str:
    return date.today().strftime("%Y-%m")


def shift_period(period: str, months: int) -> str:
    """Desplaza un periodo 'AAAA-MM' ``months`` meses (negativo = atrás)."""
    year, month = int(period[:4]), int(period[5:7])
    index = year * 12 + (month - 1) + months
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def pct(part: Decimal, whole: Decimal) -> Decimal | None:
    """Porcentaje con 2 decimales; None si el total es cero."""
    if whole == 0:
        return None
    return quantize(part / whole * HUNDRED)


def _amount(record: Mapping[str, Any]) -> Decimal:
    return Decimal(str(record["amount"]))


def _value(record: Mapping[str, Any]) -> Decimal:
    return Decimal(str(record["value"]))


# --------------------------------------------------------------------------
# Ingresos, gastos y flujo de caja
# --------------------------------------------------------------------------
def filter_transactions(
    transactions: Iterable[Mapping[str, Any]],
    kind: str | None = None,
    period: str | None = None,
    category: str | None = None,
) -> list[Mapping[str, Any]]:
    """Filtra movimientos por tipo, periodo (AAAA-MM) y categoría."""
    result = []
    for tx in transactions:
        if kind and tx.get("type") != kind:
            continue
        if period and not str(tx.get("date", "")).startswith(period):
            continue
        if category and tx.get("category") != category:
            continue
        result.append(tx)
    return result


def _total(transactions, kind, period, category=None) -> dict[str, Any]:
    items = filter_transactions(transactions, kind, period, category)
    total = sum((_amount(t) for t in items), Decimal(0))
    return {"period": period, "total": quantize(total), "count": len(items)}


def calculate_total_income(transactions: Iterable[Mapping[str, Any]], period: str | None = None) -> dict[str, Any]:
    """Total de ingresos registrados (de un periodo o de todo el historial)."""
    return _total(transactions, "income", period)


def calculate_total_expenses(
    transactions: Iterable[Mapping[str, Any]], period: str | None = None, category: str | None = None
) -> dict[str, Any]:
    """Total de gastos registrados (opcionalmente por categoría)."""
    return _total(transactions, "expense", period, category)


def calculate_savings_rate(income: Decimal, expenses: Decimal) -> dict[str, Any]:
    """Tasa de ahorro = (ingresos - gastos) / ingresos."""
    saved = quantize(income - expenses)
    rate = pct(saved, income)
    if rate is None:
        status = "sin_ingresos"
    elif rate < 0:
        status = "deficit"
    elif rate < 10:
        status = "baja"
    elif rate < 20:
        status = "moderada"
    else:
        status = "saludable"
    return {"saved": saved, "rate_pct": rate, "status": status}


def calculate_cash_flow(transactions: Iterable[Mapping[str, Any]], period: str | None = None) -> dict[str, Any]:
    """Flujo de caja = ingresos - gastos, junto con la tasa de ahorro."""
    txs = list(transactions)
    income = calculate_total_income(txs, period)
    expenses = calculate_total_expenses(txs, period)
    saving = calculate_savings_rate(income["total"], expenses["total"])
    return {
        "period": period,
        "income": income["total"],
        "expenses": expenses["total"],
        "cash_flow": saving["saved"],
        "savings_rate_pct": saving["rate_pct"],
        "savings_status": saving["status"],
        "income_count": income["count"],
        "expense_count": expenses["count"],
    }


def expense_by_category(transactions: Iterable[Mapping[str, Any]], period: str | None = None) -> dict[str, Any]:
    """Gastos agrupados por categoría con su porcentaje, de mayor a menor."""
    items = filter_transactions(transactions, "expense", period)
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for tx in items:
        totals[tx["category"]] += _amount(tx)
    grand = sum(totals.values(), Decimal(0))
    rows = [
        {"category": cat, "total": quantize(val), "pct": pct(val, grand)}
        for cat, val in sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    ]
    return {"period": period, "total": quantize(grand), "categories": rows}


def recurring_expenses(transactions: Iterable[Mapping[str, Any]], min_months: int = 2) -> list[dict[str, Any]]:
    """Gastos con la misma descripción y categoría en al menos ``min_months`` meses."""
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for tx in filter_transactions(transactions, "expense"):
        desc = _fold(tx.get("description", ""))
        if desc:
            groups[(desc, tx["category"])].append(tx)
    result = []
    for (_, category), items in groups.items():
        months = {str(t["date"])[:7] for t in items}
        if len(months) >= min_months:
            avg = sum((_amount(t) for t in items), Decimal(0)) / len(items)
            result.append({
                "description": items[0]["description"], "category": category,
                "months_seen": len(months), "average_amount": quantize(avg),
                "occurrences": len(items),
            })
    return sorted(result, key=lambda r: r["average_amount"], reverse=True)


def calculate_savings_capacity(
    transactions: Iterable[Mapping[str, Any]], end_period: str, months: int = 3
) -> dict[str, Any]:
    """Promedio de ingresos/gastos en los últimos ``months`` meses con actividad."""
    txs = list(transactions)
    considered = []
    for offset in range(months):
        period = shift_period(end_period, -offset)
        flow = calculate_cash_flow(txs, period)
        if flow["income_count"] or flow["expense_count"]:
            considered.append(flow)
    if not considered:
        return {"months_considered": 0, "periods": [], "avg_income": None, "avg_expenses": None,
                "avg_monthly_saving": None, "savings_rate_pct": None}
    n = Decimal(len(considered))
    avg_income = sum((f["income"] for f in considered), Decimal(0)) / n
    avg_exp = sum((f["expenses"] for f in considered), Decimal(0)) / n
    return {
        "months_considered": len(considered),
        "periods": [f["period"] for f in considered],
        "avg_income": quantize(avg_income),
        "avg_expenses": quantize(avg_exp),
        "avg_monthly_saving": quantize(avg_income - avg_exp),
        "savings_rate_pct": pct(avg_income - avg_exp, avg_income),
    }


def calculate_monthly_variation(
    transactions: Iterable[Mapping[str, Any]], period: str, previous: str | None = None
) -> dict[str, Any]:
    """Compara ingresos, gastos y flujo de caja entre dos periodos."""
    txs = list(transactions)
    previous = previous or shift_period(period, -1)
    now, before = calculate_cash_flow(txs, period), calculate_cash_flow(txs, previous)

    def delta(key: str) -> dict[str, Any]:
        diff = now[key] - before[key]
        return {"current": now[key], "previous": before[key], "change": quantize(diff),
                "change_pct": pct(diff, abs(before[key])) if before[key] != 0 else None}

    cat_now = {c["category"]: c["total"] for c in expense_by_category(txs, period)["categories"]}
    cat_before = {c["category"]: c["total"] for c in expense_by_category(txs, previous)["categories"]}
    cats = []
    for cat in sorted(set(cat_now) | set(cat_before)):
        diff = cat_now.get(cat, Decimal(0)) - cat_before.get(cat, Decimal(0))
        cats.append({"category": cat, "current": cat_now.get(cat, Decimal(0)),
                     "previous": cat_before.get(cat, Decimal(0)), "change": quantize(diff)})
    cats.sort(key=lambda c: abs(c["change"]), reverse=True)
    return {
        "period": period, "previous_period": previous,
        "income": delta("income"), "expenses": delta("expenses"), "cash_flow": delta("cash_flow"),
        "expense_categories": cats,
    }


# --------------------------------------------------------------------------
# Patrimonio
# --------------------------------------------------------------------------
def _distribution(totals: dict[str, Decimal], labels: Mapping[str, str]) -> dict[str, Any]:
    grand = sum(totals.values(), Decimal(0))
    rows = [
        {"type": t, "label": labels.get(t, t), "total": quantize(v), "pct": pct(v, grand)}
        for t, v in sorted(totals.items(), key=lambda kv: kv[1], reverse=True) if v > 0
    ]
    return {"total": quantize(grand), "items": rows}


def calculate_asset_distribution(
    assets: Iterable[Mapping[str, Any]], investments: Iterable[Mapping[str, Any]] | None = None
) -> dict[str, Any]:
    """Distribución porcentual de los activos (las inversiones cuentan como 'inversiones')."""
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for a in assets:
        totals[a["type"]] += _value(a)
    for inv in investments or []:
        totals["inversiones"] += _value(inv)
    return _distribution(totals, ASSET_LABELS)


def calculate_liability_distribution(liabilities: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Distribución porcentual de los pasivos por tipo."""
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for item in liabilities:
        totals[item["type"]] += _value(item)
    return _distribution(totals, LIABILITY_LABELS)


def calculate_net_worth(
    assets: Iterable[Mapping[str, Any]],
    liabilities: Iterable[Mapping[str, Any]],
    investments: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Patrimonio neto = total de activos (incl. inversiones declaradas) - total de pasivos."""
    assets, liabilities, investments = list(assets), list(liabilities), list(investments or [])
    total_assets = sum((_value(a) for a in assets), Decimal(0)) + sum((_value(i) for i in investments), Decimal(0))
    total_liabs = sum((_value(l) for l in liabilities), Decimal(0))
    ratio = pct(total_liabs, total_assets)
    return {
        "total_assets": quantize(total_assets),
        "total_liabilities": quantize(total_liabs),
        "net_worth": quantize(total_assets - total_liabs),
        "debt_to_assets_pct": ratio,
        "counts": {"assets": len(assets), "investments": len(investments), "liabilities": len(liabilities)},
    }


def calculate_net_worth_variation(history: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Variación del patrimonio entre la primera, la penúltima y la última foto."""
    snaps = sorted(history, key=lambda h: h["date"])
    if len(snaps) < 2:
        return {"snapshots": len(snaps), "available": False,
                "message": "Se necesitan al menos 2 registros históricos del patrimonio."}

    def change(a: Mapping[str, Any], b: Mapping[str, Any]) -> dict[str, Any]:
        va, vb = Decimal(str(a["net_worth"])), Decimal(str(b["net_worth"]))
        return {"from": a["date"], "to": b["date"], "change": quantize(vb - va),
                "change_pct": pct(vb - va, abs(va)) if va != 0 else None}

    return {"snapshots": len(snaps), "available": True,
            "since_first": change(snaps[0], snaps[-1]), "since_previous": change(snaps[-2], snaps[-1])}


# --------------------------------------------------------------------------
# Presupuesto
# --------------------------------------------------------------------------
def calculate_budget_execution(
    budgets: Mapping[str, Any], transactions: Iterable[Mapping[str, Any]], period: str
) -> dict[str, Any]:
    """Compara el presupuesto mensual por categoría con lo gastado en el periodo."""
    spent = {c["category"]: c["total"] for c in expense_by_category(transactions, period)["categories"]}
    rows = []
    for cat, limit_raw in budgets.items():
        limit = Decimal(str(limit_raw))
        used = spent.get(cat, Decimal(0))
        used_pct = pct(used, limit)
        status = "excedido" if used > limit else ("alerta" if used_pct is not None and used_pct >= 80 else "ok")
        rows.append({"category": cat, "budget": quantize(limit), "spent": used,
                     "remaining": quantize(limit - used), "used_pct": used_pct, "status": status})
    rows.sort(key=lambda r: r["category"])
    unbudgeted = [{"category": c, "spent": v} for c, v in spent.items() if c not in budgets]
    total_budget = sum((r["budget"] for r in rows), Decimal(0))
    total_spent = sum((r["spent"] for r in rows), Decimal(0))
    return {"period": period, "items": rows, "without_budget": unbudgeted,
            "total_budget": quantize(total_budget), "total_spent_in_budgeted": quantize(total_spent)}


def goal_progress(goal: Mapping[str, Any], today: date | None = None) -> dict[str, Any]:
    """Progreso de un objetivo de ahorro y aporte mensual necesario."""
    today = today or date.today()
    target, current = Decimal(str(goal["target_amount"])), Decimal(str(goal["current_amount"]))
    remaining = max(target - current, Decimal(0))
    info: dict[str, Any] = {
        **goal, "remaining": quantize(remaining), "progress_pct": min(pct(current, target) or Decimal(0), HUNDRED),
        "completed": current >= target, "monthly_needed": None, "months_left": None,
    }
    deadline = goal.get("deadline")
    if deadline and remaining > 0:
        dl = datetime.strptime(deadline, "%Y-%m-%d").date()
        months = (dl.year - today.year) * 12 + (dl.month - today.month)
        info["months_left"] = months
        if months > 0:
            info["monthly_needed"] = quantize(remaining / months)
    return info


# --------------------------------------------------------------------------
# Inversión (educativo)
# --------------------------------------------------------------------------
def calculate_investment_allocation(investments: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Distribución de las inversiones declaradas por clase y alertas de concentración."""
    invs = list(investments)
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for inv in invs:
        totals[inv["asset_class"]] += _value(inv)
    dist = _distribution(totals, INVESTMENT_LABELS)
    for row in dist["items"]:
        row["class"] = row.pop("type")
    warnings = []
    if not invs:
        return {**dist, "positions": 0, "classes": 0, "largest_class_pct": None,
                "largest_position_pct": None, "warnings": ["No hay inversiones declaradas."]}
    largest_class = dist["items"][0]["pct"]
    grand = Decimal(dist["total"])
    largest_pos = pct(max(_value(i) for i in invs), grand)
    if largest_class is not None and largest_class > 60:
        warnings.append(f"Alta concentración: {largest_class}% del capital invertido está en una sola clase de activo.")
    if largest_pos is not None and largest_pos > 40 and len(invs) > 1:
        warnings.append(f"Una sola posición representa {largest_pos}% del capital invertido.")
    if len(invs) == 1:
        warnings.append("Solo hay una inversión declarada: no hay diversificación.")
    if len(totals) == 1 and len(invs) > 1:
        warnings.append("Todas las inversiones pertenecen a la misma clase de activo.")
    return {**dist, "positions": len(invs), "classes": len(totals), "largest_class_pct": largest_class,
            "largest_position_pct": largest_pos, "warnings": warnings}


def simulate_investment(
    principal: Any, monthly_contribution: Any, annual_rate_pct: Any, years: Any,
    inflation_pct: Any = 0, label: str = "Escenario",
) -> dict[str, Any]:
    """Simula un escenario HIPOTÉTICO con capitalización mensual.

    La rentabilidad es un supuesto del usuario, no una predicción ni un dato real.
    """
    principal = to_money(principal, "capital_inicial", allow_zero=True)
    contribution = to_money(monthly_contribution, "aporte_mensual", allow_zero=True)
    rate = to_decimal_pct(annual_rate_pct, "tasa_anual_pct", Decimal(-50), Decimal(100))
    inflation = to_decimal_pct(inflation_pct, "inflacion_pct", Decimal(-10), Decimal(100))
    try:
        years_int = int(years)
    except (TypeError, ValueError):
        raise FinanceError("El campo 'anios' debe ser un entero entre 1 y 50.") from None
    if not 1 <= years_int <= 50:
        raise FinanceError("El campo 'anios' debe ser un entero entre 1 y 50.")
    if principal == 0 and contribution == 0:
        raise FinanceError("Indique un capital inicial o un aporte mensual mayor que cero.")

    monthly_rate = (1 + rate / HUNDRED) ** (Decimal(1) / 12) - 1
    balance, contributed = principal, principal
    series = []
    for month in range(1, years_int * 12 + 1):
        balance = balance * (1 + monthly_rate) + contribution
        contributed += contribution
        if month % 12 == 0:
            yr = month // 12
            real = balance / ((1 + inflation / HUNDRED) ** yr)
            series.append({"year": yr, "nominal": quantize(balance), "real": quantize(real),
                           "contributed": quantize(contributed)})
    last = series[-1]
    return {
        "label": label, "hypothetical": True, "annual_rate_pct": rate, "inflation_pct": inflation,
        "years": years_int, "principal": principal, "monthly_contribution": contribution,
        "total_contributed": last["contributed"], "final_nominal": last["nominal"],
        "final_real": last["real"], "nominal_gain": quantize(last["nominal"] - last["contributed"]),
        "series": series,
        "note": "Resultado HIPOTÉTICO basado en una tasa supuesta; no es una predicción ni un rendimiento real.",
    }


# --------------------------------------------------------------------------
# Informe consolidado
# --------------------------------------------------------------------------
def generate_financial_report(data: Mapping[str, Any], period: str | None = None) -> dict[str, Any]:
    """Informe integral del periodo con todos los indicadores principales."""
    period = validate_period(period)
    txs = data.get("transactions", [])
    assets, liabs, invs = data.get("assets", []), data.get("liabilities", []), data.get("investments", [])
    return {
        "period": period,
        "cash_flow": calculate_cash_flow(txs, period),
        "expenses_by_category": expense_by_category(txs, period),
        "net_worth": calculate_net_worth(assets, liabs, invs),
        "net_worth_variation": calculate_net_worth_variation(data.get("history", [])),
        "asset_distribution": calculate_asset_distribution(assets, invs),
        "liability_distribution": calculate_liability_distribution(liabs),
        "budget": calculate_budget_execution(data.get("budgets", {}), txs, period),
        "monthly_variation": calculate_monthly_variation(txs, period),
        "recurring_expenses": recurring_expenses(txs),
        "savings_capacity": calculate_savings_capacity(txs, period),
        "goals": [goal_progress(g) for g in data.get("goals", [])],
        "investment_allocation": calculate_investment_allocation(invs),
    }


def to_jsonable(obj: Any) -> Any:
    """Convierte Decimals (a cadenas con 2 decimales o enteros) para serializar a JSON."""
    if isinstance(obj, Decimal):
        return f"{obj:.2f}"
    if isinstance(obj, Mapping):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(v) for v in obj]
    return obj
