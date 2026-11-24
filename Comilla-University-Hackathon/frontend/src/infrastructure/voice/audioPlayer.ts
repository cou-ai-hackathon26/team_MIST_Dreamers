// AudioPlayer: MP3 through an <audio> element, or the browser's own voice (speechSynthesis).
// Only one sound at a time in the whole app: starting a new one stops the one before.

import type { AudioPlayer, Playback } from '../../application/voice/voicePorts'

let current: Playback | null = null

function takeOver(next: Playback): Playback {
  current?.stop()
  current = next
  return next
}

/** Calls onEnd once, however the sound ends (finished, stopped, error). */
function once(onEnd: () => void): () => void {
  let done = false
  return () => {
    if (done) return
    done = true
    onEnd()
  }
}

function bengaliVoice(lang: string): SpeechSynthesisVoice | undefined {
  const voices = window.speechSynthesis.getVoices()
  const base = lang.slice(0, 2).toLowerCase() // "bn": bn-BD or bn-IN both read Bangla
  return voices.find((v) => v.lang.toLowerCase() === lang.toLowerCase()) ??
    voices.find((v) => v.lang.toLowerCase().startsWith(base))
}

export const audioPlayer: AudioPlayer = {
  async playMp3(audio, onEnd) {
    const url = URL.createObjectURL(audio)
    const element = new Audio(url)
    const finish = once(() => {
      URL.revokeObjectURL(url)
      if (current === playback) current = null
      onEnd()
    })
    const playback: Playback = {
      stop: () => {
        element.pause()
        finish()
      },
    }
    element.onended = finish
    element.onerror = finish
    takeOver(playback)
    try {
      await element.play()
    } catch (err) {
      finish()
      throw err // the hook then tries the browser voice
    }
    return playback
  },

  canSpeak(lang) {
    return 'speechSynthesis' in window && bengaliVoice(lang) !== undefined
  },

  speak(text, lang, onEnd) {
    const synth = window.speechSynthesis
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = lang
    const voice = bengaliVoice(lang)
    if (voice) utterance.voice = voice
    const finish = once(() => {
      if (current === playback) current = null
      onEnd()
    })
    const playback: Playback = {
      stop: () => {
        synth.cancel()
        finish()
      },
    }
    utterance.onend = finish
    utterance.onerror = finish
    takeOver(playback)
    synth.cancel() // drop anything still queued
    synth.speak(utterance)
    return playback
  },
}

// Chrome loads its voice list late; asking once early means canSpeak() is right on the first tap.
if (typeof window !== 'undefined' && 'speechSynthesis' in window) window.speechSynthesis.getVoices()
