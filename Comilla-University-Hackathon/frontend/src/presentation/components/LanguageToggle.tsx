// The Bangla ⇄ English button. It shows the language you switch TO, written in that language.

import { useLanguage } from '../../application/languageContext'

export function LanguageToggle({ onDark = false }: { onDark?: boolean }) {
  const { lang, t, setLang } = useLanguage()
  const next = lang === 'bn' ? 'en' : 'bn'
  return (
    <button
      type="button"
      onClick={() => setLang(next)}
      aria-label={t.switchLanguage}
      title={t.switchLanguage}
      lang={next}
      className={
        onDark
          ? 'min-h-12 shrink-0 rounded-lg border border-white/60 px-3 text-sm font-bold text-white hover:bg-bd-green-dark'
          : 'min-h-12 shrink-0 rounded-lg border-2 border-bd-green px-3 text-sm font-bold text-bd-green hover:bg-bd-green-soft'
      }
    >
      {t.otherLanguage}
    </button>
  )
}
