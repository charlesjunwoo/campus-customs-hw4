import { playSpook } from './sound'

// spook(): fire a Halloween scare, an emoji swarm plus a spooky synth sound.
// <Spooker /> (mounted once in App) listens for the event and draws the overlay.

export const SPOOK_EVENT = 'cc:spook'
export type SpookLevel = 'full' | 'mini'

// Words that make the chat spook back (in the shopper's message or the bot's reply).
const SPOOKY_WORDS = /\b(boo+|spooky|spook|halloween|trick[- ]or[- ]treat|ghosts?|ghouls?|pumpkins?|haunted|scary|witch(es)?|bats?|skeletons?|zombies?)\b/i

export function isSpookyText(text: string): boolean {
  return SPOOKY_WORDS.test(text)
}

let last = 0

export function spook(level: SpookLevel = 'full') {
  const now = Date.now()
  if (now - last < 1500) return // no stacking scares
  last = now
  window.dispatchEvent(new CustomEvent(SPOOK_EVENT, { detail: { level } }))
  playSpook(level)
}
