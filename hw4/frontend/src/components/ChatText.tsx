import type { ReactNode } from 'react'

// Minimal, safe markdown for chat replies: **bold** and "- " / "* " bullet lists.
// Builds React elements (no innerHTML), so model output can never inject markup.
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((chunk, i) =>
    chunk.startsWith('**') && chunk.endsWith('**') && chunk.length > 4 ? (
      <strong key={i}>{chunk.slice(2, -2)}</strong>
    ) : (
      chunk
    ),
  )
}

export default function ChatText({ text }: { text: string }) {
  const blocks: ReactNode[] = []
  let bullets: string[] = []

  const flush = () => {
    if (bullets.length) {
      blocks.push(
        <ul key={`ul-${blocks.length}`}>
          {bullets.map((b, i) => (
            <li key={i}>{inline(b)}</li>
          ))}
        </ul>,
      )
      bullets = []
    }
  }

  for (const raw of text.split('\n')) {
    const line = raw.trim()
    const bullet = line.match(/^[-*•]\s+(.*)$/)
    if (bullet) {
      bullets.push(bullet[1])
      continue
    }
    flush()
    if (line) blocks.push(<p key={`p-${blocks.length}`}>{inline(line)}</p>)
  }
  flush()
  return <>{blocks}</>
}
