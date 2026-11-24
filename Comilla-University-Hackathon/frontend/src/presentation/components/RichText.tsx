// Shows the answer's display_text, which is a small piece of markdown from the agent:
// "**bold**", "- " bullet lines and a "_..._" note line. Built as React elements, never as HTML.

import type { ReactNode } from 'react'

function inline(text: string): ReactNode[] {
  // "a **b** c" -> ["a ", <strong>b</strong>, " c"]
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') && part.length > 4 ? (
      <strong key={i} className="font-bold">
        {part.slice(2, -2)}
      </strong>
    ) : (
      part
    ),
  )
}

export function RichText({ text }: { text: string }) {
  const blocks: ReactNode[] = []
  let bullets: string[] = []

  const flushBullets = () => {
    if (bullets.length === 0) return
    blocks.push(
      <ul key={`ul${blocks.length}`} className="ml-5 list-disc space-y-1">
        {bullets.map((b, i) => (
          <li key={i}>{inline(b)}</li>
        ))}
      </ul>,
    )
    bullets = []
  }

  for (const raw of text.split('\n')) {
    const line = raw.trim()
    const bullet = /^[-*•]\s+(.*)$/.exec(line)
    if (bullet) {
      bullets.push(bullet[1])
      continue
    }
    flushBullets()
    if (!line) continue
    const note = /^_(.+)_$/.exec(line)
    blocks.push(
      note ? (
        <p key={`p${blocks.length}`} className="text-base text-gray-600 italic">
          {note[1]}
        </p>
      ) : (
        <p key={`p${blocks.length}`}>{inline(line)}</p>
      ),
    )
  }
  flushBullets()

  return <div className="space-y-2 leading-relaxed break-words">{blocks}</div>
}
