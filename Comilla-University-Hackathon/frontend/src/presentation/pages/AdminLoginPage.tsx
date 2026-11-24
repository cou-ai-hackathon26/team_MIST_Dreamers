// Admin sign-in (FR-ADM-05): the officer types the admin password once. It goes to POST /api/v1/admin/login
// and is then forgotten; only the short-lived session token is kept, for this browser tab.

import { useState, type FormEvent } from 'react'
import { useLanguage } from '../../application/languageContext'
import type { AdminSession, LoginProblem } from '../../application/useAdminSession'
import type { UiText } from '../../domain/messages'
import { AppHeader } from '../components/AppHeader'

const PROBLEM_TEXT: Record<Exclude<LoginProblem, 'other'>, keyof UiText> = {
  wrong: 'adminWrongPassword',
  tooMany: 'adminTooMany',
  disabled: 'adminDisabled',
}

export function AdminLoginPage({ session }: { session: AdminSession }) {
  const { t, pick } = useLanguage()
  const [password, setPassword] = useState('')

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!password || session.busy) return
    await session.login(password)
    setPassword('') // never keep the password on screen after an attempt
  }

  const problem = session.problem
  const message =
    problem === 'other' && session.problemText
      ? pick(session.problemText)
      : problem && problem !== 'other'
        ? t[PROBLEM_TEXT[problem]]
        : null

  return (
    <div className="flex min-h-svh flex-col">
      <AppHeader logoTo="/" />
      <main className="flex flex-1 items-start justify-center px-4 py-8 sm:items-center">
        <form onSubmit={submit} className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-lg" noValidate>
          <h1 className="text-2xl font-bold text-bd-green">{t.adminLoginTitle}</h1>
          <p className="mt-1 text-gray-700">{t.adminLoginExplain}</p>

          {session.sessionEnded && !message && (
            <p role="status" className="mt-4 rounded-xl bg-bd-green-soft p-3 text-bd-green">
              {t.adminSessionEnded}
            </p>
          )}

          <label htmlFor="admin-password" className="mt-5 block text-lg font-bold">
            {t.adminPassword}
          </label>
          <input
            id="admin-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={session.busy}
            aria-invalid={message ? true : undefined}
            aria-describedby={message ? 'admin-login-error' : undefined}
            className={`mt-2 min-h-14 w-full rounded-xl border-2 px-4 text-xl outline-none focus:border-bd-green ${
              message ? 'border-bd-red-dark' : 'border-gray-300'
            }`}
          />

          {message && (
            <p id="admin-login-error" role="alert" className="mt-2 text-base text-bd-red-dark">
              {message}
            </p>
          )}

          <button
            type="submit"
            disabled={session.busy || !password}
            className="mt-5 min-h-14 w-full rounded-xl bg-bd-red px-6 text-xl font-bold text-white hover:bg-bd-red-dark disabled:opacity-60"
          >
            {session.busy ? t.adminLoggingIn : t.adminLoginButton}
          </button>
        </form>
      </main>
    </div>
  )
}
