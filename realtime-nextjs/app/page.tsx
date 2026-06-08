'use client'

import { PhoneCall } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { CallList } from '@/components/call-list'
import { TranscriptView } from '@/components/transcript-view'
import { Button } from '@/components/ui/button'

export default function Home() {
  const [ids, setIds] = useState<string[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [runningDemo, setRunningDemo] = useState(false)
  const [demoError, setDemoError] = useState<string | null>(null)

  const loadCalls = useCallback((nextSelected?: string) => {
    return fetch('/api/calls')
      .then((r) => (r.ok ? r.json() : { calls: [] }))
      .then((data: { calls: string[] }) => {
        setIds(data.calls)
        setSelected(nextSelected ?? data.calls[0] ?? null)
      })
      .catch(() => {
        setIds([])
        setSelected(null)
      })
  }, [])

  useEffect(() => {
    loadCalls()
  }, [loadCalls])

  const runDemo = async () => {
    setRunningDemo(true)
    setDemoError(null)
    try {
      const res = await fetch('/api/demo-call', { method: 'POST' })
      if (!res.ok) throw new Error(`Demo failed: ${res.status}`)
      const data: { call_id: string } = await res.json()
      await loadCalls(data.call_id)
    } catch (err) {
      setDemoError(err instanceof Error ? err.message : 'Demo failed')
    } finally {
      setRunningDemo(false)
    }
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <aside className="w-64 border-r flex flex-col shrink-0">
        <div className="px-4 py-4 border-b space-y-3">
          <div className="flex items-center justify-between gap-3">
            <h1 className="text-sm font-semibold tracking-wide uppercase text-muted-foreground">
              Calls
            </h1>
            <Button
              size="sm"
              onClick={runDemo}
              disabled={runningDemo}
              title="Run fixture demo"
            >
              <PhoneCall />
              {runningDemo ? 'Running' : 'Run demo'}
            </Button>
          </div>
          {demoError ? (
            <p className="text-xs text-destructive">{demoError}</p>
          ) : null}
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
