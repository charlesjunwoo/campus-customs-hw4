import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { useChatResults } from '../chatResults'
import ProductCard from './ProductCard'

// "Chat picks": the agent's latest product matches, shown on whatever page the shopper
// is on. Cards are the same component as the Products grid, so clicking one opens the
// same single-item page.
export default function ChatResultsStrip() {
  const { results, clear } = useChatResults()
  const { pathname } = useLocation()
  const ref = useRef<HTMLElement>(null)
  const lastId = useRef(results?.id)

  // New matches arrived: bring the strip into view and reset its scroll position.
  useEffect(() => {
    if (!results || results.id === lastId.current) return
    lastId.current = results.id
    ref.current?.querySelector('.picks__row')?.scrollTo({ left: 0 })
    ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [results])

  if (!results || results.products.length === 0) return null
  const current = pathname.startsWith('/products/') ? decodeURIComponent(pathname.split('/')[2] ?? '') : null

  return (
    <section ref={ref} id="chat-picks" className="picks" aria-label="Products from the chat assistant">
      <div className="picks__inner">
        <div className="picks__head">
          <div>
            <p className="picks__kicker">Chat picks</p>
            <h2 className="picks__title">
              {results.title} <span className="picks__count">{results.products.length}</span>
            </h2>
          </div>
          <button className="picks__close" onClick={clear} aria-label="Hide chat picks">
            Hide ×
          </button>
        </div>
        <div className="picks__row">
          {results.products.map((p, i) => (
            <ProductCard key={p.product_id} product={p} index={i} compact active={p.product_id === current} />
          ))}
        </div>
      </div>
    </section>
  )
}
