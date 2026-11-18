"""Genera un archivo de DEMOSTRACIÓN (datos ficticios) para probar y fotografiar el sistema.

Los datos se guardan en data/finanzas_demo.json, nunca en data/finanzas.json, y el
perfil queda marcado con demo=true (el dashboard muestra un aviso).

Uso (PowerShell):
    python scripts/load_demo.py
    $env:FINANZAS_DATA_PATH = "data/finanzas_demo.json"; python main.py
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import functions as fn  # noqa: E402
from storage import empty_data  # noqa: E402

OUT = ROOT / "data" / "finanzas_demo.json"


def build(today: date | None = None) -> dict:
    today = today or date.today()
    this_month = today.strftime("%Y-%m")
    data = empty_data()
    data["profile"].update({"demo": True, "note": "DATOS FICTICIOS DE DEMOSTRACIÓN"})
    counter = 0

    def add(kind, amount, category, desc, month, day):
        nonlocal counter
        counter += 1
        if month == this_month:
            day = min(day, today.day)
        data["transactions"].append({
            "id": f"t_demo{counter:03d}", "type": kind, "amount": f"{amount:.2f}", "category": category,
            "description": desc, "date": f"{month}-{day:02d}",
        })

    plans = {
        -2: dict(market=520000, transport=150000, fun=90000, health=0, edu=0),
        -1: dict(market=560000, transport=160000, fun=140000, health=80000, edu=0),
        0: dict(market=610000, transport=170000, fun=210000, health=0, edu=250000),
    }
    for offset, p in plans.items():
        m = fn.shift_period(this_month, offset)
        add("income", 3500000, "Salario", "Nómina", m, 1)
        if offset == -1:
            add("income", 450000, "Negocio", "Trabajo independiente", m, 18)
        add("expense", 900000, "Vivienda", "Arriendo", m, 2)
        add("expense", 210000, "Servicios", "Internet y energía", m, 6)
        add("expense", p["market"], "Alimentación", "Mercado", m, 8)
        add("expense", p["transport"], "Transporte", "Gasolina y pasajes", m, 10)
        add("expense", p["fun"], "Entretenimiento", "Salidas y streaming", m, 14)
        if p["health"]:
            add("expense", p["health"], "Salud", "Consulta médica", m, 12)
        if p["edu"]:
            add("expense", p["edu"], "Educación", "Curso en línea", m, 5)

    stamp = today.isoformat()
    data["assets"] = [
        {"id": "a_demo001", "name": "Efectivo", "type": "efectivo", "value": "300000.00", "updated": stamp},
        {"id": "a_demo002", "name": "Cuenta de ahorros", "type": "ahorros", "value": "2500000.00", "updated": stamp},
        {"id": "a_demo003", "name": "Moto", "type": "bienes_muebles", "value": "6000000.00", "updated": stamp},
    ]
    data["liabilities"] = [
        {"id": "l_demo001", "name": "Tarjeta de crédito", "type": "tarjeta_credito", "value": "800000.00", "updated": stamp},
        {"id": "l_demo002", "name": "Préstamo estudiantil", "type": "prestamo", "value": "4000000.00", "updated": stamp},
    ]
    data["investments"] = [
        {"id": "i_demo001", "name": "CDT 12 meses", "asset_class": "renta_fija", "value": "2000000.00", "updated": stamp},
        {"id": "i_demo002", "name": "Fondo de inversión colectiva", "asset_class": "fondos", "value": "1500000.00", "updated": stamp},
        {"id": "i_demo003", "name": "Acciones", "asset_class": "renta_variable", "value": "700000.00", "updated": stamp},
    ]
    data["budgets"] = {"Alimentación": "600000.00", "Transporte": "180000.00", "Entretenimiento": "150000.00",
                       "Vivienda": "900000.00"}
    data["goals"] = [
        {"id": "g_demo001", "name": "Fondo de emergencia", "target_amount": "6000000.00", "current_amount": "2500000.00",
         "deadline": f"{fn.shift_period(this_month, 8)}-28", "created": stamp},
        {"id": "g_demo002", "name": "Computador nuevo", "target_amount": "3000000.00", "current_amount": "600000.00",
         "deadline": None, "created": stamp},
    ]
    nw = fn.calculate_net_worth(data["assets"], data["liabilities"], data["investments"])
    for offset, factor in ((-2, "0.92"), (-1, "0.96"), (0, "1")):
        from decimal import Decimal
        m = fn.shift_period(this_month, offset)
        day = today.day if offset == 0 else 28
        total_a, total_l = nw["total_assets"] * Decimal(factor), nw["total_liabilities"]
        data["history"].append({"date": f"{m}-{day:02d}", "net_worth": fn.money_str(total_a - total_l),
                                "total_assets": fn.money_str(total_a), "total_liabilities": fn.money_str(total_l)})
    return data


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Datos de DEMOSTRACIÓN escritos en {OUT}")
    print('Para usarlos:  $env:FINANZAS_DATA_PATH = "data/finanzas_demo.json"; python app.py')
