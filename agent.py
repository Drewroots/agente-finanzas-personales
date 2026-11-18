"""Capa 2 - Núcleo del agente: Agent Loop con Tool Use Pattern (Anthropic API).

Este módulo solo orquesta la conversación con el modelo y delega todo cálculo
en las herramientas (que a su vez usan ``functions.py``). El LLM nunca calcula
ni recuerda datos por su cuenta: los consulta mediante herramientas.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

import config
from storage import DataStore
from tools import TOOL_DEFINITIONS, execute_tool

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Eres un asistente EDUCATIVO de finanzas personales. Hoy es {today}. La moneda del usuario es {currency}.
Respondes siempre en español, con claridad y de forma concisa.

CÓMO TRABAJAS
- Los datos financieros del usuario viven solo en las herramientas. Consúltalas SIEMPRE antes de dar cifras; nunca calcules de memoria ni inventes ingresos, gastos, activos, pasivos o saldos.
- Si falta un dato importante (monto, tipo, fecha, categoría dudosa, tasa de un escenario), pregúntalo antes de actuar. No lo supongas.
- Interpreta la intención, elige la herramienta adecuada, interpreta el resultado y explica el cálculo (fórmula y datos usados) en lenguaje sencillo. Si el usuario quiere revisar los datos de un cálculo, muéstralos.
- Diferencia siempre entre DATOS REGISTRADOS (reales) y ESTIMACIONES / ESCENARIOS HIPOTÉTICOS (supuestos).

AUTORIZACIÓN
- Registrar un movimiento, activo, pasivo, inversión declarada, presupuesto u objetivo cuando el usuario lo pide expresamente es una acción permitida.
- Para MODIFICAR o ELIMINAR registros, muestra el detalle y pide autorización explícita. Solo tras un "sí" claro llama de nuevo con confirm=true. Si la herramienta responde needs_confirmation, no insistas: consulta al usuario.

LÍMITES Y SEGURIDAD
- No ejecutas operaciones financieras (transferencias, compras, inversiones). Solo registras y analizas.
- Nunca pidas ni guardes contraseñas, números de tarjeta, cuentas bancarias ni credenciales. Si el usuario los escribe, indícale que no los compartas.
- No garantices rentabilidades ni presentes proyecciones como resultados seguros. Advierte sobre riesgo, comisiones, inflación, liquidez y posible pérdida de capital.
- Eres información educativa, no asesoría financiera profesional; recomienda consultar a un asesor autorizado para decisiones importantes.
- Las sugerencias deben basarse en la situación y los objetivos declarados; si no hay datos suficientes, pídelos.
- FORMATO: responde en texto plano. No uses LaTeX, ni símbolos $$, ni encabezados con #, ni negritas con **. Para listas usa guiones y escribe las fórmulas en una sola línea (por ejemplo: tasa de ahorro = (ingresos - gastos) / ingresos x 100). Muestra los montos como $1.150.000.
- Para gráficos, indica al usuario que puede verlos en el dashboard web (/dashboard) o con el comando /graficos en la terminal."""


class AgentError(RuntimeError):
    """Fallo al comunicarse con el modelo."""


class AgentConfigError(AgentError):
    """Falta configuración (por ejemplo, la API key)."""


def _block_to_dict(block: Any) -> dict[str, Any] | None:
    kind = getattr(block, "type", None)
    if kind == "text":
        return {"type": "text", "text": block.text}
    if kind == "tool_use":
        data = {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
        extra = getattr(block, "extra_content", None)  # firma de razonamiento de Gemini, se devuelve sin cambios
        if extra:
            data["extra_content"] = extra
        return data
    return None


class FinanceAgent:
    """Agente conversacional de finanzas personales."""

    def __init__(
        self,
        store: DataStore,
        client: Any | None = None,
        model: str | None = None,
        max_iterations: int | None = None,
        max_history: int = 40,
    ) -> None:
        self.store = store
        self.model = model or config.MODEL
        self.max_iterations = max_iterations or config.MAX_ITERATIONS
        self.max_history = max_history
        self._client = client
        self.messages: list[dict[str, Any]] = []
        self.last_tool_calls: list[dict[str, Any]] = []

    # -- cliente ----------------------------------------------------------
    @property
    def client(self) -> Any:
        if self._client is None:
            ready, problem = config.llm_status()
            if not ready:
                raise AgentConfigError(f"{problem} Copie .env.example a .env y complételo.")
            if config.PROVIDER == "anthropic":
                import anthropic

                self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
            else:
                import llm

                self._client = llm.OpenAICompatClient(config.BASE_URL, config.LLM_API_KEY,
                                                      reasoning_effort=config.REASONING_EFFORT or None)
        return self._client

    def system_prompt(self) -> str:
        return SYSTEM_PROMPT.format(today=date.today().isoformat(), currency=self.store.data["profile"].get("currency", config.CURRENCY))

    def reset(self) -> None:
        self.messages.clear()
        self.last_tool_calls = []

    # -- historial --------------------------------------------------------
    def _trim_history(self) -> None:
        """Descarta turnos antiguos sin romper pares tool_use / tool_result."""
        while len(self.messages) > self.max_history:
            for i in range(1, len(self.messages)):
                msg = self.messages[i]
                if msg["role"] == "user" and isinstance(msg["content"], str):
                    del self.messages[:i]
                    break
            else:
                break

    # -- agent loop -------------------------------------------------------
    def chat(self, user_message: str) -> str:
        """Procesa un mensaje del usuario y devuelve la respuesta final."""
        user_message = (user_message or "").strip()
        if not user_message:
            return "Escriba una consulta para continuar."
        self.last_tool_calls = []
        checkpoint = len(self.messages)
        self.messages.append({"role": "user", "content": user_message})
        try:
            return self._loop()
        except AgentError:
            del self.messages[checkpoint:]
            raise
        except Exception as exc:  # noqa: BLE001
            del self.messages[checkpoint:]
            logger.warning("Error en el agent loop: %s", exc)
            raise AgentError(f"No se pudo obtener respuesta del modelo: {exc}") from exc
        finally:
            self._trim_history()

    def _loop(self) -> str:
        for _ in range(self.max_iterations):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=config.MAX_TOKENS,
                system=self.system_prompt(),
                tools=TOOL_DEFINITIONS,
                messages=self.messages,
            )
            content = [d for d in (_block_to_dict(b) for b in response.content) if d]
            self.messages.append({"role": "assistant", "content": content})

            if response.stop_reason != "tool_use":
                text = "\n".join(b["text"] for b in content if b["type"] == "text").strip()
                if response.stop_reason == "max_tokens":
                    text += "\n\n(La respuesta se cortó por longitud; pida que continúe si es necesario.)"
                return text or "No obtuve una respuesta; intente reformular su consulta."

            results = []
            for block in content:
                if block["type"] != "tool_use":
                    continue
                result = execute_tool(self.store, block["name"], block["input"])
                self.last_tool_calls.append({"name": block["name"], "input": block["input"], "status": result.get("status")})
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                    "is_error": result.get("status") == "error",
                })
            self.messages.append({"role": "user", "content": results})

        # Se agotaron las iteraciones: pedir cierre sin herramientas.
        self.messages.append({"role": "user", "content": "Resume con lo obtenido hasta ahora y, si falta algo, dime qué dato necesitas."})
        response = self.client.messages.create(
            model=self.model, max_tokens=config.MAX_TOKENS, system=self.system_prompt(), messages=self.messages,
        )
        content = [d for d in (_block_to_dict(b) for b in response.content) if d]
        self.messages.append({"role": "assistant", "content": content})
        return "\n".join(b["text"] for b in content if b["type"] == "text").strip() or "No pude completar la consulta."
