#!/usr/bin/env python3
"""
1HZ50V HMA + Mladen Flow Trading Bot — Raspberry Pi ready
==========================================================

Bot autocontenido para Deriv (demo/paper por defecto).
Estrategia: cruce de flujo (Mladen) filtrado por tendencia (Hull MA).
Parámetros optimizados por sweep sobre 1HZ50V (1-min binary).

Archivos necesarios en la Pi:
  - bot_1hz50v_pi.py          (este archivo)
  - .env                      (opcional: DERIV_TOKEN=...)
  - requirements_pi.txt       (pip install -r)

Ejecutar:
  python3 bot_1hz50v_pi.py            # PAPER (solo señales, sin token)
  DERIV_TOKEN=xxx python3 bot_1hz50v_pi.py  # DEMO (coloca contratos)

Variables de entorno:
  DERIV_TOKEN        Token de API de Deriv (demo). Sin él va en PAPER.
  DERIV_SYMBOL       Símbolo (default: 1HZ50V)
  DERIV_STAKE        Stake por contrato (default: 10.0)
  DERIV_DURATION     Duración en minutos (default: 1)
  DERIV_HMA_PERIOD   HMA period (default: 20)
  DERIV_FLOW_PERIOD  Flow period (default: 14)
  DERIV_FLOW_THRESHOLD Umbral de cruce (default: 0.0)
  DERIV_LOG_LEVEL    INFO | DEBUG | WARNING (default: INFO)
  DERIV_LOG_FILE     Archivo de log (default: bot_1hz50v.log)
  DERIV_DEMO         true|false (default: true)

IMPORTANT: mladen_flow() es un placeholder. Reemplaza por la fórmula
real de TradingView antes de operar con dinero.
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import math
import os
import signal
import sys
import time
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Deque, List, Optional

try:
    import websockets
except ImportError:
    print("ERROR: falta la librería 'websockets'. Instala con: pip install -r requirements_pi.txt")
    sys.exit(1)


# ============================================================================
# CONFIGURACIÓN
# ============================================================================
def env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


def env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name, "")
    if not v:
        return default
    return v.lower() in ("1", "true", "yes", "on")


CONFIG = {
    "symbol": env_str("DERIV_SYMBOL", "1HZ50V"),
    "stake": env_float("DERIV_STAKE", 10.0),
    "duration": env_int("DERIV_DURATION", 1),
    "duration_unit": env_str("DERIV_DURATION_UNIT", "m"),
    "demo": env_bool("DERIV_DEMO", True),
    "hma_period": env_int("DERIV_HMA_PERIOD", 20),
    "flow_period": env_int("DERIV_FLOW_PERIOD", 14),
    "flow_smooth": env_int("DERIV_FLOW_SMOOTH", 3),
    "flow_threshold": env_float("DERIV_FLOW_THRESHOLD", 0.0),
    # Martingala
    "martingale_multiplier": env_float("DERIV_MARTINGALE_MULT", 2.0),
    "max_martingale_steps": env_int("DERIV_MAX_MARTINGALE_STEPS", 5),
    "max_stake": env_float("DERIV_MAX_STAKE", 100.0),
    "cooldown_seconds": env_int("DERIV_COOLDOWN_SECONDS", 30),
    "account_id": env_str("DERIV_ACCOUNT_ID", ""),
    "app_id": env_str("DERIV_APP_ID", ""),
    "log_level": env_str("DERIV_LOG_LEVEL", "INFO"),
    "log_file": env_str("DERIV_LOG_FILE", "bot_1hz50v.log"),
    "token": "".join(c for c in env_str("DERIV_TOKEN", "") if ord(c) > 32).strip(),
}

PUBLIC_WS = None  # Se construye dinámicamente en connect_public() con DERIV_APP_ID
OTP_BASE = "https://api.derivws.com"                              # REST para OTP de trading
APP_ID = env_str("DERIV_APP_ID", "")                             # Requerido para PAT
TICK_BUFFER = 500
RECONNECT_BASE_DELAY = 5  # segundos
MAX_CANDLES = 5000
WARMUP_CANDLES = 150


# ============================================================================
# LOGGING
# ============================================================================
def setup_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("1hz50v_bot")
    logger.setLevel(getattr(logging, level.upper(), logging.DEBUG))
    logger.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    try:
        fh = logging.FileHandler(CONFIG["log_file"], encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception as e:
        logger.warning(f"No se pudo abrir archivo de log {CONFIG['log_file']}: {e}")

    return logger


# Initial setup with default level (will be overridden in bot __init__)
log = setup_logging()


# ============================================================================
# INDICADORES (estrategia HMA + Mladen Flow)
# ============================================================================
def _wma(values: List[float], period: int) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(values)
    if period <= 0:
        return out
    wsum = sum(range(1, period + 1))
    for i in range(period - 1, len(values)):
        window = values[i - period + 1 : i + 1]
        # Filtrar nan para que WMA pueda empezar antes
        valid = [(j + 1) * v for j, v in enumerate(window) 
                 if not (isinstance(v, float) and math.isnan(v))]
        if valid:
            out[i] = sum(valid) / wsum
        else:
            out[i] = float("nan")
    return out


def hma(values: List[float], period: int) -> List[Optional[float]]:
    """Hull Moving Average: HMA = WMA(2*WMA(n/2) - WMA(n), round(sqrt(n)))"""
    n = max(1, period)
    half = max(1, n // 2)
    sqrt_n = max(1, round(math.sqrt(n)))

    wma_half = _wma(values, half)
    wma_full = _wma(values, n)

    raw: List[Optional[float]] = [None] * len(values)
    for i in range(len(values)):
        if wma_half[i] is not None and wma_full[i] is not None:
            raw[i] = 2.0 * wma_half[i] - wma_full[i]

    raw_floats = [r if r is not None else float("nan") for r in raw]
    return _wma(raw_floats, sqrt_n)  # type: ignore[return-value]


def hma_direction(hma_series: List[Optional[float]]) -> List[Optional[int]]:
    out: List[Optional[int]] = [None] * len(hma_series)
    for i in range(1, len(hma_series)):
        cur, prev = hma_series[i], hma_series[i - 1]
        if cur is None or prev is None:
            continue
        if cur > prev:
            out[i] = 1
        elif cur < prev:
            out[i] = -1
        else:
            out[i] = 0
    return out


def mladen_flow(prices: List[float], period: int = 14, smooth: int = 3) -> List[Optional[float]]:
    """
    Mladen-style flow oscillator (PLACEHOLDER).
    Rango [-1, 1]: normalizado min-max, centrado, suavizado con WMA.
    Reemplazar por la fórmula original de TradingView (script A8AoLSrN).
    """
    n = max(1, period)
    s = max(1, smooth)
    raw: List[Optional[float]] = [None] * len(prices)
    for i in range(n - 1, len(prices)):
        window = prices[i - n + 1 : i + 1]
        lo = min(window)
        hi = max(window)
        if hi == lo:
            raw[i] = 0.5
        else:
            raw[i] = (prices[i] - lo) / (hi - lo)

    centred = [(v - 0.5) * 2.0 if v is not None else float("nan") for v in raw]
    return _wma(centred, s)  # type: ignore[return-value]


# ============================================================================
# MODELOS DE DATOS
# ============================================================================
@dataclass
class TradeRecord:
    entry_time: str
    exit_time: Optional[str]
    side: str  # CALL / PUT
    entry_price: float
    exit_price: Optional[float]
    stake: float
    pnl: Optional[float]
    win: Optional[bool]
    contract_id: Optional[int]


@dataclass
class BotState:
    running: bool = True
    position: Optional[str] = None  # "long" / "short" / None
    open_contract_id: Optional[int] = None
    open_entry_price: float = 0.0
    open_entry_time: float = 0.0  # unix ts de entrada (para duración fija)
    open_side: Optional[str] = None
    daily_pnl: float = 0.0
    balance: float = 0.0  # saldo obtenido de la cuenta de Deriv
    trades_today: int = 0
    martingale_step: int = 0  # paso actual de martingala (0 = apuesta base)
    last_trade_exit_time: float = 0  # timestamp último cierre para cooldown
    open_stake: float = 0.0  # stake real de la operación abierta
    trades: List[TradeRecord] = field(default_factory=list)
    ticks_received: int = 0
    last_tick_time: Optional[str] = None
    last_hma: Optional[float] = None  # valor HMA último tick
    last_flow: Optional[float] = None  # valor Flow último tick
    last_price: Optional[float] = None  # último precio recibido
    last_direction: Optional[int] = None  # dirección HMA última vela
    session_start_balance: Optional[float] = None  # saldo al inicio de la sesión
    current_symbol: Optional[str] = None  # símbolo actual para dashboard
    candles_received: int = 0  # contador velas recibidas
    last_candle_time: Optional[str] = None  # hora última vela


state = BotState()


# ============================================================================
# PERSISTENCIA (CSV de trades)
# ============================================================================
TRADES_CSV = "trades_1hz50v.csv"


def save_trade_to_csv(trade: TradeRecord) -> None:
    file_exists = os.path.exists(TRADES_CSV)
    with open(TRADES_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "entry_time", "exit_time", "side", "entry_price",
                "exit_price", "stake", "pnl", "win", "contract_id",
            ])
        writer.writerow([
            trade.entry_time,
            trade.exit_time or "",
            trade.side,
            f"{trade.entry_price:.4f}",
            f"{trade.exit_price:.4f}" if trade.exit_price is not None else "",
            trade.stake,
            f"{trade.pnl:.2f}" if trade.pnl is not None else "",
            trade.win if trade.win is not None else "",
            trade.contract_id if trade.contract_id is not None else "",
        ])


# Zona horaria Argentina (GMT-3, sin DST)
try:
    import zoneinfo
    ARG_TZ = zoneinfo.ZoneInfo("America/Argentina/Buenos_Aires")
except Exception:
    # Fallback si no hay zoneinfo
    from datetime import timezone, timedelta
    ARG_TZ = timezone(timedelta(hours=-3))

def now_str() -> str:
    return datetime.now(ARG_TZ).strftime("%Y-%m-%d %H:%M:%S")


# ============================================================================
# BOT
# ============================================================================
class HMAFlowBot:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.token = cfg["token"]
        self.symbol = cfg["symbol"]
        self.stake = float(cfg["stake"])
        state.current_symbol = self.symbol  # Sincronizar símbolo actual al estado
        self.demo = bool(cfg["demo"])
        self.duration = int(cfg["duration"])
        self.duration_unit = cfg["duration_unit"]
        self._ws_lock = asyncio.Lock()  # Lock para serializar acceso a trading_ws
        self.hma_period = int(cfg["hma_period"])
        self.flow_period = int(cfg["flow_period"])
        self.flow_smooth = int(cfg["flow_smooth"])
        self.flow_threshold = float(cfg["flow_threshold"])
        self.martingale_multiplier = float(cfg["martingale_multiplier"])
        self.max_martingale_steps = int(cfg["max_martingale_steps"])
        self.max_stake = float(cfg["max_stake"])
        self.cooldown_seconds = int(cfg["cooldown_seconds"])
        self.last_trade_time = 0  # timestamp del último trade cerrado
        self.consecutive_losses = 0  # pérdidas consecutivas para pausa
        self.candles: Deque[dict] = deque(maxlen=MAX_CANDLES)
        self.public_ws = None
        self.trading_ws = None
        self.trading_ws_url = None
        
        # Reconfigurar logging con nivel del config
        global log
        log_level = cfg.get("log_level", "INFO")
        log = setup_logging(log_level)
        self._log("info", f"Log level set to {log_level}")

    # ------------------------------------------------------------------
    # Logging helper
    # ------------------------------------------------------------------
    def _log(self, level: str, msg: str) -> None:
        getattr(log, level.lower(), log.info)(msg)

    # ------------------------------------------------------------------
    # WebSocket helpers
    # ------------------------------------------------------------------
    async def _send(self, ws, msg: dict) -> dict:
        # Usar lock si es el trading_ws
        lock = self._ws_lock if ws is self.trading_ws else None
        if lock:
            async with lock:
                await ws.send(json.dumps(msg))
                raw = await ws.recv()
                return json.loads(raw)
        else:
            await ws.send(json.dumps(msg))
            raw = await ws.recv()
            return json.loads(raw)

    async def connect_public(self) -> None:
        public_ws_url = "wss://api.derivws.com/trading/v1/options/ws/public"
        self._log("info", f"Conectando a WebSocket público ({public_ws_url})...")
        self.public_ws = await websockets.connect(
            public_ws_url,
            ping_interval=20,  # enviar ping cada 20s
            ping_timeout=10,   # timeout de pong 10s
            close_timeout=10
        )
        self._log("info", "WebSocket público conectado")

    async def subscribe_candles(self) -> None:
        """Cargar historial de velas 1m y suscribirse a ticks en tiempo real (más estable)."""
        # 1) Cargar historial de velas 1m para warmup
        hist_req = {
            "ticks_history": self.symbol,
            "adjust_start_time": 1,
            "end": "latest",
            "start": 1,
            "style": "candles",
            "granularity": 60,  # 60 segundos = 1 minuto
            "count": WARMUP_CANDLES + 5,
        }
        resp = await self._send(self.public_ws, hist_req)
        candles = resp.get("candles", [])
        if candles:
            # candles vienen como: {"epoch": 123, "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.05}
            for c in candles[-WARMUP_CANDLES:]:
                self.candles.append({
                    "epoch": c["epoch"],
                    "open": float(c["open"]),
                    "high": float(c["high"]),
                    "low": float(c["low"]),
                    "close": float(c["close"]),
                })
            self._log(
                "info",
                f"Historial cargado: {len(self.candles)} velas 1m de {self.symbol} "
                f"(última close={self.candles[-1]['close']:.4f})",
            )
        else:
            self._log("warn", "No se pudo cargar historial de velas")

        # 2) Suscribirse a TICKS en tiempo real (más estable que candles)
        # Construiremos velas 1m desde los ticks
        req = {
            "ticks": self.symbol,
            "subscribe": 1
        }
        await self._send(self.public_ws, req)
        self._log("info", f"Suscrito a ticks en tiempo real de {self.symbol}")

    async def connect_trading(self) -> None:
        if not self.token:
            self._log("warning", "Sin DERIV_TOKEN — modo PAPER (sin operaciones reales)")
            return
        otp_url = self._fetch_otp_url()
        if not otp_url:
            self._log("error", "No se pudo obtener URL de trading vía OTP")
            return
        self._log("info", "Conectando a WebSocket de trading (OTP)...")
        self.trading_ws = await websockets.connect(
            otp_url,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=10
        )
        self.trading_ws_url = otp_url
        self._log("info", "WebSocket de trading autenticado conectado")
        await self.fetch_balance()
        if state.session_start_balance is None:
            state.session_start_balance = state.balance
            self._log("info", f"Saldo inicial de sesión: {state.session_start_balance:.2f} USD")

    async def fetch_balance(self) -> None:
        """Obtiene el saldo real de la cuenta de Deriv."""
        if not self.trading_ws:
            return
        try:
            req = {"balance": 1}
            resp = await self._send(self.trading_ws, req)
            balance_data = resp.get("balance", {})
            if balance_data:
                balance = balance_data.get("balance", 0)
                currency = balance_data.get("currency", "USD")
                state.balance = float(balance)
                self._log("info", f"Saldo de cuenta obtenido: {balance} {currency}")
            else:
                self._log("warning", "No se pudo obtener saldo de la cuenta")
        except Exception as e:
            self._log("error", f"Error obteniendo saldo: {e}")

    async def fetch_real_trades(self) -> None:
        """Solo sincroniza balance real. Los trades se cierran solos en Deriv al vencer (1 min)."""
        if not self.trading_ws or not self.token:
            return
        try:
            # Solo sync balance - los trades expiran solos en Deriv
            await self.fetch_balance()
            self._log("debug", "Balance sincronizado via fetch_real_trades")
        except Exception as e:
            self._log("error", f"Error sincronizando balance: {e}")

    async def sync_from_deriv(self) -> None:
        """Sincroniza todo desde Deriv API: profit_table (trades) + balance."""
        self._log("debug", "sync_from_deriv INICIO")
        if not self.trading_ws or not self.token:
            self._log("debug", "sync_from_deriv: sin ws o token")
            return
        try:
            self._log("debug", "sync_from_deriv: enviando profit_table (sin lock)")
            # 1. Obtener profit_table (últimos trades cerrados)
            req = {"profit_table": 1, "description": 1, "limit": 20, "sort": "DESC"}
            resp = await self._send(self.trading_ws, req)
            profit_data = resp.get("profit_table", {})
            transactions = profit_data.get("transactions", [])
            
            # Actualizar trades locales con datos reales de Deriv
            for tx in transactions:
                contract_id = tx.get("contract_id")
                profit = tx.get("profit")
                buy_price = tx.get("buy_price")
                sell_price = tx.get("sell_price")
                contract_type = tx.get("contract_type")
                entry_time = tx.get("entry_tick_time") or tx.get("entry_time")
                exit_time = tx.get("exit_tick_time") or tx.get("exit_time")
                
                if contract_id and profit is not None:
                    # Buscar trade local
                    for t in state.trades:
                        if t.contract_id == contract_id and t.pnl is None:
                            t.exit_price = float(sell_price) if sell_price else None
                            t.pnl = float(profit)
                            t.win = float(profit) > 0
                            if exit_time:
                                t.exit_time = exit_time
                            save_trade_to_csv(t)
                            self._log("info", f"  [DERIV SYNC] {contract_type} contract_id={contract_id} pnl={profit:+.2f} {'WIN' if profit > 0 else 'LOSS'}")
                            break
            
            # 2. Obtener balance real
            await self.fetch_balance()
            
            # 3. Actualizar martingala y daily_pnl basado en trades sincronizados
            self._update_state_from_trades()
            
        except Exception as e:
            self._log("error", f"Error sync_from_deriv: {e}")

    def _update_state_from_trades(self) -> None:
        """Actualiza martingala y daily_pnl basado en trades cerrados reales."""
        # Recalcular daily_pnl sumando PnL de trades cerrados
        total_pnl = sum(t.pnl for t in state.trades if t.pnl is not None)
        state.daily_pnl = total_pnl
        
        # Martingala: revisar último trade cerrado
        closed_trades = [t for t in state.trades if t.pnl is not None]
        if closed_trades:
            last = closed_trades[-1]
            if last.win:
                state.martingale_step = 0
                self.consecutive_losses = 0
            else:
                state.martingale_step = min(state.martingale_step + 1, self.max_martingale_steps)
                self.consecutive_losses += 1
                if state.martingale_step >= self.max_martingale_steps:
                    state.martingale_step = 0
        
        self._log("info", f"  [STATE SYNC] daily_pnl={state.daily_pnl:+.2f} martingale_step={state.martingale_step}")

    async def update_trades_from_profit_table(self) -> None:
        """Actualiza trades individuales desde profit_table (async, no bloquea)."""
        if not self.trading_ws or not self.token:
            return
        try:
            req = {"profit_table": 1, "description": 1, "limit": 20, "sort": "DESC"}
            resp = await self._send(self.trading_ws, req)
            profit_data = resp.get("profit_table", {})
            transactions = profit_data.get("transactions", [])
            
            for tx in transactions:
                contract_id = tx.get("contract_id")
                profit = tx.get("profit")
                sell_price = tx.get("sell_price")
                contract_type = tx.get("contract_type")
                exit_time = tx.get("exit_tick_time") or tx.get("exit_time")
                
                if contract_id and profit is not None:
                    for t in state.trades:
                        if t.contract_id == contract_id and t.pnl is None:
                            t.exit_price = float(sell_price) if sell_price else None
                            t.pnl = float(profit)
                            t.win = float(profit) > 0
                            if exit_time:
                                t.exit_time = exit_time
                            save_trade_to_csv(t)
                            self._log("info", f"  [DERIV SYNC] {contract_type} contract_id={contract_id} pnl={profit:+.2f} {'WIN' if profit > 0 else 'LOSS'}")
                            break
        except Exception as e:
            self._log("debug", f"update_trades_from_profit_table error: {e}")

    def reload_config(self) -> None:
        """Recarga la configuración desde config.json."""
        import json
        import os
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.json')
        old_symbol = self.symbol
        try:
            with open(config_path, 'r') as f:
                cfg = json.load(f)
            new_symbol = cfg.get("DERIV_SYMBOL", "1HZ50V")
        except Exception:
            new_symbol = os.environ.get("DERIV_SYMBOL", "1HZ50V")
        if new_symbol != old_symbol:
            self.symbol = new_symbol
            state.current_symbol = new_symbol
            self._log("info", f"Símbolo actualizado: {old_symbol} -> {new_symbol}")
            # Resuscribir a ticks del nuevo símbolo
            asyncio.create_task(self.resubscribe_symbol())

    async def resubscribe_symbol(self) -> None:
        """Reconecta y suscribe al nuevo símbolo."""
        try:
            # Cerrar WS público actual
            if self.public_ws:
                await self.public_ws.close()
            # Conectar al nuevo símbolo
            await self.connect_public()
            await self.subscribe_ticks()
            self._log("info", f"Reconectado y suscrito a {self.symbol}")
        except Exception as e:
            self._log("error", f"Error resuscribiendo a {self.symbol}: {e}")

    def _fetch_otp_url(self) -> Optional[str]:
        """Llama a POST /accounts/{accountId}/otp y devuelve la URL WebSocket con OTP."""
        account_id = self.cfg.get("account_id") or ""
        if not account_id:
            self._log("error", "DERIV_ACCOUNT_ID no configurado — no se puede obtener OTP")
            return None
        url = f"{OTP_BASE}/trading/v1/options/accounts/{account_id}/otp"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        app_id = self.cfg.get("app_id") or APP_ID
        if app_id:
            headers["Deriv-App-ID"] = app_id
        req = urllib.request.Request(url, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data.get("data", {}).get("url")
        except Exception as e:
            self._log("error", f"Fallo al obtener OTP: {e}")
            return None

    async def get_contracts_for(self) -> dict:
        """Obtiene contratos disponibles para el símbolo actual."""
        req = {
            "contracts_for": self.symbol,
            "currency": "USD",
        }
        resp = await self._send(self.trading_ws, req)
        return resp

    async def get_proposal(self, contract_type: str, stake: float) -> dict:
        """Obtiene propuesta (payout, profit) para un contrato específico."""
        req = {
            "proposal": 1,
            "amount": stake,
            "basis": "stake",
            "contract_type": contract_type,
            "currency": "USD",
            "duration": self.duration,
            "duration_unit": self.duration_unit,
            "underlying_symbol": self.symbol,
        }
        resp = await self._send(self.trading_ws, req)
        return resp

    async def validate_stake(self, contract_type: str, stake: float) -> tuple:
        """Valida stake contra límites del contrato. Retorna (stake_valido, min_stake, max_stake, payout)."""
        try:
            # Obtener propuesta para ver límites y payout
            prop = await self.get_proposal(contract_type, stake)
            if "error" in prop:
                return False, 0.35, 100000, 0
            
            proposal = prop.get("proposal", {})
            min_stake = float(proposal.get("min_price", 0.35))
            max_stake = float(proposal.get("max_price", 100000))
            payout = float(proposal.get("payout", 0))
            profit = float(proposal.get("profit", 0))
            
            # Ajustar stake a límites válidos
            stake_valido = max(min_stake, min(stake, max_stake))
            stake_valido = round(stake_valido, 2)
            
            return True, min_stake, max_stake, payout, profit, stake_valido
        except Exception as e:
            self._log("error", f"Error validando stake: {e}")
            return False, 0.35, 100000, 0, 0, 0.35

    async def buy_contract(self, contract_type: str) -> dict:
        # Validar stake con proposal
        stake_calculado = round(self.stake * (2 ** state.martingale_step), 2)
        stake_calculado = min(stake_calculado, self.max_stake)
        
        valid, min_stake, max_stake, payout, profit, stake_valido = await self.validate_stake(
            contract_type, stake_calculado
        )
        
        if not valid:
            self._log("error", f"Contrato {contract_type} no disponible")
            return {"error": "Contract not available"}
        
        # Usar stake validado
        stake_final = stake_valido
        state.open_stake = stake_final  # Guardar stake real
        
        self._log("info", f"  [CONTRACT] {contract_type} stake={stake_final:.2f} "
              f"(min={min_stake:.2f}, max={max_stake:.2f}, payout={payout:.2f}, profit={profit:.2f})")
        
        req = {
            "buy": "1",
            "price": stake_final,
            "parameters": {
                "amount": stake_final,
                "basis": "stake",
                "contract_type": contract_type,
                "currency": "USD",
                "duration": self.duration,
                "duration_unit": self.duration_unit,
                "underlying_symbol": self.symbol,
            },
        }
        resp = await self._send(self.trading_ws, req)
        return resp

    async def sell_contract(self, contract_id: int) -> dict:
        req = {"sell": contract_id, "price": 0}
        resp = await self._send(self.trading_ws, req)
        return resp

    # ------------------------------------------------------------------
    # Strategy: on_tick
    # ------------------------------------------------------------------
    async def on_candle(self, candle: dict) -> None:
        """Procesar vela 1m cerrada."""
        self.candles.append(candle)
        state.candles_received += 1
        state.last_candle_time = now_str()
        state.last_price = candle["close"]  # usar close como precio de referencia

        if len(self.candles) < WARMUP_CANDLES:
            self._log("debug", f"Warmup: {len(self.candles)}/{WARMUP_CANDLES} candles")
            return

        # Extraer series de precios de cierre para indicadores
        close_prices = [c["close"] for c in self.candles]
        hma_series = hma(close_prices, self.hma_period)
        direction = hma_direction(hma_series)
        flow = mladen_flow(close_prices, self.flow_period, self.flow_smooth)

        d = direction[-1]
        f = flow[-1]
        if d is None or f is None:
            self._log("debug", f"Warmup: candles={len(self.candles)}, d={d}, f={f}")
            return

        state.last_hma = hma_series[-1]
        state.last_flow = f
        state.last_direction = d

        thr = self.flow_threshold
        now = now_str()
        sys.stdout.write(".")
        sys.stdout.flush()

        price = candle["close"]

        self._log("debug", f"[{now}] Price={price:.4f} HMA={hma_series[-1]:.4f} Dir={d} Flow={f:.4f} Slope={hma_series[-1]-hma_series[-2]:.4f}")

        # ---- Si hay posición abierta, revisar salida por duración ----
        if state.position is not None:
            # Salir solo por duración fija (1 min), NO cerrar manualmente
            # Dejar que Deriv cierre el contrato al vencer naturalmente
            elapsed = time.time() - state.open_entry_time
            duration_seconds = self.duration * 60 if self.duration_unit == "m" else self.duration
            if elapsed < duration_seconds:
                return  # aún no sale, espera a completar 1 min
            exit_reason = f"duración {self.duration}{self.duration_unit} completada"

            side_txt = "LONG" if state.position == "long" else "SHORT"
            self._log("info",
                      f"[{now}] EXIT {side_txt} @ {price:.4f} | {exit_reason} (esperando resultado real)")

            # NO cerrar manualmente - dejar que Deriv cierre al vencer
            # Sincronizar balance y obtener profit real del contrato via profit_table
            state.trades_today += 1
            
            # Wait a moment for contract to settle, then sync via profit_table
            await asyncio.sleep(2)
            await self.update_trades_from_profit_table()
            await self.fetch_balance()
            
            # Get PnL from the closed trade (updated by profit_table sync)
            pnl_real = 0.0
            if state.trades:
                last_trade = state.trades[-1]
                if last_trade.pnl is not None:
                    pnl_real = last_trade.pnl
                    self._log("info", f"  [REAL PnL] {side_txt} stake={state.open_stake:.2f} pnl={pnl_real:+.2f} USD ({'WIN' if pnl_real > 0 else 'LOSS'})")
            
            # Actualizar martingala y daily_pnl
            state.daily_pnl += pnl_real
            if pnl_real > 0:
                state.martingale_step = 0
                self.consecutive_losses = 0
            else:
                state.martingale_step += 1
                self.consecutive_losses += 1
                if state.martingale_step >= self.max_martingale_steps:
                    state.martingale_step = 0
            
            state.last_trade_exit_time = time.time()
            self._log("info", f"  [DAILY PnL] total={state.daily_pnl:+.2f} USD")
            
            self._close_position()
            return

        # ---- Martingala se maneja con resultados reales via fetch_real_trades() ----
        # NO cerrar manualmente aquí - dejar expirar naturalmente

        # ---- Sin posición: buscar entrada (con martingala de recuperación) ----
        # NO abrir nuevo trade si ya hay uno abierto
        if state.position is not None:
            return
        
        # COOLDOWN: esperar entre trades (solo si ya hubo trades)
        if state.trades_today > 0 and time.time() - state.last_trade_exit_time < self.cooldown_seconds:
            self._log("debug", f"Cooldown active: {self.cooldown_seconds - (time.time() - state.last_trade_exit_time):.0f}s remaining")
            return
        
        # PAUSA PROTECTORA: si 3 losses consecutivas, pausa 5 min
        if self.consecutive_losses >= 3:
            if time.time() - state.last_trade_exit_time < 300:  # 5 min
                self._log("debug", f"Pause active: {300 - (time.time() - state.last_trade_exit_time):.0f}s remaining")
                return
            else:
                self.consecutive_losses = 0  # Reset tras pausa

        # Filtros de precisión (menos trades, más calidad)
        # 1. HMA dirección clara
        hma_current = hma_series[-1]
        hma_prev = hma_series[-2] if len(hma_series) > 1 else hma_current
        hma_slope = hma_current - hma_prev
        
        # 2. Precio confirma dirección HMA
        price_above_hma = price > hma_current
        price_below_hma = price < hma_current
        
        # 3. Flow fuerte (threshold bajo para más señales)
        flow_strong_up = f > (thr * 0.4) and hma_slope >= 0
        flow_strong_down = f < -(thr * 0.4) and hma_slope <= 0
        
        # 4. Volatilidad: evitar operar en laterales (HMA plano)
        # slope threshold basado en volatilidad típica, no % del precio
        hma_flat = abs(hma_slope) < 0.5  # slope < 0.5 pips/tick
        
        # 5. Filtro adicional: precio debe estar lejos del HMA (no en zona neutral)
        price_hma_dist = abs(price - hma_current) / price
        price_too_close_hma = price_hma_dist < 0.00005  # < 0.005%

        # Martingala simple: stake = base * 2^step, limitado a max_stake
        stake_efectivo = round(min(self.stake * (2 ** state.martingale_step), self.max_stake), 2)
        
        # Debug logging for signal conditions
        self._log("debug", f"Signal check: d={d} flow_up={flow_strong_up} flow_down={flow_strong_down} "
                         f"price_above={price_above_hma} price_below={price_below_hma} "
                         f"hma_flat={hma_flat} price_close={price_too_close_hma} "
                         f"slope={hma_slope:.4f} dist={price_hma_dist:.6f}")

        # Señal de alta precisión: Flow + HMA slope + Precio vs HMA + distancia HMA
        # INVERTIDO: HMA up -> PUT, HMA down -> CALL (estrategia contrarian probada en backtest)
        if d == 1 and flow_strong_up and price_above_hma and not hma_flat and not price_too_close_hma:
            self._signal(now, price, "SELL (PUT)", "HMA↑ Flow↑ Precio>HMA Dist>0.02%", "PUT", stake_efectivo)
        elif d == -1 and flow_strong_down and price_below_hma and not hma_flat and not price_too_close_hma:
            self._signal(now, price, "BUY (CALL)", "HMA↓ Flow↓ Precio<HMA Dist>0.02%", "CALL", stake_efectivo)

    def _signal(self, now: str, price: float, action: str, reason: str,
                contract_type: Optional[str], stake: float) -> None:
        self._log("info", f"[{now}] {action} @ {price:.4f} | stake={stake:.2f} | {reason}")

        if contract_type and self.token and self.trading_ws:
            asyncio.create_task(self._place_trade(action, contract_type))
        elif contract_type and not self.token:
            self._log("info", "  [PAPER] sin token — no se coloca operación")

        if action.startswith("BUY"):
            state.position = "long"
            state.open_side = "CALL"
            state.open_entry_price = price
            state.open_entry_time = time.time()
            state.open_stake = stake  # Guardar stake real
            state.trades.append(TradeRecord(
                entry_time=now, exit_time=None, side="CALL",
                entry_price=price, exit_price=None, stake=stake,
                pnl=None, win=None, contract_id=None,
            ))
        elif action.startswith("SELL"):
            state.position = "short"
            state.open_side = "PUT"
            state.open_entry_price = price
            state.open_entry_time = time.time()
            state.open_stake = stake  # Guardar stake real
            state.trades.append(TradeRecord(
                entry_time=now, exit_time=None, side="PUT",
                entry_price=price, exit_price=None, stake=stake,
                pnl=None, win=None, contract_id=None,
            ))

    async def _place_trade(self, action: str, contract_type: str) -> None:
        try:
            resp = await self.buy_contract(contract_type)
            if "error" in resp:
                self._log("error", f"[TRADE ERROR] {resp['error']}")
                state.position = None
                return
            buy = resp.get("buy", {})
            contract_id = buy.get("contract_id")
            state.open_contract_id = contract_id
            state.trades_today += 1
            if state.trades:
                state.trades[-1].contract_id = contract_id
            self._log("info",
                      f"  [TRADE] id={contract_id} type={contract_type} "
                      f"buy_price={buy.get('buy_price')} "
                      f"tx={buy.get('transaction_id')}")
        except Exception as e:
            self._log("error", f"[TRADE EXCEPTION] {e}")
            state.position = None

    async def _close_contract(self, contract_id: int) -> None:
        try:
            resp = await self.sell_contract(contract_id)
            if "error" in resp:
                self._log("error", f"[SELL ERROR] id={contract_id}: {resp['error']}")
            else:
                sell = resp.get("sell", {})
                sell_price = sell.get("sell_price")
                profit = sell.get("profit")
                self._log("info",
                          f"  [CONTRATO CERRADO] id={contract_id} "
                          f"sell_price={sell_price} profit={profit}")
                if profit is not None:
                    if state.trades:
                        state.trades[-1].exit_price = float(sell_price) if sell_price else None
                        state.trades[-1].pnl = float(profit)
                        state.trades[-1].win = float(profit) > 0
                        state.trades[-1].exit_time = now_str()
                        save_trade_to_csv(state.trades[-1])
        except Exception as e:
            self._log("error", f"[SELL EXCEPTION] id={contract_id}: {e}")

    def _close_position(self) -> None:
        state.position = None
        state.open_contract_id = None
        state.open_entry_price = 0.0
        state.open_side = None

    # ------------------------------------------------------------------
    # Main loop with reconnection
    # ------------------------------------------------------------------
    async def run(self) -> None:
        reconnect_delay = RECONNECT_BASE_DELAY
        while state.running:
            try:
                await self.connect_public()
                await self.subscribe_candles()
                await self.connect_trading()
                reconnect_delay = RECONNECT_BASE_DELAY

                # Keepalive task - ping both WS every 15 seconds
                async def keepalive():
                    while state.running:
                        try:
                            await asyncio.sleep(15)
                            if self.public_ws and not self.public_ws.closed:
                                await self.public_ws.ping()
                            if self.trading_ws and not self.trading_ws.closed:
                                await self.trading_ws.ping()
                        except Exception:
                            break

                keepalive_task = asyncio.create_task(keepalive())

                # Tick buffer for building 1m candles
                current_candle = None
                last_candle_time = 0

                while state.running:
                    try:
                        raw = await asyncio.wait_for(self.public_ws.recv(), timeout=45)
                        self._log("debug", f"Received msg: {raw[:100]}")
                    except asyncio.TimeoutError:
                        # Send ping to check connection
                        try:
                            await self.public_ws.ping()
                            continue
                        except Exception:
                            self._log("warning", "Ping failed, connection likely dead")
                            break
                    msg = json.loads(raw)
                    if msg.get("msg_type") == "tick":
                        tick = msg.get("tick", {})
                        price = tick.get("quote")
                        epoch = tick.get("epoch")
                        if price is not None and epoch is not None:
                            # Build 1m candles from ticks
                            candle_time = epoch // 60 * 60  # floor to minute
                            if candle_time != last_candle_time:
                                if current_candle is not None:
                                    # Finalize previous candle
                                    self._log("debug", f"Finalizing candle: {current_candle}")
                                    await self.on_candle(current_candle)
                                # Start new candle
                                current_candle = {
                                    "epoch": candle_time,
                                    "open": price,
                                    "high": price,
                                    "low": price,
                                    "close": price
                                }
                                last_candle_time = candle_time
                            else:
                                # Update current candle
                                current_candle["high"] = max(current_candle["high"], price)
                                current_candle["low"] = min(current_candle["low"], price)
                                current_candle["close"] = price
                    elif msg.get("msg_type") == "candle":
                        # Also handle direct candle messages if they arrive
                        candle = msg.get("candle", {})
                        self._log("debug", f"Candle received: {candle}")
                        if candle.get("is_final"):
                            self._log("info", f"Processing final candle: {candle}")
                            await self.on_candle(candle)
                    elif msg.get("msg_type") == "error":
                        self._log("error", f"[public] {msg['error']}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log("error", f"Conexión perdida: {e}. Reconectando en {reconnect_delay}s...")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 60)

        if self.public_ws:
            await self.public_ws.close()
        if self.trading_ws:
            await self.trading_ws.close()
        self._log("info", "Bot detenido")


# ============================================================================
# ENTRY POINT
# ============================================================================
def main() -> None:
    print("=" * 60)
    print("1HZ50V HMA + Mladen Flow Bot — Raspberry Pi")
    print("=" * 60)
    print(f"Símbolo     : {CONFIG['symbol']}")
    print(f"HMA         : {CONFIG['hma_period']}")
    print(f"Flow        : {CONFIG['flow_period']} (smooth={CONFIG['flow_smooth']})")
    print(f"Threshold   : {CONFIG['flow_threshold']}")
    print(f"Duración    : {CONFIG['duration']} {CONFIG['duration_unit']}")
    print(f"Stake       : {CONFIG['stake']} USD")
    print(f"Demo        : {CONFIG['demo']}")
    print(f"Token       : {'configurado' if CONFIG['token'] else 'NO (PAPER mode)'}")
    print(f"Log archivo : {CONFIG['log_file']}")
    print("=" * 60)

    if not CONFIG["token"]:
        print("\nAVISO: Ejecutando en MODO PAPER (solo señales, sin operaciones reales).")
        print("Para operar en demo, exporta DERIV_TOKEN antes de iniciar.\n")

    bot = HMAFlowBot(CONFIG)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    stop_requested = False

    def handle_signal(sig):
        nonlocal stop_requested
        stop_requested = True
        log.info(f"Señal {sig.name} recibida — deteniendo bot...")
        state.running = False

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_signal, sig)
        except NotImplementedError:
            pass  # Windows no soporta add_signal_handler en algunos casos

    try:
        loop.run_until_complete(bot.run())
    except KeyboardInterrupt:
        state.running = False
        log.info("\nInterrumpido por usuario")
    finally:
        # Guardar resumen de trades
        if state.trades:
            wins = [t for t in state.trades if t.win]
            losses = [t for t in state.trades if not t.win]
            total_pnl = sum((t.pnl or 0) for t in state.trades)
            log.info("=" * 60)
            log.info("RESUMEN DE SESIÓN")
            log.info(f"  Trades totales : {len(state.trades)}")
            log.info(f"  Ganadores      : {len(wins)}")
            log.info(f"  Perdedores     : {len(losses)}")
            log.info(f"  PnL total      : {total_pnl:.2f} USD")
            log.info(f"  Ticks recibidos: {state.ticks_received}")
            log.info("=" * 60)
        loop.close()


if __name__ == "__main__":
    main()