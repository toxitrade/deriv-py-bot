import { NextResponse } from 'next/server';

const BLOB_TOKEN = process.env.BLOB_READ_WRITE_TOKEN;
const TRADES_BLOB = 'trades.json';

async function readBlob(filename: string) {
  if (!BLOB_TOKEN) return null;
  const res = await fetch(`https://blob.vercel-storage.com/${filename}`, {
    headers: { Authorization: `Bearer ${BLOB_TOKEN}` },
    cache: 'no-store',
  });
  if (!res.ok) return null;
  return await res.json();
}

export async function GET() {
  try {
    const trades = (await readBlob(TRADES_BLOB)) || [];

    const totalTrades = trades.length;
    const wins = trades.filter((t: any) => t.resultado === 'WIN' || t.result === 'WIN').length;
    const losses = trades.filter((t: any) => t.resultado === 'LOSS' || t.result === 'LOSS').length;
    const pending = totalTrades - wins - losses;

    const totalPnL = trades.reduce((acc: number, t: any) => acc + (Number(t.pnl) || 0), 0);
    const winRate = totalTrades > 0 ? (wins / totalTrades) * 100 : 0;
    const winLossRatio = losses > 0 ? wins / losses : wins;

    return NextResponse.json({
      totalTrades,
      wins,
      losses,
      pending,
      totalPnL,
      winRate: Number(winRate.toFixed(2)),
      winLossRatio: Number(winLossRatio.toFixed(2)),
    });
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
