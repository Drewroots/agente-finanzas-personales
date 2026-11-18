"""Utilidades compartidas por las herramientas del agente (Capa 3)."""
from __future__ import annotations

from typing import Any

import functions as fn

DISCLAIMER = (
    "Información educativa basada en los datos registrados; no constituye asesoría financiera "
    "profesional ni garantiza resultados."
)


def ok(**payload: Any) -> dict[str, Any]:
    return {"status": "ok", **payload}


def error(message: str, code: str = "validation") -> dict[str, Any]:
    return {"status": "error", "code": code, "message": message}


def needs_confirmation(action: str, preview: dict[str, Any], message: str | None = None) -> dict[str, Any]:
    """Respuesta que obliga al agente a pedir autorización explícita al usuario."""
    return {
        "status": "needs_confirmation",
        "action": action,
        "preview": preview,
        "message": message or (
            "Esta operación modifica o elimina datos. Muestre el detalle al usuario, pida su "
            "autorización y, solo si la da, repita la llamada con confirm=true."
        ),
    }


def is_confirmed(params: dict[str, Any]) -> bool:
    return params.get("confirm") is True


def find_by_id(records: list[dict[str, Any]], record_id: Any, label: str) -> dict[str, Any]:
    for rec in records:
        if rec["id"] == record_id:
            return rec
    raise fn.NotFoundError(f"No existe {label} con id '{record_id}'.")


def require(params: dict[str, Any], key: str) -> Any:
    value = params.get(key)
    if value is None or value == "":
        raise fn.FinanceError(f"Falta el parámetro obligatorio '{key}'.")
    return value
