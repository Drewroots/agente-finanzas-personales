/* Utilidades compartidas por todas las páginas. */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

function esc(value) {
  const div = document.createElement("div");
  div.textContent = value == null ? "" : String(value);
  return div.innerHTML;
}

function money(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  const sign = n < 0 ? "-" : "";
  return sign + "$ " + Math.abs(n).toLocaleString("es-CO", { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}

function toast(message, isError = false) {
  const el = $("#toast");
  if (!el) return;
  el.textContent = message;
  el.classList.toggle("err", isError);
  el.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove("show"), isError ? 4500 : 2500);
}

async function api(path, { method = "GET", data } = {}) {
  const opts = { method, headers: {} };
  if (data !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(data);
  }
  let res;
  try {
    res = await fetch(path, opts);
  } catch (e) {
    throw new Error("No se pudo conectar con el servidor.");
  }
  let json = {};
  try { json = await res.json(); } catch (e) { /* respuesta sin cuerpo */ }
  if (!res.ok || json.status === "error") {
    throw new Error(json.message || `Error ${res.status}`);
  }
  return json;
}

function currentPeriod() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const LABELS = {
  assets: { efectivo: "Dinero disponible", ahorros: "Cuenta de ahorro", bienes_muebles: "Bien mueble", bienes_inmuebles: "Bien inmueble", otros: "Otro" },
  liabilities: { prestamo: "Préstamo", deuda_personal: "Deuda personal", tarjeta_credito: "Tarjeta de crédito", obligacion_financiera: "Obligación financiera", otros: "Otro" },
  investments: { renta_fija: "Renta fija", renta_variable: "Renta variable", fondos: "Fondos", inmobiliario: "Inmobiliario", criptoactivos: "Criptoactivos", otros: "Otros" },
};
