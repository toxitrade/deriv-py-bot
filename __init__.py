"""
Paquete bot_python — Trading Bot 1HZ50V HMA + Mladen Flow

Importar en enzonic:

    from bot_python import HMAFlowBot, BotState, TradeRecord, run_bot

Ejemplo:

    from bot_python import HMAFlowBot
    bot = HMAFlowBot({"symbol": "1HZ50V", "stake": 10.0, ...})
"""

from .bot_1hz50v import (
    HMAFlowBot,
    BotState,
    TradeRecord,
    CONFIG,
    PUBLIC_WS,
    AUTH_WS,
    TRADING_WS,
    TICK_BUFFER,
    RECONNECT_BASE_DELAY,
    WARMUP_TICKS,
    hma,
    hma_direction,
    mladen_flow,
    now_str,
)

__all__ = [
    "HMAFlowBot",
    "BotState",
    "TradeRecord",
    "CONFIG",
    "PUBLIC_WS",
    "AUTH_WS",
    "TRADING_WS",
    "TICK_BUFFER",
    "RECONNECT_BASE_DELAY",
    "WARMUP_TICKS",
    "hma",
    "hma_direction",
    "mladen_flow",
    "now_str",
]
