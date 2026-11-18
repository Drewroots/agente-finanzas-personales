# Guía paso a paso para abrir el agente

Pensada para Windows con PowerShell.

## Antes de empezar (una sola vez)

**1. Instala Python 3.10 o superior.** Descárgalo de python.org y marca **"Add Python to PATH"** durante la instalación. Para comprobarlo:

```powershell
python --version
```

**2. Abre PowerShell en la carpeta del proyecto.** Puedes abrir la carpeta en el Explorador, escribir `powershell` en la barra de direcciones y pulsar Enter. O ejecuta:

```powershell
cd "C:\Users\Andrew Stark\Documents\Agente inteligente\finanzas_ai"
```

**3. Crea el entorno virtual** (opcional, pero recomendable):

```powershell
python -m venv .venv
```

```powershell
.\.venv\Scripts\Activate.ps1
```

Si aparece un error de permisos, ejecuta esto y vuelve a intentarlo:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

**4. Instala las dependencias:**

```powershell
pip install -r requirements.txt
```

**5. Configura la clave de Gemini.** Copia `.env.example` como `.env` si todavía no existe. Ábrelo y deja estas líneas:

```
FINANZAS_PROVIDER=gemini
FINANZAS_MODEL=gemini-3.5-flash-lite
LLM_API_KEY=tu_clave_de_aistudio
```

Obtén la clave gratis en aistudio.google.com, en "Get API key".

> **Importante:** nunca incluyas el archivo `.env` en un .zip ni lo subas a un repositorio: contiene tu clave personal.

## Opción A: abrir en consola (CLI)

```powershell
python main.py
```

Debe aparecer `Modelo: gemini-3.5-flash-lite (proveedor: gemini)`. Después escribe preguntas como:

- `Gasté 38000 en un almuerzo`
- `¿Cuánto he gastado este mes?`
- `¿Cuál es mi patrimonio neto?`

Comandos útiles dentro del chat: `/ayuda`, `/resumen`, `/patrimonio`, `/graficos`, `/reset` y `/salir`.

Para ver qué herramienta usa el agente en cada respuesta:

```powershell
python main.py --show-tools
```

## Opción B: abrir la web

```powershell
python app.py
```

Déjala corriendo y abre el navegador en:

| Página | Dirección |
|---|---|
| Chat con el asesor | http://127.0.0.1:5000 |
| Dashboard con gráficos | http://127.0.0.1:5000/dashboard |
| Movimientos | http://127.0.0.1:5000/transactions |

Para detener el servidor, pulsa `Ctrl + C` en la consola.

## Cargar datos de ejemplo

Los datos de demostración están en `data/finanzas_demo.json`. Para ver el dashboard lleno, usa esa copia:

```powershell
python main.py --data data/finanzas_demo.json
```

Para regenerarla antes:

```powershell
python scripts/load_demo.py
```

## Ejecutar las 89 pruebas

```powershell
python -m pytest -q
```

Debe terminar con `89 passed`.

## Problemas frecuentes

| Síntoma | Solución |
|---|---|
| `python` no se reconoce | Reinstala Python marcando "Add to PATH" y abre una consola nueva. |
| Aviso "Falta LLM_API_KEY" | Revisa que `.env` esté en la carpeta `finanzas_ai` y tenga la clave. |
| Error 429 | Se agotó la cuota diaria gratuita. Espera un día o cambia `FINANZAS_MODEL`. |
| Error 503 | Gemini está saturado. El programa reintenta solo; si persiste, vuelve a intentar en unos minutos. |
| Puerto 5000 ocupado | Agrega `FLASK_PORT=5001` al `.env` y abre `http://127.0.0.1:5001`. |
| `ModuleNotFoundError` | Activa el entorno virtual y ejecuta `pip install -r requirements.txt`. |

## Para la sustentación (18 de noviembre)

1. Llega con el entorno ya instalado y prueba una consulta antes de exponer.
2. Abre `python app.py` y `/dashboard` en el navegador, y deja una consola lista con `python main.py`.
3. Si falla internet o la cuota, usa el PDF y las capturas del informe como respaldo.
