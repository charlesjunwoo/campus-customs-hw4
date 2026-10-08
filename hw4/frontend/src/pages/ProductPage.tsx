import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { formatPrice, getProduct } from '../api'
import { ASK_EVENT } from '../components/ChatWidget'
import StockBadge from '../components/StockBadge'
import type { ProductDetail } from '../types'

export default function ProductPage() {
  const { productId = '' } = useParams()
  const [product, setProduct] = useState<ProductDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [size, setSize] = useState<string | null>(null)
  const [copied, setCopied] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setProduct(null)
    setError(null)
    setSize(null)
    getProduct(productId)
      .then((p) => !cancelled && setProduct(p))
      .catch((e: Error) => !cancelled && setError(e.message))
    return () => {
      cancelled = true
    }
  }, [productId])

  if (error) {
    return (
      <div className="section">
        <p className="notice notice--error">{error === 'Product not found' ? "We couldn't find that product." : error}</p>
        <Link to="/products" className="link-arrow">
          ← Back to all products
        </Link>
      </div>
    )
  }
  if (!product) return <div className="section"><div className="loader" aria-label="Loading product" /></div>

  const selected = product.inventory.find((s) => s.size === size)

  function ask(text: string) {
    window.dispatchEvent(new CustomEvent(ASK_EVENT, { detail: { text } }))
  }

  async function copySku(sku: string) {
    try {
      await navigator.clipboard.writeText(sku)
      setCopied(sku)
      setTimeout(() => setCopied((c) => (c === sku ? null : c)), 1500)
    } catch {
      setCopied(null)
    }
  }

  return (
    <div className="section">
      <nav className="crumbs" aria-label="Breadcrumb">
        <Link to="/products">Products</Link>
        <span>/</span>
        <Link to={`/products?category=${encodeURIComponent(product.category)}`}>{product.category}</Link>
        <span>/</span>
        <span aria-current="page">{product.name}</span>
      </nav>

      <article className="pdp">
        <div className="pdp__media">
          <div className="pdp__frame">
            <img src={product.image_url} alt={product.name} />
          </div>
        </div>

        <div className="pdp__info">
          <p className="eyebrow">{product.garment_type}</p>
          <h1 className="h1 pdp__name">{product.name}</h1>
          <div className="pdp__price-row">
            <span className="price price--lg">{formatPrice(product.price)}</span>
            <StockBadge
              status={product.status}
              label={
                product.status === 'sold_out'
                  ? 'Sold out'
                  : `${product.total_stock} in stock across ${product.sizes_in_stock} sizes`
              }
            />
          </div>

          <p className="pdp__desc">{product.description}</p>

          {product.colors.length > 0 && (
            <div className="pdp__block">
              <h2 className="h3">Colors</h2>
              <ul className="tags">
                {product.colors.map((c) => (
                  <li key={c} className="tag">
                    {c}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="pdp__block">
            <h2 className="h3">Sizes &amp; stock</h2>
            <div className="sizes" role="radiogroup" aria-label="Choose a size">
              {product.inventory.map((s) => (
                <button
                  key={s.size}
                  role="radio"
                  aria-checked={size === s.size}
                  className={`size size--${s.status} ${size === s.size ? 'is-active' : ''}`}
                  disabled={s.status === 'sold_out'}
                  onClick={() => setSize(s.size)}
                >
                  <span className="size__label">{s.size}</span>
                  <span className="size__qty">{s.status === 'sold_out' ? 'Sold out' : `${s.quantity} left`}</span>
                </button>
              ))}
            </div>
            {selected ? (
              <div className="sku-box" aria-live="polite">
                <div>
                  <span className="sku-box__label">SKU</span>
                  <code className="sku-box__code">{selected.sku}</code>
                </div>
                <span className="sku-box__qty">
                  Size {selected.size}: {selected.quantity} in stock{selected.status === 'low' ? ', grab it soon!' : ''}
                </span>
                <button className="btn btn--sm" onClick={() => copySku(selected.sku)}>
                  {copied === selected.sku ? 'Copied!' : 'Copy SKU'}
                </button>
              </div>
            ) : (
              <p className="muted pdp__hint">Pick a size to see its stock and SKU. Online ordering is coming soon.</p>
            )}
          </div>

          <div className="ask-row">
            <button className="btn btn--ghost btn--sm" onClick={() => ask('Tell me more about this one')}>
              💬 Ask about this item
            </button>
            {selected && selected.status === 'sold_out' ? null : (
              <button
                className="btn btn--sm"
                onClick={() => ask(selected ? `Is the ${selected.size} still in stock?` : 'What colors and sizes does this come in?')}
              >
                {selected ? `Check ${selected.size} with the assistant` : 'Colors & sizes?'}
              </button>
            )}
          </div>

          <table className="stock-table">
            <caption className="sr-only">Stock and SKU by size</caption>
            <thead>
              <tr>
                {product.inventory.map((s) => (
                  <th key={s.size} scope="col">
                    {s.size}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                {product.inventory.map((s) => (
                  <td key={s.size} className={`qty qty--${s.status}`}>
                    {s.quantity}
                  </td>
                ))}
              </tr>
              <tr className="stock-table__sku">
                {product.inventory.map((s) => (
                  <td key={s.size} title={`SKU for size ${s.size}`}>
                    {s.sku.replace(/-[A-Z]+$/, '')}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>

          <Link to="/products" className="link-arrow">
            ← Keep shopping
          </Link>
        </div>
      </article>
    </div>
  )
}
