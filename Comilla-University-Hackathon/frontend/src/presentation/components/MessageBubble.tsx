// One message in the chat: the user's question, an answer from Ek Call, or an error (FR-APP-02, 08).
// An answer shows (SRS 3.3): service tag, the spoken-style answer, the checklist card, the sources.
// A two-service answer (sprint W2, FR-APP-11) shows the situation chip, one checklist card per
// service with its own tag and sources, and the "rules differ" box.

import { useEffect, useState } from 'react'
import { useLanguage } from '../../application/languageContext'
import type { ChatMessage, ChatResponse, Citation, ServiceChecklist } from '../../domain/types'
import { ChecklistCard } from './ChecklistCard'
import { ConflictBox } from './ConflictBox'
import { RichText } from './RichText'
import { ServiceTag } from './ServiceTag'
import { SituationChip } from './SituationChip'
import { SourceList } from './SourceList'
import { PlayAnswerButton } from './voice/PlayAnswerButton'

/** The first non-empty line of display_text if it is a bold title ("**বয়স্ক ভাতা** ..."), else "". */
function titleLine(displayText: string): string {
  const first = displayText.split('\n').find((line) => line.trim()) ?? ''
  return first.trim().startsWith('**') ? first : ''
}

/** Chunk ids are "<service_id>-NNN", so each service card can list its own sources. */
function citationsOf(citations: Citation[], serviceId: string): Citation[] {
  return citations.filter((c) => c.chunk_id.startsWith(`${serviceId}-`))
}

function MultiAnswer({ answer, checklists }: { answer: ChatResponse; checklists: ServiceChecklist[] }) {
  const { lang } = useLanguage()
  const services = answer.services ?? []
  const nameOf = (id: string) => {
    const s = services.find((x) => x.id === id)
    return s ? (lang === 'en' ? s.name_en : s.name_bn) : id
  }
  const placed = new Set(checklists.flatMap((c) => citationsOf(answer.citations, c.service_id).map((x) => x.chunk_id)))
  const rest = answer.citations.filter((c) => !placed.has(c.chunk_id))
  return (
    <>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        {services.map((s) => (
          <ServiceTag key={s.id} name={nameOf(s.id)} />
        ))}
      </div>
      <p lang="bn" className="text-lg leading-relaxed break-words">
        {answer.speech_text}
      </p>
      <div className="mt-2">
        <PlayAnswerButton text={answer.speech_text} />
      </div>
      <div className="mt-3 space-y-3">
        {checklists.map((c) => (
          <div key={c.service_id} className="space-y-2">
            <ServiceTag name={nameOf(c.service_id)} />
            <ChecklistCard checklist={c} />
            <SourceList citations={citationsOf(answer.citations, c.service_id)} />
          </div>
        ))}
      </div>
      {(answer.conflicts?.length ?? 0) > 0 && (
        <div className="mt-3">
          <ConflictBox conflicts={answer.conflicts ?? []} serviceName={nameOf} />
        </div>
      )}
      {rest.length > 0 && (
        <div className="mt-3">
          <SourceList citations={rest} />
        </div>
      )}
    </>
  )
}

function AnswerBubble({ answer }: { answer: ChatResponse }) {
  const { lang, t } = useLanguage()
  const situation = answer.situation
  if (answer.status === 'follow_up') {
    // The agent needs one more detail before it can answer; the user simply replies below.
    return (
      <div className="rounded-2xl rounded-tl-sm border-2 border-bd-red bg-bd-red-soft p-4">
        {situation && <SituationChip situation={situation} />}
        <p className="mb-1 text-base font-bold text-bd-red-dark">{t.followUpLabel}</p>
        <p lang="bn" className="text-lg font-bold">
          {answer.follow_up_question || answer.display_text}
        </p>
        <div className="mt-2">
          <PlayAnswerButton text={answer.speech_text} />
        </div>
      </div>
    )
  }

  const isFallback = answer.status !== 'answered'
  const checklists = answer.checklists ?? []
  if (!isFallback && answer.mode === 'multi' && checklists.length > 1) {
    return (
      <div className="rounded-2xl rounded-tl-sm bg-white p-4 shadow-sm">
        {situation && <SituationChip situation={situation} />}
        <MultiAnswer answer={answer} checklists={checklists} />
      </div>
    )
  }
  return (
    <div
      className={`rounded-2xl rounded-tl-sm bg-white p-4 shadow-sm ${isFallback ? 'border-2 border-gray-300' : ''}`}
    >
      {situation && !isFallback && <SituationChip situation={situation} />}
      <div className="mb-2 flex flex-wrap items-center gap-2">
        {answer.service && !isFallback && (
          <ServiceTag name={lang === 'en' ? answer.service.name_en : answer.service.name_bn} />
        )}
        {isFallback && <span className="text-sm font-bold text-gray-600">{t.fallbackLabel}</span>}
      </div>
      {/* The answer itself comes from the Bangla official documents, in every interface language. */}
      <div lang="bn">
      {answer.checklist ? (
        // The checklist card already lists the details, so only the title line of display_text
        // (it also carries the stub's "sample answer" label) and the short spoken answer go on top.
        <>
          {titleLine(answer.display_text) && <RichText text={titleLine(answer.display_text)} />}
          <p className="text-lg leading-relaxed break-words">{answer.speech_text}</p>
        </>
      ) : (
        <RichText text={answer.display_text || answer.speech_text} />
      )}
      </div>
      <div className="mt-2">
        <PlayAnswerButton text={answer.speech_text} />
      </div>
      {answer.checklist && (
        <div className="mt-3">
          <ChecklistCard checklist={answer.checklist} />
        </div>
      )}
      {answer.citations.length > 0 && (
        <div className="mt-3">
          <SourceList citations={answer.citations} />
        </div>
      )}
    </div>
  )
}

export function MessageBubble({ message }: { message: ChatMessage }) {
  const { t, pick } = useLanguage()
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-bd-green px-4 py-3 text-white break-words">
          <span className="sr-only">{t.you}: </span>
          {message.text}
        </div>
      </div>
    )
  }

  if (message.role === 'error') {
    return (
      <div className="flex justify-start" role="alert">
        <div className="max-w-[90%] rounded-2xl rounded-tl-sm border-2 border-bd-red-dark bg-bd-red-soft px-4 py-3 text-bd-red-dark">
          {pick(message.text)}
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[95%]">
        <AnswerBubble answer={message.answer} />
      </div>
    </div>
  )
}

/** After this long, the thinking bubble says the answer is taking longer (Gemini can be slow). */
const SLOW_AFTER_MS = 8_000

export function ThinkingBubble() {
  const { t } = useLanguage()
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    const timer = window.setTimeout(() => setSlow(true), SLOW_AFTER_MS)
    return () => window.clearTimeout(timer)
  }, [])

  return (
    <div className="flex justify-start" role="status" aria-live="polite">
      <div className="flex items-center gap-3 rounded-2xl rounded-tl-sm bg-white px-4 py-3 shadow-sm">
        <span className="flex gap-1" aria-hidden="true">
          <span className="h-2.5 w-2.5 animate-bounce rounded-full bg-bd-green [animation-delay:-0.3s]" />
          <span className="h-2.5 w-2.5 animate-bounce rounded-full bg-bd-green [animation-delay:-0.15s]" />
          <span className="h-2.5 w-2.5 animate-bounce rounded-full bg-bd-red" />
        </span>
        <span className="text-gray-600">{slow ? t.thinkingSlow : t.thinking}</span>
      </div>
    </div>
  )
}
