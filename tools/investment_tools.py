"""TOOL 4: investment_analysis - análisis educativo de inversión y diversificación."""
from __future__ import annotations

from datetime import date
from typing import Any

import functions as fn
from storage import DataStore

from ._common import DISCLAIMER, error, find_by_id, is_confirmed, needs_confirmation, ok, require

NAME = "investment_analysis"

CONCEPTS = {
    "riesgo": "El riesgo es la posibilidad de que el resultado real difiera del esperado, incluida la pérdida parcial o total del capital. En general, a mayor rentabilidad potencial, mayor riesgo.",
    "rentabilidad": "La rentabilidad es la ganancia (o pérdida) de una inversión respecto al capital aportado. La rentabilidad pasada no garantiza la futura y debe compararse después de comisiones e inflación.",
    "diversificacion": "Diversificar es repartir el capital entre distintas clases de activos, sectores o emisores para que un mal resultado en uno no afecte gravemente al conjunto. Reduce el riesgo específico, pero no elimina el riesgo de mercado ni la posibilidad de pérdida.",
    "liquidez": "La liquidez es la facilidad para convertir un activo en dinero sin perder valor. El efectivo es muy líquido; un inmueble no. Conviene mantener un fondo de emergencia líquido antes de asumir riesgos.",
    "inflacion": "La inflación es el aumento general de precios: reduce el poder adquisitivo. Una rentabilidad de 8 % con inflación de 6 % deja un rendimiento real aproximado de 2 %.",
    "horizonte": "El horizonte temporal es el tiempo durante el cual se mantendrá el dinero invertido. Objetivos de corto plazo exigen activos estables y líquidos; los de largo plazo pueden tolerar más volatilidad.",
    "renta_fija": "Instrumentos de deuda (CDT, bonos) con pagos conocidos de antemano; menor volatilidad, pero con riesgo de crédito, de inflación y de reinversión.",
    "renta_variable": "Participación en empresas (acciones). Mayor potencial de crecimiento y mayor volatilidad; puede perder valor durante largos periodos.",
    "fondos": "Vehículos colectivos que agrupan dinero de varios inversionistas y lo reparten en varios activos; cobran comisiones que reducen la rentabilidad neta.",
    "inmobiliario": "Inversión en propiedades o vehículos inmobiliarios: baja liquidez, costos de transacción y mantenimiento, valorización incierta.",
    "criptoactivos": "Activos digitales de muy alta volatilidad y regulación variable; pueden perder gran parte de su valor rápidamente.",
    "interes_compuesto": "Los rendimientos se reinvierten y generan nuevos rendimientos: con el tiempo el efecto crece de forma exponencial. Funciona igual con tasas negativas.",
    "fondo_de_emergencia": "Reserva líquida, habitualmente de 3 a 6 meses de gastos, para imprevistos; suele priorizarse antes de invertir con riesgo.",
}

SCHEMA = {
    "name": NAME,
    "description": (
        "Análisis EDUCATIVO de inversión: explica conceptos (riesgo, diversificación, liquidez, "
        "inflación...), administra las inversiones declaradas, calcula su distribución y concentración "
        "y simula escenarios HIPOTÉTICOS con tasas que aporta el usuario. Nunca garantiza "
        "rentabilidades ni recomienda una inversión concreta como decisión definitiva. No ejecuta "
        "operaciones. 'update_investment' y 'remove_investment' requieren confirm=true tras autorización."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["explain", "add_investment", "list_investments", "update_investment",
                         "remove_investment", "allocation", "simulate", "compare_scenarios"],
            },
            "concept": {"type": "string", "description": "Concepto a explicar: " + ", ".join(CONCEPTS)},
            "name": {"type": "string", "description": "Nombre de la inversión declarada."},
            "asset_class": {"type": "string", "description": ", ".join(fn.INVESTMENT_CLASSES)},
            "value": {"type": "number", "description": "Valor actual de la inversión declarada."},
            "investment_id": {"type": "string"},
            "principal": {"type": "number", "description": "Capital inicial de la simulación."},
            "monthly_contribution": {"type": "number", "description": "Aporte mensual (0 si no hay)."},
            "annual_rate_pct": {"type": "number", "description": "Tasa anual HIPOTÉTICA en % (supuesto del usuario)."},
            "years": {"type": "integer", "description": "Años de simulación (1-50)."},
            "inflation_pct": {"type": "number", "description": "Inflación anual supuesta en % (opcional)."},
            "scenarios": {
                "type": "array",
                "description": "Para compare_scenarios: lista de {label, annual_rate_pct}.",
                "items": {"type": "object", "properties": {
                    "label": {"type": "string"}, "annual_rate_pct": {"type": "number"}},
                    "required": ["annual_rate_pct"]},
            },
            "confirm": {"type": "boolean", "description": "true solo tras la autorización del usuario."},
        },
        "required": ["action"],
    },
}


def _with_disclaimer(**payload: Any) -> dict[str, Any]:
    return ok(**payload, disclaimer=DISCLAIMER,
              warnings=["Toda inversión implica riesgo, incluida la pérdida de capital.",
                        "Considere comisiones, impuestos, inflación y su necesidad de liquidez."])


def _simulation_args(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "principal": params.get("principal", 0),
        "monthly_contribution": params.get("monthly_contribution", 0),
        "years": require(params, "years"),
        "inflation_pct": params.get("inflation_pct", 0),
    }


def _brief(sim: dict[str, Any]) -> dict[str, Any]:
    return {k: sim[k] for k in ("label", "annual_rate_pct", "final_nominal", "final_real",
                                "total_contributed", "nominal_gain", "hypothetical")}


def run(store: DataStore, params: dict[str, Any]) -> dict[str, Any]:
    action = params.get("action")
    with store.lock:
        d = store.data
        invs = d["investments"]

        if action == "explain":
            key = fn._fold(str(params.get("concept", ""))).replace(" ", "_")
            if key in CONCEPTS:
                return _with_disclaimer(concept=key, explanation=CONCEPTS[key])
            return _with_disclaimer(message="Concepto no encontrado; conceptos disponibles:", available=list(CONCEPTS))

        if action == "add_investment":
            inv = {
                "id": store.new_id("i"),
                "name": fn.validate_text(require(params, "name"), "name", 80, required=True),
                "asset_class": fn.normalize_choice(params.get("asset_class"), fn.INVESTMENT_CLASSES, "asset_class"),
                "value": fn.money_str(fn.to_money(params.get("value"), "value")),
                "updated": date.today().isoformat(),
            }
            invs.append(inv)
            store.save()
            return _with_disclaimer(message="Inversión declarada registrada (solo registro; no se ejecuta ninguna operación).",
                                    investment=inv)

        if action == "list_investments":
            return ok(investments=invs)

        if action in ("update_investment", "remove_investment"):
            inv = find_by_id(invs, require(params, "investment_id"), "una inversión")
            changes: dict[str, Any] = {}
            if action == "update_investment":
                if params.get("name"):
                    changes["name"] = fn.validate_text(params["name"], "name", 80)
                if params.get("asset_class"):
                    changes["asset_class"] = fn.normalize_choice(params["asset_class"], fn.INVESTMENT_CLASSES, "asset_class")
                if params.get("value") is not None:
                    changes["value"] = fn.money_str(fn.to_money(params["value"], "value"))
                if not changes:
                    return error("No se indicó ningún campo para actualizar.")
            if not is_confirmed(params):
                preview = {"current": inv}
                if changes:
                    preview["changes"] = changes
                return needs_confirmation(action, preview)
            if action == "update_investment":
                inv.update(changes, updated=date.today().isoformat())
                store.save()
                return ok(message="Inversión actualizada.", investment=inv)
            invs.remove(inv)
            store.save()
            return ok(message="Inversión eliminada del registro.", deleted=inv)

        if action == "allocation":
            alloc = fn.calculate_investment_allocation(invs)
            capital = fn.calculate_asset_distribution(d["assets"], invs)
            return _with_disclaimer(
                investment_allocation=fn.to_jsonable(alloc),
                total_capital_distribution=fn.to_jsonable(capital),
                explanation=("Distribución porcentual por clase de activo y alertas de concentración. "
                             "La concentración alta no es una recomendación de vender; indica dependencia de pocos activos."),
                data_used=[(i["name"], i["asset_class"], i["value"]) for i in invs],
            )

        if action == "simulate":
            sim = fn.simulate_investment(annual_rate_pct=require(params, "annual_rate_pct"), **_simulation_args(params))
            return _with_disclaimer(simulation=fn.to_jsonable(sim), hypothetical=True)

        if action == "compare_scenarios":
            scenarios = params.get("scenarios")
            if not isinstance(scenarios, list) or not 2 <= len(scenarios) <= 6:
                raise fn.FinanceError("Indique entre 2 y 6 escenarios con su tasa anual hipotética.")
            results = []
            for i, sc in enumerate(scenarios, 1):
                sim = fn.simulate_investment(annual_rate_pct=sc.get("annual_rate_pct"),
                                             label=str(sc.get("label") or f"Escenario {i}"), **_simulation_args(params))
                results.append(_brief(sim))
            return _with_disclaimer(scenarios=fn.to_jsonable(results), hypothetical=True,
                                    note="Los escenarios usan tasas supuestas; ninguno es una predicción.")

        return error("Acción no válida para investment_analysis.")
