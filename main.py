"""
enzonic web app wrapper — Bot de trading 1HZ50V HMA + Mladen Flow (unificado).

Soporta dos modos seleccionables por variable de entorno DERIV_BOT_MODE:
  - binary  → contratos binary (CALL/PUT) con duración fija + martingala
  - multiplier → contratos multiplier (leverage) con TP/SL + salida por señal

Exposición:
  GET  /                → estado del bot
  GET  /status          → estado detallado (posición, trades, PnL)
  POST /start           → inicia el bot en background
  POST /stop            → detiene el bot
  GET  /signals         → última señal generada
  GET  /health          → health check para la plataforma
  GET  /logs            → últimas líneas del archivo de log

Variables de entorno (comunes):
  DERIV_BOT_MODE        binary | multiplier  (default: binary)
  DERIV_TOKEN           Token de API de Deriv (demo). Sin él va en PAPER.
  DERIV_SYMBOL          Símbolo (default: 1HZ50V)
  DERIV_STAKE           Stake por contrato (USD, default: 10.0)
  DERIV_DEMO            true|false (default: true)
  DERIV_HMA_PERIOD      HMA period (default: 20)
  DERIV_FLOW_PERIOD     Flow period (default: 14)
  DERIV_FLOW_SMOOTH     Flow smooth (default: 3)
  DERIV_FLOW_THRESHOLD  Umbral de cruce (default: 0.0)
  DERIV_LOG_LEVEL       INFO | DEBUG | WARNING (default: INFO)
  DERIV_LOG_FILE        Archivo de log (default: bot_1hz50v.log o multiplier_bot.log)
  DERIV_ACCOUNT_ID      ID de cuenta Options Trading (para OTP)
  DERIV_APP_ID          App ID (default: 1089, requerido para PAT)

Solo modo binary:
  DERIV_DURATION        Duración del contrato en minutos (default: 1)
  DERIV_DURATION_UNIT   m (default: m)
  DERIV_MARTINGALE_MULT Multiplicador martingala (default: 2.4)
  DERIV_MAX_MARTINGALE_STEPS (default: 4)

Solo modo multiplier:
  DERIV_MULTIPLIER      Multiplicador de apalancamiento (default: 100)
  DERIV_TP_PCT          Take profit % del precio (default: 0.001)
  DERIV_SL_PCT          Stop loss % del precio (default: 0.001)
"""

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

# Asegura que se encuentre el paquete bot_python (mismo directorio)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BOT_MODE = os.environ.get("DERIV_BOT_MODE", "binary").lower()

if BOT_MODE == "multiplier":
    from bot_python.multiplier_bot import (  # noqa: E402
        MultiplierBot as HMAFlowBot,
        state as bot_state,
    )
    BotState = type("BotState", (), {})  # placeholder para compatibilidad de tipo
else:
    from bot_python.bot_1hz50v import (  # noqa: E402
        HMAFlowBot,
        BotState,
        state as bot_state,
    )


def _build_config() -> dict:
    common = {
        "symbol": os.environ.get("DERIV_SYMBOL", "1HZ50V"),
        "stake": float(os.environ.get("DERIV_STAKE", "10.0")),
        "demo": os.environ.get("DERIV_DEMO", "true").lower()
        in ("1", "true", "yes", "on"),
        "hma_period": int(os.environ.get("DERIV_HMA_PERIOD", "20")),
        "flow_period": int(os.environ.get("DERIV_FLOW_PERIOD", "14")),
        "flow_smooth": int(os.environ.get("DERIV_FLOW_SMOOTH", "3")),
        "flow_threshold": float(os.environ.get("DERIV_FLOW_THRESHOLD", "0.0")),
        "account_id": os.environ.get("DERIV_ACCOUNT_ID", ""),
        "app_id": os.environ.get("DERIV_APP_ID", "1089"),
        "log_level": os.environ.get("DERIV_LOG_LEVEL", "INFO"),
        "log_file": os.environ.get(
            "DERIV_LOG_FILE",
            "multiplier_bot.log" if BOT_MODE == "multiplier" else "bot_1hz50v.log",
        ),
        "token": os.environ.get("DERIV_TOKEN", ""),
    }

    if BOT_MODE == "multiplier":
        common.update(
            {
                "multiplier": int(os.environ.get("DERIV_MULTIPLIER", "100")),
                "tp_pct": float(os.environ.get("DERIV_TP_PCT", "0.001")),
                "sl_pct": float(os.environ.get("DERIV_SL_PCT", "0.001")),
            }
        )
    else:
        common.update(
            {
                "duration": int(os.environ.get("DERIV_DURATION", "1")),
                "duration_unit": os.environ.get("DERIV_DURATION_UNIT", "m"),
                "martingale_multiplier": float(
                    os.environ.get("DERIV_MARTINGALE_MULT", "2.4")
                ),
                "max_martingale_steps": int(
                    os.environ.get("DERIV_MAX_MARTINGALE_STEPS", "999")
                ),
            }
        )

    return common


# ---------------------------------------------------------------------------
# Instancia global del bot (una sola por despliegue)
# ---------------------------------------------------------------------------
_bot: Optional[HMAFlowBot] = None
_bot_task: Optional[asyncio.Task] = None
_bot_running = False


async def _run_bot_loop() -> None:
    global _bot_running
    cfg = _build_config()
    _bot = HMAFlowBot(cfg)
    _bot_running = True
    try:
        await _bot.run()
    except asyncio.CancelledError:
        pass
    finally:
        _bot_running = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Arranque: no inicia el bot automáticamente (se hace por POST /start)
    yield
    # Cierre: detiene el bot si está corriendo
    global _bot_task, _bot_running
    if _bot_task and not _bot_task.done():
        _bot_task.cancel()
        try:
            await _bot_task
        except asyncio.CancelledError:
            pass
    _bot_running = False


app = FastAPI(
    title="1HZ50V HMA + Mladen Flow Bot",
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/", tags=["status"])
async def root():
    return {
        "app": "1HZ50V HMA + Mladen Flow Bot",
        "running": _bot_running,
        "mode": BOT_MODE,
        "trade_mode": "DEMO" if _build_config()["token"] else "PAPER",
    }


@app.get("/health", tags=["status"])
async def health():
    return {"status": "ok", "running": _bot_running, "mode": BOT_MODE}


@app.get("/status", tags=["status"])
async def status():
    if _bot is None:
        return {
            "running": False,
            "message": "Bot no iniciado",
            "mode": BOT_MODE,
        }

    trades = [
        {
            "entry_time": t.entry_time,
            "exit_time": t.exit_time,
            "side": t.side,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "stake": t.stake,
            "pnl": t.pnl,
            "win": t.win,
            "contract_id": t.contract_id,
        }
        for t in bot_state.trades
    ]

    base = {
        "running": _bot_running,
        "mode": BOT_MODE,
        "position": bot_state.position,
        "open_side": bot_state.open_side,
        "open_entry_price": bot_state.open_entry_price,
        "trades_today": bot_state.trades_today,
        "ticks_received": bot_state.ticks_received,
        "trades": trades,
    }

    # Campos específicos por modo
    if BOT_MODE == "binary":
        base.update(
            {
                "martingale_step": bot_state.martingale_step,
                "daily_pnl": bot_state.daily_pnl,
            }
        )
    else:
        base.update(
            {
                "multiplier": bot_state.multiplier,
                "daily_pnl": bot_state.daily_pnl,
            }
        )

    return base


@app.post("/start", tags=["control"])
async def start_bot():
    global _bot_task, _bot_running
    if _bot_running:
        return {"status": "already_running", "mode": BOT_MODE}
    _bot_task = asyncio.create_task(_run_bot_loop())
    return {
        "status": "started",
        "mode": BOT_MODE,
        "trade_mode": "DEMO" if _build_config()["token"] else "PAPER",
    }


@app.post("/stop", tags=["control"])
async def stop_bot():
    global _bot_task, _bot_running
    if not _bot_running:
        return {"status": "not_running", "mode": BOT_MODE}
    if _bot_task and not _bot_task.done():
        _bot_task.cancel()
        try:
            await _bot_task
        except asyncio.CancelledError:
            pass
    _bot_running = False
    return {"status": "stopped", "mode": BOT_MODE}


@app.get("/signals", tags=["status"])
async def signals():
    if not bot_state.trades:
        return {"signal": None, "message": "Sin trades aún", "mode": BOT_MODE}
    last = bot_state.trades[-1]
    return {
        "side": last.side,
        "entry_price": last.entry_price,
        "entry_time": last.entry_time,
        "position": bot_state.position,
        "mode": BOT_MODE,
    }


@app.get("/logs", tags=["status"])
async def logs(lines: int = 50):
    """Devuelve las últimas N líneas del archivo de log del bot."""
    log_file = _build_config().get("log_file", "bot_1hz50v.log")
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        tail = all_lines[-lines:] if lines > 0 else all_lines
        return {
            "log_file": log_file,
            "lines": len(tail),
            "logs": "".join(tail),
        }
    except FileNotFoundError:
        return {
            "log_file": log_file,
            "lines": 0,
            "logs": "Archivo de log no encontrado aún",
        }
    except Exception as e:
        return {"log_file": log_file, "lines": 0, "logs": f"Error leyendo log: {e}"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
    )
