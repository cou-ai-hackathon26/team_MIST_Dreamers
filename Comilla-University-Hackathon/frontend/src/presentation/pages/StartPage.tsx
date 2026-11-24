// Start screen: the phone number that ties app, calls and history together (FR-APP-01, SRS 3.3).

import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Session } from '../../application/useSession'
import { useLanguage } from '../../application/languageContext'
import { localPhone } from '../../domain/phone'
import { FlagMark } from '../components/AppHeader'
import { LanguageToggle } from '../components/LanguageToggle'

export function StartPage({ session }: { session: Session }) {
  const navigate = useNavigate()
  const { t } = useLanguage()
  const [raw, setRaw] = useState(() => (session.phone ? localPhone(session.phone) : ''))
  const [invalid, setInvalid] = useState(false) // a flag, so the message follows the language

  function submit(e: FormEvent) {
    e.preventDefault()
    if (session.start(raw)) navigate('/chat')
    else setInvalid(true)
  }

  return (
    <main className="flex min-h-svh items-center justify-center bg-bd-green p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-lg sm:p-8">
        <div className="-mt-2 -mr-2 flex justify-end sm:-mt-4 sm:-mr-4">
          <LanguageToggle />
        </div>
        <div className="mb-4 flex justify-center">
          <FlagMark size="lg" />
        </div>
        <h1 className="text-center text-4xl font-bold text-bd-green">{t.appName}</h1>
        <p className="mt-1 text-center text-gray-600">{t.appNameEn}</p>
        <p className="mt-4 text-center text-lg font-bold">{t.tagline}</p>
        <p className="mt-2 text-center text-gray-700">{t.startExplain}</p>

        <form onSubmit={submit} className="mt-6" noValidate>
          <label htmlFor="phone" className="block text-lg font-bold">
            {t.phoneLabel}
            {t.phoneLabelSub && <span className="block text-sm font-normal text-gray-600">{t.phoneLabelSub}</span>}
          </label>
          <input
            id="phone"
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            placeholder={t.phonePlaceholder}
            value={raw}
            onChange={(e) => {
              setRaw(e.target.value)
              setInvalid(false)
            }}
            aria-invalid={invalid ? true : undefined}
            aria-describedby={invalid ? 'phone-error' : undefined}
            className={`mt-2 min-h-14 w-full rounded-xl border-2 px-4 text-xl tracking-wide outline-none focus:border-bd-green ${
              invalid ? 'border-bd-red-dark' : 'border-gray-300'
            }`}
          />
          {invalid && (
            <p id="phone-error" role="alert" className="mt-2 text-base text-bd-red-dark">
              {t.invalidPhone}
            </p>
          )}
          <button
            type="submit"
            className="mt-5 min-h-14 w-full rounded-xl bg-bd-red px-6 text-xl font-bold text-white hover:bg-bd-red-dark"
          >
            {t.start}
            {t.startSub && <span className="ml-2 text-base font-normal text-white/90">{t.startSub}</span>}
          </button>
          <p className="mt-3 text-center text-sm text-gray-600">{t.privacyNote}</p>
        </form>
      </div>
    </main>
  )
}
