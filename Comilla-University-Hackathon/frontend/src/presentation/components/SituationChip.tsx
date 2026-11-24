// "আমি যা বুঝেছি: ..." above an answer: what the agent understood about the caller's situation
// (sprint W2, FR-APP-11). The summary comes from the agent in Bangla.

import { useLanguage } from '../../application/languageContext'
import { MSG, MSG_EN } from '../../domain/messages'
import type { Situation } from '../../domain/types'

export function SituationChip({ situation }: { situation: Situation }) {
  const { lang } = useLanguage()
  if (!situation.summary_bn.trim()) return null
  const template = lang === 'en' ? MSG_EN.SITUATION_HEARD : MSG.SITUATION_HEARD
  const [before, after] = template.split('{summary}')
  return (
    <p className="mb-2 inline-flex max-w-full items-start gap-2 rounded-2xl bg-bd-green-soft px-3 py-2 text-base text-bd-green-dark">
      <svg viewBox="0 0 24 24" className="mt-1 h-4 w-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z" />
      </svg>
      <span className="min-w-0 break-words">
        {before}
        <span lang="bn" className="font-bold">
          {situation.summary_bn}
        </span>
        {after}
      </span>
    </p>
  )
}
