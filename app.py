"""Capa 1 - Dashboard web (Flask) y API REST sobre el mismo núcleo del agente.

La API reutiliza las herramientas del agente (con ``confirm=True``, porque la
petición HTTP ya es una acción explícita del usuario), de modo que la lógica de
validación existe en un único lugar.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Callable

from flask import Flask, Response, jsonify, render_template, request

import charts
import config
import functions as fn
from agent import AgentConfigError, AgentError, FinanceAgent
from storage import DataStore, StorageError
from tools import execute_tool

logger = logging.getLogger(__name__)
MAX_SESSIONS = 50


def create_app(store: DataStore | None = None, agent_factory: Callable[[DataStore], FinanceAgent] | None = None) -> Flask:
    app = Flask(__name__)
    app.json.ensure_ascii = False
    app.config["JSON_SORT_KEYS"] = False
    store = store or DataStore()
    agent_factory = agent_factory or FinanceAgent
    sessions: dict[str, FinanceAgent] = {}

    # ---------------- utilidades ----------------
    def tool(tool_name: str, /, **params: Any) -> tuple[Response, int]:
        """Ejecuta una herramienta y traduce su estado a un código HTTP."""
        result = execute_tool(store, tool_name, params)
        if result["status"] == "error":
            code = {"not_found": 404, "unknown_tool": 400, "validation": 400}.get(result.get("code"), 500)
            return jsonify(result), code
        return jsonify(result), 200

    def body() -> dict[str, Any]:
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else {}

    @app.errorhandler(fn.FinanceError)
    def _finance_error(exc: fn.FinanceError):
        return jsonify({"status": "error", "code": exc.code, "message": str(exc)}), (404 if exc.code == "not_found" else 400)

    @app.errorhandler(StorageError)
    def _storage_error(exc: StorageError):
        return jsonify({"status": "error", "code": "storage", "message": str(exc)}), 500

    # ---------------- páginas ----------------
    @app.get("/")
    def index():
        return render_template("index.html", page="chat")

    @app.get("/dashboard")
    def dashboard():
        return render_template("dashboard.html", page="dashboard", chart_names=list(charts.CHARTS))

    @app.get("/transactions")
    def transactions_page():
        return render_template("transactions.html", page="transactions",
                               expense_categories=fn.EXPENSE_CATEGORIES, income_categories=fn.INCOME_CATEGORIES)

    # ---------------- API: salud y resumen ----------------
    @app.get("/api/health")
    def health():
        ready, problem = config.llm_status()
        return jsonify({"status": "ok", "provider": config.PROVIDER, "model": config.MODEL,
                        "llm_configured": ready, "detail": problem})

    @app.get("/api/summary")
    def summary():
        period = fn.validate_period(request.args.get("period"))
        d = store.snapshot()
        flow = fn.calculate_cash_flow(d["transactions"], period)
        payload = {
            "period": period,
            "cash_flow": flow,
            "net_worth": fn.calculate_net_worth(d["assets"], d["liabilities"], d["investments"]),
            "expenses_by_category": fn.expense_by_category(d["transactions"], period),
            "budget": fn.calculate_budget_execution(d["budgets"], d["transactions"], period),
            "goals": [fn.goal_progress(g) for g in d["goals"]],
            "assets": d["assets"], "liabilities": d["liabilities"], "investments": d["investments"],
            "investment_allocation": fn.calculate_investment_allocation(d["investments"]),
            "recent_transactions": sorted(d["transactions"], key=lambda t: (t["date"], t["id"]), reverse=True)[:8],
            "demo": d["profile"].get("demo", False),
        }
        return jsonify(fn.to_jsonable(payload))

    @app.get("/api/report")
    def report():
        return jsonify(fn.to_jsonable(fn.generate_financial_report(store.snapshot(), request.args.get("period"))))

    # ---------------- API: movimientos ----------------
    @app.get("/api/transactions")
    def list_transactions():
        a = request.args
        return tool("manage_transaction", action="list", type=a.get("type"), period=a.get("period"),
                    category=a.get("category"), limit=a.get("limit", 200))

    @app.post("/api/transactions")
    def add_transaction():
        res, code = tool("manage_transaction", **{**body(), "action": "add"})
        return res, 201 if code == 200 else code

    @app.put("/api/transactions/<tid>")
    def update_transaction(tid: str):
        return tool("manage_transaction", **{**body(), "action": "update", "transaction_id": tid, "confirm": True})

    @app.delete("/api/transactions/<tid>")
    def delete_transaction(tid: str):
        return tool("manage_transaction", action="delete", transaction_id=tid, confirm=True)

    # ---------------- API: activos, pasivos e inversiones ----------------
    def _item_routes(prefix: str, add_action: str, kind: str) -> None:
        def get_items():
            return jsonify({"status": "ok", kind: store.snapshot()[kind]})

        def add_item():
            data = body()
            data.setdefault("item_type", data.pop("type", None))
            res, code = tool("calculate_net_worth", **{**data, "action": add_action})
            return res, 201 if code == 200 else code

        def update_item(item_id: str):
            data = body()
            if "type" in data:
                data["item_type"] = data.pop("type")
            return tool("calculate_net_worth", **{**data, "action": "update_item", "item_id": item_id, "confirm": True})

        def delete_item(item_id: str):
            return tool("calculate_net_worth", action="remove_item", item_id=item_id, confirm=True)

        for fnc, methods, path in ((get_items, ["GET"], ""), (add_item, ["POST"], ""),
                                   (update_item, ["PUT"], "/<item_id>"), (delete_item, ["DELETE"], "/<item_id>")):
            app.add_url_rule(f"/api/{prefix}{path}", f"{prefix}_{fnc.__name__}", fnc, methods=methods)

    _item_routes("assets", "add_asset", "assets")
    _item_routes("liabilities", "add_liability", "liabilities")

    @app.get("/api/investments")
    def list_investments():
        return tool("investment_analysis", action="list_investments")

    @app.post("/api/investments")
    def add_investment():
        res, code = tool("investment_analysis", **{**body(), "action": "add_investment"})
        return res, 201 if code == 200 else code

    @app.put("/api/investments/<iid>")
    def update_investment(iid: str):
        return tool("investment_analysis", **{**body(), "action": "update_investment", "investment_id": iid, "confirm": True})

    @app.delete("/api/investments/<iid>")
    def delete_investment(iid: str):
        return tool("investment_analysis", action="remove_investment", investment_id=iid, confirm=True)

    @app.get("/api/investments/allocation")
    def allocation():
        return tool("investment_analysis", action="allocation")

    @app.post("/api/investments/simulate")
    def simulate():
        return tool("investment_analysis", **{**body(), "action": "simulate"})

    # ---------------- API: patrimonio ----------------
    @app.get("/api/networth")
    def networth():
        return tool("calculate_net_worth", action="calculate")

    @app.post("/api/networth/snapshot")
    def networth_snapshot():
        return tool("calculate_net_worth", action="snapshot")

    @app.get("/api/networth/history")
    def networth_history():
        return tool("calculate_net_worth", action="history")

    # ---------------- API: presupuestos y objetivos ----------------
    @app.get("/api/budgets")
    def budgets():
        return tool("analyze_finances", action="budget_status", period=request.args.get("period"))

    @app.put("/api/budgets/<category>")
    def set_budget(category: str):
        return tool("analyze_finances", action="set_budget", category=category, amount=body().get("amount"), confirm=True)

    @app.delete("/api/budgets/<category>")
    def delete_budget(category: str):
        return tool("analyze_finances", action="remove_budget", category=category, confirm=True)

    @app.get("/api/goals")
    def goals():
        return tool("analyze_finances", action="goal_list")

    @app.post("/api/goals")
    def add_goal():
        res, code = tool("analyze_finances", **{**body(), "action": "goal_add"})
        return res, 201 if code == 200 else code

    @app.put("/api/goals/<gid>")
    def update_goal(gid: str):
        return tool("analyze_finances", **{**body(), "action": "goal_update", "goal_id": gid, "confirm": True})

    @app.delete("/api/goals/<gid>")
    def delete_goal(gid: str):
        return tool("analyze_finances", action="goal_remove", goal_id=gid, confirm=True)

    @app.get("/api/stats")
    def stats():
        a = request.args
        return tool("analyze_finances", action=a.get("action", "summary"), period=a.get("period"), compare_to=a.get("compare_to"))

    # ---------------- API: gráficos ----------------
    @app.get("/api/charts/<name>.png")
    def chart(name: str):
        png = charts.render_png(name, store.snapshot(), request.args.get("period"))
        return Response(png, mimetype="image/png", headers={"Cache-Control": "no-store"})

    # ---------------- API: chat con el agente ----------------
    @app.post("/api/chat")
    def chat():
        data = body()
        message = str(data.get("message", "")).strip()
        if not message:
            return jsonify({"status": "error", "message": "El mensaje está vacío."}), 400
        if len(message) > 2000:
            return jsonify({"status": "error", "message": "El mensaje supera los 2000 caracteres."}), 400
        sid = str(data.get("session_id") or uuid.uuid4().hex)[:64]
        if sid not in sessions:
            if len(sessions) >= MAX_SESSIONS:
                sessions.pop(next(iter(sessions)))
            sessions[sid] = agent_factory(store)
        agent = sessions[sid]
        try:
            answer = agent.chat(message)
        except AgentConfigError as exc:
            return jsonify({"status": "error", "code": "config", "message": str(exc)}), 503
        except AgentError as exc:
            return jsonify({"status": "error", "code": "agent", "message": str(exc)}), 502
        return jsonify({"status": "ok", "session_id": sid, "answer": answer, "tool_calls": agent.last_tool_calls})

    @app.post("/api/chat/reset")
    def chat_reset():
        sessions.pop(str(body().get("session_id", "")), None)
        return jsonify({"status": "ok"})

    @app.errorhandler(404)
    def _not_found(_exc):
        if request.path.startswith("/api/"):
            return jsonify({"status": "error", "code": "not_found", "message": "Ruta no encontrada."}), 404
        return render_template("index.html", page="chat"), 404

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_app().run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=False)
