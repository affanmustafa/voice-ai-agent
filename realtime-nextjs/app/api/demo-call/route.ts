import { runDemoCall } from '@/lib/calls'

export async function POST() {
  const callId = await runDemoCall()
  return Response.json({ call_id: callId })
}
