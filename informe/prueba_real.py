"""Prueba del agente con el modelo REAL configurado en .env (usa una copia de los datos de demostración)."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

import config  # noqa: E402
from agent import FinanceAgent  # noqa: E402
from storage import DataStore  # noqa: E402

ready, problem = config.llm_status()
print(f"Proveedor: {config.PROVIDER} | Modelo: {config.MODEL} | Configurado: {ready} {problem}")
if not ready:
    raise SystemExit(1)

tmp = Path(tempfile.mkdtemp()) / "demo.json"
shutil.copy(ROOT / "data" / "finanzas_demo.json", tmp)
store = DataStore(tmp)
agent = FinanceAgent(store)

questions = sys.argv[1:] or [
    "¿Cuánto he gastado este mes?",
    "¿Cuál es mi patrimonio neto y cómo se calcula?",
    "Gasté 38000 en un almuerzo hoy",
    "¿Qué porcentaje de mis ingresos estoy ahorrando este mes?",
    "Elimina el gasto del almuerzo que acabo de registrar",
    "Simula 2000000 con aporte mensual de 150000 a 8% anual durante 3 años",
]
n_before = len(store.data["transactions"])
for q in questions:
    print(f"\n>>> {q}")
    try:
        answer = agent.chat(q)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}")
        continue
    for call in agent.last_tool_calls:
        print(f"  [herramienta] {call['name']} {json.dumps(call['input'], ensure_ascii=False)} -> {call['status']}")
    print(answer)
print(f"\nMovimientos antes: {n_before} | después: {len(store.data['transactions'])}")
