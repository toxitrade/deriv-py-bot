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
  contract_type?: string;
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
    } catch (err: any) {
      console.error('Metrics error:', err);
    }
  }, []);

  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch('/api/config', { cache: 'no-store' });
      if (!res.ok) throw new Error(`Config failed ${res.status}`);
      const data = await res.json();
      setConfig(data);
    } catch (err: any) {
      console.error('Config error:', err);
    }
  }, []);

  const fetchTrades = useCallback(async () => {
    try {
      const res = await fetch('/api/trades', { cache: 'no-store' });
      if (!res.ok) throw new Error(`Trades failed ${res.status}`);
      const data = await res.json();
      setTrades((data.trades || []).slice(0, 50));
    } catch (err: any) {
      console.error('Trades error:', err);
    }
  }, []);

  const fetchLogs = useCallback(async () => {
    try {
      const res = await fetch(`${API}/logs`, { cache: 'no-store' });
      if (!res.ok) return;
      const data = await res.json();
      setLogs(data.logs || []);
    } catch {
      // logs endpoint puede no estar disponible desde Vercel
    }
  }, []);

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

  const formatTime = (ts?: string) => {
    if (!ts) return '-';
    try {
      const d = new Date(ts);
      return d.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return ts;
    }
  };

  const formatDate = (ts?: string) => {
    if (!ts) return '-';
    try {
      const d = new Date(ts);
      return d.toLocaleString('es-AR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch {
      return ts;
    }
  };

  const pnlColor = (val: number) => (val >= 0 ? 'text-green-500' : 'text-red-500');

  return (
    <div className="p-4 max-w-5xl mx-auto font-sys text-sm">
      {alert && (
        <div
          className={`p-3 rounded mb-4 ${
            alert.type === 'success'
              ? 'bg-green-50 border border-green-200 text-green-800'
              : alert.type === 'error'
                ? 'bg-red-50 border border-red-200 text-red-800'
                : 'bg-blue-50 border border-blue-200 text-blue-800'
          }`}
        >
          {alert.msg}
        </div>
      )}

      <div className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold">Dashboard del Bot</h1>
        <div className="flex gap-2">
          <button
            onClick={startBot}
            disabled={status?.bot_running}
            className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
          >
            Iniciar Bot
          </button>
          <button
            onClick={stopBot}
            disabled={!status?.bot_running}
            className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
          >
            Detener Bot
          </button>
        </div>
      </div>

      {loading && <p className="text-center text-muted-foreground">Cargando...</p>}

      {!loading && (
        <>
          {/* Estado del bot */}
          <div className="bg-card p-4 rounded-lg border mb-4">
            <h2 className="text-lg font-bold mb-2">Estado del Bot</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-3 rounded bg-muted/50">
                <div className="text-xs text-muted-foreground">Estado</div>
                <div className={`font-bold ${status?.bot_running ? 'text-green-600' : 'text-red-600'}`}>
                  {status?.bot_running ? 'Ejecutándose' : 'Detenido'}
                </div>
              </div>
              <div className="p-3 rounded bg-muted/50">
                <div className="text-xs text-muted-foreground">Símbolo</div>
                <div className="font-bold">{status?.current_symbol || 'N/A'}</div>
              </div>
              <div className="p-3 rounded bg-muted/50">
                <div className="text-xs text-muted-foreground">Modo</div>
                <div className="font-bold">{status?.mode || config?.symbol ? 'binary' : 'N/A'}</div>
              </div>
              <div className="p-3 rounded bg-muted/50">
                <div className="text-xs text-muted-foreground">Balance</div>
                <div className="font-bold">
                  {status?.balance !== undefined ? `$${status.balance.toFixed(2)}` : 'N/A'}
                </div>
              </div>
              <div className="p-3 rounded bg-muted/50">
                <div className="text-xs text-muted-foreground">PnL Diario</div>
                <div className={`font-bold ${pnlColor(status?.daily_pnl || 0)}`}>
                  {status?.daily_pnl !== undefined ? `$${status.daily_pnl.toFixed(2)}` : 'N/A'}
                </div>
              </div>
              <div className="p-3 rounded bg-muted/50">
                <div className="text-xs text-muted-foreground">Balance Inicial</div>
                <div className="font-bold">
                  {status?.session_start_balance !== undefined ? `$${status.session_start_balance.toFixed(2)}` : 'N/A'}
                </div>
              </div>
            </div>
          </div>

          {/* Métricas y Señales */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
            <div className="lg:col-span-2">
              <div className="bg-card p-4 rounded-lg border">
                <h2 className="text-lg font-bold mb-2">Métricas</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                  <div>
                    <div className="text-muted-foreground">Trades Totales</div>
                    <div className="font-bold">{metrics?.totalTrades ?? 0}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Ganados</div>
                    <div className="font-bold text-green-600">{metrics?.wins ?? 0}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Perdidos</div>
                    <div className="font-bold text-red-600">{metrics?.losses ?? 0}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Pendientes</div>
                    <div className="font-bold text-yellow-600">{metrics?.pending ?? 0}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">PnL Total</div>
                    <div className={`font-bold ${pnlColor(metrics?.totalPnL || 0)}`}>
                      ${metrics?.totalPnL?.toFixed(2) ?? '0.00'}
                    </div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Win Rate</div>
                    <div className="font-bold">{metrics?.winRate?.toFixed(1) ?? '--'}%</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Ratio W/L</div>
                    <div className="font-bold">{metrics?.winLossRatio?.toFixed(2) ?? '--'}</div>
                  </div>
                </div>
              </div>

              <div className="bg-card p-4 rounded-lg border mt-4">
                <h2 className="text-lg font-bold mb-2">Última Señal</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                  <div>
                    <div className="text-muted-foreground">Tipo</div>
                    <div className="font-bold">{status?.last_signal?.side || 'N/A'}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Precio</div>
                    <div className="font-bold">
                      {status?.last_signal?.price !== undefined ? status.last_signal.price.toFixed(2) : 'N/A'}
                    </div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">HMA</div>
                    <div className="font-bold">
                      {status?.last_signal?.hma !== undefined ? status.last_signal.hma.toFixed(2) : 'N/A'}
                    </div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Hora</div>
                    <div className="font-bold">{formatTime(status?.last_signal?.timestamp)}</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Configuración */}
            <div className="lg:col-span-1">
              <div className="bg-card p-4 rounded-lg border">
                <h2 className="text-lg font-bold mb-2">Configuración</h2>
                <form onSubmit={saveConfig} className="space-y-3">
                  <div>
                    <label className="block text-xs text-muted-foreground mb-1">Símbolo</label>
                    <input
                      type="text"
                      defaultValue={config?.symbol || '1HZ50V'}
                      onChange={(e) => {
                        if (config) setConfig({ ...config, symbol: e.target.value });
                      }}
                      className="w-full border rounded px-2 py-1 bg-input"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-muted-foreground mb-1">Stake (USD)</label>
                    <input
                      type="number"
                      step="0.01"
                      defaultValue={config?.stake || 0.5}
                      onChange={(e) => {
                        if (config) setConfig({ ...config, stake: parseFloat(e.target.value) || 0 });
                      }}
                      className="w-full border rounded px-2 py-1 bg-input"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-muted-foreground mb-1">HMA Period</label>
                    <input
                      type="number"
                      defaultValue={config?.hma_period || 150}
                      onChange={(e) => {
                        if (config) setConfig({ ...config, hma_period: parseInt(e.target.value) || 150 });
                      }}
                      className="w-full border rounded px-2 py-1 bg-input"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-muted-foreground mb-1">Duración (min)</label>
                    <input
                      type="number"
                      defaultValue={config?.duration || 1}
                      onChange={(e) => {
                        if (config) setConfig({ ...config, duration: parseInt(e.target.value) || 1 });
                      }}
                      className="w-full border rounded px-2 py-1 bg-input"
                    />
                  </div>
                  <button
                    type="submit"
                    className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                  >
                    Guardar Config
                  </button>
                </form>
              </div>
            </div>
          </div>

          {/* Historial de Trades */}
          <div className="bg-card p-4 rounded-lg border mb-4">
            <h2 className="text-lg font-bold mb-2">Historial de Trades</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-muted-foreground border-b">
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
                      <td colSpan="8" className="p-4 text-center text-muted-foreground">
                        Sin trades registrados
                      </td>
                    </tr>
                  ) : (
                    trades.map((t) => (
                      <tr key={t.id || t.timestamp} className="border-b">
                        <td className="p-2">{formatTime(t.timestamp)}</td>
                        <td className="p-2">{t.symbol || 'N/A'}</td>
                        <td className="p-2">{t.side || 'N/A'}</td>
                        <td className="text-right p-2">{t.entry !== undefined ? t.entry.toFixed(2) : '-'}</td>
                        <td className="text-right p-2">{t.exit !== undefined ? t.exit.toFixed(2) : '-'}</td>
                        <td className="text-right p-2">{t.stake !== undefined ? t.stake.toFixed(2) : '-'}</td>
                        <td className={`text-right p-2 font-bold ${pnlColor(t.pnl || 0)}`}>
                          {t.pnl !== undefined ? `$${t.pnl.toFixed(2)}` : '-'}
                        </td>
                        <td className="text-center p-2">
                          {t.resultado || '--'}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Log */}
          <div className="bg-card p-4 rounded-lg border">
            <h2 className="text-lg font-bold mb-2">Log del Bot</h2>
            <div className="h-64 overflow-y-auto font-mono text-xs bg-input p-3 rounded border">
              {logs.length === 0 ? (
                <p className="text-muted-foreground">Sin logs disponibles</p>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className="mb-1">
                    {log}
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
