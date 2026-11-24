// Use case hook: ask a question by speaking (FR-APP-03).
// start() listens in Bangla, `transcript` shows the words while the user speaks, and when
// listening ends the recognised text goes to onText (sent as the question, no extra tap).

import { useCallback, useEffect, useRef, useState } from 'react'

import type { SpeechInput, SpeechInputError, SpeechSession } from './speechInput'

export const SPEECH_LANG = 'bn-BD'

export interface VoiceInput {
  supported: boolean
  listening: boolean
  transcript: string
  error: SpeechInputError | null
  start: () => void
  stop: () => void
  cancel: () => void
  dismissError: () => void
}

export function useVoiceInput(speech: SpeechInput, onText: (text: string) => void): VoiceInput {
  const [supported] = useState(() => speech.isSupported())
  const [listening, setListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [error, setError] = useState<SpeechInputError | null>(null)
  const session = useRef<SpeechSession | null>(null)
  const onTextRef = useRef(onText)

  useEffect(() => {
    onTextRef.current = onText
  }, [onText])

  const start = useCallback(() => {
    if (!supported || session.current) return
    setError(null)
    setTranscript('')
    try {
      session.current = speech.listen(SPEECH_LANG, {
        onTranscript: setTranscript,
        onError: (e) => {
          if (e !== 'aborted') setError(e)
        },
        onEnd: (text) => {
          session.current = null
          setListening(false)
          setTranscript('')
          if (text) onTextRef.current(text)
        },
      })
      setListening(true)
    } catch {
      session.current = null
      setError('failed')
    }
  }, [speech, supported])

  const stop = useCallback(() => session.current?.stop(), [])

  const cancel = useCallback(() => {
    session.current?.cancel()
    session.current = null
    setListening(false)
    setTranscript('')
  }, [])

  const dismissError = useCallback(() => setError(null), [])

  useEffect(() => () => session.current?.cancel(), []) // leaving the page stops the mic

  return { supported, listening, transcript, error, start, stop, cancel, dismissError }
}
