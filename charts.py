"""Capa 5 - Visualización con Matplotlib.

Se usa la API orientada a objetos (``Figure``) para que sea segura entre hilos
dentro de Flask. Cada gráfico recibe los datos y el periodo (AAAA-MM).
"""
from __future__ import annotations

import io
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

import functions as fn  # noqa: E402

PALETTE = ["#2E86AB", "#F6AE2D", "#33A17B", "#E4572E", "#8E6BBF", "#F26CA7", "#5C677D", "#9BC53D"]
INCOME_COLOR, EXPENSE_COLOR = "#33A17B", "#E4572E"
MONTHS_BACK = 6


def _fmt_money(value: float, _pos: int | None = None) -> str:
    return "$ " + f"{value:,.0f}".replace(",", ".")


def _f(value: Decimal | None) -> float:
    return float(value or 0)


def _placeholder(title: str, message: str = "Sin datos registrados") -> Figure:
    fig = Figure(figsize=(7, 4))
    ax = fig.subplots()
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.text(0.5, 0.5, message, ha="center", va="center", fontsize=12, color="#777", transform=ax.transAxes)
    ax.axis("off")
    return fig


def _money_axis(ax) -> None:
    ax.yaxis.set_major_formatter(FuncFormatter(_fmt_money))
    ax.grid(axis="y", alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)


def _periods(period: str, n: int = MONTHS_BACK) -> list[str]:
    return [fn.shift_period(period, -i) for i in range(n - 1, -1, -1)]


def _pie(title: str, labels: list[str], values: list[float], note: str = "") -> Figure:
    fig = Figure(figsize=(7, 4.4))
    ax = fig.subplots()
    ax.pie(values, labels=labels, autopct=lambda p: f"{p:.1f}%", startangle=90,
           colors=PALETTE[: len(values)], wedgeprops={"edgecolor": "white"}, textprops={"fontsize": 9})
    ax.set_title(title, fontsize=13, fontweight="bold")
    if note:
        fig.text(0.5, 0.02, note, ha="center", fontsize=9, color="#555")
    return fig


def income_vs_expenses(data: dict[str, Any], period: str) -> Figure:
    title = "Ingresos frente a gastos (COP)"
    periods = _periods(period)
    flows = [fn.calculate_cash_flow(data["transactions"], p) for p in periods]
    if not any(f["income_count"] or f["expense_count"] for f in flows):
        return _placeholder(title)
    fig = Figure(figsize=(8, 4.4))
    ax = fig.subplots()
    x = range(len(periods))
    w = 0.38
    ax.bar([i - w / 2 for i in x], [_f(f["income"]) for f in flows], w, label="Ingresos", color=INCOME_COLOR)
    ax.bar([i + w / 2 for i in x], [_f(f["expenses"]) for f in flows], w, label="Gastos", color=EXPENSE_COLOR)
    ax.set_xticks(list(x), periods)
    ax.set_xlabel("Mes")
    ax.set_ylabel("Monto (COP)")
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.legend(frameon=False)
    _money_axis(ax)
    return fig


def net_worth_evolution(data: dict[str, Any], period: str) -> Figure:
    title = "Evolución del patrimonio neto (COP)"
    history = sorted(data.get("history", []), key=lambda h: h["date"])
    if not history:
        return _placeholder(title, "Sin historial. Registre una foto del patrimonio.")
    fig = Figure(figsize=(8, 4.4))
    ax = fig.subplots()
    dates = [h["date"] for h in history]
    values = [float(h["net_worth"]) for h in history]
    ax.plot(dates, values, marker="o", color=PALETTE[0], linewidth=2)
    for d, v in zip(dates, values):
        ax.annotate(_fmt_money(v), (d, v), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8)
    ax.set_xlabel("Fecha del registro")
    ax.set_ylabel("Patrimonio neto (COP)")
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.tick_params(axis="x", rotation=30)
    _money_axis(ax)
    return fig


def expense_distribution(data: dict[str, Any], period: str) -> Figure:
    title = f"Distribución de gastos - {period}"
    rows = fn.expense_by_category(data["transactions"], period)["categories"]
    if not rows:
        return _placeholder(title, "Sin gastos en este periodo")
    return _pie(title, [r["category"] for r in rows], [_f(r["total"]) for r in rows],
                f"Total: {_fmt_money(_f(sum((r['total'] for r in rows), Decimal(0))))}")


def asset_distribution(data: dict[str, Any], period: str) -> Figure:
    title = "Distribución de activos"
    dist = fn.calculate_asset_distribution(data["assets"], data["investments"])
    if not dist["items"]:
        return _placeholder(title)
    return _pie(title, [r["label"] for r in dist["items"]], [_f(r["total"]) for r in dist["items"]],
                f"Total activos: {_fmt_money(_f(dist['total']))}")


def liability_distribution(data: dict[str, Any], period: str) -> Figure:
    title = "Distribución de pasivos"
    dist = fn.calculate_liability_distribution(data["liabilities"])
    if not dist["items"]:
        return _placeholder(title, "Sin pasivos registrados")
    return _pie(title, [r["label"] for r in dist["items"]], [_f(r["total"]) for r in dist["items"]],
                f"Total pasivos: {_fmt_money(_f(dist['total']))}")


def savings_evolution(data: dict[str, Any], period: str) -> Figure:
    title = "Evolución del ahorro mensual (COP)"
    periods = _periods(period)
    flows = [fn.calculate_cash_flow(data["transactions"], p) for p in periods]
    if not any(f["income_count"] or f["expense_count"] for f in flows):
        return _placeholder(title)
    fig = Figure(figsize=(8, 4.4))
    ax = fig.subplots()
    values = [_f(f["cash_flow"]) for f in flows]
    ax.bar(periods, values, color=[INCOME_COLOR if v >= 0 else EXPENSE_COLOR for v in values])
    ax.axhline(0, color="#444", linewidth=0.8)
    ax.set_xlabel("Mes")
    ax.set_ylabel("Ahorro = ingresos - gastos (COP)")
    ax.set_title(title, fontsize=13, fontweight="bold")
    _money_axis(ax)
    return fig


def capital_distribution(data: dict[str, Any], period: str) -> Figure:
    title = "Distribución porcentual del capital invertido"
    alloc = fn.calculate_investment_allocation(data["investments"])
    if not alloc["items"]:
        return _placeholder(title, "Sin inversiones declaradas")
    return _pie(title, [r["label"] for r in alloc["items"]], [_f(r["total"]) for r in alloc["items"]],
                f"Capital invertido declarado: {_fmt_money(_f(alloc['total']))}")


def budget_comparison(data: dict[str, Any], period: str) -> Figure:
    title = f"Presupuesto frente a gasto real - {period}"
    exe = fn.calculate_budget_execution(data["budgets"], data["transactions"], period)
    if not exe["items"]:
        return _placeholder(title, "Sin presupuestos definidos")
    fig = Figure(figsize=(8, 4.6))
    ax = fig.subplots()
    cats = [r["category"] for r in exe["items"]]
    x = range(len(cats))
    w = 0.38
    ax.bar([i - w / 2 for i in x], [_f(r["budget"]) for r in exe["items"]], w, label="Presupuesto", color=PALETTE[0])
    ax.bar([i + w / 2 for i in x], [_f(r["spent"]) for r in exe["items"]], w, label="Gasto real",
           color=[EXPENSE_COLOR if r["status"] == "excedido" else PALETTE[1] for r in exe["items"]])
    ax.set_xticks(list(x), cats, rotation=25, ha="right")
    ax.set_xlabel("Categoría")
    ax.set_ylabel("Monto (COP)")
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.legend(frameon=False)
    _money_axis(ax)
    return fig


CHARTS: dict[str, Callable[[dict[str, Any], str], Figure]] = {
    "income_vs_expenses": income_vs_expenses,
    "net_worth_evolution": net_worth_evolution,
    "expense_distribution": expense_distribution,
    "asset_distribution": asset_distribution,
    "liability_distribution": liability_distribution,
    "savings_evolution": savings_evolution,
    "capital_distribution": capital_distribution,
    "budget_comparison": budget_comparison,
}


def render_png(name: str, data: dict[str, Any], period: str | None = None) -> bytes:
    """Genera el gráfico ``name`` y devuelve los bytes PNG."""
    if name not in CHARTS:
        raise fn.NotFoundError(f"Gráfico desconocido: {name}. Disponibles: {', '.join(CHARTS)}")
    period = fn.validate_period(period)
    fig = CHARTS[name](data, period)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110)
    return buf.getvalue()


def save_all(data: dict[str, Any], out_dir: Path | str, period: str | None = None) -> list[Path]:
    """Guarda todos los gráficos como PNG en ``out_dir`` y devuelve las rutas."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in CHARTS:
        path = out / f"{name}.png"
        path.write_bytes(render_png(name, data, period))
        paths.append(path)
    return paths
