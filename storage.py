"""Capa 5 - Persistencia en JSON con validación, copias de seguridad y escritura atómica."""
from __future__ import annotations

import json
import os
import shutil
import threading
import uuid
from copy import deepcopy
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import config

SCHEMA_VERSION = 1


class StorageError(RuntimeError):
    """Error al leer, validar o escribir el almacenamiento."""


def empty_data() -> dict[str, Any]:
    """Estructura vacía y ampliable del archivo ``finanzas.json``."""
    return {
        "version": SCHEMA_VERSION,
        "profile": {"currency": config.CURRENCY, "created": datetime.now().isoformat(timespec="seconds"), "demo": False},
        "transactions": [],
        "assets": [],
        "liabilities": [],
        "investments": [],
        "budgets": {},
        "goals": [],
        "history": [],
    }


_LIST_KEYS = ("transactions", "assets", "liabilities", "investments", "goals", "history")


def validate_structure(data: Any) -> None:
    """Valida la estructura general y los montos del archivo; lanza StorageError."""
    if not isinstance(data, dict):
        raise StorageError("El archivo de datos debe contener un objeto JSON.")
    for key in _LIST_KEYS:
        if not isinstance(data.get(key, []), list):
            raise StorageError(f"'{key}' debe ser una lista.")
    if not isinstance(data.get("budgets", {}), dict):
        raise StorageError("'budgets' debe ser un objeto.")
    for key, field in (("transactions", "amount"), ("assets", "value"), ("liabilities", "value"),
                       ("investments", "value")):
        for rec in data.get(key, []):
            try:
                Decimal(str(rec[field]))
                rec["id"]
            except (KeyError, InvalidOperation, TypeError):
                raise StorageError(f"Registro inválido en '{key}': {rec!r}") from None


class DataStore:
    """Acceso seguro a ``finanzas.json``.

    ``store.data`` se modifica en memoria y ``store.save()`` persiste el cambio
    creando antes una copia de seguridad del archivo anterior.
    """

    def __init__(self, path: Path | str | None = None, backup_dir: Path | str | None = None,
                 max_backups: int | None = None) -> None:
        self.path = Path(path or config.DATA_PATH)
        self.backup_dir = Path(backup_dir) if backup_dir else self.path.parent / "backups"
        self.max_backups = max_backups or config.MAX_BACKUPS
        self._lock = threading.RLock()
        self.data: dict[str, Any] = self._load()

    # -- lectura ----------------------------------------------------------
    def _read(self, path: Path) -> dict[str, Any]:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        validate_structure(data)
        base = empty_data()
        base.update(data)
        return base

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            data = empty_data()
            self.data = data
            self.save(backup=False)
            return data
        try:
            return self._read(self.path)
        except (json.JSONDecodeError, StorageError, OSError) as exc:
            corrupt = self.path.with_suffix(f".corrupto-{datetime.now():%Y%m%d%H%M%S}.json")
            shutil.copy2(self.path, corrupt)
            for backup in sorted(self.backup_dir.glob("finanzas_*.json"), reverse=True):
                try:
                    data = self._read(backup)
                except (json.JSONDecodeError, StorageError, OSError):
                    continue
                return data
            raise StorageError(
                f"El archivo {self.path.name} está dañado y no hay copias válidas. "
                f"Se conservó una copia en {corrupt.name}. Detalle: {exc}"
            ) from exc

    def reload(self) -> None:
        with self._lock:
            self.data = self._load()

    # -- escritura --------------------------------------------------------
    def save(self, backup: bool = True) -> None:
        """Valida y guarda de forma atómica; respalda el archivo previo."""
        with self._lock:
            validate_structure(self.data)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if backup and self.path.exists():
                self._make_backup()
            tmp = self.path.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(self.data, fh, ensure_ascii=False, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)

    def _make_backup(self) -> None:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        shutil.copy2(self.path, self.backup_dir / f"finanzas_{stamp}.json")
        backups = sorted(self.backup_dir.glob("finanzas_*.json"))
        for old in backups[: max(0, len(backups) - self.max_backups)]:
            old.unlink(missing_ok=True)

    # -- utilidades -------------------------------------------------------
    @staticmethod
    def new_id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:8]}"

    def snapshot(self) -> dict[str, Any]:
        """Copia profunda de los datos actuales (para cálculos sin efectos laterales)."""
        with self._lock:
            return deepcopy(self.data)

    @property
    def lock(self) -> threading.RLock:
        return self._lock
