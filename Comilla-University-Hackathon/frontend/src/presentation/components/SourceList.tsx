// The official documents an answer comes from: title + link (FR-APP-02, SRS 3.3).

import { useLanguage } from '../../application/languageContext'
import type { Citation } from '../../domain/types'

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return ''
  }
}

export function SourceList({ citations }: { citations: Citation[] }) {
  const { t } = useLanguage()
  // One line per document, even if several passages of it were used.
  const unique = citations.filter((c, i) => citations.findIndex((o) => o.source_url === c.source_url) === i)
  if (unique.length === 0) return null

  return (
    <section>
      <h3 className="mb-1 text-sm font-bold text-gray-700">{t.sourcesTitle}</h3>
      <ul className="space-y-1">
        {unique.map((c) => (
          <li key={c.chunk_id || c.source_url}>
            <a
              href={c.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex min-h-12 items-start gap-2 rounded-lg px-2 py-2 text-bd-green hover:bg-bd-green-soft"
            >
              <svg viewBox="0 0 24 24" className="mt-1 h-4 w-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M14 4h6v6M20 4l-9 9M18 14v6H4V6h6" />
              </svg>
              <span lang="bn" className="min-w-0 break-words">
                <span className="underline decoration-bd-green/40 underline-offset-2">{c.title}</span>
                {hostOf(c.source_url) && (
                  <span className="block text-sm text-gray-600">{hostOf(c.source_url)}</span>
                )}
              </span>
            </a>
          </li>
        ))}
      </ul>
    </section>
  )
}
