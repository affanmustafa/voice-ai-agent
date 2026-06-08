'use client'

import { useEffect, useState } from 'react'
import { Separator } from '@/components/ui/separator'
import { UtteranceBubble } from './utterance-bubble'
import { formatCallId } from '@/lib/calls'
import type { Call } from '@/lib/calls'

function LatencyPill({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="flex flex-col items-center gap-0.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-sm font-medium tabular-nums">
        {value != null ? `${value}ms` : '—'}
      </span>
    </div>
  )
}

export function TranscriptView({ callId }: { callId: string }) {
  const [loadedCall, setLoadedCall] = useState<{
    callId: string
    call: Call | null
  } | null>(null)

  useEffect(() => {
    const controller = new AbortController()

    fetch(`/api/calls/${encodeURIComponent(callId)}`, {
      signal: controller.signal,
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data: Call | null) => setLoadedCall({ callId, call: data }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return
        }
        setLoadedCall({ callId, call: null })
      })

    return () => controller.abort()
  }, [callId])

  const call = loadedCall?.callId === callId ? loadedCall.call : null
  const loading = loadedCall?.callId !== callId

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
        Loading…
      </div>
    )
  }

  if (!call) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
        Call not found.
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-6 py-4 border-b">
        <h2 className="text-sm font-semibold">{formatCallId(call.call_id)}</h2>
        <p className="text-xs text-muted-foreground font-mono">{call.call_id}</p>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4 flex flex-col gap-4">
        {call.utterances.map((u, i) => {
          const previous = call.utterances[i - 1]
          const next = call.utterances[i + 1]
          const overlapMs = previous ? Math.max(0, previous.end_ms - u.start_ms) : 0
          const overlappedByNextMs = next ? Math.max(0, u.end_ms - next.start_ms) : 0

          return (
            <UtteranceBubble
              key={`${u.speaker}-${u.start_ms}-${i}`}
              utterance={u}
              overlapMs={overlapMs}
              previousSpeaker={previous?.speaker}
              overlappedByNextMs={overlappedByNextMs}
            />
          )
        })}
      </div>

      <div className="border-t px-6 py-4">
        <p className="text-xs text-muted-foreground mb-3 font-medium uppercase tracking-wide">
          Latency (first turn)
        </p>
        <Separator className="mb-3" />
        <div className="flex gap-6 flex-wrap">
          <LatencyPill label="Voice-to-voice" value={call.metrics.voice_to_voice_ms} />
          <LatencyPill label="STT" value={call.metrics.stt_first_final_ms} />
          <LatencyPill label="LLM first token" value={call.metrics.llm_first_token_ms} />
          <LatencyPill label="TTS first byte" value={call.metrics.tts_first_byte_ms} />
        </div>
      </div>
    </div>
  )
}
