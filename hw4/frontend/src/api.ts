import type { Category, ChatHistory, ChatReply, ChatTurn, Collection, PageInfo, ProductCard, ProductDetail, User } from './types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// FastAPI returns either a string or a list of validation errors in `detail`.
function errorMessage(detail: unknown): string | null {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0] as { loc?: string[]; msg?: string }
    const field = first.loc?.[first.loc.length - 1]?.replace('_', ' ')
    const msg = (first.msg ?? 'Invalid value').replace(/^Value error, /, '')
    return field && field !== 'body' ? `${field[0].toUpperCase()}${field.slice(1)}: ${msg}` : msg
  }
  return null
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new ApiError(res.status, errorMessage(body?.detail) ?? `Request failed (${res.status})`)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export function getProducts(params: { q?: string; category?: string; collection?: string } = {}) {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v) qs.set(k, v)
  const suffix = qs.toString() ? `?${qs}` : ''
  return request<ProductCard[]>(`/api/products${suffix}`)
}

export const getProduct = (id: string) =>
  request<ProductDetail>(`/api/products/${encodeURIComponent(id)}`)

export const getCategories = () => request<Category[]>('/api/categories')

export const getCollections = () => request<Collection[]>('/api/collections')

export const sendChat = (message: string, history: ChatTurn[], page: PageInfo) =>
  request<ChatReply>('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history, page }),
  })

export const getChatHistory = () => request<ChatHistory>('/api/chat/history')
export const clearChatHistory = () => request<void>('/api/chat/history', { method: 'DELETE' })

export const formatPrice = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })

const postJson = <T>(url: string, body?: unknown) =>
  request<T>(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })

export interface RegisterInput {
  first_name: string
  last_name: string
  email: string
  password: string
}

export const register = (input: RegisterInput) => postJson<User>('/api/auth/register', input)
export const login = (email: string, password: string) => postJson<User>('/api/auth/login', { email, password })
export const logout = () => postJson<void>('/api/auth/logout')
export const getMe = () => request<User>('/api/auth/me')
