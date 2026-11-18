"""Genera una hoja de contactos del PDF para revisar el diseño."""
from pathlib import Path

import pymupdf
from PIL import Image

here = Path(__file__).resolve().parent
(here / "prev").mkdir(exist_ok=True)
doc = pymupdf.open(here / "Informe_Agente_Finanzas_IEEE.pdf")
print("paginas", len(doc))
ims = []
for i, page in enumerate(doc):
    f = here / "prev" / f"p{i + 1:02d}.png"
    page.get_pixmap(dpi=55).save(f)
    ims.append(Image.open(f))
w, h = ims[0].size
cols = 6
rows = (len(ims) + cols - 1) // cols
sheet = Image.new("RGB", (cols * w, rows * h), "white")
for i, im in enumerate(ims):
    sheet.paste(im, ((i % cols) * w, (i // cols) * h))
sheet.save(here / "prev" / "sheet.png")
