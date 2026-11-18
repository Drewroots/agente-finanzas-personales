"""TOOL 2: calculate_net_worth - activos, pasivos y patrimonio neto."""
from __future__ import annotations

from datetime import date
from typing import Any

import functions as fn
from storage import DataStore

from ._common import error, find_by_id, is_confirmed, needs_confirmation, ok, require

NAME = "calculate_net_worth"

SCHEMA = {
    "name": NAME,
    "description": (
        "Calcula el patrimonio neto (activos - pasivos) y administra los activos y pasivos "
        "declarados por el usuario. Las inversiones declaradas se gestionan con investment_analysis "
        "y se incluyen automáticamente en los activos. 'update_item' y 'remove_item' requieren "
        "autorización del usuario (confirm=true). No inventes valores: pregúntalos."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["calculate", "list", "add_asset", "add_liability", "update_item",
                         "remove_item", "snapshot", "history"],
            },
            "name": {"type": "string", "description": "Nombre del activo o pasivo."},
            "item_type": {
                "type": "string",
                "description": "Activo: " + ", ".join(fn.ASSET_TYPES)
                + ". Pasivo: " + ", ".join(fn.LIABILITY_TYPES) + ".",
            },
            "value": {"type": "number", "description": "Valor actual (activo) o saldo adeudado (pasivo)."},
            "item_id": {"type": "string", "description": "Id del activo (a_...) o pasivo (l_...)."},
            "save_snapshot": {"type": "boolean", "description": "Guardar el resultado en el historial."},
            "confirm": {"type": "boolean", "description": "true solo tras la autorización del usuario."},
        },
        "required": ["action"],
    },
}


def _snapshot(store: DataStore) -> dict[str, Any]:
    d = store.data
    nw = fn.calculate_net_worth(d["assets"], d["liabilities"], d["investments"])
    entry = {
        "date": date.today().isoformat(),
        "net_worth": fn.money_str(nw["net_worth"]),
        "total_assets": fn.money_str(nw["total_assets"]),
        "total_liabilities": fn.money_str(nw["total_liabilities"]),
    }
    history = [h for h in d["history"] if h["date"] != entry["date"]]
    history.append(entry)
    d["history"] = sorted(history, key=lambda h: h["date"])
    store.save()
    return entry


def _bucket(item_id: str) -> tuple[str, str]:
    if item_id.startswith("a_"):
        return "assets", "un activo"
    if item_id.startswith("l_"):
        return "liabilities", "un pasivo"
    raise fn.FinanceError("El id debe empezar por 'a_' (activo) o 'l_' (pasivo).")


def _valid_types(kind: str) -> list[str]:
    return fn.ASSET_TYPES if kind == "assets" else fn.LIABILITY_TYPES


def run(store: DataStore, params: dict[str, Any]) -> dict[str, Any]:
    action = params.get("action")
    with store.lock:
        d = store.data

        if action in ("add_asset", "add_liability"):
            kind = "assets" if action == "add_asset" else "liabilities"
            item = {
                "id": store.new_id("a" if kind == "assets" else "l"),
                "name": fn.validate_text(require(params, "name"), "name", 80, required=True),
                "type": fn.normalize_choice(params.get("item_type"), _valid_types(kind), "item_type"),
                "value": fn.money_str(fn.to_money(params.get("value"), "value", allow_zero=True)),
                "updated": date.today().isoformat(),
            }
            d[kind].append(item)
            store.save()
            return ok(message="Activo registrado." if kind == "assets" else "Pasivo registrado.", item=item)

        if action in ("update_item", "remove_item"):
            kind, label = _bucket(str(require(params, "item_id")))
            item = find_by_id(d[kind], params["item_id"], label)
            changes: dict[str, Any] = {}
            if action == "update_item":
                if params.get("name"):
                    changes["name"] = fn.validate_text(params["name"], "name", 80)
                if params.get("item_type"):
                    changes["type"] = fn.normalize_choice(params["item_type"], _valid_types(kind), "item_type")
                if params.get("value") is not None:
                    changes["value"] = fn.money_str(fn.to_money(params["value"], "value", allow_zero=True))
                if not changes:
                    return error("No se indicó ningún campo para actualizar.")
            if not is_confirmed(params):
                preview = {"current": item}
                if changes:
                    preview["changes"] = changes
                return needs_confirmation(action, preview)
            if action == "update_item":
                item.update(changes, updated=date.today().isoformat())
                store.save()
                return ok(message="Registro actualizado.", item=item)
            d[kind].remove(item)
            store.save()
            return ok(message="Registro eliminado.", deleted=item)

        if action == "list":
            return ok(assets=d["assets"], liabilities=d["liabilities"], investments=d["investments"])

        if action == "history":
            return ok(history=d["history"], variation=fn.to_jsonable(fn.calculate_net_worth_variation(d["history"])))

        if action == "snapshot":
            return ok(message="Foto del patrimonio guardada en el historial.", snapshot=_snapshot(store))

        if action == "calculate":
            result = fn.calculate_net_worth(d["assets"], d["liabilities"], d["investments"])
            payload = {
                "result": fn.to_jsonable(result),
                "asset_distribution": fn.to_jsonable(fn.calculate_asset_distribution(d["assets"], d["investments"])),
                "liability_distribution": fn.to_jsonable(fn.calculate_liability_distribution(d["liabilities"])),
                "variation": fn.to_jsonable(fn.calculate_net_worth_variation(d["history"])),
                "formula": "Patrimonio neto = total de activos (incluye inversiones declaradas) - total de pasivos",
                "data_used": {
                    "assets": [(a["name"], a["value"]) for a in d["assets"]],
                    "investments": [(i["name"], i["value"]) for i in d["investments"]],
                    "liabilities": [(p["name"], p["value"]) for p in d["liabilities"]],
                },
            }
            if not (d["assets"] or d["liabilities"] or d["investments"]):
                payload["warning"] = "No hay activos, inversiones ni pasivos registrados; el patrimonio es 0 por falta de datos."
            if params.get("save_snapshot"):
                payload["snapshot"] = _snapshot(store)
            return ok(**payload)

        return error("Acción no válida para calculate_net_worth.")
