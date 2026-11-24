// Mic button on the chat page (D1-R7, FR-APP-03). Owned by Ragib.
// Contract: when speech is recognised, call onText with the Bangla text; it is sent as the question.
//
// Tap: listens until the user pauses (or taps again). Hold: listens while pressed, sends on release.
// Hidden in browsers without the Web Speech API (Firefox), so the text box is the only input there.

import { useEffect, useRef } from 'react'
import type { KeyboardEvent, PointerEvent } from 'react'

import { useVoiceInput } from '../../../application/voice/useVoiceInput'
import { webSpeech } from '../../../infrastructure/voice/webSpeech'
import { MIC_ERROR, VOICE_UI } from './voiceText'

export interface MicButtonProps {
  onText: (text: string) => void
  disabled?: boolean
}

const HOLD_MS = 500 // a press longer than this is "hold to talk"
const ERROR_SHOWN_MS = 6000

export function MicButton({ onText, disabled = false }: MicButtonProps) {
  const voice = useVoiceInput(webSpeech, onText)
  const pressedAt = useRef<number | null>(null)
  const { listening, error, cancel, dismissError } = voice

  useEffect(() => {
    if (disabled && listening) cancel() // an answer is loading: do not send a second question
  }, [disabled, listening, cancel])

  useEffect(() => {
    if (!error) return
    const timer = setTimeout(dismissError, ERROR_SHOWN_MS)
    return () => clearTimeout(timer)
  }, [error, dismissError])

  if (!voice.supported) return null

  function onPointerDown(e: PointerEvent<HTMLButtonElement>) {
    if (e.button !== 0) return
    if (voice.listening) {
      voice.stop()
      pressedAt.current = null
      return
    }
    voice.start()
    pressedAt.current = Date.now()
  }

  function onPointerUp() {
    const held = pressedAt.current !== null && Date.now() - pressedAt.current > HOLD_MS
    pressedAt.current = null
    if (held) voice.stop()
  }

  function onKeyDown(e: KeyboardEvent<HTMLButtonElement>) {
    if (e.key !== 'Enter' && e.key !== ' ') return
    e.preventDefault()
    if (voice.listening) voice.stop()
    else voice.start()
  }

  const label = voice.listening ? VOICE_UI.micStop : VOICE_UI.micStart
  const message = voice.listening ? voice.transcript || VOICE_UI.listening : error ? MIC_ERROR[error as keyof typeof MIC_ERROR] : ''

  return (
    <div className="relative shrink-0">
      <button
        type="button"
        disabled={disabled}
        aria-label={label}
        aria-pressed={voice.listening}
        title={`${label} (${VOICE_UI.holdHint})`}
        onPointerDown={onPointerDown}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
        onKeyDown={onKeyDown}
        onContextMenu={(e) => e.preventDefault()} // long press on phones would open a menu
        className={
          'flex min-h-12 w-12 touch-none select-none items-center justify-center rounded-xl border-2 disabled:opacity-50 ' +
          (voice.listening
            ? 'animate-pulse border-bd-red bg-bd-red text-white'
            : 'border-bd-green bg-white text-bd-green hover:bg-bd-green-soft')
        }
      >
        <MicIcon />
      </button>
      <p
        aria-live="polite"
        className={
          'absolute bottom-full left-0 mb-2 w-[min(36rem,calc(100vw-2rem))] rounded-xl border-2 bg-white px-4 py-3 text-lg shadow-md ' +
          (message ? '' : 'sr-only ') +
          (error && !voice.listening ? 'border-bd-red-dark text-bd-red-dark' : 'border-bd-green text-gray-900')
        }
      >
        {message}
      </p>
    </div>
  )
}

function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="9" y="2" width="6" height="12" rx="3" />
      <path d="M5 10a7 7 0 0 0 14 0" />
      <path d="M12 17v5" />
      <path d="M8 22h8" />
    </svg>
  )
}
