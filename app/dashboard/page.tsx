'use client';

import { useState, useEffect, useCallback } from 'react';

interface BotStatus {
  bot_running?: boolean;
  current_symbol?: string;
  balance?: number;
  daily_pnl?: number;
  session_start_balance?: number;
  session_start?: string;
  mode?: string;
  last_signal?: {
    side?: string;
    price?: number;
    hma?: number;
    timestamp?: string;
  };
  error?: string;
}

interface Trade {
  id?: string;
  symbol?: string;
  side?: string;
  entry?: number;
  exit?: number;
  stake?: number;
  pnl?: number;
  resultado?: string;
  timestamp?: string;
}

interface Metrics {
  totalTrades?: number;
  wins?: number;
  losses?: number;
  pending?: number;
  totalPnL?: number;
  winRate?: number;
  winLossRatio?: number;
}

interface Config {
  symbol?: string;
  stake?: number;
  hma_period?: number;
  flow_period?: number;
  flow_smooth?: number;
  flow_threshold?: number;
  duration?: number;
  duration_unit?: string;
  martingale_multiplier?: number;
  max_martingale_steps?: number;
  max_stake?: number;
  cooldown_seconds?: number;
}

export default function DashboardPage() {
  const [status, setStatus] = useState<BotStatus | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [alert, setAlert] = useState<{ msg: string; type: string } | null>(null);
  const [darkMode, setDarkMode] = useState(true);

  const API = '';

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/bot-status', { cache: 'no-store' });
      if (!res.ok) throw new Error(`Render responded ${res.status}`);
      const data = await res.json();
      setStatus(data);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    }
  }, []);

  const fetchMetrics = useCallback(async () => {
    try {
      const res = await fetch('/api/metrics', { cache: 'no-store' });
      if (!res.ok) throw new Error(`Metrics failed ${res.status}`);
      const data = await res.json();
      setMetrics(data);
    } catch {
      // silent
    }
  }, []);

  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch('/api/config', { cache: 'no-store' });
      if (!res.ok) throw new Error(`Config failed ${res.status}`);
      const data = await res.json();
      setConfig(data);
    } catch {
      // silent
    }
  }, []);

  const fetchTrades = useCallback(async () => {
    try {
      const res = await fetch('/api/trades', { cache: 'no-store' });
      if (!res.ok) throw new Error(`Trades failed ${res.status}`);
      const data = await res.json();
      setTrades((data.trades || []).slice(0, 50));
    } catch {
      // silent
    }
  }, []);

  const fetchLogs = useCallback(async () => {
    try {
      const res = await fetch('/logs', { cache: 'no-store' });
      if (!res.ok) return;
      const data = await res.json();
      setLogs(data.logs || []);
    } catch {
      // logs endpoint puede no estar disponible desde Vercel
    }
  }, []);

  useEffect(() => {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    setDarkMode(prefersDark);
    document.documentElement.classList.toggle('dark', prefersDark);
    document.documentElement.classList.toggle('light', !prefersDark);
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode);
    document.documentElement.classList.toggle('light', !darkMode);
  }, [darkMode]);

  useEffect(() => {
    fetchStatus();
    fetchMetrics();
    fetchConfig();
    fetchTrades();
    fetchLogs();
    const interval = setInterval(() => {
      fetchStatus();
      fetchMetrics();
      fetchTrades();
    }, 10000);
    return () => clearInterval(interval);
  }, [fetchStatus, fetchMetrics, fetchConfig, fetchTrades, fetchLogs]);

  const startBot = async () => {
    try {
      const res = await fetch('/start', { method: 'POST' });
      const data = await res.json();
      setAlert({ msg: data.status === 'started' ? 'Bot iniciado' : 'Bot ya estaba corriendo', type: 'success' });
      await fetchStatus();
    } catch (err: any) {
      setAlert({ msg: `Error iniciando bot: ${err.message}`, type: 'error' });
    }
  };

  const stopBot = async () => {
    try {
      const res = await fetch('/stop', { method: 'POST' });
      const data = await res.json();
      setAlert({ msg: 'Bot detenido', type: 'info' });
      await fetchStatus();
    } catch (err: any) {
      setAlert({ msg: `Error deteniendo bot: ${err.message}`, type: 'error' });
    }
  };

  const saveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!config) return;
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      const data = await res.json();
      if (data.success) {
        setAlert({ msg: 'Configuración guardada', type: 'success' });
      } else {
        setAlert({ msg: `Error: ${data.error}`, type: 'error' });
      }
    } catch (err: any) {
      setAlert({ msg: `Error guardando config: ${err.message}`, type: 'error' });
    }
  };

  const toggleTheme = () => {
    setDarkMode(!darkMode);
  };

  const formatTime = (ts?: string) => {
    if (!ts) return '-';
    try {
      const d = new Date(ts);
      return d.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return ts;
    }
  };

  const pnlColor = (val: number) => (val >= 0 ? 'text-green-400' : 'text-red-400');

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 font-sys text-sm antialiased transition-colors duration-300">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 p-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-gradient-to-br from-green-500 to-emerald-700 flex items-center justify-center">
            <span className="text-xs font-bold text-white">B</span>
          </div>
          <h1 className="text-lg font-bold tracking-tight">Deriv Bot</h1>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={toggleTheme}
            className="p-2 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 transition-colors"
            title={darkMode ? 'Modo claro' : 'Modo oscuro'}
          >
            {darkMode ? '☀️' : '🌙'}
          </button>
          <div className="flex gap-2">
            <button
              onClick={startBot}
              disabled={status?.bot_running}
              className={`px-4 py-2 rounded-lg font-semibold transition-all ${
                status?.bot_running
                  ? 'bg-gray-600 text-gray-300 cursor-not-allowed'
                  : 'bg-green-600 text-white hover:bg-green-500'
              }`}
            >
              Iniciar
            </button>
            <button
              onClick={stopBot}
              disabled={!status?.bot_running}
              className={`px-4 py-2 rounded-lg font-semibold transition-all ${
                !status?.bot_running
                  ? 'bg-gray-600 text-gray-300 cursor-not-allowed'
                  : 'bg-red-600 text-white hover:bg-red-500'
              }`}
            >
              Detener
            </button>
          </div>
        </div>
      </header>

      {alert && (
        <div className="mx-4 mb-3 p-3 rounded-lg border text-sm flex items-center gap-2 ${
          alert.type === 'success'
            ? 'bg-green-500/10 border-green-500/50 text-green-400'
            : alert.type === 'error'
              ? 'bg-red-500/10 border-red-500/50 text-red-400'
              : 'bg-blue-500/10 border-blue-500/50 text-blue-400'
        }">
          {alert.msg}
        </div>
      )}

      <main className="mx-4 pb-6 space-y-5">
        {/* Estado */}
        <section className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Estado del Bot</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-gray-700/50 rounded p-3">
              <div className="text-xs text-gray-400">Estado</div>
              <div className={`font-bold ${status?.bot_running ? 'text-green-400' : 'text-red-400'}`}>
                {status?.bot_running ? 'ACTIVO' : 'DETENIDO'}
              </div>
            </div>
            <div className="bg-gray-700/50 rounded p-3">
              <div className="text-xs text-gray-400">Símbolo</div>
              <div className="font-bold text-blue-300">{status?.current_symbol || 'N/A'}</div>
            </div>
            <div className="bg-gray-700/50 rounded p-3">
              <div className="text-xs text-gray-400">Modo</div>
              <div className="font-bold text-purple-300">{status?.mode || 'binary'}</div>
            </div>
            <div className="bg-gray-700/50 rounded p-3">
              <div className="text-xs text-gray-400">Balance</div>
              <div className={`font-bold ${pnlColor(status?.balance || 0)}`}>
                ${status?.balance?.toFixed(2) ?? '0.00'}
              </div>
            </div>
            <div className="bg-gray-700/50 rounded p-3">
              <div className="text-xs text-gray-400">PnL Diario</div>
              <div className={`font-bold ${pnlColor(status?.daily_pnl || 0)}`}>
                ${status?.daily_pnl?.toFixed(2) ?? '0.00'}
              </div>
            </div>
            <div className="bg-gray-700/50 rounded p-3">
              <div className="text-xs text-gray-400">Balance Inicial</div>
              <div className="font-bold text-gray-300">
                ${status?.session_start_balance?.toFixed(2) ?? '0.00'}
              </div>
            </div>
          </div>
        </section>

        {/* Señales y Métricas en stack vertical */}
        <section className="space-y-4">
          {/* Última señal */}
          <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
            <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Última Señal</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div>
                <div className="text-xs text-gray-400">Tipo</div>
                <div className={`font-bold capitalize ${status?.last_signal?.side === 'CALL' ? 'text-blue-400' : 'text-pink-400'}`}>
                  {status?.last_signal?.side || 'N/A'}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-400">Precio</div>
                <div className="font-bold text-gray-200">
                  {status?.last_signal?.price !== undefined ? status.last_signal.price.toFixed(2) : 'N/A'}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-400">HMA</div>
                <div className="font-bold text-gray-200">
                  {status?.last_signal?.hma !== undefined ? status.last_signal.hma.toFixed(2) : 'N/A'}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-400">Hora</div>
                <div className="font-bold text-gray-200">{formatTime(status?.last_signal?.timestamp)}</div>
              </div>
            </div>
          </div>

          {/* Métricas */}
          <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
            <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Métricas</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="bg-gray-700/50 rounded p-3">
                <div className="text-xs text-gray-400">Total Trades</div>
                <div className="font-bold text-blue-300">{metrics?.totalTrades ?? 0}</div>
              </div>
              <div className="bg-gray-700/50 rounded p-3">
                <div className="text-xs text-gray-400">Ganados</div>
                <div className="font-bold text-green-400">{metrics?.wins ?? 0}</div>
              </div>
              <div className="bg-gray-700/50 rounded p-3">
                <div className="text-xs text-gray-400">Perdidos</div>
                <div className="font-bold text-red-400">{metrics?.losses ?? 0}</div>
              </div>
              <div className="bg-gray-700/50 rounded p-3">
                <div className="text-xs text-gray-400">Win Rate</div>
                <div className="font-bold text-yellow-400">{metrics?.winRate?.toFixed(1) ?? '--'}%</div>
              </div>
              <div className="bg-gray-700/50 rounded p-3">
                <div className="text-xs text-gray-400">PnL Total</div>
                <div className={`font-bold ${pnlColor(metrics?.totalPnL || 0)}`}>
                  ${metrics?.totalPnL?.toFixed(2) ?? '0.00'}
                </div>
              </div>
              <div className="bg-gray-700/50 rounded p-3">
                <div className="text-xs text-gray-400">Ratio W/L</div>
                <div className="font-bold text-purple-400">{metrics?.winLossRatio?.toFixed(2) ?? '--'}</div>
              </div>
            </div>
          </div>
        </section>

        {/* Configuración */}
        <section className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Configuración</h2>
          <form onSubmit={saveConfig} className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Símbolo</label>
              <input
                type="text"
                defaultValue={config?.symbol || '1HZ50V'}
                onChange={(e) => {
                  if (config) setConfig({ ...config, symbol: e.target.value });
                }}
                className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm focus:ring-2 focus:ring-green-500 outline-none transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Stake (USD)</label>
              <input
                type="number"
                step="0.01"
                defaultValue={config?.stake || 0.5}
                onChange={(e) => {
                  if (config) setConfig({ ...config, stake: parseFloat(e.target.value) || 0 });
                }}
                className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm focus:ring-2 focus:ring-green-500 outline-none transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">HMA Period</label>
              <input
                type="number"
                defaultValue={config?.hma_period || 150}
                onChange={(e) => {
                  if (config) setConfig({ ...config, hma_period: parseInt(e.target.value) || 150 });
                }}
                className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm focus:ring-2 focus:ring-green-500 outline-none transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Duración (min)</label>
              <input
                type="number"
                defaultValue={config?.duration || 1}
                onChange={(e) => {
                  if (config) setConfig({ ...config, duration: parseInt(e.target.value) || 1 });
                }}
                className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm focus:ring-2 focus:ring-green-500 outline-none transition-colors"
              />
            </div>
            <button
              type="submit"
              className="col-span-1 sm:col-span-2 px-4 py-2 bg-green-600 text-white rounded-lg font-semibold hover:bg-green-500 transition-colors"
            >
              Guardar Configuración
            </button>
          </form>
        </section>

        {/* Historial de Trades */}
        <section className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <div className="flex justify-between items-center mb-3">
            <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Historial de Trades</h2>
            <span className="text-xs text-gray-500">{trades.length} trades</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-400 border-b border-gray-700">
                  <th className="text-left p-2">Hora</th>
                  <th className="text-left p-2">Símbolo</th>
                  <th className="text-left p-2">Tipo</th>
                  <th className="text-right p-2">Entrada</th>
                  <th className="text-right p-2">Salida</th>
                  <th className="text-right p-2">Stake</th>
                  <th className="text-right p-2">PnL</th>
                  <th className="text-center p-2">Resultado</th>
                </tr>
              </thead>
              <tbody>
                {trades.length === 0 ? (
                  <tr>
                    <td colSpan="8" className="p-4 text-center text-gray-500">
                      Sin trades registrados
                    </td>
                  </tr>
                ) : (
                  trades.map((t) => (
                    <tr key={t.id || t.timestamp} className="border-b border-gray-700/50">
                      <td className="p-2 text-gray-300">{formatTime(t.timestamp)}</td>
                      <td className="p-2 text-gray-300">{t.symbol || 'N/A'}</td>
                      <td className="p-2 text-gray-300 capitalize">{t.side || 'N/A'}</td>
                      <td className="text-right p-2 text-gray-300">
                        {t.entry !== undefined ? t.entry.toFixed(2) : '-'}
                      </td>
                      <td className="text-right p-2 text-gray-300">
                        {t.exit !== undefined ? t.exit.toFixed(2) : '-'}
                      </td>
                      <td className="text-right p-2 text-gray-300">
                        {t.stake !== undefined ? t.stake.toFixed(2) : '-'}
                      </td>
                      <td className={`text-right p-2 font-bold ${pnlColor(t.pnl || 0)}`}>
                        {t.pnl !== undefined ? `$${t.pnl.toFixed(2)}` : '-'}
                      </td>
                      <td className="text-center p-2">
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-bold ${
                            t.resultado === 'WIN'
                              ? 'bg-green-500/20 text-green-400'
                              : t.resultado === 'LOSS'
                                ? 'bg-red-500/20 text-red-400'
                                : 'bg-gray-600 text-gray-400'
                          }`}
                        >
                          {t.resultado || '--'}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* Log */}
        <section className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <div className="flex justify-between items-center mb-3">
            <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Log del Bot</h2>
            <button
              onClick={fetchLogs}
              className="text-xs text-green-400 hover:text-green-300 underline"
            >
              Actualizar
            </button>
          </div>
          <div className="h-48 overflow-y-auto font-mono text-xs bg-gray-950 p-3 rounded border border-gray-700">
            {logs.length === 0 ? (
              <p className="text-gray-500 italic">Sin logs disponibles</p>
            ) : (
              logs.map((log, i) => (
                <div key={i} className="mb-1 text-gray-300">
                  {log}
                </div>
              ))
            )}
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="mx-4 pt-4 pb-6 border-t border-gray-700 text-center">
        <p className="text-xs text-gray-500">
          Deriv Bot • Datos en tiempo real desde Render • {new Date().toLocaleTimeString('es-AR')}
        </p>
      </footer>
    </div>
  );
}
