// The interface language (Bangla by default, English on request). Components read texts with `t`;
// a text in both languages (an error already on screen) is shown with `pick`.

import { createContext, useContext } from 'react'
import { TEXT, type Language, type LocalText, type UiText } from '../domain/messages'

export interface LanguageState {
  lang: Language
  /** Texts of the current language. */
  t: UiText
  setLang(lang: Language): void
  pick(text: LocalText): string
}

export const LanguageContext = createContext<LanguageState>({
  lang: 'bn',
  t: TEXT.bn,
  setLang: () => undefined,
  pick: (text) => text.bn,
})

export function useLanguage(): LanguageState {
  return useContext(LanguageContext)
}
