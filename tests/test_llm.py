"""Pruebas del adaptador para proveedores compatibles con OpenAI (sin red real)."""
import json

import httpx
import pytest

import agent as agent_mod
import config
import llm
from agent import AgentConfigError, AgentError, FinanceAgent


def make_client(handler, sleeps=None):
    return llm.OpenAICompatClient("http://fake/v1", "k", transport=httpx.MockTransport(handler),
                                  sleep=(sleeps.append if sleeps is not None else (lambda s: None)))


def test_retries_transient_errors_then_succeeds():
    calls, sleeps = [], []

    def handler(request):
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(503, text="saturado")
        return reply({"content": "listo"})

    r = make_client(handler, sleeps).create(model="m", messages=[{"role": "user", "content": "hola"}])
    assert r.content[0].text == "listo" and len(calls) == 3 and sleeps == [2, 4]


def test_gives_up_after_retries_and_does_not_retry_client_errors():
    calls = []

    def always_503(request):
        calls.append(1)
        return httpx.Response(503, text="saturado")

    with pytest.raises(llm.LLMError, match="503"):
        make_client(always_503).create(model="m", messages=[{"role": "user", "content": "hola"}])
    assert len(calls) == 6  # 1 intento + 5 reintentos
    calls.clear()

    def bad_request(request):
        calls.append(1)
        return httpx.Response(400, text="mal")

    with pytest.raises(llm.LLMError, match="400"):
        make_client(bad_request).create(model="m", messages=[{"role": "user", "content": "hola"}])
    assert len(calls) == 1


def test_gemini_thought_signature_is_preserved_across_turns(store):
    """La firma de razonamiento de Gemini debe devolverse en la llamada de herramienta del historial."""
    sent = []
    sig = {"google": {"thought_signature": "FIRMA123"}}

    def handler(request):
        sent.append(json.loads(request.content))
        if len(sent) == 1:
            return reply({"content": None, "tool_calls": [{"id": "c1", "type": "function", "extra_content": sig,
                                                           "function": {"name": "analyze_finances",
                                                                        "arguments": "{\"action\": \"goal_list\"}"}}]},
                         finish="tool_calls")
        return reply({"content": "Sin objetivos."})

    assert FinanceAgent(store, client=make_client(handler)).chat("¿Tengo objetivos?") == "Sin objetivos."
    echoed = [m for m in sent[1]["messages"] if m.get("tool_calls")][0]["tool_calls"][0]
    assert echoed["extra_content"] == sig


def reply(message, finish="stop"):
    return httpx.Response(200, json={"choices": [{"message": message, "finish_reason": finish}]})


def test_tools_conversion():
    tools = llm.tools_to_openai([{"name": "t", "description": "d", "input_schema": {"type": "object"}}])
    assert tools == [{"type": "function", "function": {"name": "t", "description": "d", "parameters": {"type": "object"}}}]


def test_messages_conversion_roundtrip():
    msgs = [
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": [{"type": "text", "text": "ok"},
                                          {"type": "tool_use", "id": "c1", "name": "t", "input": {"a": 1}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1", "content": "{\"status\": \"ok\"}"}]},
    ]
    out = llm.messages_to_openai("SYS", msgs)
    assert out[0] == {"role": "system", "content": "SYS"}
    assert out[2]["tool_calls"][0]["function"]["arguments"] == '{"a": 1}'
    assert out[3] == {"role": "tool", "tool_call_id": "c1", "content": "{\"status\": \"ok\"}"}


def test_response_parsing_text_and_tool_calls():
    r = llm.response_from_openai({"choices": [{"message": {"content": "hola"}, "finish_reason": "stop"}]})
    assert r.stop_reason == "end_turn" and r.content[0].text == "hola"
    r = llm.response_from_openai({"choices": [{"message": {"content": None, "tool_calls": [
        {"id": "x", "function": {"name": "t", "arguments": "{\"a\": 2}"}}]}, "finish_reason": "tool_calls"}]})
    assert r.stop_reason == "tool_use" and r.content[0].input == {"a": 2}
    bad = llm.response_from_openai({"choices": [{"message": {"tool_calls": [
        {"function": {"name": "t", "arguments": "no es json"}}]}, "finish_reason": "stop"}]})
    assert bad.content[0].input == {} and bad.content[0].id.startswith("call_")
    assert llm.response_from_openai({"choices": [{"message": {"content": "x"}, "finish_reason": "length"}]}).stop_reason == "max_tokens"
    with pytest.raises(llm.LLMError):
        llm.response_from_openai({"error": "x"})


def test_full_agent_loop_over_openai_compat(store):
    """El agente completa un ciclo tool_use -> tool_result -> respuesta con un proveedor compatible."""
    sent = []

    def handler(request):
        body = json.loads(request.content)
        sent.append(body)
        if len(sent) == 1:
            return reply({"content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {
                "name": "manage_transaction",
                "arguments": json.dumps({"action": "add", "type": "expense", "amount": 45000, "category": "Alimentación"})}}]},
                finish="tool_calls")
        return reply({"content": "Registré tu gasto."})

    agent = FinanceAgent(store, client=make_client(handler), model="modelo-x")
    assert agent.chat("Gasté 45000 en el mercado") == "Registré tu gasto."
    assert len(store.data["transactions"]) == 1
    assert sent[0]["model"] == "modelo-x" and sent[0]["tools"][0]["type"] == "function"
    assert sent[1]["messages"][-1]["role"] == "tool"


def test_http_error_becomes_agent_error(store):
    agent = FinanceAgent(store, client=make_client(lambda r: httpx.Response(429, text="cuota agotada")))
    with pytest.raises(AgentError, match="429"):
        agent.chat("hola")
    assert agent.messages == []


def test_connection_error_message(store):
    def boom(request):
        raise httpx.ConnectError("sin servidor")

    with pytest.raises(AgentError, match="Ollama"):
        FinanceAgent(store, client=make_client(boom)).chat("hola")


@pytest.mark.parametrize("provider,key,ready", [
    ("ollama", None, True), ("gemini", None, False), ("gemini", "k", True), ("groq", "k", True), ("xyz", "k", False)])
def test_provider_configuration(monkeypatch, provider, key, ready):
    monkeypatch.setattr(config, "PROVIDER", provider)
    monkeypatch.setattr(config, "LLM_API_KEY", key)
    monkeypatch.setattr(config, "MODEL", "m")
    assert config.llm_status()[0] is ready


def test_agent_builds_openai_client_for_ollama(store, monkeypatch):
    monkeypatch.setattr(agent_mod.config, "PROVIDER", "ollama")
    monkeypatch.setattr(agent_mod.config, "BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setattr(agent_mod.config, "MODEL", "qwen2.5:7b")
    assert isinstance(FinanceAgent(store).client, llm.OpenAICompatClient)


def test_agent_missing_gemini_key(store, monkeypatch):
    monkeypatch.setattr(agent_mod.config, "PROVIDER", "gemini")
    monkeypatch.setattr(agent_mod.config, "LLM_API_KEY", None)
    with pytest.raises(AgentConfigError, match="LLM_API_KEY"):
        FinanceAgent(store).client
