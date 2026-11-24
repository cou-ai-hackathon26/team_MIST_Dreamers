// The checklist of an answer: who, papers, fee, where, decision (FR-APP-02, SRS 3.3).
// Fields the official documents do not state arrive as "তথ্য পাওয়া যায়নি" and are shown in grey,
// in the interface language. The values themselves come from Bangla documents and stay Bangla.
// Long values wrap; a fee with several tiers ("১ম বার: ...; ২য় বার: ...") shows one tier per line.

import type { ReactNode } from 'react'
import { useLanguage } from '../../application/languageContext'
import { UNKNOWN_FIELD } from '../../domain/messages'
import type { Checklist } from '../../domain/types'

function isUnknown(value: string): boolean {
  return !value.trim() || value.trim() === UNKNOWN_FIELD
}

function Row({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <div className="flex gap-3 py-2">
      <span
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white text-bd-green"
        aria-hidden="true"
      >
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <dt className="text-sm font-bold text-bd-green">{label}</dt>
        <dd className="break-words">{children}</dd>
      </div>
    </div>
  )
}

function Value({ text }: { text: string }) {
  const { t } = useLanguage()
  return isUnknown(text) ? <span className="text-gray-500">{t.unknownField}</span> : <span lang="bn">{text}</span>
}

/** A fee with several tiers shows one tier per line; a plain fee stays one line. */
function FeeValue({ text }: { text: string }) {
  const tiers = text.split(';').map((tier) => tier.trim()).filter(Boolean)
  if (isUnknown(text) || tiers.length < 2) return <Value text={text} />
  return (
    <ul lang="bn" className="space-y-0.5">
      {tiers.map((tier, i) => (
        <li key={i}>{tier}</li>
      ))}
    </ul>
  )
}

// Small line icons (24x24, stroke = currentColor), so no icon package is needed.
const svg = (path: ReactNode) => (
  <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    {path}
  </svg>
)
const ICONS = {
  who: svg(<><circle cx="12" cy="8" r="4" /><path d="M4 21c0-4 4-7 8-7s8 3 8 7" /></>),
  papers: svg(<><path d="M14 3H6v18h12V7z" /><path d="M14 3v4h4M9 12h6M9 16h6" /></>),
  fee: svg(<><rect x="3" y="6" width="18" height="12" rx="2" /><circle cx="12" cy="12" r="2.5" /></>),
  where: svg(<><path d="M12 21s-7-6.5-7-12a7 7 0 0 1 14 0c0 5.5-7 12-7 12z" /><circle cx="12" cy="9" r="2.5" /></>),
  decision: svg(<><path d="M12 3v18M5 7h14M7 7l-3 6a3 3 0 0 0 6 0zM17 7l-3 6a3 3 0 0 0 6 0z" /></>),
}

export function ChecklistCard({ checklist }: { checklist: Checklist }) {
  const { t } = useLanguage()
  const papers = checklist.papers.filter((p) => !isUnknown(p))
  return (
    <section className="rounded-xl border border-bd-green/20 bg-bd-green-soft p-3">
      <h3 className="mb-1 text-base font-bold text-bd-green">{t.checklistTitle}</h3>
      <dl className="divide-y divide-bd-green/10">
        <Row icon={ICONS.who} label={t.checklistWho}>
          <Value text={checklist.who} />
        </Row>
        <Row icon={ICONS.papers} label={t.checklistPapers}>
          {papers.length === 0 ? (
            <Value text="" />
          ) : (
            <ul lang="bn" className="ml-5 list-disc space-y-0.5">
              {papers.map((p, i) => (
                <li key={i}>{p}</li>
              ))}
            </ul>
          )}
        </Row>
        <Row icon={ICONS.fee} label={t.checklistFee}>
          <FeeValue text={checklist.fee} />
        </Row>
        <Row icon={ICONS.where} label={t.checklistWhere}>
          <Value text={checklist.where} />
        </Row>
        <Row icon={ICONS.decision} label={t.checklistDecision}>
          <Value text={checklist.decision} />
        </Row>
      </dl>
    </section>
  )
}
