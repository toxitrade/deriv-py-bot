#!/usr/bin/env python3
"""
Multiplier Bot — Deriv HMA + Mladen Flow
=========================================

Contratos con multiplicador (leverage): x40, x100, x400, etc.
Sin tiempo de expiración fijo: salida por TP / SL / señal de estrategia.

Modos:
  python3 multiplier_bot.py              # PAPER (sin token, solo señales)
  DERIV_TOKEN=xxx python3 multiplier_bot.py  # DEMO (contratos reales)

Variables de entorno:
  DERIV_TOKEN        Token de API de Deriv (demo). Sin él va en PAPER.
  DERIV_SYMBOL       Símbolo (default: 1HZ50V)
  DERIV_STAKE        Stake por contrato (default: 10.0)
  DERIV_MULTIPLIER   Multiplicador de apalancamiento (default: 100)
  DERIV_DEMO         true|false (default: true)
  DERIV_HMA_PERIOD   HMA period (default: 20)
  DERIV_FLOW_PERIOD  Flow period (default: 14)
  DERIV_FLOW_SMOOTH  Flow smooth (default: 3)
  DERIV_FLOW_THRESHOLD Umbral de cruce (default: 0.0)
  DERIV_TP_PCT       Take profit en % del precio de entrada (default: 0.001 = +0.1%)
  DERIV_SL_PCT       Stop loss en % del precio de entrada (default: 0.001 = -0.1%)
  DERIV_LOG_LEVEL    INFO | DEBUG | WARNING (default: INFO)
  DERIV_LOG_FILE     Archivo de log (default: multiplier_bot.log)
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
    print("ERROR: falta la librería 'websockets'. Instala con: pip install websockets")
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
    "multiplier": env_int("DERIV_MULTIPLIER", 100),
    "demo": env_bool("DERIV_DEMO", True),
    "hma_period": env_int("DERIV_HMA_PERIOD", 20),
    "flow_period": env_int("DERIV_FLOW_PERIOD", 14),
    "flow_smooth": env_int("DERIV_FLOW_SMOOTH", 3),
    "flow_threshold": env_float("DERIV_FLOW_THRESHOLD", 0.0),
    "tp_pct": env_float("DERIV_TP_PCT", 0.001),   # +0.1% → TP 100% del stake
    "sl_pct": env_float("DERIV_SL_PCT", 0.001),   # -0.1% → SL 50% del stake
    "account_id": env_str("DERIV_ACCOUNT_ID", ""),   # ID de cuenta Options Trading (para OTP)
    "app_id": env_str("DERIV_APP_ID", ""),       # App ID (requerido para PAT)
    "log_level": env_str("DERIV_LOG_LEVEL", "INFO"),
    "log_file": env_str("DERIV_LOG_FILE", "multiplier_bot.log"),
    "token": env_str("DERIV_TOKEN", ""),
}

PUBLIC_WS = f"wss://ws.binaryws.com/websockets/v3?app_id={APP_ID or '1089'}"  # Datos públicos (ticks/velas), sin auth
OTP_BASE = "https://api.derivws.com"                              # REST para OTP de trading
APP_ID = env_str("DERIV_APP_ID", "")                          # Requerido para PAT
TICK_BUFFER = 500
RECONNECT_BASE_DELAY = 5
WARMUP_TICKS = 40


# ============================================================================
# LOGGING
# ============================================================================
def setup_logging() -> logging.Logger:
    logger = logging.getLogger("multiplier_bot")
    logger.setLevel(getattr(logging, CONFIG["log_level"].upper(), logging.INFO))
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


log = setup_logging()


# ============================================================================
# INDICADORES (HMA + Mladen Flow)
# ============================================================================
def _wma(values: List[float], period: int) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(values)
    if period <= 0:
        return out
    wsum = sum(range(1, period + 1))
    for i in range(period - 1, len(values)):
        window = values[i - period + 1 : i + 1]
        out[i] = sum((j + 1) * v for j, v in enumerate(window)) / wsum
    return out


def hma(values: List[float], period: int) -> List[Optional[float]]:
    """Hull Moving Average."""
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
    """Mladen-style flow oscillator (PLACEHOLDER)."""
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
    multiplier: int
    pnl: Optional[float]
    win: Optional[bool]
    contract_id: Optional[int]
    exit_reason: Optional[str]


@dataclass
class BotState:
    running: bool = True
    position: Optional[str] = None  # "long" / "short" / None
    open_contract_id: Optional[int] = None
    open_entry_price: float = 0.0
    open_entry_time: float = 0.0
    open_side: Optional[str] = None
    stake: float = 0.0
    multiplier: int = 100
    daily_pnl: float = 0.0
    trades: List[TradeRecord] = field(default_factory=list)
    ticks_received: int = 0
    last_tick_time: Optional[str] = None


state = BotState()


# ============================================================================
# PERSISTENCIA (CSV de trades)
# ============================================================================
TRADES_CSV = "trades_multiplier.csv"


def save_trade_to_csv(trade: TradeRecord) -> None:
    file_exists = os.path.exists(TRADES_CSV)
    with open(TRADES_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "entry_time", "exit_time", "side", "entry_price",
                "exit_price", "stake", "multiplier", "pnl", "win",
                "contract_id", "exit_reason",
            ])
        writer.writerow([
            trade.entry_time,
            trade.exit_time or "",
            trade.side,
            f"{trade.entry_price:.4f}",
            f"{trade.exit_price:.4f}" if trade.exit_price is not None else "",
            trade.stake,
            trade.multiplier,
            f"{trade.pnl:.2f}" if trade.pnl is not None else "",
            trade.win if trade.win is not None else "",
            trade.contract_id if trade.contract_id is not None else "",
            trade.exit_reason or "",
        ])


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ============================================================================
# BOT
# ============================================================================
class MultiplierBot:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.token = cfg["token"]
        self.symbol = cfg["symbol"]
        self.stake = float(cfg["stake"])
        self.multiplier = int(cfg["multiplier"])
        self.demo = bool(cfg["demo"])
        self.hma_period = int(cfg["hma_period"])
        self.flow_period = int(cfg["flow_period"])
        self.flow_smooth = int(cfg["flow_smooth"])
        self.flow_threshold = float(cfg["flow_threshold"])
        self.tp_pct = float(cfg["tp_pct"])
        self.sl_pct = float(cfg["sl_pct"])

        self.prices: Deque[float] = deque(maxlen=TICK_BUFFER)
        self.public_ws = None
        self.trading_ws = None
        self.trading_ws_url = None

    # ------------------------------------------------------------------
    # Logging helper
    # ------------------------------------------------------------------
    def _log(self, level: str, msg: str) -> None:
        getattr(log, level.lower(), log.info)(msg)

    # ------------------------------------------------------------------
    # WebSocket helpers
    # ------------------------------------------------------------------
    async def _send(self, ws, msg: dict) -> dict:
        await ws.send(json.dumps(msg))
        raw = await ws.recv()
        return json.loads(raw)

    async def connect_public(self) -> None:
        self._log("info", f"Conectando a WebSocket público ({PUBLIC_WS})...")
        self.public_ws = await websockets.connect(PUBLIC_WS)
        self._log("info", "WebSocket público conectado")

    async def subscribe_ticks(self) -> None:
        req = {
            "ticks_history": self.symbol,
            "adjust_start_time": 1,
            "end": "latest",
            "start": 1,
            "style": "candles",
            "granularity": 60,
            "subscribe": 1,
        }
        await self._send(self.public_ws, req)
        self._log("info", f"Suscrito a velas de 1 min de {self.symbol} (público)")

    async def connect_trading(self) -> None:
        if not self.token:
            self._log("warning", "Sin DERIV_TOKEN — modo PAPER (sin operaciones reales)")
            return
        otp_url = self._fetch_otp_url()
        if not otp_url:
            self._log("error", "No se pudo obtener URL de trading vía OTP")
            return
        self._log("info", "Conectando a WebSocket de trading (OTP)...")
        self.trading_ws = await websockets.connect(otp_url)
        self.trading_ws_url = otp_url
        self._log("info", "WebSocket de trading autenticado conectado")

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

    async def buy_multiplier(self, contract_type: str, barrier: float) -> dict:
        """
        Compra un contrato multiplier.
        contract_type: 'CALL' o 'PUT'
        barrier: precio de entrada (precio actual del símbolo)
        """
        req = {
            "buy": 1,
            "price": self.stake,
            "parameters": {
                "amount": self.stake,
                "basis": "stake",
                "contract_type": contract_type,
                "currency": "USD",
                "symbol": self.symbol,
                "barrier": barrier,
                "multiplier": self.multiplier,
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
    def on_tick(self, price: float) -> None:
        self.prices.append(price)
        state.ticks_received += 1
        state.last_tick_time = now_str()

        if len(self.prices) < WARMUP_TICKS:
            return

        plist = list(self.prices)
        hma_series = hma(plist, self.hma_period)
        direction = hma_direction(hma_series)
        flow = mladen_flow(plist, self.flow_period, self.flow_smooth)

        d = direction[-1]
        f = flow[-1]
        if d is None or f is None:
            return

        thr = self.flow_threshold
        now = now_str()

        # ---- Si hay posición abierta, revisar salida (TP / SL / señal) ----
        if state.position is not None:
            if state.position == "long":
                price_move = (price - state.open_entry_price) / state.open_entry_price
                signal_exit = (d == -1 or f < 0.0)
                tp_hit = price_move >= self.tp_pct
                sl_hit = price_move <= -self.sl_pct
            else:  # short
                price_move = (state.open_entry_price - price) / state.open_entry_price
                signal_exit = (d == 1 or f > 0.0)
                tp_hit = price_move >= self.tp_pct
                sl_hit = price_move <= -self.sl_pct

            if tp_hit:
                exit_reason = "TP"
            elif sl_hit:
                exit_reason = "SL"
            elif signal_exit:
                exit_reason = f"señal (flow={f:.2f} hma_dir={d})"
            else:
                return  # aún no sale

            side_txt = "LONG" if state.position == "long" else "SHORT"
            self._log("info",
                      f"[{now}] EXIT {side_txt} @ {price:.4f} | {exit_reason}")

            # Cálculo de PnL para multiplier
            pnl = 0.0
            win = False
            if exit_reason == "TP":
                win = True
                # Ganancia aproximada: stake * multiplicador * tp_pct (simplificado)
                pnl = self.stake * self.multiplier * self.tp_pct
            elif exit_reason == "SL":
                win = False
                pnl = -self.stake * self.multiplier * self.sl_pct
            elif state.position == "long":
                win = price > state.open_entry_price
                # PnL aproximado proporcional al movimiento de precio * multiplicador
                pnl = self.stake * self.multiplier * price_move
            else:
                win = price < state.open_entry_price
                pnl = self.stake * self.multiplier * price_move

            if state.trades:
                t = state.trades[-1]
                t.exit_time = now
                t.exit_price = price
                t.pnl = pnl
                t.win = win
                t.exit_reason = exit_reason
                save_trade_to_csv(t)

            self._log("info",
                      f"  [PAPER PnL] {side_txt} stake={self.stake:.2f} "
                      f"mult={self.multiplier}x pnl={pnl:+.2f} USD "
                      f"({'WIN' if win else 'LOSS'})")

            if state.open_contract_id is not None and self.trading_ws and self.token:
                asyncio.create_task(self._close_contract(state.open_contract_id))
            self._close_position()
            return

        # ---- Sin posición: buscar entrada ----
        if d == 1 and f > thr:
            self._signal(now, price, "BUY (CALL)", "HMA alcista + flow cruza arriba", "CALL", price)
        elif d == -1 and f < -thr:
            self._signal(now, price, "SELL (PUT)", "HMA bajista + flow cruza abajo", "PUT", price)

    def _signal(self, now: str, price: float, action: str, reason: str,
                contract_type: str, barrier: float) -> None:
        self._log("info",
                  f"[{now}] {action} @ {price:.4f} | stake={self.stake:.2f} "
                  f"mult={self.multiplier}x | {reason}")

        if contract_type and self.token and self.trading_ws:
            asyncio.create_task(self._place_multiplier(action, contract_type, barrier))
        elif contract_type and not self.token:
            self._log("info", "  [PAPER] sin token — no se coloca operación")

        if action.startswith("BUY"):
            state.position = "long"
            state.open_side = "CALL"
            state.open_entry_price = price
            state.open_entry_time = time.time()
            state.stake = self.stake
            state.multiplier = self.multiplier
            state.trades.append(TradeRecord(
                entry_time=now, exit_time=None, side="CALL",
                entry_price=price, exit_price=None, stake=self.stake,
                multiplier=self.multiplier, pnl=None, win=None,
                contract_id=None, exit_reason=None,
            ))
        elif action.startswith("SELL"):
            state.position = "short"
            state.open_side = "PUT"
            state.open_entry_price = price
            state.open_entry_time = time.time()
            state.stake = self.stake
            state.multiplier = self.multiplier
            state.trades.append(TradeRecord(
                entry_time=now, exit_time=None, side="PUT",
                entry_price=price, exit_price=None, stake=self.stake,
                multiplier=self.multiplier, pnl=None, win=None,
                contract_id=None, exit_reason=None,
            ))

    async def _place_multiplier(self, action: str, contract_type: str, barrier: float) -> None:
        try:
            resp = await self.buy_multiplier(contract_type, barrier)
            if "error" in resp:
                self._log("error", f"[TRADE ERROR] {resp['error']}")
                state.position = None
                return
            buy = resp.get("buy", {})
            contract_id = buy.get("contract_id")
            state.open_contract_id = contract_id
            self._log("info",
                      f"  [TRADE] id={contract_id} type={contract_type} "
                      f"barrier={barrier:.4f} mult={self.multiplier}x "
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
                    state.daily_pnl += float(profit)
                    if state.trades:
                        state.trades[-1].exit_price = float(sell_price) if sell_price else None
                        state.trades[-1].pnl = float(profit)
                        state.trades[-1].win = float(profit) > 0
                        state.trades[-1].exit_time = now_str()
                        save_trade_to_csv(state.trades[-1])
        except Exception as e:
            self._log("error", f"[SELL EXCEPTION] id={contract_id}: {e}")

    async def _load_initial_history(self) -> None:
        """Carga las últimas WARMUP_TICKS velas cerradas para calentar el indicador al arranque."""
        req = {
            "ticks_history": self.symbol,
            "adjust_start_time": 1,
            "end": "latest",
            "start": 1,
            "style": "candles",
            "granularity": 60,
            "count": WARMUP_TICKS,
        }
        try:
            resp = await self._send(self.public_ws, req)
            candles = resp.get("candles", [])
            for c in candles:
                # El nuevo endpoint devuelve velas sin campo is_final; procesamos todas
                self.on_tick(float(c.get("close")))
            self._log("info", f"Historial inicial cargado: {len(candles)} velas")
        except Exception as e:
            self._log("warning", f"No se pudo cargar historial inicial: {e}")

    def _close_position(self) -> None:
        state.position = None
        state.open_contract_id = None
        state.open_entry_price = 0.0
        state.open_entry_time = 0.0
        state.open_side = None

    # ------------------------------------------------------------------
    # Main loop with reconnection
    # ------------------------------------------------------------------
    async def run(self) -> None:
        reconnect_delay = RECONNECT_BASE_DELAY
        while state.running:
            try:
                await self.connect_public()
                await self.subscribe_ticks()
                await self._load_initial_history()
                await self.connect_trading()
                reconnect_delay = RECONNECT_BASE_DELAY

                while state.running:
                    try:
                        raw = await asyncio.wait_for(self.public_ws.recv(), timeout=30)
                    except asyncio.TimeoutError:
                        continue
                    msg = json.loads(raw)
                    self._log("debug", f"Mensaje WS público: {msg.get('msg_type')} keys={list(msg.keys())[:6]}")
                    if msg.get("msg_type") == "ohlc":
                        candle = msg.get("ohlc", {})
                        price = float(candle.get("close"))
                        self.on_tick(price)
                    elif msg.get("msg_type") == "tick":
                        tick = msg.get("tick", {})
                        price = float(tick.get("quote"))
                        self.on_tick(price)
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
    print("Multiplier Bot — Deriv HMA + Mladen Flow")
    print("=" * 60)
    print(f"Símbolo     : {CONFIG['symbol']}")
    print(f"Stake       : {CONFIG['stake']} USD")
    print(f"Multiplier  : x{CONFIG['multiplier']}")
    print(f"HMA         : {CONFIG['hma_period']}")
    print(f"Flow        : {CONFIG['flow_period']} (smooth={CONFIG['flow_smooth']})")
    print(f"Threshold   : {CONFIG['flow_threshold']}")
    print(f"TP          : {CONFIG['tp_pct']*100:.2f}% del precio")
    print(f"SL          : {CONFIG['sl_pct']*100:.2f}% del precio")
    print(f"Demo        : {CONFIG['demo']}")
    print(f"Token       : {'configurado' if CONFIG['token'] else 'NO (PAPER mode)'}")
    print(f"Log archivo : {CONFIG['log_file']}")
    print("=" * 60)

    if not CONFIG["token"]:
        print("\nAVISO: Ejecutando en MODO PAPER (solo señales, sin operaciones reales).")
        print("Para operar en demo, exporta DERIV_TOKEN antes de iniciar.\n")

    bot = MultiplierBot(CONFIG)

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
            pass

    try:
        loop.run_until_complete(bot.run())
    except KeyboardInterrupt:
        state.running = False
        log.info("\nInterrumpido por usuario")
    finally:
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
