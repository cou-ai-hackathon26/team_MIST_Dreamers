// The round profile button in the chat header and its panel: name (optional, this device only),
// mobile number, history, a shortcut to delete history (on the history page) and, at the bottom, "change number".
// The panel closes on a second click of the button, a click outside or the Esc key.

import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useLanguage } from '../../application/languageContext'
import { NAME_MAX_LENGTH, type Session } from '../../application/useSession'
import { localPhone } from '../../domain/phone'

function initial(name: string): string {
  return Array.from(name.trim())[0]?.toUpperCase() ?? ''
}

function PersonIcon({ className }: { className: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4 4-7 8-7s8 3 8 7" strokeLinecap="round" />
    </svg>
  )
}

function Avatar({ name, large = false }: { name: string; large?: boolean }) {
  const size = large ? 'h-12 w-12 text-xl' : 'h-10 w-10 text-lg'
  const letter = initial(name)
  return (
    <span
      className={`flex shrink-0 items-center justify-center rounded-full bg-white font-bold text-bd-green ${size}`}
      aria-hidden="true"
    >
      {letter || <PersonIcon className={large ? 'h-7 w-7' : 'h-6 w-6'} />}
    </span>
  )
}

export function ProfileMenu({
  session,
  phone,
  onChangeNumber,
}: {
  session: Session
  phone: string
  onChangeNumber: () => void
}) {
  const { t } = useLanguage()
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [draftName, setDraftName] = useState('')
  const rootRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const panelId = useId()

  function close() {
    setOpen(false)
    setEditing(false)
  }

  function toggle() {
    if (open) {
      close()
      return
    }
    setOpen(true)
  }

  // Close on a click or tap outside, and on Esc (focus goes back to the button).
  useEffect(() => {
    if (!open) return
    const onPointer = (e: MouseEvent | TouchEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) close()
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        close()
        buttonRef.current?.focus()
      }
    }
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('touchstart', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('touchstart', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  function startEditing() {
    setDraftName(session.name)
    setEditing(true)
  }

  function saveName(e: FormEvent) {
    e.preventDefault()
    session.setName(draftName)
    setEditing(false)
  }

  const linkClass =
    'flex min-h-12 w-full items-center rounded-xl px-3 text-left font-bold text-bd-green hover:bg-bd-green-soft'

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        onClick={toggle}
        aria-label={t.profileOpen}
        title={t.profileOpen}
        aria-expanded={open}
        aria-controls={panelId}
        className="flex min-h-12 min-w-12 items-center justify-center rounded-full hover:bg-bd-green-dark focus-visible:outline-2 focus-visible:outline-white"
      >
        <Avatar name={session.name} />
      </button>

      {open && (
        <div
          id={panelId}
          role="dialog"
          aria-label={t.profileOpen}
          className="absolute top-full right-0 z-20 mt-2 w-[min(20rem,calc(100vw-1.5rem))] rounded-2xl bg-white p-3 text-gray-900 shadow-xl ring-1 ring-black/5"
        >
          {/* who */}
          <div className="flex items-center gap-3 rounded-xl bg-bd-green-soft p-3">
            <span className="rounded-full ring-2 ring-bd-green">
              <Avatar name={session.name} large />
            </span>
            <div className="min-w-0 flex-1">
              {session.name ? (
                <p className="truncate text-lg font-bold">{session.name}</p>
              ) : (
                <p className="text-gray-600">{t.profileName}</p>
              )}
              <p className="text-sm text-gray-700">
                {t.profilePhone}: <span className="font-bold">{localPhone(phone)}</span>
              </p>
            </div>
          </div>

          {/* name */}
          {editing ? (
            <form onSubmit={saveName} className="mt-3">
              <label htmlFor={`${panelId}-name`} className="block font-bold">
                {t.profileName}
              </label>
              <input
                id={`${panelId}-name`}
                value={draftName}
                maxLength={NAME_MAX_LENGTH}
                autoComplete="name"
                placeholder={t.profileNamePlaceholder}
                onChange={(e) => setDraftName(e.target.value)}
                autoFocus
                className="mt-1 min-h-12 w-full rounded-xl border-2 border-gray-300 px-3 text-lg outline-none focus:border-bd-green"
              />
              <p className="mt-1 text-xs text-gray-600">{t.profileNameNote}</p>
              <div className="mt-2 flex gap-2">
                <button
                  type="submit"
                  className="min-h-12 flex-1 rounded-xl bg-bd-green px-3 font-bold text-white hover:bg-bd-green-dark"
                >
                  {t.profileSave}
                </button>
                <button
                  type="button"
                  onClick={() => setEditing(false)}
                  className="min-h-12 flex-1 rounded-xl border-2 border-gray-300 px-3 font-bold text-gray-700 hover:bg-gray-50"
                >
                  {t.profileCancel}
                </button>
              </div>
            </form>
          ) : (
            <button type="button" onClick={startEditing} className={`${linkClass} mt-2`}>
              {session.name ? t.profileEditName : t.profileAddName}
            </button>
          )}

          {/* history */}
          <Link to="/history" onClick={close} className={linkClass}>
            {t.history}
          </Link>

          {/* delete history: done on the history page, where the user sees what will be deleted */}
          <Link
            to="/history"
            state={{ askDelete: true }}
            onClick={close}
            className="flex min-h-12 w-full items-center rounded-xl px-3 text-left font-bold text-gray-700 hover:bg-gray-50"
          >
            {t.deleteHistory}
          </Link>

          {/* change number, last */}
          <div className="mt-2 border-t border-gray-200 pt-2">
            <button
              type="button"
              onClick={() => {
                close()
                onChangeNumber()
              }}
              className="flex min-h-12 w-full items-center rounded-xl px-3 text-left font-bold text-bd-red-dark hover:bg-bd-red-soft"
            >
              {t.changeNumber}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
