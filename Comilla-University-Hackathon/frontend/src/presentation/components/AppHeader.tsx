// Top bar: the flag and the app name, the language button and an optional action on the right.
// On the admin pages the flag and the name link to the start page (`logoTo`).

import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useLanguage } from '../../application/languageContext'
import { LanguageToggle } from './LanguageToggle'

export function FlagMark({ size = 'md' }: { size?: 'md' | 'lg' }) {
  const box = size === 'lg' ? 'h-20 w-28 rounded-md' : 'h-8 w-12 rounded'
  const disc = size === 'lg' ? 'h-11 w-11' : 'h-4 w-4'
  return (
    <span className={`flex shrink-0 items-center justify-center bg-bd-green ${box}`} aria-hidden="true">
      <span className={`block rounded-full bg-bd-red ${disc}`} />
    </span>
  )
}

/** `logoTo`: make the flag and the name a link (used on the admin pages to go to the start page).
 *  Without it the logo is plain, so clicking it never leaves or reloads the page. */
export function AppHeader({ right, logoTo }: { right?: ReactNode; logoTo?: string }) {
  const { t } = useLanguage()
  const logo = (
    <>
      <span className="rounded bg-white p-0.5">
        <FlagMark />
      </span>
      <span className="min-w-0 leading-tight">
        <span className="block text-xl font-bold">{t.appName}</span>
        <span className="block text-sm text-white/80">{t.appNameEn}</span>
      </span>
    </>
  )

  return (
    <header className="sticky top-0 z-10 bg-bd-green text-white shadow">
      <div className="mx-auto flex min-h-14 w-full max-w-2xl items-center gap-2 px-3 py-2 sm:gap-3 sm:px-4">
        {logoTo ? (
          <Link
            to={logoTo}
            aria-label={t.goHome}
            title={t.goHome}
            className="flex min-h-12 min-w-0 flex-1 items-center gap-2 rounded-lg focus-visible:outline-2 focus-visible:outline-white sm:gap-3"
          >
            {logo}
          </Link>
        ) : (
          <div className="flex min-w-0 flex-1 items-center gap-2 sm:gap-3">{logo}</div>
        )}
        <LanguageToggle onDark />
        {right}
      </div>
    </header>
  )
}
