import { useEffect, useRef, useState } from 'react'
import ChatText from './ChatText'

// Reveals a reply word by word, like the assistant is typing it out, then calls onDone
// (so product cards and quick replies appear after the text). Total time is capped at
// ~1.4s however long the reply is, and it's skipped for reduced-motion users.
const MAX_MS = 1400
const STEP_MS = 28

export default function TypedText({ text, onDone }: { text: string; onDone?: () => void }) {
  const tokens = useRef(text.split(/(\s+)/))
  const reduce = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  const [shown, setShown] = useState(reduce ? tokens.current.length : 0)
  const done = useRef(false)

  useEffect(() => {
    const total = tokens.current.length
    if (shown >= total) {
      if (!done.current) {
        done.current = true
        onDone?.()
      }
      return
    }
    const perTick = Math.max(1, Math.ceil(total / (MAX_MS / STEP_MS)))
    const t = setTimeout(() => setShown((n) => Math.min(total, n + perTick)), STEP_MS)
    return () => clearTimeout(t)
  }, [shown, onDone])

  let partial = tokens.current.slice(0, shown).join('')
  // Close a half-revealed **bold** so it doesn't flash raw asterisks.
  if ((partial.match(/\*\*/g)?.length ?? 0) % 2 === 1) partial += '**'
  return <ChatText text={partial} />
}
