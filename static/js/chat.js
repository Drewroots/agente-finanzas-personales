/* Interfaz conversacional con el agente. */
(function () {
  const log = $("#chat-log"), form = $("#chat-form"), input = $("#chat-input"), send = $("#chat-send");
  let sessionId = null;
  try { sessionId = sessionStorage.getItem("finanzas_session"); } catch (e) { /* sin almacenamiento */ }

  function add(text, cls, tools) {
    const div = document.createElement("div");
    div.className = "msg " + cls;
    div.textContent = text;
    if (tools && tools.length) {
      const small = document.createElement("span");
      small.className = "tools";
      small.textContent = "🔧 " + tools.map(t => `${t.name}${t.input && t.input.action ? ":" + t.input.action : ""}`).join(" · ");
      div.appendChild(small);
    }
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  async function ask(text) {
    add(text, "user");
    const typing = add("Analizando tus datos…", "bot typing");
    send.disabled = true; input.disabled = true;
    try {
      const res = await api("/api/chat", { method: "POST", data: { message: text, session_id: sessionId } });
      sessionId = res.session_id;
      try { sessionStorage.setItem("finanzas_session", sessionId); } catch (e) { /* ignorar */ }
      typing.remove();
      add(res.answer, "bot", res.tool_calls);
    } catch (e) {
      typing.remove();
      add(e.message, "bot err");
    } finally {
      send.disabled = false; input.disabled = false; input.focus();
    }
  }

  form.addEventListener("submit", ev => {
    ev.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    ask(text);
  });

  $$(".chip").forEach(chip => chip.addEventListener("click", () => ask(chip.textContent.trim())));

  $("#reset-chat").addEventListener("click", async () => {
    try { await api("/api/chat/reset", { method: "POST", data: { session_id: sessionId } }); } catch (e) { /* ignorar */ }
    sessionId = null;
    try { sessionStorage.removeItem("finanzas_session"); } catch (e) { /* ignorar */ }
    $$(".msg", log).slice(1).forEach(m => m.remove());
    toast("Conversación reiniciada");
  });
})();
