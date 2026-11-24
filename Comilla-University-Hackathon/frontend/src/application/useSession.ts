// Use case: remember who is using the app: the phone number (FR-APP-01) and, if they want, their name.
// The name is saved per number on this device, so it comes back when that number logs in again.
// The API never sees it.

import { useCallback, useState } from 'react'
import { normalizePhone } from '../domain/phone'
import { usePorts } from './portsContext'

export interface Session {
  /** E.164 number (+8801XXXXXXXXX), or null before the user starts. */
  phone: string | null
  /** Normalises and saves the number. Returns false if it is not a valid BD mobile number. */
  start(rawPhone: string): boolean
  /** The name the user typed, or '' if none. */
  name: string
  /** Saves the name (trimmed, at most NAME_MAX_LENGTH characters); an empty name removes it. */
  setName(name: string): void
  /** Logs out: forgets the number. The name stays saved for that number. */
  end(): void
}

export const NAME_MAX_LENGTH = 40

function nameFor(value: string | null): string {
  return (value ?? '').replace(/\s+/g, ' ').trim().slice(0, NAME_MAX_LENGTH)
}

export function useSession(): Session {
  const { session } = usePorts()
  // A stored value is checked again, in case it was saved by an older version or edited by hand.
  const [phone, setPhone] = useState<string | null>(() => normalizePhone(session.loadPhone() ?? ''))
  const [name, setNameState] = useState<string>(() => (phone ? nameFor(session.loadName(phone)) : ''))

  const setName = useCallback(
    (value: string) => {
      if (!phone) return
      const clean = nameFor(value)
      if (clean) session.saveName(phone, clean)
      else session.clearName(phone)
      setNameState(clean)
    },
    [session, phone],
  )

  const start = useCallback(
    (rawPhone: string) => {
      const e164 = normalizePhone(rawPhone)
      if (!e164) return false
      session.savePhone(e164)
      setPhone(e164)
      setNameState(nameFor(session.loadName(e164))) // welcome back, by name
      return true
    },
    [session],
  )

  const end = useCallback(() => {
    session.clearPhone()
    setPhone(null)
    setNameState('')
  }, [session])

  return { phone, start, end, name, setName }
}
