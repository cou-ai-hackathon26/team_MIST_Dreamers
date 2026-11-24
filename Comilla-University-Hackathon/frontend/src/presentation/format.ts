// Numbers and dates for the screens: Bangla digits in Bangla (১,২৩৪), normal digits in English (1,234).

import { useLanguage } from '../application/languageContext'
import type { Language } from '../domain/messages'

export interface Format {
  number(n: number): string
  percent(n: number): string
  /** 3210 ms -> "৩.২" / "3.2" (seconds, one decimal). */
  seconds(ms: number): string
  dateTime(iso: string): string
  time(d: Date): string
}

function makeFormat(locale: string): Format {
  const number = new Intl.NumberFormat(locale)
  const oneDecimal = new Intl.NumberFormat(locale, { minimumFractionDigits: 1, maximumFractionDigits: 1 })
  const dateTime = new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' })
  const time = new Intl.DateTimeFormat(locale, { timeStyle: 'medium' })
  return {
    number: (n) => number.format(n),
    percent: (n) => `${oneDecimal.format(n)}%`,
    seconds: (ms) => oneDecimal.format(ms / 1000),
    dateTime: (iso) => {
      const d = new Date(iso)
      return Number.isNaN(d.getTime()) ? '' : dateTime.format(d)
    },
    time: (d) => time.format(d),
  }
}

const FORMATS: Record<Language, Format> = { bn: makeFormat('bn-BD'), en: makeFormat('en-GB') }

export function formatFor(lang: Language): Format {
  return FORMATS[lang]
}

/** The formatters of the current language. */
export function useFormat(): Format {
  return FORMATS[useLanguage().lang]
}
