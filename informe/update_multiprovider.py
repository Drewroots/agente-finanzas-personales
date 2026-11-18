"""Actualiza report.html: 86 pruebas y agente compatible con varios proveedores de modelos."""
from pathlib import Path

p = Path(__file__).resolve().parent / "report.html"
t = p.read_text(encoding="utf-8")


def sub(old: str, new: str, count: int = 1) -> None:
    global t
    assert t.count(old) == count, (t.count(old), old[:70])
    t = t.replace(old, new)


# Resumen
sub("un modelo de lenguaje, Claude Haiku 4.5, se limita",
    "un modelo de lenguaje configurable (Gemini, Groq, Ollama o Claude, mediante un adaptador compatible con la API de OpenAI) se limita")
sub("La validación incluyó 73 pruebas automatizadas", "La validación incluyó 86 pruebas automatizadas")
sub("entre ellas que la integración con el modelo real depende de una clave de API y que el sistema no constituye asesoría financiera.",
    "entre ellas que la calidad de la selección de herramientas depende del modelo elegido, en especial si es pequeño o local, y que el sistema no constituye asesoría financiera.")
# Objetivos
sub("basado en el patrón de uso de herramientas sobre la API de Anthropic, que funcione",
    "basado en el patrón de uso de herramientas sobre un modelo de lenguaje configurable, que funcione")
sub("conectarlas a un <i>Agent Loop</i> con Claude Haiku 4.5 configurable.",
    "conectarlas a un <i>Agent Loop</i> independiente del proveedor, con modelos gratuitos (Gemini, Groq, Ollama) o de pago (Claude).")
# Figuras
sub("AGENT LOOP (agent.py) · Claude Haiku 4.5 · Tool Use", "AGENT LOOP (agent.py) · LLM configurable (llm.py) · Tool Use")
sub('<text x="480" y="30">Claude (API)</text>', '<text x="480" y="30">LLM (API)</text>')
# Etapa 4
sub("El modelo es configurable mediante la variable <code>FINANZAS_MODEL</code>.</p>",
    "El proveedor y el modelo se eligen en <code>.env</code> (<code>FINANZAS_PROVIDER</code> y <code>FINANZAS_MODEL</code>).</p>"
    "\n  <p>Para no depender de una clave de pago se añadió el módulo <code>llm.py</code>, un adaptador que expone la misma interfaz "
    "mínima del cliente de Anthropic y traduce las herramientas y los mensajes al formato de la API compatible con OpenAI, que ofrecen "
    "Gemini [18], Groq y Ollama. Así el <i>Agent Loop</i> y las herramientas son idénticos para cualquier proveedor. Los modelos pequeños o "
    "locales pueden elegir peor las herramientas que un modelo grande, por lo que las salvaguardas se aplican en las herramientas y no solo en el <i>prompt</i>.</p>")
# Pruebas
sub("Se escribieron 73 pruebas con pytest [18] (Tabla V), todas aprobadas en 5,07 s (Fig. 3).",
    "Se escribieron 86 pruebas con pytest [19] (Tabla V), todas aprobadas en 6,79 s (Fig. 3).")
sub("la API REST y la generación de los ocho gráficos.</p>",
    "el adaptador de proveedores (con un servidor simulado), la API REST y la generación de los ocho gráficos.</p>")
sub('    <tr><td><code>test_api.py</code></td><td>API, páginas, gráficos, demo</td><td class="r">10</td></tr>\n    <tr><td colspan="2"><b>Total</b></td><td class="r"><b>73</b></td></tr>',
    '    <tr><td><code>test_api.py</code></td><td>API, páginas, gráficos, demo</td><td class="r">10</td></tr>\n'
    '    <tr><td><code>test_llm.py</code></td><td>Adaptador de proveedores, configuración</td><td class="r">13</td></tr>\n'
    '    <tr><td colspan="2"><b>Total</b></td><td class="r"><b>86</b></td></tr>')
sub('''tests\\test_agent.py      ..........                       [ 13%]
tests\\test_api.py        ..........                       [ 27%]
tests\\test_functions.py  ............................     [ 65%]
tests\\test_tools.py      .........................        [100%]

<span class="g">============================== 73 passed in 5.07s ==============================</span>''',
    '''tests\\test_agent.py      ..........                       [ 11%]
tests\\test_api.py        ..........                       [ 23%]
tests\\test_functions.py  ............................     [ 55%]
tests\\test_llm.py        .............                    [ 70%]
tests\\test_tools.py      .........................        [100%]

<span class="g">============================== 86 passed in 6.79s ==============================</span>''')
sub("<pre class=\"term\">$ python -m pytest -v", "<pre class=\"term\">$ python -m pytest")
# Validación
sub("<tr><td>Sin clave <code>ANTHROPIC_API_KEY</code></td><td>Mensaje de configuración (503 en la API)</td></tr>",
    "<tr><td>Proveedor sin clave o desconocido</td><td>Mensaje de configuración (503 en la API)</td></tr>\n"
    "    <tr><td>Respuesta con argumentos de herramienta inválidos</td><td>Se tratan como vacíos; la herramienta responde con error de validación</td></tr>")
# Discusión
sub("Primero, la integración con Claude Haiku 4.5 requiere una clave de API; las pruebas del <i>Agent Loop</i> usan un cliente simulado y la validación con el modelo real depende de ese acceso, por lo que la calidad de la selección de herramientas con lenguaje natural libre debe evaluarse con consultas reales.",
    "Primero, las pruebas del <i>Agent Loop</i> usan clientes simulados para no depender de la red ni de una clave; la calidad de la selección de herramientas con lenguaje natural libre debe evaluarse con consultas reales y varía según el modelo, sobre todo si es pequeño o local.")
sub("La separación entre el modelo y la lógica financiera permitió verificar los cálculos de forma independiente de la API: las 73 pruebas",
    "La separación entre el modelo y la lógica financiera permitió verificar los cálculos de forma independiente de la API: las 86 pruebas")
# Conclusiones
sub("Las 73 pruebas automatizadas y las pruebas funcionales respaldan el comportamiento descrito; la evaluación con el modelo real queda sujeta a la configuración de la clave de API.",
    "Las 86 pruebas automatizadas y las pruebas funcionales respaldan el comportamiento descrito. El adaptador de proveedores permite operar con modelos gratuitos o locales, sin depender de una clave de pago.")
# Referencias: nueva [18] y pytest pasa a [19]
sub('    <li>pytest-dev, “pytest documentation.”',
    '    <li>Google, “OpenAI compatibility,” Gemini API Documentation. Accessed: Nov. 17, 2026. [Online]. Available: https://ai.google.dev/gemini-api/docs/openai</li>\n'
    '    <li>pytest-dev, “pytest documentation.”')
# Instalación
sub("copy .env.example .env   # agregar ANTHROPIC_API_KEY", "copy .env.example .env   # elegir proveedor y clave")
sub("python -m pytest -q      # 73 pruebas", "python -m pytest -q      # 86 pruebas")
p.write_text(t, encoding="utf-8")
print("report.html actualizado")
