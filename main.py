"""Capa 1 - Interfaz CLI: terminal interactiva en lenguaje natural."""
from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

import charts
import config
import functions as fn
from agent import AgentConfigError, AgentError, FinanceAgent
from storage import DataStore, StorageError

BANNER = """
==============================================================
  Agente Inteligente de Finanzas Personales  (modo educativo)
  Escriba su consulta en lenguaje natural.  /ayuda para ver comandos
==============================================================
"""

HELP = """Comandos:
  /resumen    Resumen del mes actual (sin usar el modelo)
  /patrimonio Patrimonio neto actual (sin usar el modelo)
  /graficos   Genera los 8 gráficos en static/charts/
  /datos      Muestra dónde se guardan los datos
  /reset      Reinicia el contexto de la conversación
  /salir      Termina

Ejemplos:
  Recibí 3500000 de salario hoy
  Gasté 45000 en el mercado
  ¿Cuál es mi patrimonio neto?
  ¿Cómo estoy distribuyendo mis gastos este mes?
  Simula 5000000 a 8 % anual durante 5 años (hipotético)
"""


def _m(value: Decimal) -> str:
    return "$ " + f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def show_summary(store: DataStore) -> None:
    flow = fn.calculate_cash_flow(store.data["transactions"], fn.current_period())
    print(f"\nResumen {fn.current_period()}")
    print(f"  Ingresos : {_m(flow['income'])}")
    print(f"  Gastos   : {_m(flow['expenses'])}")
    print(f"  Flujo    : {_m(flow['cash_flow'])}")
    rate = flow["savings_rate_pct"]
    print(f"  Ahorro   : {'sin ingresos' if rate is None else f'{rate} %'}\n")


def show_net_worth(store: DataStore) -> None:
    d = store.data
    nw = fn.calculate_net_worth(d["assets"], d["liabilities"], d["investments"])
    print(f"\n  Activos : {_m(nw['total_assets'])}\n  Pasivos : {_m(nw['total_liabilities'])}\n  Patrimonio neto: {_m(nw['net_worth'])}\n")


def handle_command(cmd: str, store: DataStore, agent: FinanceAgent) -> bool:
    """Procesa un comando '/'. Devuelve False si se debe salir."""
    cmd = cmd.lower().strip()
    if cmd in ("/salir", "/exit", "/quit"):
        return False
    if cmd == "/ayuda":
        print(HELP)
    elif cmd == "/resumen":
        show_summary(store)
    elif cmd == "/patrimonio":
        show_net_worth(store)
    elif cmd == "/graficos":
        paths = charts.save_all(store.snapshot(), config.CHARTS_DIR)
        print("Gráficos generados:")
        for p in paths:
            print(f"  {p}")
    elif cmd == "/datos":
        print(f"Datos: {store.path}\nCopias de seguridad: {store.backup_dir}")
    elif cmd == "/reset":
        agent.reset()
        print("Contexto reiniciado.")
    else:
        print("Comando no reconocido. Use /ayuda.")
    return True


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Agente de finanzas personales (CLI)")
    parser.add_argument("--data", type=Path, help="Ruta del archivo JSON de datos")
    parser.add_argument("--show-tools", action="store_true", help="Muestra las herramientas que usa el agente")
    args = parser.parse_args(argv)

    try:
        store = DataStore(args.data) if args.data else DataStore()
    except StorageError as exc:
        print(f"Error de datos: {exc}")
        return 1
    agent = FinanceAgent(store)
    print(BANNER)
    ready, problem = config.llm_status()
    if ready:
        print(f"Modelo: {config.MODEL} (proveedor: {config.PROVIDER})\n")
    else:
        print(f"Aviso: {problem} Los comandos '/' funcionan, pero el chat requiere el modelo (.env).\n")

    while True:
        try:
            text = input("Tú > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text.startswith("/"):
            if not handle_command(text, store, agent):
                break
            continue
        try:
            answer = agent.chat(text)
        except AgentConfigError as exc:
            print(f"\n[Configuración] {exc}\n")
            continue
        except AgentError as exc:
            print(f"\n[Error] {exc}\n")
            continue
        if args.show_tools:
            for call in agent.last_tool_calls:
                print(f"  · herramienta: {call['name']} {call['input'].get('action', '')} -> {call['status']}")
        print(f"\nAsesor > {answer}\n")
    print("Hasta pronto.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
