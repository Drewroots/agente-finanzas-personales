"""Capa 2 - Adaptador para proveedores compatibles con la API de OpenAI.

Permite usar el mismo Agent Loop con modelos gratuitos o locales (Ollama,
Gemini, Groq...) sin la clave de pago de Anthropic. Expone la misma interfaz
mínima que el cliente de Anthropic (``client.messages.create(...)``) y devuelve
objetos con ``content`` (bloques ``text``/``tool_use``) y ``stop_reason``, por lo
que ``agent.py`` no necesita saber qué proveedor se usa.
"""
from __future__ import annotations

import json
import time
import uuid
from types import SimpleNamespace as NS
from typing import Any, Callable

import httpx

# Proveedor -> (URL base, modelo por defecto, ¿requiere clave?)
PRESETS: dict[str, dict[str, Any]] = {
    "ollama": {"base_url": "http://localhost:11434/v1", "model": "qwen2.5:7b", "needs_key": False},
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-3.5-flash-lite", "needs_key": True},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile", "needs_key": True},
    "openai_compat": {"base_url": "", "model": "", "needs_key": False},
}


class LLMError(RuntimeError):
    """Fallo al comunicarse con el proveedor del modelo."""


def tools_to_openai(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Convierte las definiciones de herramientas de Anthropic al formato de OpenAI."""
    return [
        {"type": "function", "function": {"name": t["name"], "description": t.get("description", ""),
                                          "parameters": t["input_schema"]}}
        for t in tools or []
    ]


def messages_to_openai(system: str | None, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convierte el historial (formato Anthropic) al formato de chat de OpenAI."""
    out: list[dict[str, Any]] = []
    if system:
        out.append({"role": "system", "content": system})
    for msg in messages:
        content = msg["content"]
        if isinstance(content, str):
            out.append({"role": msg["role"], "content": content})
            continue
        if msg["role"] == "assistant":
            text = "\n".join(b["text"] for b in content if b["type"] == "text").strip()
            calls = []
            for b in content:
                if b["type"] != "tool_use":
                    continue
                call = {"id": b["id"], "type": "function",
                        "function": {"name": b["name"], "arguments": json.dumps(b["input"], ensure_ascii=False)}}
                if b.get("extra_content"):  # p. ej. thought_signature de Gemini: debe devolverse tal cual
                    call["extra_content"] = b["extra_content"]
                calls.append(call)
            entry: dict[str, Any] = {"role": "assistant", "content": text or None}
            if calls:
                entry["tool_calls"] = calls
            out.append(entry)
        else:  # usuario con tool_result
            for block in content:
                if block["type"] == "tool_result":
                    out.append({"role": "tool", "tool_call_id": block["tool_use_id"], "content": block["content"]})
                elif block["type"] == "text":
                    out.append({"role": "user", "content": block["text"]})
    return out


def _parse_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def response_from_openai(data: dict[str, Any]) -> NS:
    """Convierte la respuesta de chat/completions al formato que usa el agente."""
    try:
        choice = data["choices"][0]
        message = choice["message"]
    except (KeyError, IndexError, TypeError):
        raise LLMError(f"Respuesta inesperada del proveedor: {str(data)[:200]}") from None
    blocks = []
    if message.get("content"):
        blocks.append(NS(type="text", text=message["content"]))
    calls = message.get("tool_calls") or []
    for call in calls:
        fn = call.get("function", {})
        blocks.append(NS(type="tool_use", id=call.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                         name=fn.get("name", ""), input=_parse_arguments(fn.get("arguments")),
                         extra_content=call.get("extra_content")))
    if calls:
        stop = "tool_use"
    elif choice.get("finish_reason") == "length":
        stop = "max_tokens"
    else:
        stop = "end_turn"
    return NS(content=blocks, stop_reason=stop)


class OpenAICompatClient:
    """Cliente mínimo con la interfaz ``client.messages.create`` de Anthropic."""

    RETRY_STATUS = (429, 500, 502, 503, 504)

    def __init__(self, base_url: str, api_key: str | None = None, timeout: float = 180.0,
                 transport: httpx.BaseTransport | None = None, retries: int = 5,
                 sleep: Callable[[float], None] = time.sleep, reasoning_effort: str | None = None) -> None:
        if not base_url:
            raise LLMError("Falta la URL base del proveedor (FINANZAS_BASE_URL).")
        self._retries, self._sleep, self._effort = retries, sleep, reasoning_effort
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._http = httpx.Client(base_url=base_url.rstrip("/") + "/", headers=headers, timeout=timeout,
                                  transport=transport)
        self.messages = self  # permite client.messages.create(...)

    def create(self, *, model: str, messages: list[dict[str, Any]], system: str | None = None,
               tools: list[dict[str, Any]] | None = None, max_tokens: int = 2048, **_: Any) -> NS:
        payload: dict[str, Any] = {"model": model, "messages": messages_to_openai(system, messages),
                                   "max_tokens": max_tokens, "temperature": 0.2}
        if tools:
            payload["tools"] = tools_to_openai(tools)
        if self._effort:
            payload["reasoning_effort"] = self._effort  # menos razonamiento = respuestas más rápidas
        resp = None
        for attempt in range(self._retries + 1):
            try:
                resp = self._http.post("chat/completions", json=payload)
            except httpx.ConnectError:
                raise LLMError("No se pudo conectar con el proveedor del modelo. Si usa Ollama, verifique que esté "
                               "ejecutándose (ollama serve).") from None
            except httpx.HTTPError as exc:
                raise LLMError(f"Error de red al llamar al modelo: {exc}") from exc
            if resp.status_code not in self.RETRY_STATUS or attempt == self._retries:
                break
            self._sleep(min(2 ** (attempt + 1), 30))  # 2, 4, 8, 16, 30 s: saturación o límite de cuota temporal
        if resp.status_code != 200:
            raise LLMError(f"El proveedor respondió {resp.status_code}: {resp.text[:300]}")
        return response_from_openai(resp.json())
