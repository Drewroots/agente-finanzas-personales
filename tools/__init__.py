"""Capa 3 - Registro de herramientas del agente (Tool Use Pattern)."""
from __future__ import annotations

import logging
from typing import Any

import functions as fn
from storage import DataStore, StorageError

from . import analysis_tools, investment_tools, patrimony_tools, transaction_tools
from ._common import error

logger = logging.getLogger(__name__)

_MODULES = (transaction_tools, patrimony_tools, analysis_tools, investment_tools)
TOOL_REGISTRY = {m.NAME: m for m in _MODULES}
TOOL_DEFINITIONS = [m.SCHEMA for m in _MODULES]


def execute_tool(store: DataStore, name: str, tool_input: dict[str, Any] | None) -> dict[str, Any]:
    """Ejecuta una herramienta y devuelve siempre un diccionario serializable."""
    module = TOOL_REGISTRY.get(name)
    if module is None:
        return error(f"Herramienta desconocida: {name}", "unknown_tool")
    if not isinstance(tool_input, dict):
        return error("Los parámetros de la herramienta deben ser un objeto.")
    try:
        return fn.to_jsonable(module.run(store, tool_input))
    except fn.FinanceError as exc:
        return error(str(exc), exc.code)
    except StorageError as exc:
        return error(f"Error de almacenamiento: {exc}", "storage")
    except Exception:  # noqa: BLE001 - nunca romper el agent loop
        logger.exception("Fallo inesperado en la herramienta %s", name)
        return error("Error interno al ejecutar la herramienta.", "internal")
