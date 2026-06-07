'use client'

import { useEffect, useState } from 'react'
import { CallList } from '@/components/call-list'
import { TranscriptView } from '@/components/transcript-view'

export default function Home() {
  const [ids, setIds] = useState<string[]>([])
  const [selected, setSelected] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/calls')
      .then((r) => (r.ok ? r.json() : { calls: [] }))
      .then((data: { calls: string[] }) => {
        setIds(data.calls)
        setSelected(data.calls[0] ?? null)
      })
      .catch(() => {
        setIds([])
        setSelected(null)
      })
  }, [])

  return (
    <div className="flex h-screen overflow-hidden">
      <aside className="w-64 border-r flex flex-col shrink-0">
        <div className="px-4 py-4 border-b">
          <h1 className="text-sm font-semibold tracking-wide uppercase text-muted-foreground">
            Calls
          </h1>
        </div>
        <div className="flex-1 overflow-y-auto">
          <CallList ids={ids} selected={selected} onSelect={setSelected} />
        </div>
      </aside>

      <main className="flex-1 flex flex-col overflow-hidden">
        {selected ? (
          <TranscriptView callId={selected} />
        ) : (
          <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
            Select a call to view its transcript.
          </div>
        )}
      </main>
    </div>
  )
}
