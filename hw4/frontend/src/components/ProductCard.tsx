import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { formatPrice } from '../api'
import type { ProductCard as Card } from '../types'
import StockBadge from './StockBadge'

const ACCENTS = ['pink', 'teal', 'yellow', 'purple'] as const

interface Props {
  product: Card
  index?: number
  compact?: boolean // fixed-width card for horizontal rows (chat picks)
  active?: boolean // the product currently open on the page
  onClick?: () => void
}

export default function ProductCard({ product, index = 0, compact, active, onClick }: Props) {
  const accent = ACCENTS[index % ACCENTS.length]
  return (
    <Link
      to={`/products/${product.product_id}`}
      className={`card card--${accent} ${compact ? 'card--compact' : ''} ${active ? 'is-active' : ''}`}
      aria-label={`${product.name}, ${formatPrice(product.price)}`}
      aria-current={active ? 'page' : undefined}
      onClick={onClick}
      style={{ '--i': index } as CSSProperties}
    >
      <div className="card__img">
        <img src={product.image_url} alt={product.name} loading="lazy" />
        <span className="card__cat">{product.category}</span>
      </div>
      <div className="card__body">
        <h3 className="card__name">{product.name}</h3>
        <p className="card__line">{product.one_liner}</p>
        <div className="card__foot">
          <span className="price">{formatPrice(product.price)}</span>
          <StockBadge status={product.status} />
        </div>
      </div>
    </Link>
  )
}
