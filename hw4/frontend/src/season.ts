// Seasonal theme. October = Halloween (Yale Blue + pumpkin, witch purple, candy corn).
// Override for demos/QA with ?theme=halloween or ?theme=classic (kept for the session).

export type Theme = 'halloween' | 'classic'
const KEY = 'cc.theme'

export function pickTheme(now = new Date()): Theme {
  const q = new URLSearchParams(window.location.search).get('theme')
  if (q === 'halloween' || q === 'classic') {
    sessionStorage.setItem(KEY, q)
    return q
  }
  const saved = sessionStorage.getItem(KEY)
  if (saved === 'halloween' || saved === 'classic') return saved
  return now.getMonth() === 9 ? 'halloween' : 'classic'
}

export const isSpooky = () => document.documentElement.dataset.theme === 'halloween'

export const prefersReducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
