'use client'

import type { LatencyEvent, ToolCall, Utterance } from '@/lib/calls'

export function formatMs(ms: number): string {
  const totalSec = ms / 1000
  const m = Math.floor(totalSec / 60)
  const s = (totalSec % 60).toFixed(1).padStart(4, '0')
  return `${m}:${s}`
}

interface UtteranceBubbleProps {
  utterance: Utterance
  overlapMs: number
  previousSpeaker?: Utterance['speaker']
  overlappedByNextMs: number
  toolCalls?: ToolCall[]
  voiceToVoiceMs?: number
  latencyEvent?: LatencyEvent
}

export function UtteranceBubble({
  utterance,
  overlapMs,
  previousSpeaker,
  overlappedByNextMs,
  toolCalls = [],
  voiceToVoiceMs,
  latencyEvent,
}: UtteranceBubbleProps) {
  const isUser = utterance.speaker === 'user'
  const isInterrupted = utterance.interrupted === true
  const durationMs = Math.max(0, utterance.end_ms - utterance.start_ms)
  const isBargeIn = isUser && previousSpeaker === 'agent' && overlapMs > 0

  return (
    <div className={`flex flex-col gap-1.5 ${isUser ? 'items-end' : 'items-start'}`}>
      <div
        className={[
          'max-w-[76%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm',
          isUser
            ? 'bg-primary text-primary-foreground rounded-br-sm'
            : 'bg-muted text-foreground rounded-bl-sm',
          isInterrupted ? 'border-l-4 border-amber-500' : '',
        ]
          .filter(Boolean)
          .join(' ')}
      >
        <p>{utterance.text}</p>
        {isInterrupted && (
          <div className="mt-2 border-t border-amber-300/70 pt-2">
            <span className="text-xs font-medium text-amber-700">
              Interrupted at {formatMs(utterance.end_ms)}
              {overlappedByNextMs > 0 ? ` · user overlapped ${overlappedByNextMs} ms` : ''}
            </span>
          </div>
        )}
      </div>
      {toolCalls.length > 0 && (
        <div className="max-w-[76%] w-full flex flex-col gap-1.5">
          {toolCalls.map((tc, idx) => {
            const query =
              typeof tc.arguments?.query === 'string' ? tc.arguments.query : ''
            return (
              <div
                key={`${tc.name}-${idx}`}
                className="rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-xs"
              >
                <div className="flex items-center gap-1.5 text-violet-700">
                  <span className="font-mono font-semibold">{tc.name}</span>
                  {query && (
                    <span className="font-mono text-violet-500">
                      ({JSON.stringify(query)})
                    </span>
                  )}
                </div>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {tc.result.map((item, ri) => (
                    <span
                      key={`${item.name}-${ri}`}
                      className={[
                        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-medium',
                        item.in_stock
                          ? 'bg-emerald-100 text-emerald-800'
                          : 'bg-rose-100 text-rose-800',
                      ].join(' ')}
                    >
                      {item.name} · ${item.price.toFixed(2)}
                      {item.in_stock ? '' : ' · out of stock'}
                    </span>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}
      <div
        className={[
          'flex flex-wrap items-center gap-x-2 gap-y-1 px-1 text-xs text-muted-foreground',
          isUser ? 'justify-end text-right' : 'justify-start',
        ].join(' ')}
      >
        <span className="font-medium text-foreground">{isUser ? 'User' : 'Agent'}</span>
        <span className="font-mono">
          {formatMs(utterance.start_ms)}-{formatMs(utterance.end_ms)}
        </span>
        <span className="font-mono">{durationMs} ms</span>
        {latencyEvent?.stt_first_final_ms != null && (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 font-medium text-slate-700">
            STT: {latencyEvent.stt_first_final_ms} ms
          </span>
        )}
        {latencyEvent?.llm_first_token_ms != null && (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 font-medium text-slate-700">
            LLM: {latencyEvent.llm_first_token_ms} ms
          </span>
        )}
        {latencyEvent?.tts_first_byte_ms != null && (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 font-medium text-slate-700">
            TTS: {latencyEvent.tts_first_byte_ms} ms
          </span>
        )}
        {voiceToVoiceMs != null && (
          <span className="rounded-full bg-sky-100 px-2 py-0.5 font-medium text-sky-800">
            voice-to-voice: {voiceToVoiceMs} ms
          </span>
        )}
        {isBargeIn && (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-800">
            Barge-in: {overlapMs} ms overlap
          </span>
        )}
      </div>
    </div>
  )
}
