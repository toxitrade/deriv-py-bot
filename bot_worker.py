#!/usr/bin/env python3
"""
Bot worker - corre como proceso separado en Render background worker
"""
import os
import sys
import asyncio
import time
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot_python.bot_1hz50v import HMAFlowBot, state as binary_state
from bot_python.multiplier_bot import MultiplierBot, state as multiplier_state

CONFIG_FILE = "config.json"

def _load_config():
    """Carga config desde config.json + variables de entorno."""
    # Defaults
    cfg = {
        "symbol": os.environ.get("DERIV_SYMBOL", "1HZ50V"),
        "stake": float(os.environ.get("DERIV_STAKE", "10.0")),
        "multiplier": int(os.environ.get("DERIV_MULTIPLIER", "100")),
        "demo": os.environ.get("DERIV_DEMO", "true").lower() == "true",
        "hma_period": int(os.environ.get("DERIV_HMA_PERIOD", "30")),
        "flow_period": int(os.environ.get("DERIV_FLOW_PERIOD", "14")),
        "flow_smooth": int(os.environ.get("DERIV_FLOW_SMOOTH", "3")),
        "flow_threshold": float(os.environ.get("DERIV_FLOW_THRESHOLD", "0.3")),
        "tp_pct": float(os.environ.get("DERIV_TP_PCT", "0.001")),
        "sl_pct": float(os.environ.get("DERIV_SL_PCT", "0.001")),
        "account_id": os.environ.get("DERIV_ACCOUNT_ID", ""),
        "app_id": os.environ.get("DERIV_APP_ID", ""),
        "log_level": os.environ.get("DERIV_LOG_LEVEL", "INFO"),
        "log_file": os.environ.get("DERIV_LOG_FILE", "bot.log"),
        "token": os.environ.get("DERIV_TOKEN", "").strip(),
    }
    
    # Override from config.json if exists
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                file_cfg = json.load(f)
                cfg.update(file_cfg)
        except:
            pass
    
    return cfg

async def run_bot():
    """Ejecuta el bot en loop persistente."""
    cfg = _load_config()
    mode = cfg.get("mode", "binary").lower()
    
    if mode == "multiplier":
        bot = MultiplierBot(cfg)
        state = multiplier_state
    else:
        bot = HMAFlowBot(cfg)
        state = binary_state
    
    print(f"[WORKER] Iniciando bot en modo {mode}...")
    
    while True:
        try:
            await bot.run()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[WORKER] Error en bot: {e}. Reiniciando en 5s...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(run_bot())
