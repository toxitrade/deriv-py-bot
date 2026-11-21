#!/usr/bin/env python3
"""
Uptime Robot casero — hace GET /health cada 60s al bot de Deriv en Render.
Además descarga el log de trades (/logs) cada 60s y lo guarda localmente.
Uso:
    python3 uptime_bot.py          # primer plano
    nohup python3 uptime_bot.py &  # background
"""

import time
import datetime
import urllib.request
import urllib.error
import sys
import os
import json

URL_HEALTH = "https://deriv-py-bot.onrender.com/health"
URL_LOGS = "https://deriv-py-bot.onrender.com/logs?lines=200"
LOG_FILE = "uptime_bot.log"
TRADES_LOG_FILE = "trades_log.jsonl"
INTERVAL = 60  # segundos


def log(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def save_trades_log(trades_data: dict) -> None:
    """Guarda el log de trades en formato JSONL (una línea por trade)."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    trades = trades_data.get("logs", "")
    if trades:
        with open(TRADES_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {trades}\n")


def check_health() -> bool:
    try:
        req = urllib.request.Request(URL_HEALTH, headers={"User-Agent": "uptime-bot/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            if resp.status == 200 and "ok" in body:
                log(f"OK {resp.status} {body.strip()}")
                return True
            else:
                log(f"WARN status={resp.status} body={body.strip()}")
                return False
    except urllib.error.URLError as e:
        log(f"ERROR {e}")
        return False
    except Exception as e:
        log(f"ERROR {type(e).__name__}: {e}")
        return False


def check_logs() -> bool:
    """Descarga y guarda el log de trades del bot."""
    try:
        req = urllib.request.Request(URL_LOGS, headers={"User-Agent": "uptime-bot/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            if resp.status == 200:
                data = json.loads(body)
                log(f"LOGS descargados: {data.get('lines', 0)} líneas")
                save_trades_log(data)
                return True
            else:
                log(f"LOGS WARN status={resp.status}")
                return False
    except urllib.error.URLError as e:
        log(f"LOGS ERROR {e}")
        return False
    except Exception as e:
        log(f"LOGS ERROR {type(e).__name__}: {e}")
        return False


def main() -> None:
    log(f"Iniciando uptime-bot -> {URL_HEALTH} cada {INTERVAL}s (incluye descarga de trades)")
    while True:
        check_health()
        check_logs()
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()