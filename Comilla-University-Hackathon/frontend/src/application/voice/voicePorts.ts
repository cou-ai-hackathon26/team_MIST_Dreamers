// Ports for answer audio and "Call me" (FR-APP-04, 06). Adapters live in infrastructure/voice/.

/** Ragib's two backend calls (SRS 8). Both throw ApiError with a Bangla message on failure. */
export interface VoiceApi {
  /** POST /api/v1/tts: the text as Bangla MP3. */
  speech(text: string, signal?: AbortSignal): Promise<Blob>
  /** POST /api/v1/callback: Ek Call phones this number; returns the call SID. */
  callMe(phone: string): Promise<string>
}

/** A sound that is playing; stop() ends it early (onEnd is then still called once). */
export interface Playback {
  stop(): void
}

/** Plays one sound at a time: starting a new one stops the one before. */
export interface AudioPlayer {
  playMp3(audio: Blob, onEnd: () => void): Promise<Playback>
  /** True if the browser can read Bangla itself (a Bengali speechSynthesis voice exists). */
  canSpeak(lang: string): boolean
  speak(text: string, lang: string, onEnd: () => void): Playback
}
