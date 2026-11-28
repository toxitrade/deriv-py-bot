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

async function writeBlob(filename: string, data: any) {
  if (!BLOB_TOKEN) throw new Error('BLOB_READ_WRITE_TOKEN not configured');
  const res = await fetch(`https://blob.vercel-storage.com/${filename}`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${BLOB_TOKEN}`,
      'Content-Type': 'application/json',
      'x-blob-content-type': 'application/json',
      'x-blob-cache-control': '3600',
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Blob write failed: ${res.status}`);
  return await res.json();
}

export async function GET() {
  try {
    const trades = await readBlob(TRADES_BLOB) || [];
    return NextResponse.json({ trades, count: trades.length });
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const newTrade = await req.json();
    const existing = (await readBlob(TRADES_BLOB)) || [];
    const updated = [...existing, newTrade];
    await writeBlob(TRADES_BLOB, updated);
    return NextResponse.json({ success: true, count: updated.length });
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
