'use client';

import { useState, useEffect, useCallback } from 'react';

const RENDER_API = 'https://deriv-py-bot.onrender.com';

export default function DashboardPage() {
  const [status, setStatus] = useState<any>(null);
  const [metrics, setMetrics] = useState<any>(null);
  const [trades, setTrades] = useState<any[]>([]);
  const [config, setConfig] = useState<any>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [darkMode, setDarkMode] = useState(true);
  const [alert, setAlert] = useState<{ msg: string; type: string } | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem('deriv_bot_theme');
    const initial = saved ? saved === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
    setDarkMode(initial);
    document.documentElement.classList.toggle('dark', initial);
    document.documentElement.classList.toggle('light', !initial);
  }, []);

  useEffect(() => {
    localStorage.setItem('deriv_bot_theme', darkMode ? 'dark' : 'light');
    document.documentElement.classList.toggle('dark', darkMode);
    document.documentElement.classList.toggle('light', !darkMode);
  }, [darkMode]);

  const fetchApi = useCallback(async (path: string) => {
    const res = await fetch(`${RENDER_API}${path}`, { cache: 'no-store', mode: 'cors' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  }, []);

  const loadAll = useCallback(async () => {
    try {
      const [s, m] = await Promise.all([
        fetchApi('/status'),
        fetchApi('/signals'),
      ]);
      setStatus(s);
      setMetrics(m);
      // trades desde signals o status
      if (s.trades) setTrades(Array.isArray(s.trades) ? s.trades : []);
      if (m.trades) setTrades(Array.isArray(m.trades) ? m.trades : []);
    } catch (e: any) {
      setAlert({ msg: `Error cargando: ${e.message}`, type: 'error' });
    }
  }, [fetchApi]);

  useEffect(() => {
    loadAll();
    const iv = setInterval(loadAll, 10000);
    return () => clearInterval(iv);
  }, [loadAll]);

  const startStop = async (action: 'start' | 'stop') => {
    try {
      const res = await fetch(`${RENDER_API}/${action}`, { method: 'POST' });
      const data = await res.json();
      setAlert({ msg: data.status || action, type: 'success' });
      await loadAll();
    } catch (e: any) {
      setAlert({ msg: `Error ${action}: ${e.message}`, type: 'error' });
    }
  };

  const pnlColor = (v: number) => (v >= 0 ? 'text-green-400' : 'text-red-400');
  const fmt = (ts?: string) => {
    if (!ts) return '-';
    try { return new Date(ts).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' }); } catch { return ts; }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 font-sys text-sm antialiased transition-colors duration-300 overflow-y-auto">
      <header className="bg-gray-800 border-b border-gray-700 p-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3 sticky top-0 z-50">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-gradient-to-br from-green-500 to-emerald-700 flex items-center justify-center">
            <span className="text-xs font-bold text-white">B</span>
          </div>
          <h1 className="text-lg font-bold tracking-tight">Deriv Bot</h1>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setDarkMode(!darkMode)}
            className="p-2 rounded bg-gray-700 hover:bg-gray-600 text-gray-300"
            title={darkMode ? 'Modo claro' : 'Modo oscuro'}
          >
            {darkMode ? '☀️' : '🌙'}
          </button>
          <div className="flex gap-2">
            <button
              onClick={() => startStop('start')}
              disabled={status?.bot_running}
              className={`px-4 py-2 rounded-lg font-semibold ${status?.bot_running ? 'bg-gray-600 text-gray-300 cursor-not-allowed' : 'bg-green-600 text-white hover:bg-green-500'}`}
            >
              Iniciar
            </button>
            <button
              onClick={() => startStop('stop')}
              disabled={!status?.bot_running}
              className={`px-4 py-2 rounded-lg font-semibold ${!status?.bot_running ? 'bg-gray-600 text-gray-300 cursor-not-allowed' : 'bg-red-600 text-white hover:bg-red-500'}`}
            >
              Detener
            </button>
          </div>
        </div>
      </header>

      {alert && (
        <div className="mx-4 mb-3 p-3 rounded-lg border flex items-center gap-2 text-sm ${
          alert.type === 'success' ? 'bg-green-500/10 border-green-500/50 text-green-400' : 'bg-red-500/10 border-red-500/50 text-red-400'
        }}">
          {alert.msg}
        </div>
      )}

      <main className="mx-4 pb-6 space-y-5 min-h-[calc(100vh-200px)]">
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
              <div className="text-xs text-gray-400">Balance</div>
              <div className={`font-bold ${pnlColor(status?.balance || 0)}`}>${status?.balance?.toFixed(2) ?? '0.00'}</div>
            </div>
            <div className="bg-gray-700/50 rounded p-3">
              <div className="text-xs text-gray-400">PnL Diario</div>
              <div className={`font-bold ${pnlColor(status?.daily_pnl || 0)}`}>${status?.daily_pnl?.toFixed(2) ?? '0.00'}</div>
            </div>
          </div>
        </section>

        <section className="bg-gray-800 border border-gray-700 rounded-xl p-4">
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
              <div className="font-bold text-gray-200">{status?.last_signal?.price !== undefined ? status.last_signal.price.toFixed(2) : 'N/A'}</div>
            </div>
            <div>
              <div className="text-xs text-gray-400">HMA</div>
              <div className="font-bold text-gray-200">{status?.last_signal?.hma !== undefined ? status.last_signal.hma.toFixed(2) : 'N/A'}</div>
            </div>
            <div>
              <div className="text-xs text-gray-400">Hora</div>
              <div className="font-bold text-gray-200">{fmt(status?.last_signal?.timestamp)}</div>
            </div>
          </div>
        </section>

        <section className="bg-gray-800 border border-gray-700 rounded-xl p-4">
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
              <div className={`font-bold ${pnlColor(metrics?.totalPnL || 0)}`}>${metrics?.totalPnL?.toFixed(2) ?? '0.00'}</div>
            </div>
            <div className="bg-gray-700/50 rounded p-3">
              <div className="text-xs text-gray-400">Ratio W/L</div>
              <div className="font-bold text-purple-400">{metrics?.winLossRatio?.toFixed(2) ?? '--'}</div>
            </div>
          </div>
        </section>

        <section className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Configuración</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Símbolo</label>
              <input type="text" defaultValue={config?.symbol || '1HZ50V'} className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Stake (USD)</label>
              <input type="number" step="0.01" defaultValue={config?.stake || 0.5} className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">HMA Period</label>
              <input type="number" defaultValue={config?.hma_period || 150} className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Duración (min)</label>
              <input type="number" defaultValue={config?.duration || 1} className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm" />
            </div>
          </div>
        </section>

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
                  <tr><td colSpan="8" className="p-4 text-center text-gray-500">Sin trades</td></tr>
                ) : (
                  trades.map((t: any) => (
                    <tr key={t.contract_id || t.timestamp} className="border-b border-gray-700/50">
                      <td className="p-2 text-gray-300">{t.entry_time || '-'}</td>
                      <td className="p-2 text-gray-300">{t.symbol || 'N/A'}</td>
                      <td className="p-2 text-gray-300 capitalize">{t.side || 'N/A'}</td>
                      <td className="text-right p-2 text-gray-300">{t.entry_price !== undefined ? t.entry_price.toFixed(2) : '-'}</td>
                      <td className="text-right p-2 text-gray-300">{t.exit_price !== undefined ? t.exit_price.toFixed(2) : '-'}</td>
                      <td className="text-right p-2 text-gray-300">{t.stake !== undefined ? t.stake.toFixed(2) : '-'}</td>
                      <td className={`text-right p-2 font-bold ${pnlColor(t.pnl || 0)}`}>{t.pnl !== undefined ? `$${t.pnl.toFixed(2)}` : '-'}</td>
                      <td className="text-center p-2">
                        <span className={`px-2 py-0.5 rounded text-xs font-bold ${t.win ? 'bg-green-500/20 text-green-400' : !t.win && t.win !== null ? 'bg-red-500/20 text-red-400' : 'bg-gray-600 text-gray-400'}`}>
                          {t.win === null ? '--' : t.win ? 'WIN' : 'LOSS'}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <div className="flex justify-between items-center mb-3">
            <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Log del Bot</h2>
          </div>
          <div className="h-48 overflow-y-auto font-mono text-xs bg-gray-950 p-3 rounded border border-gray-700">
            {logs.length === 0 ? <p className="text-gray-500 italic">Sin logs disponibles</p> : logs.map((l, i) => <div key={i} className="mb-1 text-gray-300">{l}</div>)}
          </div>
        </section>
      </main>

      <footer className="mx-4 pt-4 pb-6 border-t border-gray-700 text-center">
        <p className="text-xs text-gray-500">Deriv Bot • Datos en tiempo real desde Render • {new Date().toLocaleTimeString('es-AR')}</p>
      </footer>
    </div>
  );
}
