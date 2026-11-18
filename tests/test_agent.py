"""Pruebas del Agent Loop con un cliente simulado (sin llamar a la API real)."""
from types import SimpleNamespace as NS

import pytest

import agent as agent_mod
from agent import AgentConfigError, AgentError, FinanceAgent


def text(t, stop="end_turn"):
    return NS(content=[NS(type="text", text=t)], stop_reason=stop)


def tool(name, tid="tu_1", **inp):
    return NS(content=[NS(type="tool_use", id=tid, name=name, input=inp)], stop_reason="tool_use")


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        import copy
        self.calls.append(copy.deepcopy(kwargs))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_agent_executes_tool_and_returns_text(store):
    client = FakeClient([
        tool("manage_transaction", action="add", type="expense", amount=45000, category="Alimentación"),
        text("Registré tu gasto de $45.000 en Alimentación."),
    ])
    agent = FinanceAgent(store, client=client)
    answer = agent.chat("Gasté 45000 en el mercado")
    assert "45.000" in answer
    assert len(store.data["transactions"]) == 1
    assert agent.last_tool_calls[0]["name"] == "manage_transaction"
    # el resultado de la herramienta se devolvió al modelo
    last_call_msgs = client.calls[1]["messages"]
    assert last_call_msgs[-1]["content"][0]["type"] == "tool_result"
    assert client.calls[0]["tools"] and "EDUCATIVO" in client.calls[0]["system"]


def test_agent_keeps_context_between_turns(store):
    client = FakeClient([text("Hola"), text("Te dije hola.")])
    agent = FinanceAgent(store, client=client)
    agent.chat("Hola")
    agent.chat("¿Qué dijiste?")
    assert len(client.calls[1]["messages"]) == 3
    agent.reset()
    assert agent.messages == []


def test_tool_errors_flagged_not_crashing(store):
    client = FakeClient([tool("manage_transaction", action="add", type="expense"), text("Necesito el monto.")])
    agent = FinanceAgent(store, client=client)
    assert "monto" in agent.chat("Registra un gasto")
    result = client.calls[1]["messages"][-1]["content"][0]
    assert result["is_error"] is True


def test_confirmation_flow_is_not_bypassed(store):
    store.data["transactions"].append({"id": "t_1", "type": "expense", "amount": "10.00", "category": "Otros", "description": "", "date": "2026-11-01"})
    client = FakeClient([tool("manage_transaction", action="delete", transaction_id="t_1"), text("¿Confirmas eliminar?")])
    agent = FinanceAgent(store, client=client)
    agent.chat("Elimina el movimiento t_1")
    assert len(store.data["transactions"]) == 1
    assert agent.last_tool_calls[0]["status"] == "needs_confirmation"


def test_api_failure_rolls_back_history(store):
    agent = FinanceAgent(store, client=FakeClient([RuntimeError("sin red")]))
    with pytest.raises(AgentError):
        agent.chat("Hola")
    assert agent.messages == []


def test_max_iterations_closes_gracefully(store):
    loops = [tool("analyze_finances", tid=f"tu_{i}", action="goal_list") for i in range(2)]
    client = FakeClient(loops + [text("Resumen parcial.")])
    agent = FinanceAgent(store, client=client, max_iterations=2)
    assert agent.chat("analiza todo") == "Resumen parcial."


def test_missing_api_key(store, monkeypatch):
    monkeypatch.setattr(agent_mod.config, "PROVIDER", "anthropic")
    monkeypatch.setattr(agent_mod.config, "ANTHROPIC_API_KEY", None)
    with pytest.raises(AgentConfigError):
        FinanceAgent(store).chat("Hola")


def test_model_is_configurable(store):
    assert FinanceAgent(store, client=FakeClient([]), model="otro-modelo").model == "otro-modelo"


def test_history_trim_keeps_valid_start(store):
    agent = FinanceAgent(store, client=FakeClient([text(str(i)) for i in range(10)]), max_history=4)
    for i in range(10):
        agent.chat(f"msg {i}")
    assert len(agent.messages) <= 5
    assert agent.messages[0]["role"] == "user" and isinstance(agent.messages[0]["content"], str)


def test_empty_message(store):
    assert "consulta" in FinanceAgent(store, client=FakeClient([])).chat("   ")
