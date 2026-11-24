// Use case hook: "Call me" (FR-APP-06, FR-CALL-07).
// Asks the backend to phone this number. After a call is placed the button rests for 60 s, the
// same limit the server enforces (a second request inside it would get 429 RATE_LIMITED).

import { useCallback, useEffect, useRef, useState } from 'react'

import { ApiError } from '../../domain/types'
import type { VoiceApi } from './voicePorts'

export const CALL_COOLDOWN_S = 60

export type CallMeState = 'idle' | 'calling' | 'called' | 'error'

export interface CallMe {
  state: CallMeState
  /** Seconds until the next call is allowed (0 = allowed now). */
  waitS: number
  /** Bangla error from the server (e.g. RATE_LIMITED) or the general error message. */
  errorBn: string
  call: () => void
}

export function useCallMe(api: VoiceApi, phone: string, fallbackErrorBn: string): CallMe {
  const [state, setState] = useState<CallMeState>('idle')
  const [readyAt, setReadyAt] = useState(0)
  const [now, setNow] = useState(() => Date.now())
  const [errorBn, setErrorBn] = useState('')
  const alive = useRef(true)

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
    }
  }, [])

  const waitS = Math.max(0, Math.ceil((readyAt - now) / 1000))

  useEffect(() => {
    if (readyAt <= Date.now()) return
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [readyAt])

  const call = useCallback(() => {
    if (state === 'calling' || waitS > 0 || !phone) return
    setState('calling')
    setErrorBn('')
    api.callMe(phone).then(
      () => {
        if (!alive.current) return
        setNow(Date.now())
        setReadyAt(Date.now() + CALL_COOLDOWN_S * 1000)
        setState('called')
      },
      (err: unknown) => {
        if (!alive.current) return
        const limited = err instanceof ApiError && err.status === 429
        if (limited) {
          setNow(Date.now())
          setReadyAt(Date.now() + CALL_COOLDOWN_S * 1000)
        }
        setErrorBn(err instanceof ApiError ? err.messageBn : fallbackErrorBn)
        setState('error')
      },
    )
  }, [api, phone, state, waitS, fallbackErrorBn])

  // "Call placed" turns back into "ready" when the rest time is over (derived, no extra render).
  const shown: CallMeState = state === 'called' && waitS === 0 ? 'idle' : state
  return { state: shown, waitS, errorBn, call }
}
