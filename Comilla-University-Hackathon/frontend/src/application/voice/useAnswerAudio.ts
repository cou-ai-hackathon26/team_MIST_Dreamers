// Use case hook: read an answer aloud (FR-APP-04).
// First the server's Bangla MP3 (/api/v1/tts); if that fails, the browser's own Bengali voice.
// The MP3 is kept after the first play, so playing again needs no request.

import { useCallback, useEffect, useRef, useState } from 'react'

import type { AudioPlayer, Playback, VoiceApi } from './voicePorts'

export const SPEECH_OUT_LANG = 'bn-BD'
const TTS_TIMEOUT_MS = 15_000

export type AnswerAudioState = 'idle' | 'loading' | 'playing' | 'error'

export interface AnswerAudio {
  state: AnswerAudioState
  /** Play when idle, stop when loading or playing. */
  toggle: () => void
  dismissError: () => void
}

export function useAnswerAudio(api: VoiceApi, player: AudioPlayer, text: string): AnswerAudio {
  const [state, setState] = useState<AnswerAudioState>('idle')
  const mp3 = useRef<Blob | null>(null)
  const playback = useRef<Playback | null>(null)
  const pending = useRef<AbortController | null>(null)
  const alive = useRef(true)

  useEffect(() => {
    mp3.current = null // a new text needs new audio
  }, [text])

  const ended = useCallback(() => {
    playback.current = null
    if (alive.current) setState((s) => (s === 'playing' ? 'idle' : s))
  }, [])

  const stop = useCallback(() => {
    pending.current?.abort()
    pending.current = null
    playback.current?.stop()
    playback.current = null
    if (alive.current) setState('idle')
  }, [])

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
      pending.current?.abort()
      playback.current?.stop()
    }
  }, [])

  const fallback = useCallback(() => {
    if (!player.canSpeak(SPEECH_OUT_LANG)) {
      setState('error')
      return
    }
    playback.current = player.speak(text, SPEECH_OUT_LANG, ended)
    setState('playing')
  }, [player, text, ended])

  const play = useCallback(async () => {
    setState('loading')
    const controller = new AbortController()
    pending.current = controller
    const timer = setTimeout(() => controller.abort(), TTS_TIMEOUT_MS)
    try {
      mp3.current ??= await api.speech(text, controller.signal)
      if (pending.current !== controller || !alive.current) return // stopped while loading
      playback.current = await player.playMp3(mp3.current, ended)
      setState('playing')
    } catch {
      if (pending.current !== controller || !alive.current) return
      mp3.current = null
      fallback()
    } finally {
      clearTimeout(timer)
      if (pending.current === controller) pending.current = null
    }
  }, [api, player, text, ended, fallback])

  const toggle = useCallback(() => {
    if (state === 'loading' || state === 'playing') stop()
    else void play()
  }, [state, play, stop])

  const dismissError = useCallback(() => setState((s) => (s === 'error' ? 'idle' : s)), [])

  return { state, toggle, dismissError }
}
