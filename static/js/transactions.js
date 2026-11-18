/* Historial de movimientos: alta, filtrado, edición de monto y eliminación. */
(function () {
  const typeSel = $("#tx-type"), catSel = $("#tx-category"), body = $("#tx-body");
  const fType = $("#f-type"), fPeriod = $("#f-period");
  $("#form-tx [name=date]").value = todayISO();

  function fillCategories() {
    const list = typeSel.value === "income" ? window.INCOME_CATEGORIES : window.EXPENSE_CATEGORIES;
    catSel.innerHTML = list.map(c => `<option>${esc(c)}</option>`).join("");
  }
  typeSel.addEventListener("change", fillCategories);
  fillCategories();

  async function load() {
    const q = new URLSearchParams({ limit: 300 });
    if (fType.value) q.set("type", fType.value);
    if (fPeriod.value) q.set("period", fPeriod.value);
    try {
      const res = await api("/api/transactions?" + q);
      body.innerHTML = res.transactions.length ? res.transactions.map(t => `
        <tr><td>${esc(t.date)}</td>
        <td><span class="tag ${esc(t.type)}">${t.type === "income" ? "Ingreso" : "Gasto"}</span></td>
        <td>${esc(t.category)}</td><td>${esc(t.description)}</td>
        <td class="num ${t.type === "income" ? "pos" : "neg"}">${t.type === "income" ? "+" : "−"} ${money(t.amount)}</td>
        <td class="num"><button class="btn ghost small" data-edit="${esc(t.id)}" data-amount="${esc(t.amount)}">Editar monto</button>
        <button class="btn danger small" data-del="${esc(t.id)}">Eliminar</button></td></tr>`).join("")
        : '<tr><td colspan="6" class="muted">Sin movimientos registrados.</td></tr>';
      $("#tx-totals").textContent = `${res.matched} movimientos · Ingresos ${money(res.total_income)} · Gastos ${money(res.total_expenses)}`;
    } catch (e) { toast(e.message, true); }
  }

  $("#form-tx").addEventListener("submit", async ev => {
    ev.preventDefault();
    const d = Object.fromEntries(new FormData(ev.target));
    d.amount = Number(d.amount);
    if (!d.date) delete d.date;
    try {
      await api("/api/transactions", { method: "POST", data: d });
      ev.target.reset(); $("#form-tx [name=date]").value = todayISO(); fillCategories();
      await load(); toast("Movimiento registrado");
    } catch (e) { toast(e.message, true); }
  });

  body.addEventListener("click", async ev => {
    const edit = ev.target.closest("[data-edit]"), del = ev.target.closest("[data-del]");
    try {
      if (edit) {
        const v = prompt("Nuevo monto:", edit.dataset.amount);
        if (v === null) return;
        await api(`/api/transactions/${edit.dataset.edit}`, { method: "PUT", data: { amount: Number(v) } });
        toast("Monto actualizado");
      } else if (del) {
        if (!confirm("¿Eliminar este movimiento? Esta acción no se puede deshacer.")) return;
        await api(`/api/transactions/${del.dataset.del}`, { method: "DELETE" });
        toast("Movimiento eliminado");
      } else return;
      await load();
    } catch (e) { toast(e.message, true); }
  });

  [fType, fPeriod].forEach(el => el.addEventListener("change", load));
  $("#f-clear").addEventListener("click", () => { fType.value = ""; fPeriod.value = ""; load(); });
  load();
})();
