/* Panel financiero: KPIs, gráficos, presupuesto, objetivos y patrimonio. */
(function () {
  const periodInput = $("#period");
  periodInput.value = currentPeriod();

  function kpi(label, value, sub, cls = "") {
    return `<div class="kpi"><div class="label">${esc(label)}</div><div class="value ${cls}">${value}</div>${sub ? `<div class="sub">${esc(sub)}</div>` : ""}</div>`;
  }

  function renderKpis(s) {
    const cf = s.cash_flow, nw = s.net_worth;
    const rate = cf.savings_rate_pct === null ? "—" : cf.savings_rate_pct + " %";
    $("#kpis").innerHTML =
      kpi("Ingresos", money(cf.income), `${cf.income_count} registros`, "pos") +
      kpi("Gastos", money(cf.expenses), `${cf.expense_count} registros`, "neg") +
      kpi("Flujo de caja", money(cf.cash_flow), "ingresos − gastos", Number(cf.cash_flow) >= 0 ? "pos" : "neg") +
      kpi("Tasa de ahorro", rate, cf.savings_status.replace("_", " ")) +
      kpi("Patrimonio neto", money(nw.net_worth), "activos − pasivos", Number(nw.net_worth) >= 0 ? "pos" : "neg") +
      kpi("Activos", money(nw.total_assets), `${nw.counts.assets + nw.counts.investments} registros`) +
      kpi("Pasivos", money(nw.total_liabilities), nw.debt_to_assets_pct ? `${nw.debt_to_assets_pct} % de los activos` : "");
  }

  function renderBudget(s) {
    const items = s.budget.items;
    let html = items.length ? "" : '<p class="muted">Sin presupuestos definidos.</p>';
    for (const r of items) {
      const p = Math.min(Number(r.used_pct || 0), 100);
      html += `<div class="row"><div class="head"><span>${esc(r.category)} <span class="tag ${esc(r.status)}">${esc(r.status)}</span></span>
        <span class="num">${money(r.spent)} / ${money(r.budget)}</span></div>
        <div class="bar ${esc(r.status)}"><i style="width:${p}%"></i></div></div>`;
    }
    if (s.budget.without_budget.length) {
      html += `<p class="muted small">Sin presupuesto: ${s.budget.without_budget.map(x => `${esc(x.category)} (${money(x.spent)})`).join(", ")}</p>`;
    }
    $("#budget").innerHTML = html;
  }

  function renderGoals(s) {
    if (!s.goals.length) { $("#goals").innerHTML = '<p class="muted">Sin objetivos definidos.</p>'; return; }
    $("#goals").innerHTML = s.goals.map(g => {
      const extra = g.completed ? "✅ Cumplido" :
        (g.monthly_needed ? `Aporte mensual necesario: ${money(g.monthly_needed)} (${g.months_left} meses)` : `Faltan ${money(g.remaining)}`);
      return `<div class="row"><div class="head"><span>${esc(g.name)}</span><span class="num">${money(g.current_amount)} / ${money(g.target_amount)}
        <button class="btn danger small" data-del-goal="${esc(g.id)}" title="Eliminar">✕</button></span></div>
        <div class="bar"><i style="width:${Math.min(Number(g.progress_pct), 100)}%"></i></div>
        <div class="muted small">${g.progress_pct} % · ${extra}</div></div>`;
    }).join("");
  }

  function holdingCol(title, kind, rows, typeKey) {
    const list = rows.length ? rows.map(r => `<div class="holding"><span>${esc(r.name)}<br><span class="muted small">${esc(LABELS[kind][r[typeKey]] || r[typeKey])}</span></span>
      <span class="num">${money(r.value)}<button class="btn danger small" data-del="${kind}:${esc(r.id)}" title="Eliminar">✕</button></span></div>`).join("")
      : '<p class="muted small">Sin registros.</p>';
    return `<div class="holdings"><h4>${title}</h4>${list}</div>`;
  }

  function renderHoldings(s) {
    $("#holdings").innerHTML = holdingCol("Activos", "assets", s.assets, "type") +
      holdingCol("Pasivos", "liabilities", s.liabilities, "type") +
      holdingCol("Inversiones declaradas", "investments", s.investments, "asset_class");
  }

  function loadCharts() {
    const p = periodInput.value || currentPeriod();
    $$("img[data-chart]").forEach(img => { img.src = `/api/charts/${img.dataset.chart}.png?period=${encodeURIComponent(p)}&t=${Date.now()}`; });
  }

  async function refresh() {
    try {
      const s = await api(`/api/summary?period=${encodeURIComponent(periodInput.value || currentPeriod())}`);
      $("#demo-banner").hidden = !s.demo;
      renderKpis(s); renderBudget(s); renderGoals(s); renderHoldings(s); loadCharts();
    } catch (e) { toast(e.message, true); }
  }

  async function submit(ev, fn) {
    ev.preventDefault();
    try { await fn(Object.fromEntries(new FormData(ev.target))); ev.target.reset(); refreshTypes(); await refresh(); toast("Guardado"); }
    catch (e) { toast(e.message, true); }
  }

  const numeric = (o, ...keys) => { keys.forEach(k => { if (o[k] === "") delete o[k]; else if (k in o) o[k] = Number(o[k]); }); return o; };

  $("#form-budget").addEventListener("submit", ev => submit(ev, d =>
    api(`/api/budgets/${encodeURIComponent(d.category)}`, { method: "PUT", data: { amount: Number(d.amount) } })));
  $("#form-goal").addEventListener("submit", ev => submit(ev, d =>
    api("/api/goals", { method: "POST", data: numeric(d, "target_amount", "current_amount") })));
  $("#form-holding").addEventListener("submit", ev => submit(ev, d => {
    const body = { name: d.name, value: Number(d.value) };
    if (d.kind === "investments") body.asset_class = d.type; else body.type = d.type;
    return api(`/api/${d.kind}`, { method: "POST", data: body });
  }));

  function refreshTypes() {
    const kind = $("#holding-kind").value;
    $("#holding-type").innerHTML = Object.entries(LABELS[kind]).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
  }
  $("#holding-kind").addEventListener("change", refreshTypes);
  refreshTypes();

  document.addEventListener("click", async ev => {
    const del = ev.target.closest("[data-del]"), delGoal = ev.target.closest("[data-del-goal]");
    try {
      if (del) {
        const [kind, id] = del.dataset.del.split(":");
        if (!confirm("¿Eliminar este registro? Esta acción no se puede deshacer.")) return;
        await api(`/api/${kind}/${id}`, { method: "DELETE" });
      } else if (delGoal) {
        if (!confirm("¿Eliminar este objetivo?")) return;
        await api(`/api/goals/${delGoal.dataset.delGoal}`, { method: "DELETE" });
      } else return;
      await refresh(); toast("Eliminado");
    } catch (e) { toast(e.message, true); }
  });

  $("#btn-snapshot").addEventListener("click", async () => {
    try { await api("/api/networth/snapshot", { method: "POST" }); await refresh(); toast("Patrimonio guardado en el historial"); }
    catch (e) { toast(e.message, true); }
  });

  periodInput.addEventListener("change", refresh);
  refresh();
})();
