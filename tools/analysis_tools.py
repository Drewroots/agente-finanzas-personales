"""TOOL 3: analyze_finances - flujo de caja, presupuesto, tendencias y objetivos."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import functions as fn
from storage import DataStore

from ._common import error, find_by_id, is_confirmed, needs_confirmation, ok, require

NAME = "analyze_finances"

SCHEMA = {
    "name": NAME,
    "description": (
        "Analiza las finanzas personales con los datos registrados: resumen de flujo de caja, "
        "gastos por categoría, capacidad de ahorro, gastos recurrentes, comparación entre meses, "
        "ejecución del presupuesto, objetivos de ahorro e informe completo. Calcula indicadores y "
        "devuelve su interpretación. Usa solo datos registrados."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["summary", "expenses_by_category", "savings_capacity", "recurring",
                         "compare_periods", "budget_status", "set_budget", "remove_budget",
                         "goal_add", "goal_list", "goal_update", "goal_remove", "report"],
            },
            "period": {"type": "string", "description": "Mes a analizar AAAA-MM (por defecto el mes actual)."},
            "compare_to": {"type": "string", "description": "Mes de comparación AAAA-MM (por defecto el anterior)."},
            "months": {"type": "integer", "description": "Meses a promediar en savings_capacity (1-12, por defecto 3)."},
            "category": {"type": "string", "description": "Categoría de gasto para set_budget/remove_budget."},
            "amount": {"type": "number", "description": "Monto mensual del presupuesto."},
            "goal_id": {"type": "string"},
            "name": {"type": "string", "description": "Nombre del objetivo de ahorro."},
            "target_amount": {"type": "number"},
            "current_amount": {"type": "number", "description": "Ahorrado hasta ahora."},
            "deadline": {"type": "string", "description": "Fecha límite AAAA-MM-DD (opcional)."},
            "confirm": {"type": "boolean", "description": "true solo tras la autorización del usuario."},
        },
        "required": ["action"],
    },
}

_STATUS_TEXT = {
    "sin_ingresos": "No hay ingresos registrados en el periodo, no se puede calcular la tasa de ahorro.",
    "deficit": "Déficit: se gastó más de lo que ingresó.",
    "baja": "Tasa de ahorro baja (< 10 %).",
    "moderada": "Tasa de ahorro moderada (10 % a 20 %).",
    "saludable": "Tasa de ahorro saludable (>= 20 %), según una referencia general educativa.",
}


def _interpret_flow(flow: dict[str, Any]) -> list[str]:
    notes = [_STATUS_TEXT[flow["savings_status"]]]
    if not (flow["income_count"] or flow["expense_count"]):
        notes = ["No hay movimientos registrados en este periodo."]
    return notes


def _goal_from_params(params: dict[str, Any], base: dict[str, Any] | None = None) -> dict[str, Any]:
    goal = dict(base or {})
    if base is None or params.get("name"):
        goal["name"] = fn.validate_text(require(params, "name") if base is None else params["name"], "name", 80, True)
    if base is None or params.get("target_amount") is not None:
        goal["target_amount"] = fn.money_str(fn.to_money(params.get("target_amount"), "target_amount"))
    if base is None:
        goal["current_amount"] = fn.money_str(fn.to_money(params.get("current_amount", 0), "current_amount", True))
    elif params.get("current_amount") is not None:
        goal["current_amount"] = fn.money_str(fn.to_money(params["current_amount"], "current_amount", True))
    if params.get("deadline"):
        goal["deadline"] = fn.validate_date(params["deadline"])
    else:
        goal.setdefault("deadline", None)
    return goal


def run(store: DataStore, params: dict[str, Any]) -> dict[str, Any]:
    action = params.get("action")
    with store.lock:
        d = store.data
        txs = d["transactions"]
        needs_period = action in ("summary", "expenses_by_category", "savings_capacity",
                                  "compare_periods", "budget_status", "report")
        period = fn.validate_period(params.get("period")) if needs_period else None

        if action == "summary":
            flow = fn.calculate_cash_flow(txs, period)
            return ok(period=period, cash_flow=fn.to_jsonable(flow), interpretation=_interpret_flow(flow),
                      formulas={"flujo_de_caja": "ingresos - gastos",
                                "tasa_de_ahorro": "(ingresos - gastos) / ingresos x 100"},
                      data_used={"income_records": flow["income_count"], "expense_records": flow["expense_count"]})

        if action == "expenses_by_category":
            dist = fn.expense_by_category(txs, period)
            note = None
            if dist["categories"] and dist["categories"][0]["pct"] and dist["categories"][0]["pct"] >= 40:
                note = f"La categoría '{dist['categories'][0]['category']}' concentra {dist['categories'][0]['pct']} % del gasto."
            return ok(distribution=fn.to_jsonable(dist), observation=note)

        if action == "savings_capacity":
            months = max(1, min(int(params.get("months") or 3), 12))
            cap = fn.calculate_savings_capacity(txs, period, months)
            msg = ("No hay movimientos en el rango analizado." if not cap["months_considered"] else
                   "Promedio de ingresos y gastos de los meses con movimientos registrados; es un histórico, no una proyección.")
            return ok(period_end=period, months_requested=months, capacity=fn.to_jsonable(cap), note=msg)

        if action == "recurring":
            rec = fn.recurring_expenses(txs)
            return ok(recurring=fn.to_jsonable(rec),
                      note="Gastos con la misma descripción y categoría en 2 o más meses distintos." if rec
                      else "No se detectaron gastos recurrentes (se requieren al menos 2 meses con la misma descripción).")

        if action == "compare_periods":
            compare_to = fn.validate_period(params["compare_to"]) if params.get("compare_to") else None
            var = fn.calculate_monthly_variation(txs, period, compare_to)
            return ok(comparison=fn.to_jsonable(var),
                      note="Un cambio porcentual nulo significa que el periodo base no tiene valor para comparar.")

        if action == "budget_status":
            return ok(budget=fn.to_jsonable(fn.calculate_budget_execution(d["budgets"], txs, period)),
                      note="Estado: ok < 80 %, alerta >= 80 %, excedido > 100 % del presupuesto.")

        if action in ("set_budget", "remove_budget"):
            category = fn.normalize_choice(params.get("category"), fn.EXPENSE_CATEGORIES, "category")
            current = d["budgets"].get(category)
            if action == "remove_budget":
                if current is None:
                    raise fn.NotFoundError(f"No hay presupuesto para '{category}'.")
                if not is_confirmed(params):
                    return needs_confirmation(action, {"category": category, "current_budget": current})
                del d["budgets"][category]
                store.save()
                return ok(message=f"Presupuesto de '{category}' eliminado.")
            amount = fn.money_str(fn.to_money(params.get("amount"), "amount"))
            if current is not None and current != amount and not is_confirmed(params):
                return needs_confirmation(action, {"category": category, "current_budget": current, "new_budget": amount})
            d["budgets"][category] = amount
            store.save()
            return ok(message=f"Presupuesto mensual de '{category}' fijado.", category=category, budget=amount)

        if action == "goal_add":
            goal = _goal_from_params(params)
            goal["id"] = store.new_id("g")
            goal["created"] = date.today().isoformat()
            d["goals"].append(goal)
            store.save()
            return ok(message="Objetivo de ahorro creado.", goal=fn.to_jsonable(fn.goal_progress(goal)))

        if action == "goal_list":
            return ok(goals=fn.to_jsonable([fn.goal_progress(g) for g in d["goals"]]))

        if action in ("goal_update", "goal_remove"):
            goal = find_by_id(d["goals"], require(params, "goal_id"), "un objetivo")
            changes = _goal_from_params(params, goal) if action == "goal_update" else None
            if not is_confirmed(params):
                preview = {"current": goal}
                if changes:
                    preview["new"] = changes
                return needs_confirmation(action, preview)
            if action == "goal_update":
                goal.update(changes)
                store.save()
                return ok(message="Objetivo actualizado.", goal=fn.to_jsonable(fn.goal_progress(goal)))
            d["goals"].remove(goal)
            store.save()
            return ok(message="Objetivo eliminado.", deleted=goal)

        if action == "report":
            return ok(report=fn.to_jsonable(fn.generate_financial_report(d, period)))

        return error("Acción no válida para analyze_finances.")
