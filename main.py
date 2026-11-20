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
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; background: #0f172a; color: #f1f5f9; }
  .container { max-width: 1200px; margin: 0 auto; padding: 24px; }
  header { background: #1e293b; color: #fff; padding: 16px 24px; border-radius: 8px 8px 0 0; margin-bottom: 20px; border-bottom: 2px solid #334155; }
  header h1 { margin: 0; font-size: 18px; display: flex; align-items: center; gap: 10px; }
  header .badge { font-size: 11px; background: #22c55e; color: #fff; padding: 2px 8px; border-radius: 10px; margin-left: 8px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-bottom: 20px; }
  .card { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
  .card h2 { font-size: 13px; margin: 0 0 12px 0; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; display: flex; align-items: center; gap: 8px; }
  .status { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
  .dot { width: 10px; height: 10px; border-radius: 50%; background: #64748b; }
  .dot.running { background: #22c55e; box-shadow: 0 0 8px #22c55e; }
  .dot.stopped { background: #ef4444; box-shadow: 0 0 8px #ef4444; }
  .big { font-size: 28px; font-weight: 700; margin: 8px 0; }
  .small { font-size: 13px; color: #94a3b8; }
  .btn { background: #334155; color: #fff; border: none; padding: 10px 18px; border-radius: 6px; font-size: 14px; cursor: pointer; font-weight: 600; margin: 4px 4px 4px 0; transition: background 0.2s; }
  .btn:hover { background: #475569; }
  .btn.start { background: #22c55e; }
  .btn.start:hover { background: #16a34a; }
  .btn.stop { background: #ef4444; }
  .btn.stop:hover { background: #dc2626; }
  .btn.secondary { background: #1e293b; color: #cbd5e1; border: 1px solid #334155; }
  .btn.secondary:hover { background: #334155; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .form-group { margin-bottom: 12px; }
  .form-group label { display: block; font-size: 12px; color: #94a3b8; margin-bottom: 4px; font-weight: 600; }
  .form-group input { width: 100%; padding: 8px 10px; border: 1px solid #334155; border-radius: 6px; font-size: 14px; background: #0f172a; color: #fff; }
  .form-group input:focus { outline: none; border-color: #3b82f6; }
  .form-group select { width: 100%; padding: 8px 10px; border: 1px solid #334155; border-radius: 6px; font-size: 14px; background: #0f172a; color: #fff; }
  .form-group select:focus { outline: none; border-color: #3b82f6; }
  .row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .log { background: #0f172a; color: #cbd5e1; border-radius: 8px; padding: 12px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px; max-height: 400px; overflow-y: auto; margin-top: 12px; border: 1px solid #334155; }
  .log .line { white-space: pre-wrap; margin: 2px 0; }
  .log .error { color: #f87171; }
  .log .info { color: #34d399; }
  .log .warn { color: #fbbf24; }
  .alert { padding: 10px 14px; border-radius: 6px; margin-bottom: 16px; font-size: 13px; }
  .alert.info { background: #1e3a8a; color: #bfdbfe; border-left: 4px solid #3b82f6; }
  .alert.warn { background: #7c2d12; color: #fedaa6; border-left: 4px solid #ea580c; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 12px; border: 1px solid #334155; }
  th { text-align: left; color: #94a3b8; font-size: 11px; text-transform: uppercase; padding: 8px; border-bottom: 1px solid #334155; background: #0f172a; }
  td { padding: 8px; border-bottom: 1px solid #1e293b; }
  tr:nth-child(even) td { background: #0f172a; }
  .win { color: #34d399; font-weight: 700; }
  .lose { color: #f87171; font-weight: 700; }
  .kpi-value { font-size: 20px; font-weight: 700; color: #f1f5f9; }
  .kpi-positive { color: #34d399; }
  .kpi-negative { color: #f87171; }
  .kpi-neutral { color: #94a3b8; }
  .indicators-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 8px; }
  .indicator-card { background: #0f172a; border: 1px solid #334155; border-radius: 6px; padding: 10px; text-align: center; }
  .indicator-label { font-size: 11px; color: #94a3b8; margin-bottom: 4px; text-transform: uppercase; }
  .indicator-value { font-size: 16px; font-weight: 700; font-family: ui-monospace; color: #cbd5e1; }
  .indicator-up { color: #34d399; }
  .indicator-down { color: #f87171; }
  .indicator-neutral { color: #94a3b8; }
  .signal-box { padding: 20px; border-radius: 8px; text-align: center; }
  .hidden { display: none !important; }
  .multiplier-config { background: #0f172a; border: 1px solid #334155; border-radius: 6px; padding: 12px; margin-top: 12px; }
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
      <h2>💰 Saldo</h2>
      <div class="kpi-value kpi-neutral" id="balance-text">$0.00</div>
      <div class="small" id="daily-pnl-text">PnL diario: $0.00</div>
    </div>

    <div class="card">
      <h2>⚙️ Indicadores</h2>
      <div class="indicators-row">
        <div class="indicator-card">
          <div class="indicator-label">Precio</div>
          <div class="indicator-value kpi-neutral" id="price-value">—</div>
        </div>
        <div class="indicator-card">
          <div class="indicator-label">HMA</div>
          <div class="indicator-value indicator-neutral" id="hma-value">—</div>
        </div>
        <div class="indicator-card">
          <div class="indicator-label">Flow</div>
          <div class="indicator-value indicator-neutral" id="flow-value">—</div>
        </div>
        <div class="indicator-card">
          <div class="indicator-label">Dirección</div>
          <div class="indicator-value indicator-neutral" id="direction-value">—</div>
        </div>
        <div class="indicator-card">
          <div class="indicator-label">Martingala</div>
          <div class="indicator-value indicator-neutral" id="martingale-value">0</div>
        </div>
      </div>
    </div>

    <div class="card">
      <h2>Configuración rápida</h2>
      <div class="form-group">
        <label>Modo</label>
        <select id="sel-mode" style="width:100%;padding:8px 10px;border:1px solid #334155;border-radius:6px;font-size:14px;background:#0f172a;color:#fff;">
          <option value="binary">Binary (CALL/PUT)</option>
          <option value="multiplier">Multiplier (leverage)</option>
        </select>
      </div>
      <div class="row">
        <div class="form-group">
          <label>Símbolo</label>
          <select id="sel-symbol" style="width:100%;padding:8px 10px;border:1px solid #334155;border-radius:6px;font-size:14px;background:#0f172a;color:#fff;">
            <option value="1HZ50V">1HZ50V (Volatility 50)</option>
            <option value="R_50">R_50 (Volatility 50 Index)</option>
            <option value="R_100">R_100 (Volatility 100 Index)</option>
            <option value="R_25">R_25 (Volatility 25 Index)</option>
            <option value="R_10">R_10 (Volatility 10 Index)</option>
            <option value="1HZ10V">1HZ10V</option>
            <option value="1HZ100V">1HZ100V</option>
            <option value="1HZ25V">1HZ25V</option>
            <option value="1HZ75V">1HZ75V</option>
          </select>
        </div>
        <div class="form-group">
          <label>Stake (USD)</label>
          <input id="sel-stake" type="number" value="10" step="0.1" />
        </div>
      </div>
      <div class="multiplier-config" id="multiplier-config">
        <div class="row">
          <div class="form-group">
            <label>Multiplicador</label>
            <select id="sel-multiplier" style="width:100%;padding:8px 10px;border:1px solid #334155;border-radius:6px;font-size:14px;background:#0f172a;color:#fff;">
              <option value="10">x10</option>
              <option value="50">x50</option>
              <option value="100" selected>x100</option>
              <option value="200">x200</option>
              <option value="400">x400</option>
              <option value="1000">x1000</option>
            </select>
          </div>
          <div class="form-group">
            <label>Take Profit %</label>
            <input id="sel-tp-pct" type="number" value="0.001" step="0.0001" />
          </div>
          <div class="form-group">
            <label>Stop Loss %</label>
            <input id="sel-sl-pct" type="number" value="0.001" step="0.0001" />
          </div>
        </div>
      </div>
      <button class="btn secondary" id="btn-save">Guardar configuración</button>
      <button class="btn secondary" id="btn-clear-local">Borrar config local</button>
    </div>
  </div>

  <div class="card">
    <h2>Señal actual</h2>
    <div id="signal-box" class="signal-box" style="background:#1e293b; border:1px solid #334155;">
      <div class="small">Esperando datos...</div>
      <div style="font-size:32px; font-weight:800; margin-top:8px;" id="signal-value">—</div>
      <div class="small" id="signal-reason"></div>
    </div>
  </div>

  <div class="card" style="margin-top:20px;">
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

  // Balance y PnL
  const bal = s.balance !== undefined ? s.balance : 0;
  const balEl = $('balance-text');
  balEl.textContent = '$' + bal.toFixed(2);
  balEl.className = 'kpi-value ' + (bal >= 0 ? 'kpi-positive' : 'kpi-negative');
  const dp = s.daily_pnl !== undefined ? s.daily_pnl : 0;
  const dpEl = $('daily-pnl-text');
  dpEl.textContent = 'PnL diario: $' + dp.toFixed(2) + ' (' + (dp >= 0 ? '+' : '') + dp.toFixed(2) + ')';
  dpEl.className = 'small ' + (dp >= 0 ? 'kpi-positive' : dp < 0 ? 'kpi-negative' : 'kpi-neutral');

  // Indicadores (solo valores, sin debug)
  const priceEl = $('price-value');
  if (s.last_price !== undefined && s.last_price !== null){
    priceEl.textContent = s.last_price.toFixed(4);
  } else {
    priceEl.textContent = '—';
  }

  const hmaEl = $('hma-value');
  if (s.last_hma !== undefined && s.last_hma !== null){
    hmaEl.textContent = s.last_hma.toFixed(4);
  } else {
    hmaEl.textContent = '—';
  }

  const flowEl = $('flow-value');
  if (s.last_flow !== undefined && s.last_flow !== null){
    flowEl.textContent = s.last_flow.toFixed(4);
  } else {
    flowEl.textContent = '—';
  }

  const dirEl = $('direction-value');
  if (s.last_direction !== undefined && s.last_direction !== null){
    dirEl.textContent = s.last_direction === 1 ? '▲' : s.last_direction === -1 ? '▼' : '—';
  } else {
    dirEl.textContent = '—';
  }

  const martEl = $('martingale-value');
  if (s.martingale_step !== undefined){
    martEl.textContent = s.martingale_step;
  } else {
    martEl.textContent = '0';
  }

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
      const pnlCls = t.win ? 'win' : (t.pnl !== null && t.pnl < 0 ? 'lose' : '');
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${formatTime(t.entry_time)}</td>
                      <td>${t.side}</td>
                      <td>${t.entry_price !== null ? t.entry_price.toFixed(4) : '-'}</td>
                      <td>${t.exit_price !== null ? t.exit_price.toFixed(4) : '-'}</td>
                      <td>${t.stake !== null ? t.stake.toFixed(2) : '-'}</td>
                      <td class="${pnlCls}">${pnl}</td>
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
    box.style.background = '#1e293b';
    box.style.borderColor = '#334155';
    val.textContent = '—';
    val.style.color = '#94a3b8';
    reason.textContent = s.message || 'Esperando señal...';
    reason.style.color = '#94a3b8';
  } else {
    const isCall = s.signal === 'call';
    box.style.background = isCall ? '#064e3b' : '#450a0a';
    box.style.borderColor = isCall ? '#34d399' : '#f87171';
    val.textContent = s.signal.toUpperCase();
    val.style.color = isCall ? '#34d399' : '#f87171';
    const dirLabel = s.last_direction === 1 ? 'HMA alcista' : s.last_direction === -1 ? 'HMA bajista' : 'HMA neutro';
    reason.textContent = (s.position ? 'Posición: ' + s.position.toUpperCase() + ' · ' : '') + dirLabel + ' · HMA: ' + (s.last_hma !== undefined ? s.last_hma.toFixed(4) : '—') + ' · Flow: ' + (s.last_flow !== undefined ? s.last_flow.toFixed(4) : '—') + ' · Saldo: $' + (s.balance !== undefined ? s.balance.toFixed(2) : '0.00');
    reason.style.color = '#cbd5e1';
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
  const saved = localStorage.getItem('bot_config');
  if (saved){
    try{
      const c = JSON.parse(saved);
      $('sel-mode').value = c.mode || 'binary';
      $('sel-symbol').value = c.symbol || '1HZ50V';
      $('sel-stake').value = c.stake || 10;
      if (c.multiplier !== undefined) $('sel-multiplier').value = c.multiplier;
      if (c.tp_pct !== undefined) $('sel-tp-pct').value = c.tp_pct;
      if (c.sl_pct !== undefined) $('sel-sl-pct').value = c.sl_pct;
      $('mode-badge').textContent = (c.mode === 'multiplier' ? 'Multiplier' : 'Binary');
      toggleMultiplierConfig(c.mode);
      setAlert('Configuración cargada desde tu navegador (localStorage)');
      return;
    }catch(e){}
  }
  const c = await api('/config');
  $('sel-mode').value = c.mode || 'binary';
  $('sel-symbol').value = c.symbol || '1HZ50V';
  $('sel-stake').value = c.stake || 10;
  if (c.multiplier !== undefined) $('sel-multiplier').value = c.multiplier;
  if (c.tp_pct !== undefined) $('sel-tp-pct').value = c.tp_pct;
  if (c.sl_pct !== undefined) $('sel-sl-pct').value = c.sl_pct;
  $('mode-badge').textContent = (c.mode === 'multiplier' ? 'Multiplier' : 'Binary');
  toggleMultiplierConfig(c.mode);
}

function toggleMultiplierConfig(mode){
  const config = $('multiplier-config');
  if (mode === 'multiplier'){
    config.classList.remove('hidden');
  } else {
    config.classList.add('hidden');
  }
}

async function saveConfig(){
  const payload = {
    mode: $('sel-mode').value,
    symbol: $('sel-symbol').value,
    stake: parseFloat($('sel-stake').value) || 10,
  };
  if ($('sel-mode').value === 'multiplier'){
    payload.multiplier = parseInt($('sel-multiplier').value) || 100;
    payload.tp_pct = parseFloat($('sel-tp-pct').value) || 0.001;
    payload.sl_pct = parseFloat($('sel-sl-pct').value) || 0.001;
  } else {
    payload.duration = 1;
    payload.duration_unit = 'm';
    payload.martingale_multiplier = parseFloat($('sel-martingale-mult').value) || 2.4;
    payload.max_martingale_steps = parseInt($('sel-max-martingale').value) || 10;
  }
  await api('/config', 'POST', payload);
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

$('sel-mode').addEventListener('change', function(){
  toggleMultiplierConfig(this.value);
  toggleBinaryConfig(this.value);
});

function toggleBinaryConfig(mode){
  const config = $('binary-config');
  if (mode === 'binary'){
    config.classList.remove('hidden');
  } else {
    config.classList.add('hidden');
  }
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
    """Prioridad: config.json (guardado desde sitio) > variable de entorno > default."""
    # Primero verificar config.json (lo que el usuario guarda desde el sitio)
    if name in PERSISTENT_CFG and PERSISTENT_CFG[name] not in (None, ""):
        return str(PERSISTENT_CFG[name])
    # Luego variable de entorno
    env_val = os.environ.get(name)
    if env_val is not None and env_val != "":
        return env_val
    return default


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
        "hma_period": int(_get_env("DERIV_HMA_PERIOD", "30")),
        "flow_period": int(_get_env("DERIV_FLOW_PERIOD", "14")),
        "flow_smooth": int(_get_env("DERIV_FLOW_SMOOTH", "3")),
        "flow_threshold": float(_get_env("DERIV_FLOW_THRESHOLD", "0.3")),
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
                    _get_env("DERIV_MAX_MARTINGALE_STEPS", "10")
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

    # Mapear claves del frontend a claves de entorno
    key_map = {
        "mode": "DERIV_BOT_MODE",
        "symbol": "DERIV_SYMBOL",
        "stake": "DERIV_STAKE",
        "account_id": "DERIV_ACCOUNT_ID",
        "app_id": "DERIV_APP_ID",
        "hma_period": "DERIV_HMA_PERIOD",
        "flow_period": "DERIV_FLOW_PERIOD",
        "flow_smooth": "DERIV_FLOW_SMOOTH",
        "flow_threshold": "DERIV_FLOW_THRESHOLD",
        "duration": "DERIV_DURATION",
        "duration_unit": "DERIV_DURATION_UNIT",
        "martingale_multiplier": "DERIV_MARTINGALE_MULT",
        "max_martingale_steps": "DERIV_MAX_MARTINGALE_STEPS",
        "multiplier": "DERIV_MULTIPLIER",
        "tp_pct": "DERIV_TP_PCT",
        "sl_pct": "DERIV_SL_PCT",
    }

    for key, value in updates.items():
        if key in allowed:
            env_key = key_map.get(key, key)
            PERSISTENT_CFG[env_key] = value

    _save_persistent_config(PERSISTENT_CFG)

    # Recargar configuración en el bot si está corriendo
    global _bot_task, _bot_running, _bot
    if _bot is not None and hasattr(_bot, 'reload_config'):
        _bot.reload_config()

    # Si cambió el modo, reiniciar el bot completamente
    new_mode = str(PERSISTENT_CFG.get("DERIV_BOT_MODE", BOT_MODE)).lower()
    if new_mode != BOT_MODE:
        BOT_MODE = new_mode
        # Guardar estado de running antes de cancelar
        was_running = _bot_running
        # Reiniciar bot task si está corriendo
        if _bot_task and not _bot_task.done():
            _bot_running = False
            _bot_task.cancel()
            try:
                await _bot_task
            except asyncio.CancelledError:
                pass
        # Recargar la clase del bot
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
        # Reiniciar bot automáticamente si estaba corriendo
        if was_running:
            _bot_task = asyncio.create_task(_run_bot_loop())

    return {"status": "saved", "mode": BOT_MODE, "config": await get_config()}


@app.get("/status", tags=["status"])
async def status():
    # Usar _bot_running (consistente con /health)
    try:
        if not _bot_running:
            return {
                "running": False,
                "message": "Bot no iniciado",
                "mode": BOT_MODE,
            }

        trades = []
        try:
            for t in bot_state.trades:
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
            "symbol": getattr(bot_state, 'current_symbol', ''),
            "position": getattr(bot_state, 'position', None),
            "open_side": getattr(bot_state, 'open_side', None),
            "open_entry_price": getattr(bot_state, 'open_entry_price', None),
            "trades_today": getattr(bot_state, 'trades_today', 0),
            "ticks_received": getattr(bot_state, 'ticks_received', 0),
            "balance": getattr(bot_state, 'balance', 0),
            "daily_pnl": getattr(bot_state, 'daily_pnl', 0),
            "last_price": getattr(bot_state, 'last_price', None),
            "last_hma": getattr(bot_state, 'last_hma', None),
            "last_flow": getattr(bot_state, 'last_flow', None),
            "last_direction": getattr(bot_state, 'last_direction', None),
            "trades": trades,
        }

        if BOT_MODE == "binary":
            base.update(
                {
                    "martingale_step": getattr(bot_state, 'martingale_step', 0),
                    "daily_pnl": getattr(bot_state, 'daily_pnl', 0),
                }
            )
        else:
            base.update(
                {
                    "multiplier": getattr(bot_state, 'multiplier', 0),
                    "daily_pnl": getattr(bot_state, 'daily_pnl', 0),
                }
            )

        return base
    except Exception as e:
        return {
            "running": False,
            "message": f"Error: {str(e)}",
            "mode": BOT_MODE,
        }


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
    _bot_running = False
    if _bot_task and not _bot_task.done():
        _bot_task.cancel()
        try:
            await _bot_task
        except asyncio.CancelledError:
            pass
    _bot_task = None
    _bot = None
    return {"status": "stopped", "mode": BOT_MODE}


@app.get("/signals", tags=["status"])
async def signals():
    if not bot_state.trades:
        return {"signal": None, "message": "Sin trades aún", "mode": BOT_MODE}
    last = bot_state.trades[-1]
    return {
        "signal": last.side.lower(),
        "side": last.side,
        "symbol": bot_state.current_symbol,
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
