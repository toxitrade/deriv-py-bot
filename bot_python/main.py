"""
enzonic web app wrapper para el bot de trading 1HZ50V HMA + Mladen Flow.

Exposición:
  GET  /                → estado del bot
  GET  /status          → estado detallado (posición, trades, PnL)
  POST  /start          → inicia el bot en background (PAPER o DEMO según DERIV_TOKEN)
  POST  /stop           → detiene el bot
  GET  /signals         → última señal generada
  GET  /health          → health check para el platforma

Variables de entorno:
  DERIV_TOKEN, DERIV_SYMBOL, DERIV_STAKE, DERIV_DURATION,
  DERIV_DURATION_UNIT, DERIV_DEMO, DERIV_HMA_PERIOD, DERIV_FLOW_PERIOD,
  DERIV_FLOW_SMOOTH, DERIV_FLOW_THRESHOLD, DERIV_MAX_MARTINGALE_STEPS,
  DERIV_LOG_LEVEL, DERIV_LOG_FILE
"""

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Asegura que se encuentre el paquete bot_python (mismo directorio)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot_1hz50v import HMAFlowBot, BotState, TradeRecord, state as bot_state  # noqa: E402


# ---------------------------------------------------------------------------
# Instancia global del bot (una sola por despliegue)
# ---------------------------------------------------------------------------
_bot: Optional[HMAFlowBot] = None
_bot_task: Optional[asyncio.Task] = None
_bot_running = False


def _build_config() -> dict:
    return {
        "symbol": os.environ.get("DERIV_SYMBOL", "1HZ50V"),
        "stake": float(os.environ.get("DERIV_STAKE", "10.0")),
        "duration": int(os.environ.get("DERIV_DURATION", "1")),
        "duration_unit": os.environ.get("DERIV_DURATION_UNIT", "m"),
        "demo": os.environ.get("DERIV_DEMO", "true").lower() in ("1", "true", "yes", "on"),
        "hma_period": int(os.environ.get("DERIV_HMA_PERIOD", "20")),
        "flow_period": int(os.environ.get("DERIV_FLOW_PERIOD", "14")),
        "flow_smooth": int(os.environ.get("DERIV_FLOW_SMOOTH", "3")),
        "flow_threshold": float(os.environ.get("DERIV_FLOW_THRESHOLD", "0.0")),
        "martingale_multiplier": float(os.environ.get("DERIV_MARTINGALE_MULT", "2.4")),
        "max_martingale_steps": int(os.environ.get("DERIV_MAX_MARTINGALE_STEPS", "999")),
        "account_id": os.environ.get("DERIV_ACCOUNT_ID", ""),
        "app_id": os.environ.get("DERIV_APP_ID", "1089"),
        "log_level": os.environ.get("DERIV_LOG_LEVEL", "INFO"),
        "log_file": os.environ.get("DERIV_LOG_FILE", "bot_1hz50v.log"),
        "token": os.environ.get("DERIV_TOKEN", ""),
    }


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
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/", tags=["status"])
async def root():
    return {
        "app": "1HZ50V HMA + Mladen Flow Bot",
        "running": _bot_running,
        "mode": "DEMO" if _build_config()["token"] else "PAPER",
    }


@app.get("/health", tags=["status"])
async def health():
    return {"status": "ok", "running": _bot_running}


@app.get("/status", tags=["status"])
async def status():
    if _bot is None:
        return {"running": False, "message": "Bot no iniciado"}
    st: BotState = _bot.state if hasattr(_bot, "state") else None
    # BotState vive en el módulo; accedemos al estado global del paquete
    from bot_1hz50v import state as bot_state

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
    return {
        "running": _bot_running,
        "position": bot_state.position,
        "open_side": bot_state.open_side,
        "open_entry_price": bot_state.open_entry_price,
        "martingale_step": bot_state.martingale_step,
        "trades_today": bot_state.trades_today,
        "ticks_received": bot_state.ticks_received,
        "trades": trades,
    }


@app.post("/start", tags=["control"])
async def start_bot():
    global _bot_task, _bot_running
    if _bot_running:
        return {"status": "already_running"}
    _bot_task = asyncio.create_task(_run_bot_loop())
    return {"status": "started", "mode": "DEMO" if _build_config()["token"] else "PAPER"}


@app.post("/stop", tags=["control"])
async def stop_bot():
    global _bot_task, _bot_running
    if not _bot_running:
        return {"status": "not_running"}
    if _bot_task and not _bot_task.done():
        _bot_task.cancel()
        try:
            await _bot_task
        except asyncio.CancelledError:
            pass
    _bot_running = False
    return {"status": "stopped"}


@app.get("/signals", tags=["status"])
async def signals():
    from bot_1hz50v import state as bot_state

    if not bot_state.trades:
        return {"signal": None, "message": "Sin trades aún"}
    last = bot_state.trades[-1]
    return {
        "side": last.side,
        "entry_price": last.entry_price,
        "entry_time": last.entry_time,
        "position": bot_state.position,
        "martingale_step": bot_state.martingale_step,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
