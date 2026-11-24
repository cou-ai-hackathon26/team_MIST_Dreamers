// Logged questions on the admin dashboard: recent activity and the unanswered ones (SRS 3.4).
// A list, not a wide table, so it fits a 360 px phone. Status is always a word, never colour alone.

import { useLanguage } from '../../application/languageContext'
import type { ServiceNames } from '../../application/useServiceNames'
import type { UiText } from '../../domain/messages'
import type { AdminQuestion, AnswerStatus } from '../../domain/types'
import { useFormat } from '../format'

const STATUS: Record<AnswerStatus, { label: keyof UiText; className: string }> = {
  answered: { label: 'statusAnswered', className: 'bg-bd-green-soft text-bd-green' },
  follow_up: { label: 'statusFollowUp', className: 'bg-gray-100 text-gray-700' },
  fallback: { label: 'statusFallback', className: 'bg-bd-red-soft text-bd-red-dark' },
  error: { label: 'statusError', className: 'bg-bd-red-soft text-bd-red-dark' },
}

export function QuestionList({
  title,
  rows,
  empty,
  serviceName,
}: {
  title: string
  rows: AdminQuestion[]
  empty: string
  serviceName: ServiceNames
}) {
  const { lang, t } = useLanguage()
  const format = useFormat()
  return (
    <section className="rounded-2xl bg-white p-4 shadow-sm">
      <h2 className="mb-2 text-lg font-bold text-bd-green">{title}</h2>
      {rows.length === 0 ? (
        <p className="text-gray-600">{empty}</p>
      ) : (
        <ul className="divide-y divide-gray-100">
          {rows.map((q, i) => {
            const status = STATUS[q.status] ?? STATUS.error
            return (
              <li key={`${q.created_at}-${i}`} className="py-2">
                <p lang="bn" className="break-words">
                  {q.text}
                </p>
                <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-gray-600">
                  <span className={`rounded-full px-2 py-0.5 font-bold ${status.className}`}>{t[status.label]}</span>
                  {q.service_id && <span>{serviceName(q.service_id, lang) || q.service_name_bn}</span>}
                  <span>· {q.channel === 'voice' ? t.channelVoice : t.channelApp}</span>
                  {q.latency_ms > 0 && (
                    <span>
                      · {format.seconds(q.latency_ms)} {t.secondsShort}
                    </span>
                  )}
                  <span>· {format.dateTime(q.created_at)}</span>
                  {q.is_demo && (
                    <span className="rounded-full border border-gray-300 px-2 py-0.5">{t.demoBadge}</span>
                  )}
                </p>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
