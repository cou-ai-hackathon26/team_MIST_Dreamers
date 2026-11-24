// "Call me" button on the chat page (D2-R2, FR-APP-06, FR-CALL-07). Owned by Ragib.
// Contract: phone is the E.164 number from the session (+8801XXXXXXXXX).
//
// One tap: Ek Call phones this number, and the normal phone conversation starts when it is
// answered. The citizen pays nothing (incoming calls are free). The button then rests for 60 s.

import { useCallMe } from '../../../application/voice/useCallMe'
import { MSG } from '../../../domain/messages'
import { voiceApi } from '../../../infrastructure/voice/voiceApi'
import { CALL_UI, bnNumber } from './voiceText'

export interface CallMeButtonProps {
  phone: string
}

export function CallMeButton({ phone }: CallMeButtonProps) {
  const { state, waitS, errorBn, call } = useCallMe(voiceApi, phone, MSG.ERROR)
  if (!phone) return null

  const calling = state === 'calling'
  const resting = waitS > 0
  const label = calling
    ? CALL_UI.calling
    : resting
      ? `${CALL_UI.waitPrefix} ${bnNumber(waitS)} ${CALL_UI.waitSuffix}`
      : CALL_UI.callMe

  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        onClick={call}
        disabled={calling || resting}
        aria-busy={calling}
        className="flex min-h-12 items-center gap-2 rounded-xl bg-bd-green px-4 font-bold text-white hover:bg-bd-green-dark disabled:cursor-not-allowed disabled:bg-gray-400"
      >
        <PhoneIcon />
        {label}
        {!calling && !resting && <span className="text-sm font-normal text-white/80">{CALL_UI.callMeEn}</span>}
      </button>
      <p role="status" aria-live="polite" className="text-sm font-bold">
        {state === 'called' && <span className="text-bd-green">{CALL_UI.called}</span>}
        {state === 'error' && <span className="text-bd-red-dark">{errorBn}</span>}
      </p>
    </div>
  )
}

function PhoneIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor" aria-hidden="true">
      <path d="M6.6 10.8a15.1 15.1 0 0 0 6.6 6.6l2.2-2.2a1 1 0 0 1 1-.25 11.4 11.4 0 0 0 3.6.57 1 1 0 0 1 1 1V20a1 1 0 0 1-1 1A17 17 0 0 1 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1c0 1.25.2 2.45.57 3.6a1 1 0 0 1-.25 1l-2.22 2.2z" />
    </svg>
  )
}
