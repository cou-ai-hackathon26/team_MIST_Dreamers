// Speech-to-text in the browser with the Web Speech API (FR-APP-03).
// Chrome and Edge support it (prefixed as webkitSpeechRecognition); Firefox does not, so callers
// check isSupported() and hide the mic. Chrome sends the audio to Google for recognition, so it
// needs an internet connection and a secure page (https or localhost).

import type { SpeechInput, SpeechInputError, SpeechSession, SpeechHandlers } from '../../application/voice/speechInput'

// The parts of the Web Speech API used here (not in TypeScript's DOM types).
interface RecognitionAlternative {
  transcript: string
}
interface RecognitionResult {
  readonly isFinal: boolean
  readonly length: number
  [index: number]: RecognitionAlternative
}
interface RecognitionEvent {
  readonly results: { readonly length: number; [index: number]: RecognitionResult }
}
interface RecognitionErrorEvent {
  readonly error: string
}
interface Recognition {
  lang: string
  continuous: boolean
  interimResults: boolean
  maxAlternatives: number
  onresult: ((event: RecognitionEvent) => void) | null
  onerror: ((event: RecognitionErrorEvent) => void) | null
  onend: (() => void) | null
  start(): void
  stop(): void
  abort(): void
}
type RecognitionConstructor = new () => Recognition

// Seconds of silence after the last words that end the question. Chrome's own end-of-speech is
// very short, so continuous mode + this timer keeps two-sentence questions whole.
const END_SILENCE_MS = 2000

function recognitionClass(): RecognitionConstructor | undefined {
  const w = window as unknown as { SpeechRecognition?: RecognitionConstructor; webkitSpeechRecognition?: RecognitionConstructor }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition
}

function toError(code: string): SpeechInputError {
  switch (code) {
    case 'not-allowed':
    case 'service-not-allowed':
      return 'denied'
    case 'no-speech':
      return 'no-speech'
    case 'network':
      return 'network'
    case 'aborted':
      return 'aborted'
    default:
      return 'failed'
  }
}

export const webSpeech: SpeechInput = {
  isSupported: () => typeof window !== 'undefined' && recognitionClass() !== undefined,

  listen(lang: string, handlers: SpeechHandlers): SpeechSession {
    const Ctor = recognitionClass()
    if (!Ctor) throw new Error('speech recognition is not supported')
    const recognition = new Ctor()
    recognition.lang = lang
    recognition.continuous = true
    recognition.interimResults = true
    recognition.maxAlternatives = 1

    let finalText = ''
    let silenceTimer: ReturnType<typeof setTimeout> | undefined
    const clearSilence = () => silenceTimer !== undefined && clearTimeout(silenceTimer)

    recognition.onresult = (event) => {
      let done = ''
      let interim = ''
      for (let i = 0; i < event.results.length; i++) {
        const result = event.results[i]
        if (result.isFinal) done += result[0].transcript
        else interim += result[0].transcript
      }
      finalText = done
      handlers.onTranscript(tidy(done + ' ' + interim))
      clearSilence()
      silenceTimer = setTimeout(() => recognition.stop(), END_SILENCE_MS)
    }
    recognition.onerror = (event) => handlers.onError(toError(event.error))
    recognition.onend = () => {
      clearSilence()
      handlers.onEnd(tidy(finalText))
    }
    recognition.start()

    return {
      stop: () => recognition.stop(), // finishes and delivers what was heard
      cancel: () => {
        clearSilence()
        recognition.onend = null
        recognition.abort()
      },
    }
  },
}

function tidy(text: string): string {
  return text.replace(/\s+/g, ' ').trim()
}
