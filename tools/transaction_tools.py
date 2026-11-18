"""TOOL 1: manage_transaction - registro y consulta de ingresos y gastos."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import functions as fn
from storage import DataStore

from ._common import error, find_by_id, is_confirmed, needs_confirmation, ok, require

NAME = "manage_transaction"

SCHEMA = {
    "name": NAME,
    "description": (
        "Gestiona los movimientos financieros del usuario: registrar ingresos y gastos, "
        "consultarlos, actualizarlos y eliminarlos. Para 'update' y 'delete' primero se muestra "
        "el detalle; solo después de que el usuario autorice se repite con confirm=true. "
        "Nunca inventes montos: si falta el monto o el tipo, pregunta al usuario."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["add", "list", "update", "delete"]},
            "type": {"type": "string", "enum": ["income", "expense"], "description": "Ingreso o gasto."},
            "amount": {"type": "number", "description": "Monto positivo en la moneda del usuario."},
            "category": {
                "type": "string",
                "description": "Gastos: " + ", ".join(fn.EXPENSE_CATEGORIES)
                + ". Ingresos: " + ", ".join(fn.INCOME_CATEGORIES) + ".",
            },
            "description": {"type": "string", "description": "Detalle breve (sin datos bancarios)."},
            "date": {"type": "string", "description": "AAAA-MM-DD; por defecto hoy."},
            "transaction_id": {"type": "string", "description": "Id del movimiento (update/delete)."},
            "period": {"type": "string", "description": "Filtro AAAA-MM para 'list'."},
            "limit": {"type": "integer", "description": "Máximo de registros en 'list' (por defecto 50)."},
            "confirm": {"type": "boolean", "description": "true solo tras la autorización del usuario."},
        },
        "required": ["action"],
    },
}


def _category_for(kind: str, value: Any) -> str:
    if kind == "income":
        return fn.normalize_choice(value, fn.INCOME_CATEGORIES, "category", default="Otros ingresos")
    return fn.normalize_choice(value, fn.EXPENSE_CATEGORIES, "category", default="Otros")


def _public(tx: dict[str, Any]) -> dict[str, Any]:
    return {k: tx[k] for k in ("id", "type", "amount", "category", "description", "date")}


def run(store: DataStore, params: dict[str, Any]) -> dict[str, Any]:
    action = params.get("action")
    with store.lock:
        txs = store.data["transactions"]

        if action == "add":
            kind = fn.normalize_choice(params.get("type"), ["income", "expense"], "type")
            tx = {
                "id": store.new_id("t"),
                "type": kind,
                "amount": fn.money_str(fn.to_money(params.get("amount"), "amount")),
                "category": _category_for(kind, params.get("category")),
                "description": fn.validate_text(params.get("description"), "description"),
                "date": fn.validate_date(params.get("date")),
            }
            txs.append(tx)
            store.save()
            return ok(message="Movimiento registrado.", transaction=_public(tx))

        if action == "list":
            kind = params.get("type")
            period = fn.validate_period(params["period"]) if params.get("period") else None
            category = None
            if params.get("category"):
                category = _category_for(kind or "expense", params["category"])
            items = fn.filter_transactions(txs, kind, period, category)
            items = sorted(items, key=lambda t: (t["date"], t["id"]), reverse=True)
            limit = max(1, min(int(params.get("limit") or 50), 500))
            income = sum((Decimal(t["amount"]) for t in items if t["type"] == "income"), Decimal(0))
            expense = sum((Decimal(t["amount"]) for t in items if t["type"] == "expense"), Decimal(0))
            return ok(
                filters={"type": kind, "period": period, "category": category},
                matched=len(items), shown=min(limit, len(items)),
                total_income=fn.money_str(income), total_expenses=fn.money_str(expense),
                transactions=[_public(t) for t in items[:limit]],
            )

        if action in ("update", "delete"):
            tx = find_by_id(txs, require(params, "transaction_id"), "un movimiento")
            changes: dict[str, Any] = {}
            if action == "update":
                if "type" in params and params["type"] != tx["type"]:
                    changes["type"] = fn.normalize_choice(params["type"], ["income", "expense"], "type")
                kind = changes.get("type", tx["type"])
                if params.get("amount") is not None:
                    changes["amount"] = fn.money_str(fn.to_money(params["amount"], "amount"))
                if params.get("category"):
                    changes["category"] = _category_for(kind, params["category"])
                elif "type" in changes:
                    changes["category"] = _category_for(kind, None)
                if "description" in params:
                    changes["description"] = fn.validate_text(params["description"], "description")
                if params.get("date"):
                    changes["date"] = fn.validate_date(params["date"])
                if not changes:
                    return error("No se indicó ningún campo para actualizar.")
            if not is_confirmed(params):
                preview = {"current": _public(tx)}
                if changes:
                    preview["changes"] = changes
                return needs_confirmation(action, preview)
            if action == "update":
                tx.update(changes)
                store.save()
                return ok(message="Movimiento actualizado.", transaction=_public(tx))
            txs.remove(tx)
            store.save()
            return ok(message="Movimiento eliminado.", deleted=_public(tx))

        return error("Acción no válida. Use: add, list, update o delete.")
