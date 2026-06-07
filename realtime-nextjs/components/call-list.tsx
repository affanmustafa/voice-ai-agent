'use client'

import { formatCallId } from '@/lib/calls'

interface CallListProps {
  ids: string[]
  selected: string | null
  onSelect: (id: string) => void
}

export function CallList({ ids, selected, onSelect }: CallListProps) {
  if (ids.length === 0) {
    return (
      <div className="px-4 py-6 text-sm text-muted-foreground text-center">
        No calls yet.
      </div>
    )
  }

  return (
    <ul className="flex flex-col gap-1 p-2">
      {ids.map((id) => (
        <li key={id}>
          <button
            onClick={() => onSelect(id)}
            className={[
              'w-full text-left px-3 py-2 rounded-lg text-sm truncate transition-colors',
              selected === id
                ? 'bg-accent text-accent-foreground font-medium'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground',
            ].join(' ')}
          >
            {formatCallId(id)}
          </button>
        </li>
      ))}
    </ul>
  )
}
