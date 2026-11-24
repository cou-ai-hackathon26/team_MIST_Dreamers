// Bangla texts of the voice pieces in the app (mic, answer audio, "Call me").
// Kept here, in the voice folder, so these components stay in one owner's files.

import type { SpeechInputError } from '../../../application/voice/speechInput'

export const VOICE_UI = {
  micStart: 'বলে প্রশ্ন করুন',
  micStop: 'শোনা শেষ করুন',
  listening: 'শুনছি… বলুন',
  holdHint: 'চেপে ধরে বলুন, অথবা একবার চাপ দিয়ে বলুন',
} as const

export const MIC_ERROR: Record<Exclude<SpeechInputError, 'aborted'>, string> = {
  denied: 'মাইক্রোফোন ব্যবহারের অনুমতি দিন (ঠিকানার ঘরের পাশের আইকনে চাপ দিন), তারপর আবার চেষ্টা করুন।',
  'no-speech': 'কিছু শোনা যায়নি। মাইকে চাপ দিয়ে আবার বলুন।',
  network: 'কথা বুঝতে ইন্টারনেট লাগে। সংযোগ দেখে আবার চেষ্টা করুন।',
  failed: 'কথা বোঝা যায়নি। আবার বলুন অথবা লিখে প্রশ্ন করুন।',
}

export const AUDIO_UI = {
  play: 'শুনুন',
  stop: 'থামুন',
  loading: 'আনছি…',
  playLabel: 'উত্তরটি শুনুন',
  stopLabel: 'শোনা বন্ধ করুন',
  failed: 'এখন শোনানো যাচ্ছে না। উত্তরটি পড়ে নিন।',
} as const

export const CALL_UI = {
  callMe: 'আমাকে কল করুন',
  callMeEn: 'Call me',
  calling: 'কল করা হচ্ছে…',
  called: 'আপনার ফোনে কল যাচ্ছে। ফোনটি ধরে প্রশ্ন করুন।',
  waitPrefix: 'আবার কল',
  waitSuffix: 'সেকেন্ড পরে',
} as const

const BN_DIGITS = '০১২৩৪৫৬৭৮৯'

/** 45 -> "৪৫" */
export function bnNumber(n: number): string {
  return String(n).replace(/\d/g, (d) => BN_DIGITS[Number(d)])
}
