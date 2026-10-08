import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import type { ChatResults } from './types'

// The latest product matches surfaced by the chat agent. Shared so the chat bubble and
// the on-page "Chat picks" strip show the same cards, and kept in sessionStorage so the
// strip survives clicking into a product page and pressing Back or reloading.

export interface ShownResults extends ChatResults {
  id: number // bumps on every new result set, so listeners can react
}

interface ChatResultsState {
  results: ShownResults | null
  show: (r: ChatResults) => void
  clear: () => void
}

const KEY = 'cc.chatResults'
const Ctx = createContext<ChatResultsState | null>(null)

function load(): ShownResults | null {
  try {
    const raw = sessionStorage.getItem(KEY)
    return raw ? (JSON.parse(raw) as ShownResults) : null
  } catch {
    return null
  }
}

export function ChatResultsProvider({ children }: { children: ReactNode }) {
  const [results, setResults] = useState<ShownResults | null>(load)

  useEffect(() => {
    if (results) sessionStorage.setItem(KEY, JSON.stringify(results))
    else sessionStorage.removeItem(KEY)
  }, [results])

  const show = useCallback((r: ChatResults) => setResults({ ...r, id: Date.now() }), [])
  const clear = useCallback(() => setResults(null), [])

  return <Ctx.Provider value={{ results, show, clear }}>{children}</Ctx.Provider>
}

export function useChatResults() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useChatResults must be used inside <ChatResultsProvider>')
  return ctx
}
