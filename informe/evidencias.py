"""Genera las evidencias REALES (salidas de CLI, pruebas, API y agent loop) usadas en el informe."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "evidence"
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


def run(cmd, stdin=None, env_extra=None):
    env = {**os.environ, "PYTHONUTF8": "1", **(env_extra or {})}
    return subprocess.run(cmd, input=stdin, capture_output=True, text=True, encoding="utf-8",
                          cwd=ROOT, env=env).stdout


# 1) CLI con datos de demostración
cli_in = "\n/resumen\n/patrimonio\n/datos\n/salir\n"
cli = run([sys.executable, "main.py"], cli_in, {"FINANZAS_DATA_PATH": "data/finanzas_demo.json", "ANTHROPIC_API_KEY": ""})
(OUT / "cli.txt").write_text(cli, encoding="utf-8")

# 2) Pruebas
pyt = run([sys.executable, "-m", "pytest", "-v", "-p", "no:cacheprovider", "--no-header", "-q"])
(OUT / "pytest.txt").write_text(pyt, encoding="utf-8")

# 3) API con almacenamiento temporal vacío
import app as app_mod  # noqa: E402
from storage import DataStore  # noqa: E402

tmp = Path(tempfile.mkdtemp())
store = DataStore(tmp / "finanzas.json")
client = app_mod.create_app(store).test_client()
lines = []


def call(method, path, body=None, show=True):
    r = getattr(client, method.lower())(path, json=body) if body is not None else getattr(client, method.lower())(path)
    data = r.get_json()
    if show:
        lines.append(f"> {method} {path}" + (f"  {json.dumps(body, ensure_ascii=False)}" if body else ""))
        text = json.dumps(data, ensure_ascii=False)
        lines.append(f"< {r.status_code}  {text[:230]}{'…' if len(text) > 230 else ''}\n")
    return data


t = call("POST", "/api/transactions", {"type": "income", "amount": 3500000, "category": "Salario", "description": "Nómina", "date": "2026-11-01"})
tid = call("POST", "/api/transactions", {"type": "expense", "amount": 45000, "category": "Alimentación", "description": "Mercado", "date": "2026-11-03"})["transaction"]["id"]
call("POST", "/api/transactions", {"type": "expense", "amount": -5})
call("POST", "/api/transactions", {"type": "expense", "amount": 10, "description": "tarjeta 4111 1111 1111 1111"})
call("POST", "/api/assets", {"name": "Cuenta de ahorros", "type": "ahorros", "value": 2000000})
call("POST", "/api/liabilities", {"name": "Préstamo", "type": "prestamo", "value": 500000})
call("GET", "/api/networth")
call("POST", "/api/investments/simulate", {"principal": 1000000, "monthly_contribution": 0, "annual_rate_pct": 10, "years": 2})
call("PUT", f"/api/transactions/{tid}", {"amount": 50000})
call("DELETE", f"/api/transactions/{tid}")
call("DELETE", f"/api/transactions/{tid}")
(OUT / "api.txt").write_text("\n".join(lines), encoding="utf-8")

# 4) Traza del agent loop con cliente simulado (NO es una llamada real a la API)
from agent import FinanceAgent  # noqa: E402


class Fake:
    def __init__(self, resp):
        self.resp, self.messages = list(resp), self

    def create(self, **kw):
        return self.resp.pop(0)


s2 = DataStore(tmp / "traza.json")
fake = Fake([
    NS(stop_reason="tool_use", content=[NS(type="tool_use", id="tu_1", name="manage_transaction",
       input={"action": "add", "type": "expense", "amount": 45000, "category": "Alimentación", "description": "Mercado"})]),
    NS(stop_reason="end_turn", content=[NS(type="text", text="Registré tu gasto de $45.000 en Alimentación.")]),
    NS(stop_reason="tool_use", content=[NS(type="tool_use", id="tu_2", name="manage_transaction",
       input={"action": "delete", "transaction_id": "__ID__"})]),
    NS(stop_reason="end_turn", content=[NS(type="text", text="Vas a eliminar el gasto de $45.000. ¿Confirmas?")]),
])
agent = FinanceAgent(s2, client=fake)
trace = ["Usuario: Gasté 45000 en el mercado"]
trace.append("Agente: " + agent.chat("Gasté 45000 en el mercado"))
trace.append(f"  [herramienta] {agent.last_tool_calls[0]['name']} {json.dumps(agent.last_tool_calls[0]['input'], ensure_ascii=False)} -> {agent.last_tool_calls[0]['status']}")
tx_id = s2.data["transactions"][0]["id"]
fake.resp[0].content[0].input["transaction_id"] = tx_id
trace.append("\nUsuario: Elimina ese gasto")
trace.append("Agente: " + agent.chat("Elimina ese gasto"))
trace.append(f"  [herramienta] {agent.last_tool_calls[0]['name']} {json.dumps(agent.last_tool_calls[0]['input'], ensure_ascii=False)} -> {agent.last_tool_calls[0]['status']}")
trace.append(f"  Movimientos almacenados tras la consulta: {len(s2.data['transactions'])} (no se eliminó sin autorización)")
(OUT / "agent_trace.txt").write_text("\n".join(trace), encoding="utf-8")
print("Evidencias escritas en", OUT)
