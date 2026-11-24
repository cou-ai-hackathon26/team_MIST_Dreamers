// Use case: the admin dashboard data, refreshed every 10 seconds (FR-ADM-01, 02, 06; SRS 3.4).

import { useCallback, useEffect, useRef, useState } from 'react'
import type { LocalText } from '../domain/messages'
import { ApiError, errorText, type AdminQuestion, type AdminStats } from '../domain/types'
import { usePorts } from './portsContext'

export const REFRESH_MS = 10_000
const RECENT_LIMIT = 20

export interface AdminData {
  stats: AdminStats | null
  /** Last 20 questions, newest first. */
  recent: AdminQuestion[]
  /** Last 20 unanswered (fallback) questions. */
  unanswered: AdminQuestion[]
  /** True only until the first answer arrives. */
  loading: boolean
  /** Error of the last refresh in both languages, or null. Old data stays on screen. */
  error: LocalText | null
  /** The backend refused the admin token (401). */
  unauthorized: boolean
  updatedAt: Date | null
  refresh(): void
}

export function useAdmin(): AdminData {
  const { api } = usePorts()
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [recent, setRecent] = useState<AdminQuestion[]>([])
  const [unanswered, setUnanswered] = useState<AdminQuestion[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<LocalText | null>(null)
  const [unauthorized, setUnauthorized] = useState(false)
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null)
  const inFlight = useRef(false) // never two refreshes at the same time
  const mounted = useRef(true)

  const load = useCallback(async () => {
    if (inFlight.current) return
    inFlight.current = true
    try {
      const [s, r, u] = await Promise.all([
        api.adminStats(),
        api.adminQuestions({ limit: RECENT_LIMIT }),
        api.adminQuestions({ status: 'fallback', limit: RECENT_LIMIT }),
      ])
      if (!mounted.current) return
      setStats(s)
      setRecent(r)
      setUnanswered(u)
      setError(null)
      setUnauthorized(false)
      setUpdatedAt(new Date())
    } catch (err) {
      if (!mounted.current) return
      setUnauthorized(err instanceof ApiError && err.status === 401)
      setError(errorText(err))
    } finally {
      inFlight.current = false
      if (mounted.current) setLoading(false)
    }
  }, [api])

  useEffect(() => {
    mounted.current = true
    void load()
    const timer = window.setInterval(() => {
      if (!document.hidden) void load() // no requests while the tab is in the background
    }, REFRESH_MS)
    return () => {
      mounted.current = false
      window.clearInterval(timer)
    }
  }, [load])

  const refresh = useCallback(() => void load(), [load])

  return { stats, recent, unanswered, loading, error, unauthorized, updatedAt, refresh }
}
