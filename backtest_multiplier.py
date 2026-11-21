#!/usr/bin/env python3
"""
Backtester de Multipliers — Deriv HMA + Mladen Flow
====================================================

Hace sweep de parámetros sobre velas históricas y reporta configuraciones
con profit positivo.

Uso:
  python3 backtest_multiplier.py [data_file] [symbol]

Ejemplo:
  python3 backtest_multiplier.py ../scripts/backtest/data/R_25-60.json R_25
"""

import csv
import itertools
import json
import math
import os
import sys
from datetime import datetime
from typing import Deque, List, Optional

# --- Agregar path para importar indicadores del bot ---
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bot_1hz50v import hma, hma_direction, mladen_flow  # noqa: E402


def load_candles(path: str) -> List[dict]:
    """Carga velas desde un archivo JSON generado por fetch-candles.mjs."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # El JSON puede ser una lista directa o un dict con clave 'candles'
    if isinstance(data, dict) and "candles" in data:
        candles = data["candles"]
    elif isinstance(data, list):
        candles = data
    else:
        raise ValueError(f"Formato de JSON no reconocido en {path}")

    # Normalizar campos
    out = []
    for c in candles:
        out.append({
            "epoch": int(c.get("epoch", 0)),
            "open": float(c.get("open", 0)),
            "high": float(c.get("high", 0)),
            "low": float(c.get("low", 0)),
            "close": float(c.get("close", 0)),
        })
    return sorted(out, key=lambda x: x["epoch"])


def run_backtest(
    candles: List[dict],
    symbol: str,
    stake: float = 10.0,
    multiplier: int = 100,
    hma_period: int = 20,
    flow_period: int = 14,
    flow_smooth: int = 3,
    flow_threshold: float = 0.0,
    tp_pct: float = 0.005,
    sl_pct: float = 0.0025,
) -> dict:
    """
    Ejecuta un backtest de un solo conjunto de parámetros.

    Retorna dict con métricas: trades, wins, losses, pnl, win_rate, etc.
    """
    prices: List[float] = []
    position: Optional[str] = None
    entry_price: float = 0.0
    entry_time: int = 0

    trades: List[dict] = []
    daily_pnl = 0.0

    for candle in candles:
        close = candle["close"]
        epoch = candle["epoch"]
        prices.append(close)

        if len(prices) < 50:  # warmup mínimo
            continue

        # Calcular indicadores sobre precios históricos hasta ahora
        hma_series = hma(prices, hma_period)
        direction = hma_direction(hma_series)
        flow = mladen_flow(prices, flow_period, flow_smooth)

        d = direction[-1]
        f = flow[-1]
        if d is None or f is None:
            continue

        thr = flow_threshold

        # --- Si hay posición abierta, revisar salida ---
        if position is not None:
            if position == "long":
                price_move = (close - entry_price) / entry_price
                signal_exit = (d == -1 or f < 0.0)
                tp_hit = price_move >= tp_pct
                sl_hit = price_move <= -sl_pct
            else:  # short
                price_move = (entry_price - close) / entry_price
                signal_exit = (d == 1 or f > 0.0)
                tp_hit = price_move >= tp_pct
                sl_hit = price_move <= -sl_pct

            if tp_hit:
                exit_reason = "TP"
            elif sl_hit:
                exit_reason = "SL"
            elif signal_exit:
                exit_reason = "señal"
            else:
                continue  # seguir en posición

            # Calcular PnL
            if exit_reason == "TP":
                pnl = stake * multiplier * tp_pct
                win = True
            elif exit_reason == "SL":
                pnl = -stake * multiplier * sl_pct
                win = False
            elif position == "long":
                win = close > entry_price
                pnl = stake * multiplier * price_move
            else:
                win = close < entry_price
                pnl = stake * multiplier * price_move

            trades.append({
                "entry_time": entry_time,
                "exit_time": epoch,
                "side": position,
                "entry_price": entry_price,
                "exit_price": close,
                "stake": stake,
                "multiplier": multiplier,
                "pnl": pnl,
                "win": win,
                "exit_reason": exit_reason,
            })
            daily_pnl += pnl

            position = None

        # --- Sin posición: buscar entrada ---
        else:
            if d == 1 and f > thr:
                position = "long"
                entry_price = close
                entry_time = epoch
            elif d == -1 and f < -thr:
                position = "short"
                entry_price = close
                entry_time = epoch

    # --- Métricas ---
    total_trades = len(trades)
    wins = [t for t in trades if t["win"]]
    losses = [t for t in trades if not t["win"]]
    total_pnl = sum(t["pnl"] for t in trades)
    win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0
    avg_win = sum(t["pnl"] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t["pnl"] for t in losses) / len(losses) if losses else 0

    return {
        "symbol": symbol,
        "stake": stake,
        "multiplier": multiplier,
        "hma_period": hma_period,
        "flow_period": flow_period,
        "flow_smooth": flow_smooth,
        "flow_threshold": flow_threshold,
        "tp_pct": tp_pct,
        "sl_pct": sl_pct,
        "trades": total_trades,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 2),
        "pnl": round(total_pnl, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(
            sum(t["pnl"] for t in wins) / abs(sum(t["pnl"] for t in losses)), 2
        ) if losses else float("inf"),
    }


def sweep_parameters(
    candles: List[dict],
    symbol: str,
    hma_periods: List[int] = None,
    flow_periods: List[int] = None,
    flow_smooths: List[int] = None,
    flow_thresholds: List[float] = None,
    multipliers: List[int] = None,
    tp_pcts: List[float] = None,
    sl_pcts: List[float] = None,
    top_n: int = 10,
) -> List[dict]:
    """Hace sweep de parámetros y retorna los top N con mejor PnL."""

    hma_periods = hma_periods or [10, 20, 30]
    flow_periods = flow_periods or [10, 14, 20]
    flow_smooths = flow_smooths or [2, 3, 5]
    flow_thresholds = flow_thresholds or [0.0, 0.1, 0.2]
    multipliers = multipliers or [50, 100, 200]
    tp_pcts = tp_pcts or [0.002, 0.005, 0.01]
    sl_pcts = sl_pcts or [0.001, 0.0025, 0.005]

    total_combos = (
        len(hma_periods) * len(flow_periods) * len(flow_smooths) *
        len(flow_thresholds) * len(multipliers) * len(tp_pcts) * len(sl_pcts)
    )
    print(f"\nIniciando sweep: {total_combos} combinaciones de parámetros\n")

    results: List[dict] = []
    count = 0

    for hp, fp, fs, ft, mult, tp, sl in itertools.product(
        hma_periods, flow_periods, flow_smooths, flow_thresholds,
        multipliers, tp_pcts, sl_pcts
    ):
        count += 1
        r = run_backtest(
            candles, symbol,
            hma_period=hp,
            flow_period=fp,
            flow_smooth=fs,
            flow_threshold=ft,
            multiplier=mult,
            tp_pct=tp,
            sl_pct=sl,
        )
        results.append(r)

        if count % 50 == 0:
            print(f"  Procesadas {count}/{total_combos} combinaciones...")

    # Ordenar por PnL descendente
    results.sort(key=lambda x: x["pnl"], reverse=True)

    print(f"\n{'='*80}")
    print(f"TOP {top_n} CONFIGURACIONES (por PnL)")
    print(f"{'='*80}")
    print(
        f"{'#':<3} {'PnL':>10} {'Trades':>7} {'Win%':>7} {'W':>4} {'L':>4} "
        f"{'Mult':>5} {'HMA':>5} {'Flow':>6} {'Smooth':>7} {'Thr':>6} "
        f"{'TP%':>7} {'SL%':>7} {'PF':>7}"
    )
    print("-" * 80)

    for i, r in enumerate(results[:top_n], 1):
        print(
            f"{i:<3} {r['pnl']:>10.2f} {r['trades']:>7} {r['win_rate']:>7.1f} "
            f"{r['wins']:>4} {r['losses']:>4} {r['multiplier']:>5} "
            f"{r['hma_period']:>5} {r['flow_period']:>6} {r['flow_smooth']:>7} "
            f"{r['flow_threshold']:>6.1f} {r['tp_pct']*100:>6.2f}% "
            f"{r['sl_pct']*100:>6.2f}% {r['profit_factor']:>7}"
        )

    # Guardar todos los resultados a CSV
    csv_path = f"backtest_results_{symbol}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print(f"\nResultados guardados en: {csv_path}")

    return results


def main():
    data_file = sys.argv[1] if len(sys.argv) > 1 else \
        "../scripts/backtest/data/R_25-60.json"
    symbol = sys.argv[2] if len(sys.argv) > 2 else "R_25"

    print(f"Cargando velas desde: {data_file}")
    candles = load_candles(data_file)
    print(f"Velas cargadas: {len(candles)}")
    print(f"Rango: {candles[0]['epoch']} a {candles[-1]['epoch']}")

    results = sweep_parameters(candles, symbol)

    if results:
        best = results[0]
        print(f"\n{'='*80}")
        print("MEJOR CONFIGURACIÓN:")
        print(f"{'='*80}")
        for k, v in best.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
