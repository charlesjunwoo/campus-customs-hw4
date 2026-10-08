import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

export default function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    // Opening a product while "Chat picks" is showing: land on the product itself
    // (large image + details), not on the strip above it.
    const picks = document.getElementById('chat-picks')
    const main = document.querySelector<HTMLElement>('main')
    if (pathname.startsWith('/products/') && picks && main) {
      const nav = document.querySelector<HTMLElement>('.nav')?.offsetHeight ?? 0
      window.scrollTo(0, main.offsetTop - nav)
    } else {
      window.scrollTo(0, 0)
    }
  }, [pathname])
  return null
}
