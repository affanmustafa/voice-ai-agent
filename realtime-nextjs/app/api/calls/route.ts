import { listCallIds } from '@/lib/calls'

export async function GET() {
  const ids = await listCallIds()
  return Response.json({ calls: ids })
}
