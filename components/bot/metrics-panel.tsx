'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useEffect, useState } from 'react';

interface Metrics {
  totalTrades?: number;
  wins?: number;
  losses?: number;
  pending?: number;
  totalPnL?: number;
  winRate?: number;
  winLossRatio?: number;
}

export function MetricsPanel() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const res = await fetch('/api/metrics', { cache: 'no-store' });
        if (!res.ok) throw new Error(`Server responded ${res.status}`);
        const data = await res.json();
        setMetrics(data);
        setError(null);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchMetrics();
    const interval = setInterval(fetchMetrics, 10000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return (
    <Card>
      <CardContent className="pt-4 text-center">
        <p className="text-xs text-muted-foreground">Cargando métricas...</p>
      </CardContent>
    </Card>
  );

  if (error) return (
    <Card>
      <CardContent className="pt-4 text-center">
        <p className="text-xs text-red-500">Error: {error}</p>
      </CardContent>
    </Card>
  );

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">Métricas (Vercel Blob)</CardTitle>
      </CardHeader>
      <CardContent className="pt-4 space-y-2">
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <div className="text-muted-foreground">Trades totales</div>
            <div className="font-bold">{metrics?.totalTrades ?? 0}</div>
          </div>
          <div>
            <div className="text-muted-foreground">Ganados</div>
            <div className="font-bold text-green-500">{metrics?.wins ?? 0}</div>
          </div>
          <div>
            <div className="text-muted-foreground">Perdidos</div>
            <div className="font-bold text-red-500">{metrics?.losses ?? 0}</div>
          </div>
          <div>
            <div className="text-muted-foreground">Pendientes</div>
            <div className="font-bold text-yellow-500">{metrics?.pending ?? 0}</div>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs mt-2">
          <div>
            <div className="text-muted-foreground">PnL total</div>
            <div className={`font-bold ${(metrics?.totalPnL || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              ${metrics?.totalPnL?.toFixed(2) ?? '0.00'}
            </div>
          </div>
          <div>
            <div className="text-muted-foreground">Win rate</div>
            <div className="font-bold">{metrics?.winRate?.toFixed(1) ?? '--'}%</div>
          </div>
          <div>
            <div className="text-muted-foreground">Ratio W/L</div>
            <div className="font-bold">{metrics?.winLossRatio?.toFixed(2) ?? '--'}</div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
