'use client';

import { useEffect, useState } from 'react';

interface BotStatus {
  bot_running?: boolean;
  current_symbol?: string;
  balance?: number;
  daily_pnl?: number;
  session_start_balance?: number;
  last_signal?: {
    side?: string;
    price?: number;
    hma?: number;
    timestamp?: string;
  };
  error?: string;
}

export default function BotStatusPage() {
  const [status, setStatus] = useState<BotStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = async () => {
    try {
      const res = await fetch('/api/bot-status', { cache: 'no-store' });
      if (!res.ok) throw new Error(`Render responded ${res.status}`);
      const data = await res.json();
      setStatus(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return (
    <div className="p-4 text-center">
      <p>Cargando estado del bot...</p>
    </div>
  );

  if (error) return (
    <div className="p-4 text-red-500 text-center">
      <p>Error: {error}</p>
      <button onClick={fetchStatus} className="mt-2 px-4 py-2 bg-blue-600 text-white rounded">
        Reintentar
      </button>
    </div>
  );

  return (
    <div className="p-4 max-w-md mx-auto">
      <h1 className="text-xl font-bold mb-4">Estado del Bot</h1>

      <div className="bg-gray-50 p-4 rounded-lg mb-4">
        <p><strong>Ejecutándose:</strong> {status.bot_running ? 'Sí' : 'No'}</p>
        <p><strong>Símbolo:</strong> {status.current_symbol || 'N/A'}</p>
        <p><strong>Balance:</strong> {status.balance !== undefined ? `$${status.balance.toFixed(2)}` : 'N/A'}</p>
        <p><strong>PnL diario:</strong> {status.daily_pnl !== undefined ? `$${status.daily_pnl.toFixed(2)}` : 'N/A'}</p>
        <p><strong>Balance inicial:</strong> {status.session_start_balance !== undefined ? `$${status.session_start_balance.toFixed(2)}` : 'N/A'}</p>
      </div>

      <div className="bg-blue-50 p-4 rounded-lg">
        <h2 className="text-lg font-bold mb-2">Última señal</h2>
        {status.last_signal ? (
          <div className="space-y-1">
            <p><strong>Tipo:</strong> {status.last_signal.side || 'N/A'}</p>
            <p><strong>Precio:</strong> {status.last_signal.price !== undefined ? status.last_signal.price.toFixed(2) : 'N/A'}</p>
            <p><strong>HMA:</strong> {status.last_signal.hma !== undefined ? status.last_signal.hma.toFixed(2) : 'N/A'}</p>
            <p><strong>Hora:</strong> {status.last_signal.timestamp || 'N/A'}</p>
          </div>
        ) : (
          <p>Sin señales recientes</p>
        )}
      </div>

      <div className="mt-4 text-xs text-gray-500">
        <p>Datos desde Render: {status.error || 'OK'}</p>
      </div>
    </div>
  );
}
