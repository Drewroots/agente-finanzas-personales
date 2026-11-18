import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from storage import DataStore  # noqa: E402


@pytest.fixture
def store(tmp_path):
    return DataStore(tmp_path / "finanzas.json")


@pytest.fixture
def populated(store):
    """Datos de PRUEBA (no reales) con dos meses de movimientos."""
    d = store.data
    def tx(i, kind, amount, cat, desc, day):
        d["transactions"].append({"id": f"t_{i}", "type": kind, "amount": amount, "category": cat,
                                  "description": desc, "date": day})
    tx(1, "income", "3000000.00", "Salario", "Nómina", "2026-10-01")
    tx(2, "expense", "800000.00", "Vivienda", "Arriendo", "2026-10-02")
    tx(3, "expense", "400000.00", "Alimentación", "Mercado", "2026-10-05")
    tx(4, "income", "3200000.00", "Salario", "Nómina", "2026-11-01")
    tx(5, "expense", "800000.00", "Vivienda", "Arriendo", "2026-11-02")
    tx(6, "expense", "600000.00", "Alimentación", "Mercado", "2026-11-05")
    d["assets"] += [
        {"id": "a_1", "name": "Cuenta", "type": "ahorros", "value": "2000000.00", "updated": "2026-11-01"},
        {"id": "a_2", "name": "Moto", "type": "bienes_muebles", "value": "5000000.00", "updated": "2026-11-01"},
    ]
    d["liabilities"].append({"id": "l_1", "name": "Tarjeta", "type": "tarjeta_credito", "value": "1000000.00", "updated": "2026-11-01"})
    d["investments"].append({"id": "i_1", "name": "CDT", "asset_class": "renta_fija", "value": "3000000.00", "updated": "2026-11-01"})
    store.save()
    return store
