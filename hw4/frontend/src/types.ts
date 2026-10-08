export type StockStatus = 'in_stock' | 'low' | 'sold_out'

export interface ProductCard {
  product_id: string
  name: string
  category: string
  garment_type: string
  one_liner: string
  price: number
  image_url: string
  total_stock: number
  sizes_in_stock: number
  status: StockStatus
}

export interface SizeStock {
  size: string
  quantity: number
  status: StockStatus
  sku: string // e.g. CC-0477-M
}

export interface ProductDetail extends ProductCard {
  description: string
  colors: string[]
  search_tags: string[]
  inventory: SizeStock[]
}

export interface Category {
  name: string
  count: number
}

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatResults {
  title: string
  products: ProductCard[]
}

// Sound effect chosen server-side from the turn's database lookups
export type Cue = 'found' | 'in_stock' | 'out_of_stock' | 'no_match' | 'oops'

// POST /api/chat response (backend models.ChatResponse)
export interface ChatReply {
  reply: string
  results: ChatResults | null
  cue: Cue | null
  tools_used: string[]
}

export interface Collection {
  slug: string
  name: string
  count: number
}

export interface User {
  id: number
  first_name: string
  last_name: string
  name: string
  email: string
}

// Where the shopper is when they chat (backend models.PageInfo)
export interface PageInfo {
  path: string
  product_id: string | null
}

// GET /api/chat/history (backend models.ChatHistory)
export interface StoredMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  results: ChatResults | null
  created_at: string
}

export interface Recap {
  text: string
  products: ProductCard[]
}

export interface ChatHistory {
  signed_in: boolean
  messages: StoredMessage[]
  recap: Recap | null
}
