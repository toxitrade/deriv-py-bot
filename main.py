"""
enzonic web app wrapper — Bot de trading 1HZ50V HMA + Mladen Flow (unificado).

Soporta dos modos seleccionables desde el sitio (no hace falta entrar a Render):
  - binary  → contratos binary (CALL/PUT) con duración fija + martingala
  - multiplier → contratos multiplier (leverage) con TP/SL + salida por señal

Siempre opera en modo DEMO (no se permite trade real).

Exposición:
  GET  /                → estado del bot
  GET  /status          → estado detallado (posición, trades, PnL)
  GET  /config          → configuración actual (sin secretos)
  POST /config          → guarda configuración (symbol, mode, stake, etc.)
  POST /start           → inicia el bot en background
  POST /stop            → detiene el bot
  GET  /signals         → última señal generada
  GET  /health          → health check para la plataforma
  GET  /logs            → últimas líneas del archivo de log

Variables de entorno (solo para DERIV_TOKEN y secretos, se setean en Render):
  DERIV_TOKEN           Token de API de Deriv (demo). Sin él va en PAPER.
  DERIV_APP_ID          App ID (requerido para PAT, tu propio ID de aplicación Deriv)
  DERIV_LOG_LEVEL       INFO | DEBUG | WARNING (default: INFO)

Configurables desde el sitio (se guardan en config.json):
  DERIV_BOT_MODE        binary | multiplier  (default: binary)
  DERIV_SYMBOL          Símbolo (default: 1HZ50V)
  DERIV_STAKE           Stake por contrato (USD, default: 10.0)
  DERIV_ACCOUNT_ID      ID de cuenta Options Trading (para OTP)
  DERIV_DURATION        Duración del contrato en minutos (default: 1)
  DERIV_DURATION_UNIT   m (default: m)
  DERIV_MARTINGALE_MULT Multiplicador martingala (default: 2.4)
  DERIV_MAX_MARTINGALE_STEPS (default: 4)
  DERIV_MULTIPLIER      Multiplicador de apalancamiento (default: 100)
  DERIV_TP_PCT          Take profit % del precio (default: 0.001)
  DERIV_SL_PCT          Stop loss % del precio (default: 0.001)
  DERIV_HMA_PERIOD      HMA period (default: 20)
  DERIV_FLOW_PERIOD     Flow period (default: 14)
  DERIV_FLOW_SMOOTH     Flow smooth (default: 3)
  DERIV_FLOW_THRESHOLD  Umbral de cruce (default: 0.0)
  DERIV_DEMO            Siempre true (forzado desde el sitio)
"""

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

# Asegura que se encuentre el paquete bot_python (mismo directorio)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CONFIG_FILE = "config.json"


# ===========================================================================
# DASHBOARD WEB (HTML embebido — accesible desde cualquier navegador)
# ===========================================================================
DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Deriv Bot — HMA + Mladen Flow</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; background: #f5f7fa; color: #1a1a1a; }
  .container { max-width: 900px; margin: 0 auto; padding: 24px; }
  header { background: #0f172a; color: #fff; padding: 16px 24px; border-radius: 8px 8px 0 0; margin-bottom: 20px; }
  header h1 { margin: 0; font-size: 18px; display: flex; align-items: center; gap: 10px; }
  header .badge { font-size: 11px; background: #22c55e; color: #fff; padding: 2px 8px; border-radius: 10px; margin-left: 8px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-bottom: 20px; }
  .card { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
  .card h2 { font-size: 14px; margin: 0 0 12px 0; color: #475569; text-transform: uppercase; letter-spacing: 0.5px; }
  .status { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
  .dot { width: 10px; height: 10px; border-radius: 50%; background: #94a3b8; }
  .dot.running { background: #22c55e; box-shadow: 0 0 8px #22c55e; }
  .dot.stopped { background: #ef4444; box-shadow: 0 0 8px #ef4444; }
  .big { font-size: 28px; font-weight: 700; margin: 8px 0; }
  .small { font-size: 13px; color: #64748b; }
  .btn { background: #0f172a; color: #fff; border: none; padding: 10px 18px; border-radius: 6px; font-size: 14px; cursor: pointer; font-weight: 600; margin: 4px 4px 4px 0; }
  .btn:hover { background: #1e293b; }
  .btn.start { background: #22c55e; }
  .btn.start:hover { background: #16a34a; }
  .btn.stop { background: #ef4444; }
  .btn.stop:hover { background: #dc2626; }
  .btn.secondary { background: #f1f5f9; color: #334155; }
  .btn.secondary:hover { background: #e2e8f0; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .form-group { margin-bottom: 12px; }
  .form-group label { display: block; font-size: 12px; color: #64748b; margin-bottom: 4px; font-weight: 600; }
  .form-group input { width: 100%; padding: 8px 10px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 14px; background: #fff; }
  .form-group input:focus { outline: none; border-color: #3b82f6; }
  .row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .log { background: #0f172a; color: #cbd5e1; border-radius: 8px; padding: 12px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px; max-height: 400px; overflow-y: auto; margin-top: 12px; }
  .log .line { white-space: pre-wrap; margin: 2px 0; }
  .log .error { color: #f87171; }
  .log .info { color: #34d399; }
  .log .warn { color: #fbbf24; }
  .alert { padding: 10px 14px; border-radius: 6px; margin-bottom: 16px; font-size: 13px; }
  .alert.info { background: #dbeafe; color: #1e40af; border-left: 4px solid #3b82f6; }
  .alert.warn { background: #fef3c7; color: #92400e; border-left: 4px solid #f59e0b; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 12px; }
  th { text-align: left; color: #64748b; font-size: 11px; text-transform: uppercase; padding: 8px; border-bottom: 2px solid #e2e8f0; }
  td { padding: 8px; border-bottom: 1px solid #f1f5f9; }
  tr:nth-child(even) td { background: #f8fafc; }
  .win { color: #16a34a; font-weight: 700; }
  .lose { color: #dc2626; font-weight: 700; }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>📊 Deriv Bot — HMA + Mladen Flow <span class="badge" id="mode-badge">binary</span></h1>
  </header>

  <div class="alert info" id="alert-box" style="display:none;"></div>

  <div class="grid">
    <div class="card">
      <h2>Estado</h2>
      <div class="status">
        <div class="dot stopped" id="dot"></div>
        <span id="status-text">Detenido</span>
      </div>
      <div class="big" id="mode-text">Binary</div>
      <div class="small" id="trade-mode">Modo: DEMO</div>
      <div style="margin-top:14px;">
        <button class="btn start" id="btn-start">Iniciar bot</button>
        <button class="btn stop" id="btn-stop">Detener</button>
      </div>
    </div>

    <div class="card">
      <h2>Configuración rápida</h2>
      <div class="form-group">
        <label>Modo</label>
        <select id="sel-mode" style="width:100%;padding:8px 10px;border:1px solid #cbd5e1;border-radius:6px;font-size:14px;">
          <option value="binary">Binary (CALL/PUT)</option>
          <option value="multiplier">Multiplier (leverage)</option>
        </select>
      </div>
      <div class="row">
        <div class="form-group">
          <label>Símbolo</label>
          <input id="sel-symbol" value="1HZ50V" />
        </div>
        <div class="form-group">
          <label>Stake (USD)</label>
          <input id="sel-stake" type="number" value="10" step="0.1" />
        </div>
      </div>
      <button class="btn secondary" id="btn-save">Guardar configuración</button>
      <button class="btn secondary" id="btn-clear-local">Borrar config local</button>
    </div>
  </div>

  <div class="card">
    <h2>Señal actual</h2>
    <div id="signal-box" style="padding:16px; border-radius:8px; background:#f8fafc; border:1px solid #e2e8f0; text-align:center;">
      <div class="small">Esperando datos...</div>
      <div style="font-size:32px; font-weight:800; margin-top:8px;" id="signal-value">—</div>
      <div class="small" id="signal-reason"></div>
    </div>
  </div>

  <div class="card">
    <h2>Últimos trades</h2>
    <table id="trades-table">
      <thead><tr><th>Hora</th><th>Tipo</th><th>Entrada</th><th>Salida</th><th>Stake</th><th>PnL</th><th>Resultado</th></tr></thead>
      <tbody id="trades-body"><tr><td colspan="7" style="text-align:center; color:#94a3b8;">Sin trades aún</td></tr></tbody>
    </table>
  </div>

  <div class="card" style="margin-top:20px;">
    <h2>Log</h2>
    <div class="log" id="log-box">
      <div class="line">Cargando log...</div>
    </div>
    <div style="margin-top:8px;">
      <button class="btn secondary" id="btn-refresh-log">Actualizar log</button>
      <span class="small">Se actualiza automáticamente cada 10s</span>
    </div>
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

function setAlert(msg, type='info'){
  const box = $('alert-box');
  box.textContent = msg;
  box.className = 'alert ' + type;
  box.style.display = 'block';
  setTimeout(()=>{ box.style.display='none'; }, 5000);
}

function formatTime(ts){
  if (!ts) return '-';
  const d = new Date(ts);
  return d.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit', second:'2-digit'});
}

async function loadStatus(){
  const s = await api('/status');
  const dot = $('dot');
  const txt = $('status-text');
  const btnStart = $('btn-start');
  const btnStop = $('btn-stop');

  if (s.running){
    dot.className = 'dot running';
    txt.textContent = 'Ejecutándose';
    btnStart.disabled = true;
    btnStop.disabled = false;
  } else {
    dot.className = 'dot stopped';
    txt.textContent = s.message || 'Detenido';
    btnStart.disabled = false;
    btnStop.disabled = true;
  }

  $('mode-text').textContent = (s.mode === 'multiplier' ? 'Multiplier' : 'Binary') + (s.trade_mode ? ' · ' + s.trade_mode : '');
  $('trade-mode').textContent = 'Modo: ' + (s.trade_mode || 'DEMO');

  const tbody = $('trades-body');
  tbody.innerHTML = '';
  if (!s.trades || s.trades.length === 0){
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:#94a3b8;">Sin trades aún</td></tr>';
  } else {
    const recent = s.trades.slice().reverse().slice(0, 10);
    recent.forEach(t => {
      const winCls = t.win ? 'win' : 'lose';
      const winTxt = t.win ? 'WIN' : 'LOSE';
      const pnl = t.pnl !== null && t.pnl !== undefined ? t.pnl.toFixed(2) : '-';
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${formatTime(t.entry_time)}</td>
                      <td>${t.side}</td>
                      <td>${t.entry_price !== null ? t.entry_price.toFixed(2) : '-'}</td>
                      <td>${t.exit_price !== null ? t.exit_price.toFixed(2) : '-'}</td>
                      <td>${t.stake !== null ? t.stake.toFixed(2) : '-'}</td>
                      <td>${pnl}</td>
                      <td class="${winCls}">${winTxt}</td>`;
      tbody.appendChild(tr);
    });
  }
}

async function loadSignal(){
  const s = await api('/signals');
  const box = $('signal-box');
  const val = $('signal-value');
  const reason = $('signal-reason');
  if (!s.signal){
    box.style.background = '#f8fafc';
    box.style.borderColor = '#e2e8f0';
    val.textContent = '—';
    val.style.color = '#64748b';
    reason.textContent = s.message || 'Esperando señal...';
    reason.style.color = '#94a3b8';
  } else {
    const isCall = s.signal === 'call';
    box.style.background = isCall ? '#dcfce7' : '#fee2e2';
    box.style.borderColor = isCall ? '#86efac' : '#fca5a5';
    val.textContent = s.signal.toUpperCase();
    val.style.color = isCall ? '#16a34a' : '#dc2626';
    reason.textContent = (s.position ? 'Posición: ' + s.position.toUpperCase() + ' · ' : '') + (s.reason || '');
    reason.style.color = '#475569';
  }
}

async function loadLog(){
  const r = await api('/logs?lines=40');
  const box = $('log-box');
  if (r.lines === 0){
    box.innerHTML = '<div class="line">Sin log aún</div>';
  } else {
    box.innerHTML = r.logs.split('\n').filter(l => l.trim()).map(l => {
      const cls = l.includes('ERROR') ? 'error' : (l.includes('INFO') ? 'info' : (l.includes('WARNING') ? 'warn' : ''));
      return `<div class="line ${cls}">${escapeHtml(l)}</div>`;
    }).join('');
  }
  box.scrollTop = box.scrollHeight;
}

function escapeHtml(s){
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

async function loadConfig(){
  // Primero intenta cargar desde localStorage (configuración del usuario)
  const saved = localStorage.getItem('bot_config');
  if (saved){
    try{
      const c = JSON.parse(saved);
      $('sel-mode').value = c.mode || 'binary';
      $('sel-symbol').value = c.symbol || '1HZ50V';
      $('sel-stake').value = c.stake || 10;
      $('mode-badge').textContent = (c.mode === 'multiplier' ? 'Multiplier' : 'Binary');
      setAlert('Configuración cargada desde tu navegador (localStorage)');
      return;
    }catch(e){
      // Ignorar errores de parseo y continuar con el servidor
    }
  }
  // Fallback: cargar desde el servidor
  const c = await api('/config');
  $('sel-mode').value = c.mode || 'binary';
  $('sel-symbol').value = c.symbol || '1HZ50V';
  $('sel-stake').value = c.stake || 10;
  $('mode-badge').textContent = (c.mode === 'multiplier' ? 'Multiplier' : 'Binary');
}

async function saveConfig(){
  const payload = {
    mode: $('sel-mode').value,
    symbol: $('sel-symbol').value,
    stake: parseFloat($('sel-stake').value) || 10,
  };
  await api('/config', 'POST', payload);
  // Guardar también en localStorage del navegador
  localStorage.setItem('bot_config', JSON.stringify(payload));
  setAlert('Configuración guardada en servidor y en tu navegador');
  await loadStatus();
}

async function clearLocalConfig(){
  localStorage.removeItem('bot_config');
  setAlert('Configuración local borrada. Se usará la del servidor.');
  await loadConfig();
}

async function startBot(){
  const r = await api('/start', 'POST');
  if (r.status === 'started'){
    setAlert('Bot iniciado en modo ' + r.trade_mode);
  } else {
    setAlert('El bot ya está ejecutándose', 'warn');
  }
  await loadStatus();
}

async function stopBot(){
  const r = await api('/stop', 'POST');
  setAlert('Bot detenido');
  await loadStatus();
}

loadStatus();
loadSignal();
loadConfig();
loadLog();

setInterval(() => {
  loadStatus();
  loadSignal();
  loadLog();
}, 10000);

$('btn-start').onclick = startBot;
$('btn-stop').onclick = stopBot;
$('btn-save').onclick = saveConfig;
$('btn-refresh-log').onclick = loadLog;
$('btn-clear-local').onclick = clearLocalConfig;
</script>
</body>
</html>"""

# ---------------------------------------------------------------------------
# Configuración persistente (config.json) — editable desde el sitio
# ---------------------------------------------------------------------------
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
    """Prioridad: variable de entorno > config.json > default."""
    env_val = os.environ.get(name)
    if env_val is not None and env_val != "":
        return env_val
    return str(PERSISTENT_CFG.get(name, default))


BOT_MODE = _get_env("DERIV_BOT_MODE", "binary").lower()

if BOT_MODE == "multiplier":
    from bot_python.multiplier_bot import (  # noqa: E402
        MultiplierBot as HMAFlowBot,
        state as bot_state,
    )
else:
    from bot_python.bot_1hz50v import (  # noqa: E402
        HMAFlowBot,
        state as bot_state,
    )


def _build_config() -> dict:
    common = {
        "symbol": _get_env("DERIV_SYMBOL", "1HZ50V"),
        "stake": float(_get_env("DERIV_STAKE", "10.0")),
        # Siempre DEMO — no se permite trade real desde el sitio
        "demo": True,
        "hma_period": int(_get_env("DERIV_HMA_PERIOD", "20")),
        "flow_period": int(_get_env("DERIV_FLOW_PERIOD", "14")),
        "flow_smooth": int(_get_env("DERIV_FLOW_SMOOTH", "3")),
        "flow_threshold": float(_get_env("DERIV_FLOW_THRESHOLD", "0.0")),
        "account_id": os.environ.get("DERIV_ACCOUNT_ID", ""),
        "app_id": os.environ.get("DERIV_APP_ID", ""),
        "log_level": os.environ.get("DERIV_LOG_LEVEL", "INFO"),
        "log_file": _get_env(
            "DERIV_LOG_FILE",
            "multiplier_bot.log" if BOT_MODE == "multiplier" else "bot_1hz50v.log",
        ),
        "token": os.environ.get("DERIV_TOKEN", ""),
    }

    if BOT_MODE == "multiplier":
        common.update(
            {
                "multiplier": int(_get_env("DERIV_MULTIPLIER", "100")),
                "tp_pct": float(_get_env("DERIV_TP_PCT", "0.001")),
                "sl_pct": float(_get_env("DERIV_SL_PCT", "0.001")),
            }
        )
    else:
        common.update(
            {
                "duration": int(_get_env("DERIV_DURATION", "1")),
                "duration_unit": _get_env("DERIV_DURATION_UNIT", "m"),
                "martingale_multiplier": float(
                    _get_env("DERIV_MARTINGALE_MULT", "2.4")
                ),
                "max_martingale_steps": int(
                    _get_env("DERIV_MAX_MARTINGALE_STEPS", "999")
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
    yield
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
    version="3.0.0",
    lifespan=lifespan,
)


@app.get("/", response_class=HTMLResponse, tags=["status"])
async def root():
    return DASHBOARD_HTML


@app.get("/dashboard", response_class=HTMLResponse, tags=["status"])
async def dashboard():
    """Panel web para configurar y controlar el bot desde cualquier navegador."""
    return DASHBOARD_HTML


@app.get("/api-root", tags=["status"])
async def api_root():
    return {
        "app": "1HZ50V HMA + Mladen Flow Bot",
        "running": _bot_running,
        "mode": BOT_MODE,
        "trade_mode": "DEMO",
        "configurable_from_web": True,
        "dashboard_url": "/dashboard",
    }


@app.get("/printenv", tags=["status"])
async def print_env():
    """Imprime en el log del servidor las variables de entorno relevantes
    (valores secretos enmascarados) y devuelve un resumen seguro."""
    import os as _os

    secret_keys = {
        "DERIV_TOKEN",
        "DERIV_ACCOUNT_ID",
        "DERIV_APP_ID",
    }

    env_summary = {}
    for key, value in _os.environ.items():
        if key.startswith("DERIV_"):
            if key in secret_keys:
                # Mostrar valor real pero reemplazar los últimos 2 caracteres por "xx"
                if value and len(value) > 2:
                    masked = value[:-2] + "xx"
                else:
                    masked = value
                env_summary[key] = masked
                print(f"[ENV] {key}={masked}")
            else:
                env_summary[key] = value
                print(f"[ENV] {key}={value}")

    print(f"[ENV] Total DERIV_ variables: {len(env_summary)}")
    return {
        "env_count": len(env_summary),
        "env": env_summary,
        "note": "Las variables secretas (DERIV_TOKEN, DERIV_ACCOUNT_ID, DERIV_APP_ID) muestran los últimos 2 caracteres reemplazados por 'xx'.",
    }


@app.get("/health", tags=["status"])
async def health():
    return {"status": "ok", "running": _bot_running, "mode": BOT_MODE}


@app.get("/config", tags=["config"])
async def get_config():
    """Devuelve la configuración actual (sin secretos como el token)."""
    cfg = _build_config()
    return {
        "mode": BOT_MODE,
        "symbol": cfg["symbol"],
        "stake": cfg["stake"],
        "demo": cfg["demo"],
        "account_id": "",
        "app_id": "",
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


@app.post("/config", tags=["config"])
async def set_config(updates: dict):
    """Guarda configuración desde el sitio. Campos permitidos:
    mode, symbol, stake, account_id, app_id, hma_period, flow_period,
    flow_smooth, flow_threshold, duration, duration_unit,
    martingale_multiplier, max_martingale_steps, multiplier, tp_pct, sl_pct.
    """
    global BOT_MODE
    allowed = {
        "mode",
        "symbol",
        "stake",
        "hma_period",
        "flow_period",
        "flow_smooth",
        "flow_threshold",
        "duration",
        "duration_unit",
        "martingale_multiplier",
        "max_martingale_steps",
        "multiplier",
        "tp_pct",
        "sl_pct",
    }

    for key, value in updates.items():
        if key in allowed:
            PERSISTENT_CFG[key] = value

    _save_persistent_config(PERSISTENT_CFG)

    # Si cambió el modo, recargar la clase del bot
    new_mode = str(PERSISTENT_CFG.get("mode", BOT_MODE)).lower()
    if new_mode != BOT_MODE:
        BOT_MODE = new_mode
        if BOT_MODE == "multiplier":
            from bot_python.multiplier_bot import (  # noqa: E402
                MultiplierBot as HMAFlowBot,
                state as bot_state,
            )
        else:
            from bot_python.bot_1hz50v import (  # noqa: E402
                HMAFlowBot,
                state as bot_state,
            )

    return {"status": "saved", "mode": BOT_MODE, "config": await get_config()}


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
        "trade_mode": "DEMO",
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
