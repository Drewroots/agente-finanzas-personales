"""Inspecciona la respuesta cruda del proveedor para una llamada de herramienta (sin imprimir la clave)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

import httpx  # noqa: E402

import config  # noqa: E402
import llm  # noqa: E402
from tools import TOOL_DEFINITIONS  # noqa: E402

payload = {
    "model": config.MODEL,
    "messages": llm.messages_to_openai("Eres un asistente financiero.", [{"role": "user", "content": "¿Cuánto he gastado este mes?"}]),
    "tools": llm.tools_to_openai(TOOL_DEFINITIONS),
    "max_tokens": 512,
}
import os  # noqa: E402

if os.getenv("EFFORT"):
    payload["reasoning_effort"] = os.environ["EFFORT"]
import time  # noqa: E402

t0 = time.time()
r = httpx.post(config.BASE_URL.rstrip("/") + "/chat/completions", json=payload,
               headers={"Authorization": f"Bearer {config.LLM_API_KEY}"}, timeout=120)
print(r.status_code, f"{time.time() - t0:.1f}s")
data = r.json()
if r.status_code != 200:
    print(json.dumps(data, ensure_ascii=False)[:1500])
else:
    msg = (data.get("choices") or [{}])[0].get("message", data)
    print(json.dumps(msg, ensure_ascii=False, indent=1)[:500], "\nusage:", data.get("usage"))
