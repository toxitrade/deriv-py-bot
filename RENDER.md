# Deriv Bot - Render Deployment

## Descripción general
Bot de trading para Deriv.com desplegado en Render.com. Proporciona trading rise/fall con indicadores técnicos EMA/SMA y estrategia de martingala.

## Configuración de Render

### Variables de entorno obligatorias
Estas variables deben configurarse en el dashboard de Render (no subirlas a git):

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `DERIV_TOKEN` | Token de API de Deriv (secreto) | — |
| `DERIV_ACCOUNT_ID` | ID de cuenta Deriv | — |
| `DERIV_APP_ID` | ID de la app Deriv | — |
| `DERIV_SYMBOL` | Símbolo a operar | `1HZ50V` |
| `DERIV_STAKE` | Monto por operación | `10.0` |
| `DERIV_DEMO` | Modo demo (true/false) | `true` |
| `DERIV_DURATION` | Duración de la operación | `1` |
| `DERIV_DURATION_UNIT` | Unidad de duración (`m`=minutos, `s`=segundos) | `m` |
| `DERIV_HMA_PERIOD` | Período del indicador HMA | `20` |
| `DERIV_FLOW_PERIOD` | Período del indicador Flow | `14` |
| `DERIV_FLOW_SMOOTH` | Suavizado del indicador Flow | `3` |
| `DERIV_FLOW_THRESHOLD` | Umbral del indicador Flow | `0.0` |
| `DERIV_MARTINGALE_MULT` | Multiplicador de martingala | `2.4` |
| `DERIV_MAX_MARTINGALE_STEPS` | Pasos máximos de martingala | `999` |
| `DERIV_MULTIPLIER` | Multiplicador de beneficio | `100` |
| `DERIV_TP_PCT` | Take-profit en % | `0.001` |
| `DERIV_SL_PCT` | Stop-loss en % | `0.001` |
| `DERIV_LOG_LEVEL` | Nivel de log | `INFO` |
| `DERIV_BOT_MODE` | Modo de bot: `binary` o `multiplier` | `binary` |

### Archivo `render.yaml`
El archivo `render.yaml` contiene la configuración completa del servicio:

```yaml
services:
  - type: web
    name: deriv-py-bot
    env: python
    region: ohio
    buildCommand: "pip install -r requirements.txt && pip install -r requirements_web.txt"
    startCommand: "uvicorn main:app --host 0.0.0.0 --port $PORT"
    envVars:
      - key: DERIV_SYMBOL
        value: 1HZ50V
      - key: DERIV_STAKE
        value: 10.0
      - key: DERIV_DEMO
        value: true
      - key: DERIV_HMA_PERIOD
        value: 20
      - key: DERIV_FLOW_PERIOD
        value: 14
      - key: DERIV_FLOW_SMOOTH
        value: 3
      - key: DERIV_FLOW_THRESHOLD
        value: 0.0
      - key: DERIV_DURATION
        value: 1
      - key: DERIV_DURATION_UNIT
        value: m
      - key: DERIV_MARTINGALE_MULT
        value: 2.4
      - key: DERIV_MAX_MARTINGALE_STEPS
        value: 999
      - key: DERIV_MULTIPLIER
        value: 100
      - key: DERIV_TP_PCT
        value: 0.001
      - key: DERIV_SL_PCT
        value: 0.001
      - key: DERIV_LOG_LEVEL
        value: INFO
      - key: DERIV_BOT_MODE
        value: binary
      # Secretos - configúralos en el dashboard de Render (no se suben a git):
      - key: DERIV_TOKEN
        sync: false
      - key: DERIV_ACCOUNT_ID
        sync: false
      - key: DERIV_APP_ID
        sync: false
```

## Flujo de trabajo de despliegue

1. **Push a main**: Render detecta automáticamente y empieza el build
2. **Build**: Se instalan dependencias (`requirements.txt` y `requirements_web.txt`)
3. **Start**: `uvicorn main:app` se inicia en el puerto asignado por Render
4. **Health check**: Render verifica que la aplicación responda en el puerto

## Desarrollo local

```bash
# Variables de entorno locales
cp .env.example .env
# Editar .env con tus credenciales

# Ejecutar localmente
python3 -m bot_python.run
# O con token:
DERIV_TOKEN=tu_token python3 -m bot_python.run
```

## Endpoints de la API

La aplicación FastAPI expone los siguientes endpoints:

- `GET /printenv` - Consultar variables de entorno (solo desarrollo)
- `WS /ws` - WebSocket para streaming de ticks y señales
- `POST /trade` - Ejecutar operación
- `GET /status` - Estado actual del bot

## Notas importantes

- **Token secreto**: `DERIV_TOKEN` nunca debe subirse al repositorio. Configúralo como secret en el dashboard de Render.
- **Modo binary**: El bot usa trading tipo "rise/fall" (predicción de dirección de precio).
- **Estrategia EMA/SMA**: La señal se genera al cruce de EMA y SMA para entradas más rápidas.
- **Martingala**: Si una operación falla, el siguiente monto se multiplica por `DERIV_MARTINGALE_MULT`.
- **Logs**: Disponibles en el dashboard de Render o mediante `DERIV_LOG_FILE`.