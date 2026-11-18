"""Prueba del endpoint web /api/chat con el modelo REAL configurado (copia de los datos de demostración)."""
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

import app as app_mod  # noqa: E402
import config  # noqa: E402
from storage import DataStore  # noqa: E402

tmp = Path(tempfile.mkdtemp()) / "demo.json"
shutil.copy(ROOT / "data" / "finanzas_demo.json", tmp)
client = app_mod.create_app(DataStore(tmp)).test_client()
print(f"Proveedor: {config.PROVIDER} | Modelo: {config.MODEL}")
sid = None
for q in ["¿Cuáles son mis principales gastos este mes?", "¿Y qué significa diversificar mi capital?"]:
    r = client.post("/api/chat", json={"message": q, "session_id": sid})
    data = r.get_json()
    print(f"\nPOST /api/chat  {q!r} -> HTTP {r.status_code}")
    if r.status_code != 200:
        print(data)
        continue
    sid = data["session_id"]
    print("herramientas:", [(c["name"], c["status"]) for c in data["tool_calls"]])
    print(data["answer"])
