// Keeps the chosen language, saves it for the next visit and sets <html lang> for screen readers.

import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { LanguageContext, type LanguageState } from '../application/languageContext'
import { usePorts } from '../application/portsContext'
import { TEXT, type Language } from '../domain/messages'

export function LanguageProvider({ children }: { children: ReactNode }) {
  const { preferences } = usePorts()
  const [lang, setLangState] = useState<Language>(() => preferences.loadLanguage() ?? 'bn')

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const setLang = useCallback(
    (next: Language) => {
      preferences.saveLanguage(next)
      setLangState(next)
    },
    [preferences],
  )

  const value = useMemo<LanguageState>(
    () => ({ lang, t: TEXT[lang], setLang, pick: (text) => text[lang] }),
    [lang, setLang],
  )
  return <LanguageContext value={value}>{children}</LanguageContext>
}
