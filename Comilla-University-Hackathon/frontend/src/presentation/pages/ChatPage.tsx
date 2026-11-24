// Chat screen: messages, text box, example chips and the voice buttons (FR-APP-02, 07, 08; SRS 3.3).
// The three components in ./components/voice/ belong to Ragib; this page only places them.

import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { MAX_QUESTION_LENGTH, useChat } from '../../application/useChat'
import type { Session } from '../../application/useSession'
import { useLanguage } from '../../application/languageContext'
import { fill } from '../../domain/messages'
import { AppHeader } from '../components/AppHeader'
import { ExampleChips } from '../components/ExampleChips'
import { MessageBubble, ThinkingBubble } from '../components/MessageBubble'
import { ProfileMenu } from '../components/ProfileMenu'
import { CallMeButton } from '../components/voice/CallMeButton'
import { MicButton } from '../components/voice/MicButton'

export function ChatPage({ session, phone }: { session: Session; phone: string }) {
  const navigate = useNavigate()
  const { messages, loading, send } = useChat(phone)
  const { t } = useLanguage()
  const [draft, setDraft] = useState('')
  const endRef = useRef<HTMLDivElement>(null)

  // Keep the newest message in view.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length, loading])

  function ask(text: string) {
    if (loading) return
    setDraft('')
    void send(text)
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    ask(draft)
  }

  function changeNumber() {
    session.end()
    navigate('/')
  }

  return (
    <div className="flex min-h-svh flex-col">
      <AppHeader
        right={
          <ProfileMenu session={session} phone={phone} onChangeNumber={changeNumber} />
        }
      />

      <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-3 px-4 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to="/history"
            className="flex min-h-12 items-center rounded-xl border-2 border-bd-green bg-white px-4 font-bold text-bd-green hover:bg-bd-green-soft"
          >
            {t.history}
            {t.historySub && <span className="ml-2 text-sm font-normal text-gray-600">{t.historySub}</span>}
          </Link>
          <CallMeButton phone={phone} />
        </div>

        {messages.length === 0 && !loading && (
          <div className="rounded-2xl bg-white p-4 text-center text-gray-700 shadow-sm">
            {session.name && (
              <p className="mb-1 text-lg font-bold text-bd-green">{fill(t.welcomeName, { name: session.name })}</p>
            )}
            <p>{t.emptyChat}</p>
            {t.answersInBangla && <p className="mt-1 text-sm text-gray-600">{t.answersInBangla}</p>}
          </div>
        )}

        <ul className="flex flex-col gap-3" aria-live="polite">
          {messages.map((m) => (
            <li key={m.id}>
              <MessageBubble message={m} />
            </li>
          ))}
        </ul>
        {loading && <ThinkingBubble />}
        <div ref={endRef} />
      </main>

      <footer className="sticky bottom-0 border-t border-gray-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex w-full max-w-2xl flex-col gap-3 px-4 py-3">
          <ExampleChips onPick={ask} disabled={loading} title={messages.length === 0 ? t.examplesTitle : undefined} />
          <form onSubmit={submit} className="flex items-end gap-2">
            <MicButton onText={ask} disabled={loading} />
            <label htmlFor="question" className="sr-only">
              {t.inputPlaceholder}
            </label>
            <input
              id="question"
              type="text"
              enterKeyHint="send"
              autoComplete="off"
              maxLength={MAX_QUESTION_LENGTH}
              placeholder={t.inputPlaceholder}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              className="min-h-12 min-w-0 flex-1 rounded-xl border-2 border-gray-300 px-4 text-lg outline-none focus:border-bd-green"
            />
            <button
              type="submit"
              disabled={loading || !draft.trim()}
              className="min-h-12 shrink-0 rounded-xl bg-bd-red px-5 text-lg font-bold text-white hover:bg-bd-red-dark disabled:opacity-50"
            >
              {t.send}
            </button>
          </form>
        </div>
      </footer>
    </div>
  )
}
