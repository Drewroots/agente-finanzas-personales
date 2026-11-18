# Finanzas AI — Agente inteligente de finanzas personales

Asistente **educativo** que gestiona finanzas personales en lenguaje natural mediante un
*Agent Loop* con *Tool Use Pattern* (Anthropic API, Claude Haiku 4.5 configurable).
Funciona por **terminal (CLI)**, **dashboard web (Flask)** y **API REST** sobre el mismo núcleo.

> No ejecuta operaciones financieras, no garantiza rentabilidades y no reemplaza la asesoría profesional.

## Arquitectura (5 capas, según el diagrama de referencia)

| Capa | Componente | Archivos |
|---|---|---|
| 1. Interfaces | CLI, Dashboard Flask, API REST | `main.py`, `app.py`, `templates/`, `static/` |
| 2. Núcleo del agente | Agent Loop + Claude (tool use) | `agent.py` |
| 3. Herramientas | 4 tools con esquema JSON | `tools/` |
| 4. Lógica de negocio | Cálculos con `Decimal` | `functions.py` |
| 5. Datos y gráficos | JSON con backups, Matplotlib | `storage.py`, `charts.py`, `data/` |

Flujo: usuario → interfaz → `FinanceAgent.chat()` → Claude elige herramienta → `tools/*` valida y llama a
`functions.py` → resultado estructurado → Claude lo interpreta y responde. La lógica financiera nunca vive
en el LLM: el modelo no calcula ni recuerda cifras por su cuenta.

### Herramientas del agente

| Tool | Acciones |
|---|---|
| `manage_transaction` | add, list, update*, delete* |
| `calculate_net_worth` | calculate, list, add_asset, add_liability, update_item*, remove_item*, snapshot, history |
| `analyze_finances` | summary, expenses_by_category, savings_capacity, recurring, compare_periods, budget_status, set_budget*, remove_budget*, goal_add/list/update*/remove*, report |
| `investment_analysis` | explain, add/list/update*/remove* investment, allocation, simulate, compare_scenarios |

\* Requieren `confirm=true`, que el agente solo envía tras la autorización explícita del usuario.

### Seguridad y responsabilidad

- Sin datos inventados: el agente consulta herramientas; si falta un dato, lo pregunta.
- Modificar o eliminar exige confirmación; sin ella la herramienta responde `needs_confirmation`.
- Se rechazan textos con apariencia de número de tarjeta/cuenta (13–19 dígitos); no se guardan credenciales.
- Escritura atómica + copia de seguridad en cada guardado (`data/backups/`, últimas 10) y recuperación si el JSON se daña.
- Simulaciones marcadas como **hipotéticas**; toda respuesta de inversión incluye advertencias de riesgo.
- `data/finanzas.json` (datos reales) está en `.gitignore`. El servidor escucha solo en `127.0.0.1`.
- Cada resultado incluye los datos usados (`data_used`, fórmulas) para que el usuario pueda revisarlos.

## Instalación (Windows / PowerShell)

```powershell
cd finanzas_ai
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # y elija el proveedor del modelo en .env (ver abajo)
```

## Ejecución

```powershell
python main.py              # CLI conversacional (comandos: /ayuda, /resumen, /patrimonio, /graficos, /reset, /salir)
python app.py               # Web en http://127.0.0.1:5000  (/, /dashboard, /transactions)
```

### Proveedor del modelo (con o sin clave de pago)

El agente funciona con cualquiera de estos proveedores, que se eligen en `.env` (ver `.env.example`):

| `FINANZAS_PROVIDER` | Costo | Requiere |
|---|---|---|
| `ollama` | Gratis, local | Instalar Ollama y `ollama pull qwen2.5:7b`; sin clave |
| `gemini` | Capa gratuita | `LLM_API_KEY` gratis de Google AI Studio |
| `groq` | Capa gratuita | `LLM_API_KEY` gratis de Groq |
| `anthropic` | De pago | `ANTHROPIC_API_KEY` (Claude Haiku 4.5) |
| `openai_compat` | Variable | `FINANZAS_BASE_URL` de un servicio compatible con OpenAI |

`llm.py` adapta el formato de herramientas y mensajes, de modo que el Agent Loop y las herramientas son idénticos
para todos los proveedores. Los modelos pequeños o locales pueden elegir peor las herramientas que un modelo grande:
revise siempre los resultados.

### Datos de demostración (ficticios)

```powershell
python scripts/load_demo.py
$env:FINANZAS_DATA_PATH = "data/finanzas_demo.json"
python app.py
```

El dashboard muestra un aviso cuando se usan datos de demostración. `finanzas.json` queda vacío para sus datos reales.

## API REST (JSON)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/health` | Estado y modelo |
| GET | `/api/summary?period=AAAA-MM` | Resumen del dashboard |
| GET | `/api/report?period=` | Informe financiero completo |
| GET/POST | `/api/transactions` | Listar (`type`, `period`, `category`) / registrar |
| PUT/DELETE | `/api/transactions/<id>` | Actualizar / eliminar |
| GET/POST, PUT/DELETE | `/api/assets`, `/api/liabilities`, `/api/investments` (`/<id>`) | Gestión de patrimonio |
| GET | `/api/networth`, `/api/networth/history` · POST `/api/networth/snapshot` | Patrimonio neto y su evolución |
| GET | `/api/investments/allocation` · POST `/api/investments/simulate` | Distribución y simulación hipotética |
| GET | `/api/budgets` · PUT/DELETE `/api/budgets/<categoria>` | Presupuestos |
| GET/POST, PUT/DELETE | `/api/goals` (`/<id>`) | Objetivos de ahorro |
| GET | `/api/stats?action=summary|recurring|compare_periods...` | Estadísticas |
| GET | `/api/charts/<nombre>.png?period=` | Gráficos (8 disponibles) |
| POST | `/api/chat` `{message, session_id}` | Conversación con el agente |

Ejemplo:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:5000/api/transactions -ContentType "application/json" `
  -Body '{"type":"expense","amount":45000,"category":"Alimentación","description":"Mercado"}'
```

Errores: `400` validación, `404` no encontrado, `502/503` fallo o falta de configuración del modelo. Las
peticiones DELETE/PUT por HTTP se consideran acciones explícitas del usuario.

## Pruebas

```powershell
python -m pytest -q
```

86 pruebas: cálculos (Decimal), herramientas (validación, confirmaciones, persistencia, backups),
agent loop con cliente simulado (no consume API), adaptador de proveedores compatibles con OpenAI y API/gráficos.
La integración con un modelo real (Ollama, Gemini, Groq o Claude) se verifica manualmente desde la CLI o el chat web.

## Estructura

```
finanzas_ai/
├── main.py  app.py  agent.py  functions.py  charts.py  storage.py  config.py
├── tools/        (transaction, patrimony, analysis, investment, _common)
├── data/         (finanzas.json, backups/)
├── templates/    (base, index, dashboard, transactions)
├── static/       (css, js, charts)
├── scripts/      (load_demo.py)
└── tests/
```

`storage.py` y `tools/_common.py` son adiciones a la estructura propuesta: separan la persistencia (capa 5)
y las utilidades comunes de las herramientas (capa 3) para respetar la separación de capas.
