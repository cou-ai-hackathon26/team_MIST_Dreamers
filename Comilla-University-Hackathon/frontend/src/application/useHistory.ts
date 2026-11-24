// Use case: show the past checklists of this phone number, from the app and from calls (FR-APP-05).

import { useCallback, useEffect, useState } from 'react'
import type { LocalText } from '../domain/messages'
import { errorText, type ChecklistRecord } from '../domain/types'
import { usePorts } from './portsContext'

export interface History {
  /** Newest first, as the API returns them. */
  checklists: ChecklistRecord[]
  loading: boolean
  /** Error in both languages, or null. */
  error: LocalText | null
  reload(): void
  /** Takes one checklist off the list on screen (after the server deleted it). */
  forget(checklistId: string): void
}

export function useHistory(phone: string): History {
  const { api } = usePorts()
  const [checklists, setChecklists] = useState<ChecklistRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<LocalText | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false // ignore a late answer after the page was left or reloaded
    setLoading(true)
    setError(null)
    api
      .getHistory(phone)
      .then((history) => {
        if (!cancelled) setChecklists(history.checklists)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(errorText(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [api, phone, attempt])

  const reload = useCallback(() => setAttempt((n) => n + 1), [])
  const forget = useCallback(
    (checklistId: string) => setChecklists((list) => list.filter((r) => r.id !== checklistId)),
    [],
  )

  return { checklists, loading, error, reload, forget }
}
