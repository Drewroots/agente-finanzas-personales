"""Construye el informe PDF (formato artículo IEEE) a partir de report.html.

Uso:  python informe/build_report.py
Edite informe/autores.json con los nombres del grupo y vuelva a ejecutar.
Requiere Google Chrome o Microsoft Edge instalado (modo headless).
"""
from __future__ import annotations

import html
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHROMES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
OUT_PDF = HERE / "Informe_Agente_Finanzas_IEEE.pdf"


def main() -> int:
    authors = json.loads((HERE / "autores.json").read_text(encoding="utf-8"))
    cover = "<br>".join(html.escape(a["nombre"]) for a in authors)
    block = "".join(
        f"<div><b>{html.escape(a['nombre'])}</b><i>{html.escape(a.get('afiliacion', 'CORHUILA'))}</i>"
        f"<i>{html.escape(a.get('correo', ''))}</i></div>" for a in authors
    )
    text = (HERE / "report.html").read_text(encoding="utf-8")
    text = text.replace("[[INTEGRANTES_PORTADA]]", cover).replace("[[AUTORES_ARTICULO]]", block)
    for ev in (HERE / "evidence").glob("*.txt"):
        text = text.replace(f"[[EV:{ev.stem}]]", html.escape(ev.read_text(encoding="utf-8-sig").strip()))
    built = HERE / "_report_build.html"
    built.write_text(text, encoding="utf-8")

    chrome = next((c for c in CHROMES if Path(c).exists()), None)
    if not chrome:
        print("No se encontró Chrome ni Edge.")
        return 1
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--allow-file-access-from-files",
                    "--virtual-time-budget=10000", f"--print-to-pdf={OUT_PDF}", built.as_uri()],
                   check=True, capture_output=True)
    print("PDF generado:", OUT_PDF)
    return 0


if __name__ == "__main__":
    sys.exit(main())
