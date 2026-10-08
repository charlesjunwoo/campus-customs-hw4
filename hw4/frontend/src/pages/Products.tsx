import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getCategories, getCollections, getProducts } from '../api'
import ProductCard from '../components/ProductCard'
import type { Category, Collection, ProductCard as Card } from '../types'

type Sort = 'name' | 'price-asc' | 'price-desc'

export default function Products() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const category = params.get('category') ?? ''
  const collection = params.get('collection') ?? ''
  const sort = (params.get('sort') as Sort) || 'name'

  const [products, setProducts] = useState<Card[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [categories, setCategories] = useState<Category[]>([])
  const [collections, setCollections] = useState<Collection[]>([])
  const [draft, setDraft] = useState(q)

  useEffect(() => {
    getCategories().then(setCategories).catch(() => {})
    getCollections().then(setCollections).catch(() => {})
  }, [])

  useEffect(() => {
    setDraft(q)
  }, [q])

  useEffect(() => {
    let cancelled = false
    setProducts(null)
    setError(null)
    getProducts({ q, category, collection })
      .then((p) => !cancelled && setProducts(p))
      .catch((e: Error) => !cancelled && setError(e.message))
    return () => {
      cancelled = true
    }
  }, [q, category, collection])

  const sorted = useMemo(() => {
    if (!products) return null
    const list = [...products]
    if (sort === 'price-asc') list.sort((a, b) => a.price - b.price || a.name.localeCompare(b.name))
    if (sort === 'price-desc') list.sort((a, b) => b.price - a.price || a.name.localeCompare(b.name))
    return list
  }, [products, sort])

  function update(key: string, value: string) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  const activeCollection = collections.find((c) => c.slug === collection)
  const hasFilters = Boolean(q || category || collection)

  return (
    <div className="section">
      <div className="page-head">
        <p className="eyebrow">The shop</p>
        <h1 className="h1">
          {activeCollection ? activeCollection.name : category || 'All products'}
        </h1>
      </div>

      <div className="filters">
        <form
          className="search"
          role="search"
          onSubmit={(e) => {
            e.preventDefault()
            update('q', draft.trim())
          }}
        >
          <input
            type="search"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Search hoodies, colleges, sports, colors…"
            aria-label="Search products"
          />
          <button type="submit" className="btn btn--sm">
            Search
          </button>
        </form>

        <div className="chips" aria-label="Filter by type">
          <button className={`chip ${!category ? 'is-active' : ''}`} onClick={() => update('category', '')}>
            All types
          </button>
          {categories.map((c) => (
            <button
              key={c.name}
              className={`chip ${category === c.name ? 'is-active' : ''}`}
              onClick={() => update('category', category === c.name ? '' : c.name)}
            >
              {c.name} <span className="chip__n">{c.count}</span>
            </button>
          ))}
        </div>

        <div className="filters__row">
          <label className="select">
            <span>Collection</span>
            <select value={collection} onChange={(e) => update('collection', e.target.value)}>
              <option value="">All collections</option>
              {collections.map((c) => (
                <option key={c.slug} value={c.slug}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label className="select">
            <span>Sort</span>
            <select value={sort} onChange={(e) => update('sort', e.target.value === 'name' ? '' : e.target.value)}>
              <option value="name">Name A–Z</option>
              <option value="price-asc">Price: low to high</option>
              <option value="price-desc">Price: high to low</option>
            </select>
          </label>
          {hasFilters && (
            <button className="link-btn" onClick={() => setParams({}, { replace: true })}>
              Clear filters
            </button>
          )}
          {sorted && <span className="muted filters__count">{sorted.length} items</span>}
        </div>
      </div>

      {error && <p className="notice notice--error">Couldn't load products: {error}</p>}
      {!sorted && !error && <div className="loader" aria-label="Loading products" />}
      {sorted && sorted.length === 0 && (
        <p className="notice">No matches. Try a different search, or clear the filters.</p>
      )}
      {sorted && sorted.length > 0 && (
        <div className="grid">
          {sorted.map((p, i) => (
            <ProductCard key={p.product_id} product={p} index={i} />
          ))}
        </div>
      )}
    </div>
  )
}
