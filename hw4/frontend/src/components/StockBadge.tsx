import type { StockStatus } from '../types'

const LABELS: Record<StockStatus, string> = {
  in_stock: 'In stock',
  low: 'Low stock',
  sold_out: 'Sold out',
}

export default function StockBadge({ status, label }: { status: StockStatus; label?: string }) {
  return <span className={`badge badge--${status}`}>{label ?? LABELS[status]}</span>
}
