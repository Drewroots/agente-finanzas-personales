"""Ejecuta main.py (CLI) con el modelo REAL sobre una copia de los datos de demostración y guarda la salida."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
tmp = Path(tempfile.mkdtemp()) / "demo.json"
shutil.copy(ROOT / "data" / "finanzas_demo.json", tmp)
entrada = "\n".join(["¿Cuánto dinero he recibido este mes?", "¿Cuál es mi patrimonio neto?", "/salir"]) + "\n"
res = subprocess.run([sys.executable, "-X", "utf8", "main.py", "--data", str(tmp), "--show-tools"], input=entrada,
                     capture_output=True, text=True, encoding="utf-8", cwd=ROOT, timeout=300)
salida = res.stdout.replace(str(tmp), "data/finanzas_demo.json")
(Path(__file__).resolve().parent / "evidence" / "real_cli_raw.txt").write_text(salida, encoding="utf-8")
print(salida)
