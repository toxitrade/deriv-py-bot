# deriv-py-bot

Bot de trading 1HZ50V HMA + Mladen Flow para enzonic.

## Instalación
```bash
pip install -r requirements.txt
pip install -r requirements_web.txt
```

## Ejecutar
```bash
# Modo PAPER (sin operaciones reales)
python3 main.py

# Modo DEMO (con token real)
DERIV_TOKEN=tu_token python3 main.py
```

## Endpoints FastAPI
- `GET /` — estado del bot
- `GET /health` — health check
- `GET /status` — posición, trades, PnL
- `POST /start` — iniciar bot en background
- `POST /stop` — detener bot
- `GET /signals` — última señal
- `GET /docs` — documentación Swagger

## Variables de entorno (`.env`)
Copia `.env.example` a `.env` y configura `DERIV_TOKEN` con tu token de Deriv.
