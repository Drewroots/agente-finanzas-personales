"""Unifica el flujo de dos columnas del informe (figuras anchas sin cerrar el bloque)."""
import re
from pathlib import Path

p = Path(__file__).resolve().parent / "report.html"
t = p.read_text(encoding="utf-8")
pat = re.compile(r'</div>\s*(<figure class="wide".*?</figure>)\s*<div class="paper">', re.S)
t, n = pat.subn(lambda m: m.group(1), t)
t = t.replace("width:80%;margin-left:auto;margin-right:auto", "width:64%;margin-left:auto;margin-right:auto")
p.write_text(t, encoding="utf-8")
print("fusiones:", n)
