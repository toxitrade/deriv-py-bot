'use client';

import { useState, useEffect, useCallback } from 'react';

export interface BotStatus {
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

export function useBotStatus() {
  const [status, setStatus] = useState<BotStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/bot-status', { cache: 'no-store' });
      if (!res.ok) throw new Error(`Render responded ${res.status}`);
      const data = await res.json();
      setStatus(data);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchSignals = useCallback(async () => {
    try {
      const res = await fetch('/api/bot-signals', { cache: 'no-store' });
      if (!res.ok) throw new Error(`Render responded ${res.status}`);
      const data = await res.json();
      setStatus((prev) => ({ ...prev, last_signal: data }));
    } catch (err: any) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    fetchSignals();
    const interval = setInterval(() => {
      fetchStatus();
      fetchSignals();
    }, 10000);
    return () => clearInterval(interval);
  }, [fetchStatus, fetchSignals]);

  return { status, loading, error };
}
