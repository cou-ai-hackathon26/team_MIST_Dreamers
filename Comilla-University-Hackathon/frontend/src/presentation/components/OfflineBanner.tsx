// A Bangla notice when the device loses the internet, and a short "back online" note when it returns
// (FR-APP-08). Shown on every page; it never blocks the screen.

import { useEffect, useState } from 'react'
import { useLanguage } from '../../application/languageContext'

const BACK_ONLINE_MS = 3_000

export function OfflineBanner() {
  const { t } = useLanguage()
  const [online, setOnline] = useState(() => navigator.onLine)
  const [justBack, setJustBack] = useState(false)

  useEffect(() => {
    let timer: number | undefined
    const goOnline = () => {
      setOnline(true)
      setJustBack(true)
      window.clearTimeout(timer)
      timer = window.setTimeout(() => setJustBack(false), BACK_ONLINE_MS)
    }
    const goOffline = () => {
      setOnline(false)
      setJustBack(false)
    }
    window.addEventListener('online', goOnline)
    window.addEventListener('offline', goOffline)
    return () => {
      window.removeEventListener('online', goOnline)
      window.removeEventListener('offline', goOffline)
      window.clearTimeout(timer)
    }
  }, [])

  if (online && !justBack) return null
  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed inset-x-0 bottom-24 z-30 mx-auto w-[calc(100%-2rem)] max-w-md rounded-xl px-4 py-3 text-center font-bold shadow-lg ${
        online ? 'bg-bd-green text-white' : 'border-2 border-bd-red-dark bg-bd-red-soft text-bd-red-dark'
      }`}
    >
      {online ? t.backOnline : t.offline}
    </div>
  )
}
