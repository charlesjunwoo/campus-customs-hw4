import { useEffect, useState, type CSSProperties } from 'react'
import { prefersReducedMotion } from '../season'
import { SPOOK_EVENT, type SpookLevel } from '../spook'

// Emoji swarm overlay for spook(). Each emoji gets a motion that suits it: bats swoop
// across, ghosts float up, spiders drop on a thread, pumpkins and skulls pop.
const CAST: { emoji: string; motion: 'swoop' | 'float' | 'drop' | 'pop' }[] = [
  { emoji: '🦇', motion: 'swoop' },
  { emoji: '👻', motion: 'float' },
  { emoji: '🕷️', motion: 'drop' },
  { emoji: '🎃', motion: 'pop' },
  { emoji: '💀', motion: 'pop' },
  { emoji: '🕸️', motion: 'pop' },
  { emoji: '🍬', motion: 'float' },
]

interface Sprite {
  id: number
  emoji: string
  motion: string
  style: CSSProperties
}

let nextId = 0
const rand = (a: number, b: number) => a + Math.random() * (b - a)

function swarm(level: SpookLevel): Sprite[] {
  const count = level === 'mini' ? 6 : 22
  return Array.from({ length: count }, (_, i) => {
    const c = CAST[i % CAST.length]
    return {
      id: nextId++,
      emoji: c.emoji,
      motion: c.motion,
      style: {
        left: `${rand(2, 92)}%`,
        top: `${rand(5, 85)}%`,
        fontSize: `${rand(level === 'mini' ? 22 : 28, level === 'mini' ? 34 : 64)}px`,
        animationDelay: `${rand(0, level === 'mini' ? 0.3 : 0.6)}s`,
        animationDuration: `${rand(1.6, 2.4)}s`,
      } as CSSProperties,
    }
  })
}

export default function Spooker() {
  const [scare, setScare] = useState<{ key: number; level: SpookLevel; sprites: Sprite[] } | null>(null)

  useEffect(() => {
    let timer: number | undefined
    const onSpook = (e: Event) => {
      const level = (e as CustomEvent<{ level: SpookLevel }>).detail?.level ?? 'full'
      setScare({ key: Date.now(), level, sprites: swarm(level) })
      window.clearTimeout(timer)
      timer = window.setTimeout(() => setScare(null), level === 'mini' ? 2600 : 3200)
    }
    window.addEventListener(SPOOK_EVENT, onSpook)
    return () => {
      window.removeEventListener(SPOOK_EVENT, onSpook)
      window.clearTimeout(timer)
    }
  }, [])

  if (!scare) return null
  const still = prefersReducedMotion()
  return (
    <div
      key={scare.key}
      className={`spooker spooker--${scare.level} ${still ? 'spooker--still' : ''}`}
      aria-hidden="true"
      onClick={() => setScare(null)}
    >
      {scare.level === 'full' && <div className="spooker__boo">BOO!</div>}
      {scare.sprites.map((s) => (
        <span key={s.id} className={`spooker__sprite spooker__sprite--${s.motion}`} style={s.style}>
          {s.emoji}
        </span>
      ))}
    </div>
  )
}
