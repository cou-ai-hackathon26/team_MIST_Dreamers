// Play button under each answer (D2-R2, FR-APP-04). Owned by Ragib.
// Contract: text is the answer's speech_text; the button reads it aloud.
//
// Tap to play, tap again to stop. Server audio first (/api/v1/tts), the browser's Bengali voice
// if that fails. Starting one answer stops any other that is playing.

import { useEffect } from 'react'

import { useAnswerAudio } from '../../../application/voice/useAnswerAudio'
import { audioPlayer } from '../../../infrastructure/voice/audioPlayer'
import { voiceApi } from '../../../infrastructure/voice/voiceApi'
import { AUDIO_UI } from './voiceText'

export interface PlayAnswerButtonProps {
  text: string
}

const ERROR_SHOWN_MS = 6000

export function PlayAnswerButton({ text }: PlayAnswerButtonProps) {
  const { state, toggle, dismissError } = useAnswerAudio(voiceApi, audioPlayer, text)

  useEffect(() => {
    if (state !== 'error') return
    const timer = setTimeout(dismissError, ERROR_SHOWN_MS)
    return () => clearTimeout(timer)
  }, [state, dismissError])

  if (!text.trim()) return null

  const busy = state === 'loading' || state === 'playing'
  const label = state === 'loading' ? AUDIO_UI.loading : busy ? AUDIO_UI.stop : AUDIO_UI.play

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={toggle}
        aria-label={busy ? AUDIO_UI.stopLabel : AUDIO_UI.playLabel}
        aria-pressed={busy}
        className={`flex min-h-11 items-center gap-2 rounded-full border-2 border-bd-green px-4 font-bold ${
          busy ? 'bg-bd-green text-white hover:bg-bd-green-dark' : 'bg-white text-bd-green hover:bg-bd-green-soft'
        }`}
      >
        {state === 'loading' ? <Spinner /> : busy ? <StopIcon /> : <SpeakerIcon />}
        {label}
      </button>
      {state === 'error' && (
        <p role="status" className="text-sm font-bold text-bd-red-dark">
          {AUDIO_UI.failed}
        </p>
      )}
    </div>
  )
}

function SpeakerIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor" aria-hidden="true">
      <path d="M4 9v6h4l5 4V5L8 9H4z" />
      <path d="M16 8.5a5 5 0 0 1 0 7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <path d="M18.5 6a8.5 8.5 0 0 1 0 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

function StopIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor" aria-hidden="true">
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </svg>
  )
}

function Spinner() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5 animate-spin" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.3" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}
