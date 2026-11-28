import { NextResponse } from 'next/server';

const RENDER_URL = 'https://deriv-py-bot.onrender.com/health';

export async function GET() {
  try {
    const res = await fetch(RENDER_URL, { cache: 'no-store' });
    if (!res.ok) throw new Error(`Render responded ${res.status}`);
    const data = await res.json();
    return NextResponse.json({ ok: true, status: res.status, render: data });
  } catch (error: any) {
    return NextResponse.json({ ok: false, error: error.message }, { status: 502 });
  }
}
