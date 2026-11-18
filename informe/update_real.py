"""Actualiza report.html con la validación sobre un modelo real (Gemini) y las cifras finales (89 pruebas)."""
from pathlib import Path

p = Path(__file__).resolve().parent / "report.html"
t = p.read_text(encoding="utf-8")


def sub(old: str, new: str, count: int = 1) -> None:
    global t
    assert t.count(old) == count, (t.count(old), old[:80])
    t = t.replace(old, new)


# ---- Resumen ----
sub("La validación incluyó 86 pruebas automatizadas, todas aprobadas, y pruebas funcionales en consola y web con datos de demostración.",
    "La validación incluyó 89 pruebas automatizadas, todas aprobadas, y pruebas funcionales en consola y web con datos de demostración, "
    "incluida una validación con un modelo real (Gemini 3.5 Flash-Lite, capa gratuita) cuyas cifras coincidieron con un cálculo independiente.")
# ---- Cifras de pruebas ----
sub("las 86 pruebas se ejecutan sin red y sin costo", "las 89 pruebas se ejecutan sin red y sin costo")
sub("Se escribieron 86 pruebas con pytest [19] (Tabla V), todas aprobadas en 6,79 s (Fig. 3).",
    "Se escribieron 89 pruebas con pytest [19] (Tabla V), todas aprobadas en 4,39 s (Fig. 3).")
sub('<td><code>test_llm.py</code></td><td>Adaptador de proveedores, configuración</td><td class="r">13</td>',
    '<td><code>test_llm.py</code></td><td>Adaptador de proveedores, reintentos, firma de Gemini</td><td class="r">16</td>')
sub('<td class="r"><b>86</b></td>', '<td class="r"><b>89</b></td>')
sub("tests\\test_api.py        ..........                       [ 23%]", "tests\\test_api.py        ..........                       [ 22%]")
sub("tests\\test_functions.py  ............................     [ 55%]", "tests\\test_functions.py  ............................     [ 53%]")
sub("tests\\test_llm.py        .............                    [ 70%]", "tests\\test_llm.py        ................                 [ 71%]")
sub("86 passed in 6.79s", "89 passed in 4.39s")
sub("# 86 pruebas", "# 89 pruebas")
sub("Las 86 pruebas automatizadas y las pruebas funcionales respaldan el comportamiento descrito. El adaptador de proveedores permite operar con modelos gratuitos o locales, sin depender de una clave de pago.",
    "Las 89 pruebas automatizadas y las pruebas funcionales respaldan el comportamiento descrito. El adaptador de proveedores permite operar con modelos gratuitos o locales, "
    "sin depender de una clave de pago; con un modelo real gratuito (Gemini 3.5 Flash-Lite) el agente respondió correctamente consultas en consola y web, y sus cifras coincidieron con el cálculo independiente.")
# ---- Etapa 4: detalles descubiertos con el modelo real ----
sub("por lo que las salvaguardas se aplican en las herramientas y no solo en el <i>prompt</i>.</p>",
    "por lo que las salvaguardas se aplican en las herramientas y no solo en el <i>prompt</i>. Al probar con un modelo real se descubrió que Gemini exige devolver, en el "
    "historial, la firma de razonamiento (<i>thought signature</i>) de cada llamada a herramienta; de lo contrario responde con un error 400. El adaptador la conserva sin cambios y, "
    "además, reintenta con esperas crecientes ante errores temporales (429 y 5xx). El <i>prompt</i> pide respuestas en texto plano para que se vean bien en consola y web.</p>")
# ---- Consola: figura 4 con modelo configurado ----
sub("<span class=\"y\">Aviso: Falta LLM_API_KEY en .env para el proveedor gemini. Los comandos '/' funcionan, pero el chat requiere el modelo (.env).</span>",
    "Modelo: gemini-3.5-flash-lite (proveedor: gemini)")
# ---- Nueva subsección con el modelo real ----
new_section = '''<h3>F. Validación con un modelo de lenguaje real</h3>
  <p class="ni">Se probó el sistema con Gemini 3.5 Flash-Lite (capa gratuita de Google) sobre una copia de los datos de demostración. La Fig. 11 muestra seis consultas hechas con el mismo <i>Agent Loop</i> que usan la consola y la web; la Fig. 12, una sesión real de <code>main.py</code>; y la Fig. 13, el punto <code>/api/chat</code> con contexto de conversación. En todos los casos el modelo eligió la herramienta correcta y las cifras coincidieron con el cálculo manual de la Tabla VI: gastos de $2.350.000, patrimonio neto de $8.200.000 y tasa de ahorro de 31,77 % tras registrar un almuerzo de $38.000 (gastos de $2.388.000). La simulación con $2.000.000, aporte mensual de $150.000, 8 % anual y 3 años arrojó $8.574.229,36, igual al valor obtenido con un cálculo independiente. Al pedir eliminar el almuerzo, el agente mostró el detalle y solicitó autorización sin borrar el registro (los movimientos pasaron de 21 a 22, no a 21 de nuevo).</p>
  <p>La validación también expuso problemas reales que se corrigieron. Primero, el modelo gemini-3.8-flash devolvió errores 503 por saturación y luego 429 porque la capa gratuita permite solo 20 solicitudes diarias por modelo, lo que motivó los reintentos y el cambio al modelo Flash-Lite, que tiene cuota propia. Segundo, los modelos Gemini actuales rechazaron el historial sin la firma de razonamiento (error 400), lo que llevó a conservarla. Tercero, las primeras respuestas incluían fórmulas en LaTeX y negritas que no se ven bien en una consola, por lo que se ajustó el <i>prompt</i> a texto plano.</p>
  <h3>G. Gráficos generados</h3>'''
sub("<h3>F. Gráficos generados</h3>", new_section)
sub("<h3>G. Pruebas de validación y seguridad</h3>", "<h3>H. Pruebas de validación y seguridad</h3>")
sub("<h3>H. Cumplimiento de los requisitos</h3>", "<h3>I. Cumplimiento de los requisitos</h3>")
sub("generan con Matplotlib (Fig. 11)", "generan con Matplotlib (Fig. 14)")
sub("Fig. 11. Los ocho gráficos", "Fig. 14. Los ocho gráficos")
sub("<td>Fig. 3, Fig. 4, Tabla VI</td>", "<td>Fig. 3, Fig. 4, Fig. 11, Fig. 12, Tabla VI</td>")
sub("<td>Fig. 5–8, Fig. 9</td>", "<td>Fig. 5–9, Fig. 13</td>")
# ---- Figuras nuevas: antes de la figura de los gráficos ----
marker = '<figure class="wide">\n  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:4px">'
assert t.count(marker) == 1, t.count(marker)
figs = '''<figure class="wide" style="width:86%;margin-left:auto;margin-right:auto">
<pre class="term">[[EV:real_llm_raw]]</pre>
<figcaption>Fig. 11. Seis consultas al agente con Gemini 3.5 Flash-Lite (salida real; se resumen los registros de depuración).</figcaption>
</figure>
<figure class="wide" style="width:70%;margin-left:auto;margin-right:auto">
<pre class="term"><span class="p">$ python main.py --show-tools</span>
Modelo: gemini-3.5-flash-lite (proveedor: gemini)

<span class="p">Tú &gt;</span> ¿Cuánto dinero he recibido este mes?
  · herramienta: analyze_finances summary -&gt; ok
Asesor &gt; Durante este mes (noviembre de 2026) has recibido un total de $3.500.000,00, según 1 registro de ingresos en el sistema.

<span class="p">Tú &gt;</span> ¿Cuál es mi patrimonio neto?
  · herramienta: calculate_net_worth calculate -&gt; ok
Asesor &gt; Tu patrimonio neto actual es de $8.200.000,00.
Patrimonio neto = total de activos - total de pasivos
- Total de activos (efectivo, ahorros, bienes muebles e inversiones declaradas): $13.000.000,00
- Total de pasivos (tarjetas de crédito y préstamos): $4.800.000,00
<span class="p">Tú &gt;</span> /salir
Hasta pronto.</pre>
<figcaption>Fig. 12. Sesión real de la CLI con el modelo configurado (se omiten las líneas de la bienvenida).</figcaption>
</figure>
<figure class="wide" style="width:86%;margin-left:auto;margin-right:auto">
<pre class="term">[[EV:real_web_raw]]</pre>
<figcaption>Fig. 13. Consultas al punto <code>/api/chat</code> con el modelo real; la segunda reutiliza el mismo <code>session_id</code> (contexto).</figcaption>
</figure>
'''
t = t.replace(marker, figs + marker)
p.write_text(t, encoding="utf-8")
print("report.html actualizado")
