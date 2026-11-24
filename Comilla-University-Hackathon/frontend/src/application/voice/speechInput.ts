// Port for speech-to-text in the app (FR-APP-03). The Web Speech adapter lives in
// infrastructure/voice/webSpeech.ts; tests or other browsers can pass a different one.

export type SpeechInputError = 'denied' | 'no-speech' | 'network' | 'aborted' | 'failed'

export interface SpeechHandlers {
  /** Everything heard so far (final + interim words), for showing while the user speaks. */
  onTranscript: (text: string) => void
  /** Listening stopped; `text` is the recognised question ('' when nothing was understood). */
  onEnd: (text: string) => void
  onError: (error: SpeechInputError) => void
}

export interface SpeechSession {
  /** Stop listening and deliver what was heard through onEnd. */
  stop: () => void
  /** Stop listening and drop everything (no onEnd). */
  cancel: () => void
}

export interface SpeechInput {
  isSupported: () => boolean
  listen: (lang: string, handlers: SpeechHandlers) => SpeechSession
}
