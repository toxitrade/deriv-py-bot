#!/usr/bin/env python3
"""
FastAPI web app wrapper — Bot de trading 1HZ50V HMA + Mladen Flow (unificado).

Soporta dos modos seleccionables desde el dashboard (no hace falta entrar a Render):
  - binary    → contratos binary (CALL/PUT) con duración fija + martingala
  - multiplier → contratos multiplier (MULTUP/MULTDOWN) con TP/SL + salida por señal

Siempre opera en modo DEMO (no se permite trade real).

Exposición:
  GET  /                → dashboard web
  GET  /status          → estado detallado (posición, trades, PnL)
  GET  /config          → configuración actual (sin secretos)
  POST /config          → guarda configuración (symbol, mode, stake, etc.)
  POST /start           → asegura que el bot esté corriendo
  POST /stop            → detiene el bot
  GET  /signals         → última señal generada
  GET  /health          → health check (siempre ok para Render)
  GET  /logs            → últimas líneas del archivo de log
"""

import asyncio
import json
import math
import os
import sys
from contextlib import asynccontextmanager
from typing import Any, Optional

def _sanitize(v: Any) -> Any:
    """Convierte NaN/Inf a None para JSON válido."""
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Asegura que se encuentre el paquete bot_python (mismo directorio)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importar bots y estados
from bot_python.bot_1hz50v import HMAFlowBot, state as binary_state
from bot_python.multiplier_bot import MultiplierBot, state as multiplier_state

CONFIG_FILE = "config.json"

# ===========================================================================
# DASHBOARD WEB (HTML embebido — accesible desde cualquier navegador)
# ===========================================================================
DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>1HZ50V HMA + Mladen Flow Bot</title>
<style>
:root{--bg:#0b0f14;--card:#111827;--text:#e5e7eb;--muted:#9ca3af;--accent:#22c55e;--accent2:#3b82f6;--danger:#ef4444;--border:#1f2937}
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--text);margin:0;padding:16px;max-width:1000px;margin:0 auto}
h1{font-size:1.4rem;margin:0 0 .8rem}h2{font-size:1rem;margin:1.2rem 0 .4rem;border-bottom:1px solid var(--border);padding-bottom:.3rem}
.card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:1rem;margin-bottom:1rem}
.row{display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:.5rem}
.row > *{flex:1;min-width:140px}
label{display:block;font-size:.8rem;color:var(--muted);margin-bottom:.2rem}
select,input{width:100%;background:#0b0f14;border:1px solid var(--border);color:var(--text);padding:.5rem;border-radius:4px}
button{padding:.5rem 1rem;border:none;border-radius:4px;cursor:pointer;font-weight:600}
.btn-primary{background:var(--accent);color:#000}
.btn-danger{background:var(--danger);color:#fff}
.btn-secondary{background:var(--accent2);color:#fff}
.status-row{display:flex;align-items:center;gap:1rem;flex-wrap:wrap}
.dot{width:12px;height:12px;border-radius:50%;background:#6b7280}
.dot.running{background:var(--accent);box-shadow:0 0 8px var(--accent)}
.dot.stopped{background:var(--danger)}
.muted{color:var(--muted);font-size:.85rem}
table{width:100%;border-collapse:collapse;font-size:.8rem}
th,td{padding:.35rem .5rem;text-align:left;border-bottom:1px solid var(--border)}
th{color:var(--muted);font-weight:600}
tr.win td{color:var(--accent)}tr.loss td{color:var(--danger)}
.badge{display:inline-block;padding:.1rem .4rem;border-radius:9999px;font-size:.7rem;font-weight:700}
.badge-binary{background:#3b82f620;color:#3b82f6}
.badge-multiplier{background:#a855f720;color:#a855f7}
.alert{padding:.75rem;border-radius:4px;margin-bottom:1rem;display:none}
.alert.info{background:#1e3a5f;border:1px solid #3b82f6}
.alert.success{background:#14532d;border:1px solid #22c55e}
.alert.error{background:#7f1d1d;border:1px solid #ef4444}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:.8rem}
.stat{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:1rem}
.stat .label{color:var(--muted);font-size:.7rem}
.stat .value{font-size:1.4rem;font-weight:700;margin-top:.2rem}

/* Frames con altura controlada y scroll */
.frame{background:#0b0f14;border:1px solid var(--border);border-radius:8px;overflow:hidden;display:flex;flex-direction:column}
.frame-header{background:#111827;border-bottom:1px solid var(--border);padding:.6rem 1rem;font-weight:600;display:flex;justify-content:space-between;align-items:center}
.frame-body{overflow:auto;flex:1;min-height:0}
.frame-body table{width:100%;border-collapse:collapse;font-size:.8rem}
.frame-body th,.frame-body td{padding:.35rem .5rem;text-align:left;border-bottom:1px solid var(--border)}
.frame-body th{color:var(--muted);font-weight:600;position:sticky;top:0;background:#0b0f14;z-index:1}
.frame-body tr.win td{color:var(--accent)}
.frame-body tr.loss td{color:var(--danger)}

/* Alturas máximas */
#trades-frame{max-height:55vh}
#log-frame{max-height:40vh}

.log-box{font-family:monospace;font-size:.7rem;background:#0b0f14;padding:.5rem;white-space:pre-wrap;font-family:monospace}
.muted{color:var(--muted);font-size:.85rem}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:.8rem}
.stat{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:1rem}
.stat .label{color:var(--muted);font-size:.7rem}
.stat .value{font-size:1.4rem;font-weight:700;margin-top:.2rem}
.badge{display:inline-block;padding:.1rem .4rem;border-radius:9999px;font-size:.7rem;font-weight:700}
.badge-binary{background:#3b82f620;color:#3b82f6}
.badge-multiplier{background:#a855f720;color:#a855f7}
.alert{padding:.75rem;border-radius:4px;margin-bottom:1rem;display:none}
.alert.info{background:#1e3a5f;border:1px solid #3b82f6}
.alert.success{background:#14532d;border:1px solid #22c55e}
.alert.error{background:#7f1d1d;border:1px solid #ef4444}
.row{display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:.5rem}
.row > *{flex:1;min-width:140px}
label{display:block;font-size:.8rem;color:var(--muted);margin-bottom:.2rem}
select,input{width:100%;background:#0b0f14;border:1px solid var(--border);color:var(--text);padding:.5rem;border-radius:4px}
button{padding:.5rem 1rem;border:none;border-radius:4px;cursor:pointer;font-weight:600}
.btn-primary{background:var(--accent);color:#000}
.btn-danger{background:var(--danger);color:#fff}
.btn-secondary{background:var(--accent2);color:#fff}
.status-row{display:flex;align-items:center;gap:1rem;flex-wrap:wrap}
.dot{width:12px;height:12px;border-radius:50%;background:#6b7280}
.dot.running{background:var(--accent);box-shadow:0 0 8px var(--accent)}
.dot.stopped{background:var(--danger)}
.muted{color:var(--muted);font-size:.85rem}

*[box-sizing:border-box]body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--text);margin:0;padding:16px;max-width:1000px;margin:0 auto}
h1{font-size:1.4rem;margin:0 0 .8rem}h2{font-size:1rem;margin:1.2rem 0 .4rem;border-bottom:1px solid var(--border);padding-bottom:.3rem}
.card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:1rem;margin-bottom:1rem}
.row{display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:.5rem}
.row > *{flex:1;min-width:140px}
label{display:block;font-size:.8rem;color:var(--muted);margin-bottom:.2rem}
select,input{width:100%;background:#0b0f14;border:1px solid var(--border);color:var(--text);padding:.5rem;border-radius:4px}
button{padding:.5rem 1rem;border:none;border-radius:4px;cursor:pointer;font-weight:600}
.btn-primary{background:var(--accent);color:#000}
.btn-danger{background:var(--danger);color:#fff}
.btn-secondary{background:var(--accent2);color:#fff}
.status-row{display:flex;align-items:center;gap:1rem;flex-wrap:wrap}
.dot{width:12px;height:12px;border-radius:50%;background:#6b7280}
.dot.running{background:var(--accent);box-shadow:0 0 8px var(--accent)}
.dot.stopped{background:var(--danger)}
.muted{color:var(--muted);font-size:.85rem}
</style>
</head>
<body>
<h1>1HZ50V HMA + Mladen Flow Bot</title>
<div id="alert-box" class="alert"></div>

<div class="status-row">
  <div id="dot" class="dot"></div>
  <div>
    <strong id="status-text">Cargando...</strong>
    <span class="muted" id="mode-text"></span>
  </div>
</div>

<div class="card">
  <h2>Control</h2>
  <div class="row">
    <button id="btn-start" class="btn-primary" onclick="startBot()">Iniciar Bot</button>
    <button id="btn-stop" class="btn-danger" onclick="stopBot()">Detener Bot</button>
  </div>
  
  <!-- Stats principales -->
  <div class="grid" id="stats" style="margin-top:1rem">
    <div class="stat"><div class="label">Saldo</div><div class="value" id="stat-balance">--</div></div>
    <div class="stat"><div class="label">PnL Diario</div><div class="value" id="stat-pnl">--</div></div>
    <div class="stat"><div class="label">Trades Hoy</div><div class="value" id="stat-trades">--</div></div>
    <div class="stat"><div class="label">Ticks</div><div class="value" id="stat-ticks">--</div></div>
  </div>
  
  <!-- Info de sesión -->
  <div class="grid" id="session-info" style="margin-top:1rem;display:none">
    <div class="stat"><div class="label">Inicio del Bot</div><div class="value" id="session-start">--</div></div>
    <div class="stat"><div class="label">Wins / Losses</div><div class="value" id="session-wl">-- / --</div></div>
    <div class="stat"><div class="label">Win Rate</div><div class="value" id="session-wr">--%</div></div>
    <div class="stat"><div class="label">Max Loss in Row</div><div class="value" id="session-maxloss">--</div></div>
    <div class="stat"><div class="label">Max Win in Row</div><div class="value" id="session-maxwin">--</div></div>
    <div class="stat"><div class="label">Max Drawdown</div><div class="value" id="session-maxdd">$--</div></div>
  </div>
</div>

<div class="card">
  <h2>Indicadores (Tiempo Real)</h2>
  <div class="grid">
    <div class="stat"><div class="label">Precio</div><div class="value" id="ind-price">--</div></div>
    <div class="stat"><div class="label">HMA</div><div class="value" id="ind-hma">--</div></div>
    <div class="stat"><div class="label">Flow</div><div class="value" id="ind-flow">--</div></div>
    <div class="stat"><div class="label">Dirección</div><div class="value" id="ind-dir">--</div></div>
    <div class="stat"><div class="label">Martingala Step</div><div class="value" id="ind-mart">0</div></div>
    <div class="stat"><div class="label">Símbolo Actual</div><div class="value" id="ind-symbol">--</div></div>
  </div>
</div>

<div class="card">
  <h2>Señal Actual</h2>
  <div class="grid">
    <div class="stat"><div class="label">Dirección</div><div class="value" id="sig-side">--</div></div>
    <div class="stat"><div class="label">Entrada</div><div class="value" id="sig-entry">--</div></div>
    <div class="stat"><div class="label">Hora</div><div class="value" id="sig-time">--</div></div>
    <div class="stat"><div class="label">Posición</div><div class="value" id="sig-pos">--</div></div>
  </div>
</div>

<!-- Trades con scroll y últimas 20 -->
<div class="card frame" id="trades-frame">
  <div class="frame-header">
    <span>Trades (últimas 20)</span>
    <span class="muted" id="trades-count">0 trades</span>
  </div>
  <div class="frame-body">
    <table id="trades-table"><thead><tr><th>Hora</th><th>Tipo</th><th>Entrada</th><th>Salida</th><th>Stake</th><th>PnL</th><th>Resultado</th></tr></thead><tbody></tbody></table>
  </div>
</div>

<!-- Log con scroll -->
<div class="card frame" id="log-frame">
  <div class="frame-header">
    <span>Log del Bot</span>
    <div style="display:flex;gap:.5rem;align-items:center">
      <button class="btn-secondary" id="btn-refresh-log" style="padding:.3rem .6rem;font-size:.75rem">Actualizar</button>
      <span class="muted">Auto-refresh 10s</span>
    </div>
  </div>
  <div class="frame-body">
    <pre class="log-box" id="log-box">Cargando log...</pre>
  </div>
</div>

<script>
const API = window.location.origin;
function $(id){ return document.getElementById(id); }
async function api(path, method='GET', body=null){
  const opts = { method, headers: {} };
  if (body) opts.headers['Content-Type'] = 'application/json';
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(API + path, opts);
  return r.json();
}
function setAlert(msg, type='info'){ const box = $('alert-box'); box.textContent = msg; box.className = 'alert ' + type; box.style.display = 'block'; setTimeout(()=>{ box.style.display='none'; }, 5000); }
function formatTime(ts){ if (!ts) return '-'; const d = new Date(ts); return d.toLocaleTimeString('es-AR', {hour:'2-digit', minute:'2-digit', second:'2-digit'}); }
function formatDate(ts){ if (!ts) return '-'; const d = new Date(ts); return d.toLocaleString('es-AR', {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit', second:'2-digit'}); }

async function loadStatus(){
  const s = await api('/status');
  const dot = $('dot'); const txt = $('status-text');
  const btnStart = $('btn-start'); const btnStop = $('btn-stop');
  if (s.running){
    dot.className = 'dot running'; txt.textContent = 'Ejecutándose';
    btnStart.disabled = true; btnStop.disabled = false;
    $('session-info').style.display = 'grid';
  } else {
    dot.className = 'dot stopped'; txt.textContent = s.message || 'Detenido';
    btnStart.disabled = false; btnStop.disabled = true;
    $('session-info').style.display = 'none';
  }
  $('mode-text').textContent = (s.mode === 'multiplier' ? 'Multiplier' : 'Binary') + (s.trade_mode ? ' · ' + s.trade_mode : '');
  $('stat-balance').textContent = typeof s.balance === 'number' ? '$' + s.balance.toFixed(2) : '--';
  $('stat-pnl').textContent = typeof s.daily_pnl === 'number' ? (s.daily_pnl >= 0 ? '+' : '') + s.daily_pnl.toFixed(2) : '--';
  $('stat-trades').textContent = s.trades_today || 0;
  $('stat-ticks').textContent = s.ticks_received || 0;
  $('ind-price').textContent = s.last_price !== null && s.last_price !== undefined ? s.last_price.toFixed(4) : '--';
  $('ind-hma').textContent = s.last_hma !== null && s.last_hma !== undefined ? s.last_hma.toFixed(4) : '--';
  $('ind-flow').textContent = s.last_flow !== null && s.last_flow !== undefined ? s.last_flow.toFixed(4) : '--';
  $('ind-dir').textContent = s.last_direction === 1 ? '↑ Alcista' : s.last_direction === -1 ? '↓ Bajista' : '→ Neutral';
  $('ind-mart').textContent = s.martingale_step !== undefined ? s.martingale_step : (s.multiplier !== undefined ? 'x' + s.multiplier : '--');
  $('ind-symbol').textContent = s.symbol || '--';

  // Calcular stats de sesión
  const trades = s.trades || [];
  const closed = trades.filter(t => t.win !== null && t.win !== undefined);
  const wins = closed.filter(t => t.win === true).length;
  const losses = closed.filter(t => t.win === false).length;
  const total = wins + losses;
  const wr = total > 0 ? ((wins / total) * 100).toFixed(1) : '--';
  
  // Max loss/win in a row
  let maxLossRow = 0, maxWinRow = 0, currLossRow = 0, currWinRow = 0;
  let maxDD = 0, peak = 0, runningPnL = 0;
  closed.forEach(t => {
    if (t.win === true) { currWinRow++; currLossRow = 0; maxWinRow = Math.max(maxWinRow, currWinRow); }
    else { currLossRow++; currWinRow = 0; maxLossRow = Math.max(maxLossRow, currLossRow); }
    runningPnL += t.pnl || 0;
    peak = Math.max(peak, runningPnL);
    maxDD = Math.max(maxDD, peak - runningPnL);
  });
  
  // Hora de inicio (primer trade)
  const firstTrade = trades.length > 0 ? trades[0] : null;
  const startTime = firstTrade ? formatDate(firstTrade.entry_time) : '--';
  
  $('session-start').textContent = startTime;
  $('session-wl').textContent = `${wins} / ${losses}`;
  $('session-wr').textContent = `${wr}%`;
  $('session-maxloss').textContent = maxLossRow;
  $('session-maxwin').textContent = maxWinRow;
  $('session-maxdd').textContent = '$' + maxDD.toFixed(2);

  // Trades: últimas 20 con scroll
  const tbody = document.querySelector('#trades-table tbody');
  tbody.innerHTML = '';
  const last20 = [...trades].reverse().slice(0, 20);
  $('trades-count').textContent = `${trades.length} trades (mostrando ${last20.length})`;
  last20.forEach(t => {
    const tr = document.createElement('tr');
    if (t.win === true) tr.className = 'win';
    else if (t.win === false) tr.className = 'loss';
    const pnl = t.pnl !== null && t.pnl !== undefined ? (t.pnl >= 0 ? '+' : '') + t.pnl.toFixed(2) : '--';
    const win = t.win === true ? '<span class="badge badge-binary">WIN</span>' : t.win === false ? '<span class="badge badge-binary">LOSS</span>' : '--';
    tr.innerHTML = `<td>${formatDate(t.entry_time)}</td><td>${t.side}</td><td>${t.entry_price?.toFixed(4) || '--'}</td><td>${t.exit_price?.toFixed(4) || '--'}</td><td>${t.stake?.toFixed(2) || '--'}</td><td>${pnl}</td><td>${win}</td>`;
    tbody.appendChild(tr);
  });
}
async function startBot(){ const r = await api('/start', 'POST'); setAlert(r.status === 'started' ? 'Bot iniciado' : r.status === 'already_running' ? 'Ya estaba corriendo' : 'Iniciado', r.status === 'already_running' ? 'info' : 'success'); await loadStatus(); }
async function stopBot(){ const r = await api('/stop', 'POST'); setAlert('Bot detenido', 'info'); await loadStatus(); }
async function loadSignals(){
  const s = await api('/signals');
  if (s.signal){
    $('sig-side').innerHTML = s.side === 'CALL' ? '<span class="badge badge-binary">CALL ↑</span>' : '<span class="badge badge-binary">PUT ↓</span>';
    $('sig-entry').textContent = s.entry_price?.toFixed(4) || '--';
    $('sig-time').textContent = formatTime(s.entry_time);
    $('sig-pos').textContent = s.position === 'long' ? 'LONG' : s.position === 'short' ? 'SHORT' : '--';
  } else {
    $('sig-side').textContent = 'Sin señal';
  }
}
async function loadLogs(){ const r = await api('/logs?lines=50'); $('log-box').textContent = r.logs || 'Sin logs'; }
setInterval(loadStatus, 5000);
setInterval(loadSignals, 5000);
setInterval(loadLogs, 10000);
$('btn-refresh-log').onclick = loadLogs;
loadStatus(); loadSignals(); loadLogs();
</script>
</body>
</html>"""

# ===========================================================================
# CONFIGURACIÓN
# ===========================================================================
def _load_persistent_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_persistent_config(cfg: dict) -> None:
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"No se pudo guardar config.json: {e}")

PERSISTENT_CFG = _load_persistent_config()

def _get_env(name: str, default: str) -> str:
    """Prioridad: config.json (guardado desde sitio) > variable de entorno > default."""
    if name in PERSISTENT_CFG and PERSISTENT_CFG[name] not in (None, ""):
        return str(PERSISTENT_CFG[name])
    env_val = os.environ.get(name)
    if env_val is not None and env_val != "":
        return env_val
    return default

def _build_config() -> dict:
    mode = _get_env("DERIV_BOT_MODE", "binary").lower()
    common = {
        "symbol": _get_env("DERIV_SYMBOL", "1HZ50V"),
        "stake": float(_get_env("DERIV_STAKE", "10.0")),
        "demo": True,
        "hma_period": int(_get_env("DERIV_HMA_PERIOD", "30")),
        "flow_period": int(_get_env("DERIV_FLOW_PERIOD", "14")),
        "flow_smooth": int(_get_env("DERIV_FLOW_SMOOTH", "3")),
        "flow_threshold": float(_get_env("DERIV_FLOW_THRESHOLD", "0.3")),
        "account_id": os.environ.get("DERIV_ACCOUNT_ID", ""),
        "app_id": os.environ.get("DERIV_APP_ID", ""),
        "log_level": _get_env("DERIV_LOG_LEVEL", "INFO"),
        "log_file": _get_env("DERIV_LOG_FILE", "bot_1hz50v.log" if mode == "binary" else "multiplier_bot.log"),
        "token": os.environ.get("DERIV_TOKEN", ""),
    }
    if mode == "multiplier":
        common.update({
            "multiplier": int(_get_env("DERIV_MULTIPLIER", "100")),
            "tp_pct": float(_get_env("DERIV_TP_PCT", "0.001")),
            "sl_pct": float(_get_env("DERIV_SL_PCT", "0.001")),
        })
    else:
        common.update({
            "duration": int(_get_env("DERIV_DURATION", "1")),
            "duration_unit": _get_env("DERIV_DURATION_UNIT", "m"),
            "martingale_multiplier": float(_get_env("DERIV_MARTINGALE_MULT", "2.0")),
            "max_martingale_steps": int(_get_env("DERIV_MAX_MARTINGALE_STEPS", "5")),
            "max_stake": float(_get_env("DERIV_MAX_STAKE", "100.0")),
            "cooldown_seconds": int(_get_env("DERIV_COOLDOWN_SECONDS", "30")),
        })
    return common

# ===========================================================================
# BOT BACKGROUND TASK
# ===========================================================================
BOT_MODE = _get_env("DERIV_BOT_MODE", "binary").lower()
_bot: Any = None
_bot_task: Optional[asyncio.Task] = None
_bot_running = False

async def _run_bot_loop() -> None:
    """Loop persistente del bot - corre como background task."""
    global _bot_running, _bot
    cfg = _build_config()
    
    if BOT_MODE == "multiplier":
        _bot = MultiplierBot(cfg)
    else:
        _bot = HMAFlowBot(cfg)
    
    _bot_running = True
    try:
        while _bot_running:
            try:
                await _bot.run()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[BOT] Error en run(): {e}. Reiniciando en 5s...")
                await asyncio.sleep(5)
    finally:
        _bot_running = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Iniciar bot automáticamente al arrancar
    global _bot_task, _bot_running
    _bot_task = asyncio.create_task(_run_bot_loop())
    yield
    # Cleanup al apagar
    _bot_running = False
    if _bot_task and not _bot_task.done():
        _bot_task.cancel()
        try:
            await _bot_task
        except asyncio.CancelledError:
            pass

# ===========================================================================
# FASTAPI APP
# ===========================================================================
import asyncio
import json
import math
import os
import sys
from contextlib import asynccontextmanager
from typing import Any, Optional

def _sanitize(v: Any) -> Any:
    """Convierte NaN/Inf a None para JSON válido."""
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Asegura que se encuentre el paquete bot_python (mismo directorio)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importar bots y estados
from bot_python.bot_1hz50v import HMAFlowBot, state as binary_state
from bot_python.multiplier_bot import MultiplierBot, state as multiplier_state

CONFIG_FILE = "config.json"

# ===========================================================================
# CONFIGURACIÓN
# ===========================================================================
def _load_persistent_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_persistent_config(cfg: dict) -> None:
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"No se pudo guardar config.json: {e}")

PERSISTENT_CFG = _load_persistent_config()

def _get_env(name: str, default: str) -> str:
    """Prioridad: config.json (guardado desde sitio) > variable de entorno > default."""
    if name in PERSISTENT_CFG and PERSISTENT_CFG[name] not in (None, ""):
        return str(PERSISTENT_CFG[name])
    env_val = os.environ.get(name)
    if env_val is not None and env_val != "":
        return env_val
    return default

def _build_config() -> dict:
    mode = _get_env("DERIV_BOT_MODE", "binary").lower()
    common = {
        "symbol": _get_env("DERIV_SYMBOL", "1HZ50V"),
        "stake": float(_get_env("DERIV_STAKE", "10.0")),
        "demo": True,
        "hma_period": int(_get_env("DERIV_HMA_PERIOD", "30")),
        "flow_period": int(_get_env("DERIV_FLOW_PERIOD", "14")),
        "flow_smooth": int(_get_env("DERIV_FLOW_SMOOTH", "3")),
        "flow_threshold": float(_get_env("DERIV_FLOW_THRESHOLD", "0.3")),
        "account_id": os.environ.get("DERIV_ACCOUNT_ID", ""),
        "app_id": os.environ.get("DERIV_APP_ID", ""),
        "log_level": _get_env("DERIV_LOG_LEVEL", "INFO"),
        "log_file": _get_env("DERIV_LOG_FILE", "bot_1hz50v.log" if mode == "binary" else "multiplier_bot.log"),
        "token": os.environ.get("DERIV_TOKEN", ""),
    }
    if mode == "multiplier":
        common.update({
            "multiplier": int(_get_env("DERIV_MULTIPLIER", "100")),
            "tp_pct": float(_get_env("DERIV_TP_PCT", "0.001")),
            "sl_pct": float(_get_env("DERIV_SL_PCT", "0.001")),
        })
    else:
        common.update({
            "duration": int(_get_env("DERIV_DURATION", "1")),
            "duration_unit": _get_env("DERIV_DURATION_UNIT", "m"),
            "martingale_multiplier": float(_get_env("DERIV_MARTINGALE_MULT", "2.0")),
            "max_martingale_steps": int(_get_env("DERIV_MAX_MARTINGALE_STEPS", "5")),
            "max_stake": float(_get_env("DERIV_MAX_STAKE", "100.0")),
            "cooldown_seconds": int(_get_env("DERIV_COOLDOWN_SECONDS", "30")),
        })
    return common

# ===========================================================================
# BOT BACKGROUND TASK
# ===========================================================================
BOT_MODE = _get_env("DERIV_BOT_MODE", "binary").lower()
_bot: Any = None
_bot_task: Optional[asyncio.Task] = None
_bot_running = False

async def _run_bot_loop() -> None:
    """Loop persistente del bot - corre como background task."""
    global _bot_running, _bot
    cfg = _build_config()
    
    if BOT_MODE == "multiplier":
        _bot = MultiplierBot(cfg)
    else:
        _bot = HMAFlowBot(cfg)
    
    _bot_running = True
    try:
        while _bot_running:
            try:
                await _bot.run()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[BOT] Error en run(): {e}. Reiniciando en 5s...")
                await asyncio.sleep(5)
    finally:
        _bot_running = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Iniciar bot automáticamente al arrancar
    global _bot_task, _bot_running
    _bot_task = asyncio.create_task(_run_bot_loop())
    yield
    # Cleanup al apagar
    _bot_running = False
    if _bot_task and not _bot_task.done():
        _bot_task.cancel()
        try:
            await _bot_task
        except asyncio.CancelledError:
            pass

# ===========================================================================
# FASTAPI APP
# ===========================================================================
app = FastAPI(title="1HZ50V HMA + Mladen Flow Bot", version="3.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ---------------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def root(): return DASHBOARD_HTML

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(): return DASHBOARD_HTML

@app.get("/health")
async def health():
    return {"status": "ok", "running": _bot_running, "mode": BOT_MODE}

@app.get("/config")
async def get_config():
    cfg = _build_config()
    return {
        "mode": BOT_MODE,
        "symbol": cfg["symbol"],
        "stake": cfg["stake"],
        "demo": cfg["demo"],
        "account_id": cfg["account_id"],
        "app_id": cfg["app_id"],
        "hma_period": cfg["hma_period"],
        "flow_period": cfg["flow_period"],
        "flow_smooth": cfg["flow_smooth"],
        "flow_threshold": cfg["flow_threshold"],
        "duration": cfg.get("duration"),
        "duration_unit": cfg.get("duration_unit"),
        "martingale_multiplier": cfg.get("martingale_multiplier"),
        "max_martingale_steps": cfg.get("max_martingale_steps"),
        "multiplier": cfg.get("multiplier"),
        "tp_pct": cfg.get("tp_pct"),
        "sl_pct": cfg.get("sl_pct"),
        "log_level": cfg["log_level"],
        "log_file": cfg["log_file"],
        "token_configured": bool(cfg["token"]),
    }

@app.post("/config")
async def set_config(updates: dict):
    allowed = {"mode","symbol","stake","account_id","app_id","hma_period","flow_period",
               "flow_smooth","flow_threshold","duration","duration_unit",
               "martingale_multiplier","max_martingale_steps","multiplier","tp_pct","sl_pct"}
    key_map = {"mode":"DERIV_BOT_MODE","symbol":"DERIV_SYMBOL","stake":"DERIV_STAKE",
               "account_id":"DERIV_ACCOUNT_ID","app_id":"DERIV_APP_ID",
               "hma_period":"DERIV_HMA_PERIOD","flow_period":"DERIV_FLOW_PERIOD",
               "flow_smooth":"DERIV_FLOW_SMOOTH","flow_threshold":"DERIV_FLOW_THRESHOLD",
               "duration":"DERIV_DURATION","duration_unit":"DERIV_DURATION_UNIT",
               "martingale_multiplier":"DERIV_MARTINGALE_MULT",
               "max_martingale_steps":"DERIV_MAX_MARTINGALE_STEPS",
               "multiplier":"DERIV_MULTIPLIER","tp_pct":"DERIV_TP_PCT","sl_pct":"DERIV_SL_PCT"}
    for key, value in updates.items():
        if key in allowed:
            env_key = key_map.get(key, key)
            PERSISTENT_CFG[env_key] = value
    _save_persistent_config(PERSISTENT_CFG)
    
    # Si cambió el modo, recargar la clase del bot
    global BOT_MODE, _bot_task, _bot_running
    new_mode = str(PERSISTENT_CFG.get("DERIV_BOT_MODE", BOT_MODE)).lower()
    if new_mode != BOT_MODE:
        BOT_MODE = new_mode
        # Reiniciar bot task
        _bot_running = False
        if _bot_task and not _bot_task.done():
            _bot_task.cancel()
            try:
                await _bot_task
            except asyncio.CancelledError:
                pass
        _bot_task = asyncio.create_task(_run_bot_loop())
    
    return {"status": "saved", "mode": BOT_MODE, "config": await get_config()}

def _get_state():
    """Obtiene el state del módulo correcto según BOT_MODE."""
    if BOT_MODE == "multiplier":
        return multiplier_state
    return binary_state

@app.get("/status")
async def status():
    if not _bot_running:
        return {"running": False, "message": "Bot no iniciado", "mode": BOT_MODE}
    
    state = _get_state()
    trades = []
    try:
        for t in state.trades:
            trades.append({
                "entry_time": getattr(t, 'entry_time', None),
                "exit_time": getattr(t, 'exit_time', None),
                "side": getattr(t, 'side', None),
                "entry_price": getattr(t, 'entry_price', None),
                "exit_price": getattr(t, 'exit_price', None),
                "stake": getattr(t, 'stake', None),
                "pnl": getattr(t, 'pnl', None),
                "win": getattr(t, 'win', None),
                "contract_id": getattr(t, 'contract_id', None),
            })
    except Exception:
        trades = []
    
    base = {
        "running": _bot_running,
        "mode": BOT_MODE,
        "symbol": getattr(state, 'current_symbol', ''),
        "position": getattr(state, 'position', None),
        "open_side": getattr(state, 'open_side', None),
        "open_entry_price": getattr(state, 'open_entry_price', None),
        "trades_today": getattr(state, 'trades_today', 0),
        "ticks_received": getattr(state, 'ticks_received', 0),
        "balance": getattr(state, 'balance', 0),
        "daily_pnl": getattr(state, 'daily_pnl', 0),
        "session_start_balance": getattr(state, 'session_start_balance', None),
        "last_price": _sanitize(getattr(state, 'last_price', None)),
        "last_hma": _sanitize(getattr(state, 'last_hma', None)),
        "last_flow": _sanitize(getattr(state, 'last_flow', None)),
        "last_direction": getattr(state, 'last_direction', None),
        "trades": trades,
    }
    if BOT_MODE == "binary":
        base.update({"martingale_step": getattr(state, 'martingale_step', 0)})
    else:
        base.update({"multiplier": getattr(state, 'multiplier', 0)})
    return base

@app.get("/signals")
async def signals():
    state = _get_state()
    if not state.trades:
        return {"signal": None, "message": "Sin trades aún", "mode": BOT_MODE}
    last = state.trades[-1]
    return {
        "signal": last.side.lower(),
        "side": last.side,
        "symbol": getattr(state, 'current_symbol', ''),
        "entry_price": last.entry_price,
        "entry_time": last.entry_time,
        "position": getattr(state, 'position', None),
        "mode": BOT_MODE,
    }

@app.post("/start")
async def start_bot():
    global _bot_task, _bot_running
    if _bot_running:
        return {"status": "already_running", "mode": BOT_MODE}
    _bot_task = asyncio.create_task(_run_bot_loop())
    return {"status": "started", "mode": BOT_MODE, "trade_mode": "DEMO"}

@app.post("/stop")
async def stop_bot():
    global _bot_task, _bot_running
    _bot_running = False
    if _bot_task and not _bot_task.done():
        _bot_task.cancel()
        try:
            await _bot_task
        except asyncio.CancelledError:
            pass
    _bot_task = None
    return {"status": "stopped", "mode": BOT_MODE}

@app.get("/logs")
async def logs(lines: int = 50):
    log_file = _build_config().get("log_file", "bot_1hz50v.log")
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        tail = all_lines[-lines:] if lines > 0 else all_lines
        return {"log_file": log_file, "lines": len(tail), "logs": "".join(tail)}
    except FileNotFoundError:
        return {"log_file": log_file, "lines": 0, "logs": "Archivo de log no encontrado aún"}
    except Exception as e:
        return {"log_file": log_file, "lines": 0, "logs": f"Error leyendo log: {e}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
