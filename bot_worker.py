#!/usr/bin/env python3
"""
Bot worker - corre como proceso separado en Render background worker
"""
import os
import sys
import asyncio
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot_python.bot_1hz50v import HMAFlowBot, state as binary_state
from bot_python.multiplier_bot import MultiplierBot, state as multiplier_state

from main import _build_config, BOT_MODE, _get_env

async def run_bot():
    """Ejecuta el bot en loop persistente."""
    cfg = _build_config()
    
    if BOT_MODE == "multiplier":
        bot = MultiplierBot(cfg)
        state = multiplier_state
    else:
        bot = HMAFlowBot(cfg)
        state = binary_state
    
    print(f"[WORKER] Iniciando bot en modo {BOT_MODE}...")
    
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
