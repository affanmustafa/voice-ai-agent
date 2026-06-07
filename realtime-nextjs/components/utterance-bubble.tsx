'use client'

import type { Utterance } from '@/lib/calls'

export function formatMs(ms: number): string {
  const totalSec = ms / 1000
  const m = Math.floor(totalSec / 60)
  const s = (totalSec % 60).toFixed(1).padStart(4, '0')
  return `${m}:${s}`
}

export function UtteranceBubble({ utterance }: { utterance: Utterance }) {
  const isUser = utterance.speaker === 'user'
  const isInterrupted = utterance.interrupted === true
  const durationMs = Math.max(0, utterance.end_ms - utterance.start_ms)

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
              cut off at {formatMs(utterance.end_ms)}
            </span>
          </div>
        )}
      </div>
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
      </div>
    </div>
  )
}
