// Use case: delete ONE checklist from this number's history, chosen by the user (NFR-PRIV-03).
// Uses DELETE /api/v1/conversations/{phone}/checklists/{id}. Anonymous question logs (hashed number)
// stay for the statistics.

import { useCallback, useState } from 'react'
import type { LocalText } from '../domain/messages'
import { ApiError, errorText } from '../domain/types'
import { usePorts } from './portsContext'

export type DeleteState = 'idle' | 'deleting' | 'done' | 'error'

export interface DeleteHistoryItem {
  state: DeleteState
  error: LocalText | null
  /** Resolves to true when the server deleted that checklist. */
  remove(checklistId: string): Promise<boolean>
  reset(): void
}

export function useDeleteHistoryItem(phone: string): DeleteHistoryItem {
  const { api } = usePorts()
  const [state, setState] = useState<DeleteState>('idle')
  const [error, setError] = useState<LocalText | null>(null)

  const remove = useCallback(
    async (checklistId: string) => {
      setState('deleting')
      setError(null)
      try {
        await api.deleteChecklist(phone, checklistId)
        setState('done')
        return true
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          setState('done') // already gone (deleted in another tab): same result for the user
          return true
        }
        setError(errorText(err))
        setState('error')
        return false
      }
    },
    [api, phone],
  )

  const reset = useCallback(() => {
    setState('idle')
    setError(null)
  }, [])

  return { state, error, remove, reset }
}
