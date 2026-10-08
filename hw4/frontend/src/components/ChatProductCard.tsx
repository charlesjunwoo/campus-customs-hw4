import { Link } from 'react-router-dom'
import { formatPrice } from '../api'
import type { ProductCard } from '../types'
import StockBadge from './StockBadge'

export default function ChatProductCard({ product, onOpen }: { product: ProductCard; onOpen?: () => void }) {
  return (
    <Link to={`/products/${product.product_id}`} className="chat-card" onClick={onOpen}>
      <img src={product.image_url} alt="" loading="lazy" />
      <span className="chat-card__body">
        <span className="chat-card__name">{product.name}</span>
        <span className="chat-card__line">{product.one_liner}</span>
        <span className="chat-card__meta">
          <span className="chat-card__price">{formatPrice(product.price)}</span>
          <StockBadge status={product.status} />
        </span>
      </span>
    </Link>
  )
}
