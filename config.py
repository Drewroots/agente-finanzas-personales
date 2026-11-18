"""Configuración central del proyecto (variables de entorno y rutas)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from llm import PRESETS

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Proveedor del modelo: anthropic | ollama | gemini | groq | openai_compat
PROVIDER: str = os.getenv("FINANZAS_PROVIDER", "anthropic").strip().lower()
ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY") or None
LLM_API_KEY: str | None = os.getenv("LLM_API_KEY") or None  # Gemini, Groq u otro compatible
BASE_URL: str = os.getenv("FINANZAS_BASE_URL") or PRESETS.get(PROVIDER, {}).get("base_url", "")
_DEFAULT_MODEL = "claude-haiku-4-5" if PROVIDER == "anthropic" else PRESETS.get(PROVIDER, {}).get("model", "")
MODEL: str = os.getenv("FINANZAS_MODEL") or _DEFAULT_MODEL
# Nivel de razonamiento (none/low/medium/high). Por defecto "low" en Gemini: más rápido y con menos cuota.
REASONING_EFFORT: str = os.getenv("FINANZAS_REASONING_EFFORT", "low" if PROVIDER == "gemini" else "").strip().lower()
MAX_TOKENS: int = int(os.getenv("FINANZAS_MAX_TOKENS", "2048"))
MAX_ITERATIONS: int = int(os.getenv("FINANZAS_MAX_ITERATIONS", "8"))
CURRENCY: str = os.getenv("FINANZAS_CURRENCY", "COP")

DATA_PATH = Path(os.getenv("FINANZAS_DATA_PATH", BASE_DIR / "data" / "finanzas.json"))
BACKUP_DIR = DATA_PATH.parent / "backups"
MAX_BACKUPS: int = int(os.getenv("FINANZAS_MAX_BACKUPS", "10"))
CHARTS_DIR = BASE_DIR / "static" / "charts"

FLASK_HOST: str = os.getenv("FLASK_HOST", "127.0.0.1")
FLASK_PORT: int = int(os.getenv("FLASK_PORT", "5000"))


def llm_status() -> tuple[bool, str]:
    """Indica si el proveedor está configurado y, si no, qué falta."""
    if PROVIDER == "anthropic":
        return (True, "") if ANTHROPIC_API_KEY else (False, "Falta ANTHROPIC_API_KEY en .env.")
    preset = PRESETS.get(PROVIDER)
    if preset is None:
        return False, f"Proveedor desconocido: {PROVIDER}. Use anthropic, ollama, gemini, groq u openai_compat."
    if preset["needs_key"] and not LLM_API_KEY:
        return False, f"Falta LLM_API_KEY en .env para el proveedor {PROVIDER}."
    if not MODEL:
        return False, "Falta FINANZAS_MODEL en .env."
    return True, ""
