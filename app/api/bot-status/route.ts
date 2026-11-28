import { NextResponse } from 'next/server';

const RENDER_URL = process.env.NEXT_PUBLIC_API_URL || 'https://deriv-py-bot.onrender.com';

export async function GET() {
  try {
    const res = await fetch(`${RENDER_URL}/status`, { cache: 'no-store' });
    if (!res.ok) throw new Error(`Render responded ${res.status}`);
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json({ error: 'Failed to reach Render backend' }, { status: 502 });
  }
}