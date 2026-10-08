import type { Cue } from './types'

// Tiny 80s synth sound effects, generated with the Web Audio API (no audio files).
// The backend picks the cue from what the database said; this just plays it.

type Note = [freqHz: number, startS: number, lengthS: number]

const SONGS: Record<Cue, { wave: OscillatorType; notes: Note[] }> = {
  // rising major arpeggio: "look what I found!"
  found: { wave: 'square', notes: [[523, 0, 0.09], [659, 0.08, 0.09], [784, 0.16, 0.16]] },
  // bright two-note "yes!"
  in_stock: { wave: 'square', notes: [[784, 0, 0.08], [1047, 0.08, 0.18]] },
  // gentle falling minor third: "sorry, that size is gone"
  out_of_stock: { wave: 'triangle', notes: [[440, 0, 0.14], [370, 0.13, 0.26]] },
  // soft single low blip: "nothing matched"
  no_match: { wave: 'triangle', notes: [[330, 0, 0.2]] },
  // short buzz: blocked or couldn't verify
  oops: { wave: 'sawtooth', notes: [[196, 0, 0.12], [185, 0.11, 0.14]] },
}

const KEY = 'cc.sound'
let ctx: AudioContext | null = null

export function soundEnabled(): boolean {
  return localStorage.getItem(KEY) !== 'off' // on by default; shoppers can mute
}

export function setSoundEnabled(on: boolean) {
  localStorage.setItem(KEY, on ? 'on' : 'off')
}

export function playCue(cue: Cue | null | undefined) {
  if (!cue || !soundEnabled()) return
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return
  try {
    ctx ??= new AudioContext()
    if (ctx.state === 'suspended') void ctx.resume()
    const { wave, notes } = SONGS[cue]
    const now = ctx.currentTime + 0.02
    for (const [freq, start, length] of notes) {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = wave
      osc.frequency.value = freq
      // quick attack, exponential release; kept quiet (0.06) so it never startles
      gain.gain.setValueAtTime(0.0001, now + start)
      gain.gain.exponentialRampToValueAtTime(0.06, now + start + 0.01)
      gain.gain.exponentialRampToValueAtTime(0.0001, now + start + length)
      osc.connect(gain).connect(ctx.destination)
      osc.start(now + start)
      osc.stop(now + start + length + 0.02)
    }
  } catch {
    // Audio unavailable (old browser, blocked): silently skip.
  }
}

// Halloween scare: a wobbly theremin glide (sine + vibrato), a low "boo" growl, and a
// flutter of bat-wing clicks. Same mute toggle and reduced-motion rule as the cues.
export function playSpook(level: 'full' | 'mini' = 'full') {
  if (!soundEnabled()) return
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return
  try {
    ctx ??= new AudioContext()
    if (ctx.state === 'suspended') void ctx.resume()
    const t = ctx.currentTime + 0.02
    const vol = level === 'mini' ? 0.035 : 0.07

    // Theremin: 880 Hz sliding down to 220 Hz, with a 6 Hz vibrato.
    const theremin = ctx.createOscillator()
    const vibrato = ctx.createOscillator()
    const depth = ctx.createGain()
    const g1 = ctx.createGain()
    theremin.type = 'sine'
    theremin.frequency.setValueAtTime(880, t)
    theremin.frequency.exponentialRampToValueAtTime(220, t + 1.3)
    vibrato.frequency.value = 6
    depth.gain.value = 18
    vibrato.connect(depth).connect(theremin.frequency)
    g1.gain.setValueAtTime(0.0001, t)
    g1.gain.exponentialRampToValueAtTime(vol, t + 0.08)
    g1.gain.exponentialRampToValueAtTime(0.0001, t + 1.4)
    theremin.connect(g1).connect(ctx.destination)
    theremin.start(t)
    vibrato.start(t)
    theremin.stop(t + 1.45)
    vibrato.stop(t + 1.45)
    if (level === 'mini') return

    // "Boo": low sawtooth growl through a low-pass filter.
    const boo = ctx.createOscillator()
    const lp = ctx.createBiquadFilter()
    const g2 = ctx.createGain()
    boo.type = 'sawtooth'
    boo.frequency.setValueAtTime(110, t + 0.15)
    boo.frequency.exponentialRampToValueAtTime(70, t + 0.75)
    lp.type = 'lowpass'
    lp.frequency.value = 420
    g2.gain.setValueAtTime(0.0001, t + 0.15)
    g2.gain.exponentialRampToValueAtTime(vol * 1.4, t + 0.22)
    g2.gain.exponentialRampToValueAtTime(0.0001, t + 0.8)
    boo.connect(lp).connect(g2).connect(ctx.destination)
    boo.start(t + 0.15)
    boo.stop(t + 0.85)

    // Bat wings: six tiny high clicks.
    for (let i = 0; i < 6; i++) {
      const click = ctx.createOscillator()
      const g3 = ctx.createGain()
      const at = t + 0.5 + i * 0.07
      click.type = 'square'
      click.frequency.value = 2400 + (i % 2) * 400
      g3.gain.setValueAtTime(0.0001, at)
      g3.gain.exponentialRampToValueAtTime(vol * 0.5, at + 0.005)
      g3.gain.exponentialRampToValueAtTime(0.0001, at + 0.04)
      click.connect(g3).connect(ctx.destination)
      click.start(at)
      click.stop(at + 0.05)
    }
  } catch {
    // Audio unavailable: the visual scare still runs.
  }
}
