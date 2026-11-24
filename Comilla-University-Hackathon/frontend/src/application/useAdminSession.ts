// Use case: the officer signs in with the admin password and gets a short-lived session (FR-ADM-05).
// The password is only sent once to POST /api/v1/admin/login; the app keeps just the session token.

import { useCallback, useEffect, useState } from 'react'
import type { LocalText } from '../domain/messages'
import { ApiError, errorText } from '../domain/types'
import { usePorts } from './portsContext'

export type LoginProblem = 'wrong' | 'tooMany' | 'disabled' | 'other'

export interface AdminSession {
  loggedIn: boolean
  busy: boolean
  /** Why the last sign-in failed, or null. */
  problem: LoginProblem | null
  /** The error text for problem = 'other'. */
  problemText: LocalText | null
  /** True after the session ran out or the server refused it, so the sign-in page can say so. */
  sessionEnded: boolean
  login(password: string): Promise<void>
  /** `ended` = true when the server refused the session (not a sign-out by the officer). */
  logout(ended?: boolean): void
}

const PROBLEM_BY_STATUS: Record<number, LoginProblem> = { 401: 'wrong', 429: 'tooMany', 503: 'disabled' }

export function useAdminSession(): AdminSession {
  const { api, adminSession } = usePorts()
  const [expiresAt, setExpiresAt] = useState<number | null>(() => adminSession.load()?.expiresAt ?? null)
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<LoginProblem | null>(null)
  const [problemText, setProblemText] = useState<LocalText | null>(null)
  const [sessionEnded, setSessionEnded] = useState(false)

  const logout = useCallback(
    (ended = false) => {
      adminSession.clear()
      setExpiresAt(null)
      setSessionEnded(ended)
    },
    [adminSession],
  )

  // Sign out by itself when the session runs out (default 8 hours).
  useEffect(() => {
    if (expiresAt === null) return
    const timer = window.setTimeout(() => logout(true), Math.max(0, expiresAt - Date.now()))
    return () => window.clearTimeout(timer)
  }, [expiresAt, logout])

  const login = useCallback(
    async (password: string) => {
      setBusy(true)
      setProblem(null)
      setProblemText(null)
      try {
        const session = await api.adminLogin(password)
        const until = Date.parse(session.expires_at)
        adminSession.save(session.token, until)
        setSessionEnded(false)
        setExpiresAt(until)
      } catch (err) {
        const status = err instanceof ApiError ? err.status : 0
        const kind = PROBLEM_BY_STATUS[status] ?? 'other'
        setProblem(kind)
        setProblemText(kind === 'other' ? errorText(err) : null)
      } finally {
        setBusy(false)
      }
    },
    [api, adminSession],
  )

  return { loggedIn: expiresAt !== null, busy, problem, problemText, sessionEnded, login, logout }
}
