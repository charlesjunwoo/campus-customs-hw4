import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { useLocation } from 'react-router-dom'
import { clearChatHistory, getChatHistory, sendChat } from '../api'
import { useAuth } from '../auth'
import { useChatResults } from '../chatResults'
import { isSpooky } from '../season'
import { playCue, setSoundEnabled, soundEnabled } from '../sound'
import { isSpookyText, spook } from '../spook'
import type { ChatResults, ChatTurn, Cue, PageInfo, Recap, StoredMessage } from '../types'
import ChatProductCard from './ChatProductCard'
import ChatText from './ChatText'
import TypedText from './TypedText'

interface Message {
  key: string
  role: 'user' | 'assistant'
  text: string
  results?: ChatResults
  cue?: Cue | null
  error?: boolean
  system?: boolean // greeting / recap: shown, but never sent to the agent as history
  animate?: boolean // new reply: type it out, then reveal cards + quick replies
  divider?: string // a date divider row instead of a bubble
}

const MAX_HISTORY = 12
const CARDS_IN_BUBBLE = 3

// Other components can open the chat with a question: dispatchEvent(new CustomEvent(ASK_EVENT, {detail}))
export const ASK_EVENT = 'cc:ask'

const GUEST_GREETING = "Hi! I'm the Campus Customs assistant. Ask me about hoodies, sizes, or what's in stock."
const SUGGESTIONS = ['Navy hoodies in a medium?', 'Gift ideas for a Yale dad', 'What do you sell?']
const PRODUCT_SUGGESTIONS = ['Is this in stock in M?', 'What colors does this come in?', 'Tell me more about this one']

let seq = 0
const key = () => `m${++seq}`

// Page context sent with every message; on a product page the server resolves the item.
function pageInfo(pathname: string): PageInfo {
  const m = pathname.match(/^\/products\/([^/]+)/)
  return { path: pathname, product_id: m ? decodeURIComponent(m[1]) : null }
}

const fromStored = (m: StoredMessage): Message => ({
  key: `s${m.id}`,
  role: m.role,
  text: m.content,
  results: m.results ?? undefined,
})

function dayLabel(ts: string): string {
  const d = new Date(ts.replace(' ', 'T') + 'Z')
  if (Number.isNaN(d.getTime())) return 'Earlier'
  const today = new Date()
  if (d.toDateString() === today.toDateString()) return 'Earlier today'
  return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
}

// Restored history, grouped under date dividers, followed by the welcome-back recap.
function restore(messages: StoredMessage[], recap: Recap | null, firstName: string): Message[] {
  const out: Message[] = []
  let lastDay = ''
  for (const m of messages) {
    const label = dayLabel(m.created_at)
    if (label !== lastDay) {
      out.push({ key: key(), role: 'assistant', text: '', divider: label })
      lastDay = label
    }
    out.push(fromStored(m))
  }
  if (messages.length) out.push({ key: key(), role: 'assistant', text: '', divider: 'Now' })
  out.push({
    key: key(),
    role: 'assistant',
    system: true,
    text: recap?.text ?? `Hi ${firstName}! I'm the Campus Customs assistant. Your chat is saved to your account.`,
    results: recap?.products.length ? { title: 'Where we left off', products: recap.products } : undefined,
  })
  return out
}

const shortName = (name: string) => name.replace(/^(Yale|District Vit|Hype And Vice Yale University)\s+/i, '')

// Natural next questions, based on what just happened.
function quickReplies(last: Message | undefined, onProductPage: boolean): string[] {
  if (!last || last.role !== 'assistant' || last.error) return onProductPage ? PRODUCT_SUGGESTIONS : SUGGESTIONS
  if (last.cue === 'out_of_stock') return ['Which sizes are in stock?', 'Show me similar items']
  if (last.cue === 'no_match') return ['Show me hoodies', 'What do you sell?']
  const first = last.results?.products[0]
  if (first) {
    const more = last.results!.products.length > 1
    return [`Is the ${shortName(first.name)} in M?`, more ? 'Which is your top pick?' : 'Show me similar items', 'Anything cheaper?']
  }
  return onProductPage ? PRODUCT_SUGGESTIONS : SUGGESTIONS
}

export default function ChatWidget() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([
    { key: key(), role: 'assistant', text: GUEST_GREETING, system: true },
  ])
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [typing, setTyping] = useState<string | null>(null) // key of the reply being typed out
  const [sound, setSound] = useState(soundEnabled)
  const logRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const { pathname } = useLocation()
  const { user, loading: authLoading } = useAuth()
  const { show, clear: clearPicks } = useChatResults()
  const [historyState, setHistoryState] = useState<'idle' | 'loading' | 'loaded' | 'error'>('idle')
  const userId = user?.id ?? null
  // Which user's history is on screen: undefined = nothing yet, null = guest.
  const loadedFor = useRef<number | null | undefined>(undefined)
  const firstName = useRef('')
  firstName.current = user?.first_name ?? ''
  const onProductPage = pageInfo(pathname).product_id !== null
  const hasHistory = messages.some((m) => !m.system && !m.divider)

  // Customer memory: load the saved conversation (plus a welcome-back recap) when someone
  // signs in or returns already signed in; reset to a guest greeting when they sign out.
  useEffect(() => {
    if (authLoading) return
    const loaded = loadedFor.current
    if (userId === null) {
      if (loaded !== null) {
        setMessages([{ key: key(), role: 'assistant', text: GUEST_GREETING, system: true }])
        setHistoryState('idle')
        if (loaded !== undefined) clearPicks() // signed out: don't leave their picks on screen
      }
      loadedFor.current = null
      return
    }
    if (loaded === userId) return
    let cancelled = false
    setHistoryState('loading')
    getChatHistory()
      .then((h) => {
        if (cancelled) return
        loadedFor.current = userId // only once it actually loaded, so a cancelled run retries
        setMessages(restore(h.messages, h.recap, firstName.current))
        setHistoryState('loaded')
      })
      .catch(() => !cancelled && setHistoryState('error'))
    return () => {
      cancelled = true
    }
  }, [userId, authLoading, clearPicks])

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, sending, typing, open])

  useEffect(() => {
    if (!open) return
    inputRef.current?.focus()
    // In October, the first chat open of the session gets a small, quiet "boo".
    if (isSpooky() && !sessionStorage.getItem('cc.spooked')) {
      sessionStorage.setItem('cc.spooked', '1')
      spook('mini')
    }
  }, [open])

  const send = useCallback(
    async (raw: string) => {
      const text = raw.trim()
      if (!text || sending) return
      // Guests: earlier turns give the agent context. Signed in: the server loads saved
      // history itself and ignores this.
      const history: ChatTurn[] = user
        ? []
        : messages
            .filter((m) => !m.system && !m.error && !m.divider)
            .slice(-MAX_HISTORY)
            .map((m) => ({ role: m.role, content: m.text }))
      setMessages((m) => [...m, { key: key(), role: 'user', text }])
      setDraft('')
      setSending(true)
      try {
        const res = await sendChat(text, history, pageInfo(pathname))
        const k = key()
        setTyping(k)
        setMessages((m) => [
          ...m,
          { key: k, role: 'assistant', text: res.reply, results: res.results ?? undefined, cue: res.cue, animate: true },
        ])
        // Halloween fun: spooky words from either side earn a scare instead of the usual chime.
        if (isSpookyText(text) || isSpookyText(res.reply)) spook('full')
        else playCue(res.cue)
        if (res.results?.products.length) show(res.results) // also render on the page
      } catch (err) {
        const msg = (err as Error).message || "I couldn't reach the store server. Please try again in a moment."
        setMessages((m) => [...m, { key: key(), role: 'assistant', text: msg, error: true }])
        playCue('oops')
      } finally {
        setSending(false)
      }
    },
    [sending, user, messages, pathname, show],
  )

  // "Ask about this item" buttons elsewhere on the site open the chat with a question.
  const sendRef = useRef(send)
  sendRef.current = send
  useEffect(() => {
    const onAsk = (e: Event) => {
      const text = (e as CustomEvent<{ text: string }>).detail?.text
      setOpen(true)
      if (text) void sendRef.current(text)
    }
    window.addEventListener(ASK_EVENT, onAsk)
    return () => window.removeEventListener(ASK_EVENT, onAsk)
  }, [])

  async function onClearHistory() {
    if (!window.confirm('Delete your saved chat history? This cannot be undone.')) return
    try {
      await clearChatHistory()
      setMessages(restore([], null, user?.first_name ?? ''))
      clearPicks()
    } catch (err) {
      setMessages((m) => [...m, { key: key(), role: 'assistant', text: (err as Error).message, error: true }])
    }
  }

  function toggleSound() {
    const next = !sound
    setSound(next)
    setSoundEnabled(next)
    if (next) playCue('found') // preview so shoppers know what they turned on
  }

  function onShowAll(results: ChatResults) {
    show(results)
    setOpen(false)
    requestAnimationFrame(() =>
      document.getElementById('chat-picks')?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
    )
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    void send(draft)
  }

  const last = [...messages].reverse().find((m) => !m.divider)
  const chips = !sending && !typing && historyState !== 'loading' ? quickReplies(last, onProductPage) : []

  return (
    <div className={`chat ${open ? 'chat--open' : ''}`}>
      {open && (
        <section className="chat__panel" role="dialog" aria-label="Campus Customs chat assistant">
          <header className="chat__head">
            <div>
              <p className="chat__title">Ask the Bulldog</p>
              <p className="chat__sub">
                {user ? `Signed in as ${user.first_name} · history saved` : 'Guest · chat not saved'}
              </p>
            </div>
            <div className="chat__actions">
              <button
                className={`chat__sound ${sound ? 'is-on' : ''}`}
                onClick={toggleSound}
                aria-pressed={sound}
                title={sound ? 'Sound effects on (click to mute)' : 'Sound effects off (click to turn on)'}
              >
                {sound ? '🔊 On' : '🔇 Off'}
              </button>
              {user && hasHistory && (
                <button className="chat__clear" onClick={onClearHistory} title="Delete saved chat history">
                  Clear
                </button>
              )}
              <button className="chat__close" onClick={() => setOpen(false)} aria-label="Close chat">
                ×
              </button>
            </div>
          </header>

          <div className="chat__log" ref={logRef} aria-live="polite">
            {historyState === 'loading' && <p className="chat__status">Loading your saved chat…</p>}
            {historyState === 'error' && <p className="chat__status">Couldn't load your saved chat.</p>}
            {messages.map((m) => {
              if (m.divider) {
                return (
                  <div key={m.key} className="chat__divider" role="separator">
                    <span>{m.divider}</span>
                  </div>
                )
              }
              const isTyping = typing === m.key
              return (
                <div key={m.key} className={`msg msg--${m.role}`}>
                  <div className={`bubble bubble--${m.role} ${m.error ? 'bubble--error' : ''}`}>
                    {m.role === 'user' ? (
                      m.text
                    ) : m.animate && isTyping ? (
                      <TypedText text={m.text} onDone={() => setTyping((t) => (t === m.key ? null : t))} />
                    ) : (
                      <ChatText text={m.text} />
                    )}
                  </div>
                  {!isTyping && m.results && m.results.products.length > 0 && (
                    <div className="chat-cards">
                      {m.results.products.slice(0, CARDS_IN_BUBBLE).map((p) => (
                        // Opening a product tucks the chat away so the full product page is visible.
                        <ChatProductCard key={p.product_id} product={p} onOpen={() => setOpen(false)} />
                      ))}
                      <button className="chat-cards__more" onClick={() => onShowAll(m.results!)}>
                        {m.results.products.length > CARDS_IN_BUBBLE
                          ? `See all ${m.results.products.length} on the page ↑`
                          : 'Show on the page ↑'}
                      </button>
                    </div>
                  )}
                </div>
              )
            })}
            {sending && (
              <div className="bubble bubble--assistant bubble--typing" aria-label="Assistant is typing">
                <span />
                <span />
                <span />
              </div>
            )}
            {chips.length > 0 && (
              <div className="chat__suggest" aria-label="Suggested replies">
                {chips.map((s) => (
                  <button key={s} className="chip" onClick={() => void send(s)}>
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>

          <form className="chat__form" onSubmit={onSubmit}>
            <input
              ref={inputRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={onProductPage ? 'Ask about this item…' : 'Ask about our merch…'}
              aria-label="Message"
              maxLength={2000}
            />
            <button type="submit" className="btn btn--pink btn--sm" disabled={!draft.trim() || sending}>
              Send
            </button>
          </form>
        </section>
      )}

      <button
        className="chat__fab"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-label={open ? 'Close chat' : 'Open chat'}
      >
        <span className="chat__fab-icon" aria-hidden="true" />
        <span className="chat__fab-label">{open ? 'Close' : 'Chat'}</span>
      </button>
    </div>
  )
}
