import type { NextRequest } from 'next/server'
import { getCall } from '@/lib/calls'

export async function GET(_req: NextRequest, ctx: RouteContext<'/api/calls/[id]'>) {
  const { id } = await ctx.params
  const call = await getCall(id)
  if (!call) {
    return Response.json({ error: 'Not found' }, { status: 404 })
  }
  return Response.json(call)
}
