import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function GET(request) {
  const forwarded = request.headers.get('x-forwarded-for');
  const real = request.headers.get('x-real-ip');
  const candidate = (forwarded || real || '').split(',')[0].trim();
  const host = request.headers.get('host') || '';

  return NextResponse.json({
    clientIp: candidate || null,
    frontendHost: host,
    note: 'On a NetworkStream downstream, this is the client address seen by the local gateway frontend.'
  }, { headers: { 'Cache-Control': 'no-store' } });
}
