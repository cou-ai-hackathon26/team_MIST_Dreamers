// "নিয়ম আলাদা": two services' documents say different things on the same point (sprint W2,
// FR-APP-11, FR-AGT-22). Each side shows its service, its own rule and its own source, side by side
// (stacked on a narrow phone). Neutral style: no side is coloured as the "winner".

import { useLanguage } from '../../application/languageContext'
import { fill, MSG, MSG_EN } from '../../domain/messages'
import type { Conflict } from '../../domain/types'

export function ConflictBox({ conflicts, serviceName }: { conflicts: Conflict[]; serviceName: (id: string) => string }) {
  const { lang, t } = useLanguage()
  if (conflicts.length === 0) return null
  return (
    <section className="rounded-xl border-2 border-gray-300 bg-white p-3" aria-label={t.conflictTitle}>
      <h3 className="mb-2 flex items-center gap-2 text-base font-bold text-gray-800">
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M12 3v18M5 7h14M7 7l-3 6a3 3 0 0 0 6 0zM17 7l-3 6a3 3 0 0 0 6 0z" />
        </svg>
        {t.conflictTitle}
      </h3>
      <div className="space-y-3">
        {conflicts.map((conflict, i) => (
          <div key={i}>
            {conflict.topic_bn && (
              <p lang="bn" className="mb-1 text-sm font-bold text-gray-700">
                {fill(t.conflictTopic, { topic: conflict.topic_bn })}
              </p>
            )}
            <div className="grid gap-2 sm:grid-cols-2">
              {conflict.sides.map((side) => (
                <div key={side.service_id} className="min-w-0 rounded-lg bg-gray-50 p-3">
                  <p className="text-sm font-bold text-bd-green">{serviceName(side.service_id)}</p>
                  <p lang="bn" className="mt-1 break-words">
                    {side.rule_bn}
                  </p>
                  {side.source_url && (
                    <a
                      href={side.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      lang="bn"
                      className="mt-1 inline-flex min-h-12 items-center break-words text-sm text-bd-green underline decoration-bd-green/40 underline-offset-2"
                    >
                      {side.source_title || side.source_url}
                    </a>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-base text-gray-700">{lang === 'en' ? MSG_EN.CONFLICT_NOTE : MSG.CONFLICT_NOTE}</p>
    </section>
  )
}
