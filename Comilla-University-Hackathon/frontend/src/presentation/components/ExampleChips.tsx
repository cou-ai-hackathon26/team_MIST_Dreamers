// Example questions for the main services (FR-APP-07). Typed exactly like
// backend/data/questions/demo_questions.txt, so they hit the pre-warmed answer cache.
// The two situation examples (sprint S10, S12) describe a life, not a service name; such answers
// are never cached.

import { useLanguage } from '../../application/languageContext'
import type { UiText } from '../../domain/messages'

// The questions stay in Bangla in both languages (they must match the cache); only the labels change.
const EXAMPLES: { label: keyof UiText; question: string }[] = [
  { label: 'chipOldAge', question: 'আমার বয়স ৬৭। আমি কি বয়স্ক ভাতা পাবো? কী কী লাগবে?' },
  { label: 'chipWidow', question: 'বিধবা ভাতার জন্য কী লাগে?' },
  { label: 'chipNid', question: 'NID-te namer banan bhul, ki korbo?' },
  { label: 'chipBirth', question: 'জন্ম নিবন্ধন করতে কী কী কাগজ লাগে?' },
  { label: 'chipPassport', question: 'ই-পাসপোর্ট করতে কত টাকা লাগে?' },
  { label: 'chipDisability', question: 'প্রতিবন্ধী ভাতা পেতে কী কী কাগজ লাগে?' },
  {
    label: 'chipSituationWidow',
    question: 'আমার স্বামী গত বছর মারা গেছেন, দুটো বাচ্চা নিয়ে খুব কষ্টে আছি। সরকার থেকে কোনো সাহায্য পাওয়া যায়?',
  },
  { label: 'chipSituationMixed', question: 'আমি বিধবা, বয়স ৬৬। বয়স্ক ভাতা আর বিধবা ভাতা দুটোই কি একসাথে পাবো?' },
]

export function ExampleChips({
  onPick,
  disabled,
  title,
}: {
  onPick: (question: string) => void
  disabled?: boolean
  title?: string
}) {
  const { t } = useLanguage()
  return (
    <div>
      {title && <p className="mb-2 text-base font-bold text-bd-green">{title}</p>}
      <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 [scrollbar-width:none] sm:flex-wrap sm:overflow-visible [&::-webkit-scrollbar]:hidden">
        {EXAMPLES.map((e) => (
          <button
            key={e.label}
            type="button"
            title={e.question}
            disabled={disabled}
            onClick={() => onPick(e.question)}
            className="min-h-12 shrink-0 rounded-full border-2 border-bd-green bg-white px-4 text-base font-bold text-bd-green hover:bg-bd-green-soft disabled:opacity-50"
          >
            {t[e.label]}
          </button>
        ))}
      </div>
    </div>
  )
}
