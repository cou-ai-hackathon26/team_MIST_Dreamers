// A small "are you sure?" pop-up for actions that cannot be undone (deleting history).
// Focus starts on the safe button ("No"); Esc or a click on the dark background cancels;
// Tab stays inside the pop-up while it is open.

import { useEffect, useId, useRef, type KeyboardEvent, type ReactNode } from 'react'

export function ConfirmDialog({
  title,
  message,
  confirmLabel,
  cancelLabel,
  busy = false,
  busyLabel,
  error,
  onConfirm,
  onCancel,
}: {
  title: string
  message: string
  confirmLabel: string
  cancelLabel: string
  busy?: boolean
  busyLabel?: string
  /** Shown inside the pop-up when the action failed. */
  error?: ReactNode
  onConfirm: () => void
  onCancel: () => void
}) {
  const titleId = useId()
  const messageId = useId()
  const boxRef = useRef<HTMLDivElement>(null)
  const cancelRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const before = document.activeElement as HTMLElement | null
    cancelRef.current?.focus()
    return () => before?.focus() // focus goes back to the button that opened the pop-up
  }, [])

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === 'Escape' && !busy) {
      e.stopPropagation()
      onCancel()
      return
    }
    if (e.key !== 'Tab' || !boxRef.current) return
    const buttons = Array.from(boxRef.current.querySelectorAll<HTMLButtonElement>('button:not([disabled])'))
    if (buttons.length === 0) return
    const first = buttons[0]
    const last = buttons[buttons.length - 1]
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault()
      last.focus()
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault()
      first.focus()
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-3 sm:items-center"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !busy) onCancel()
      }}
    >
      <div
        ref={boxRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={messageId}
        onKeyDown={onKeyDown}
        className="w-full max-w-sm rounded-2xl bg-white p-5 text-gray-900 shadow-xl"
      >
        <h2 id={titleId} className="text-xl font-bold text-bd-red-dark">
          {title}
        </h2>
        <p id={messageId} className="mt-2 text-gray-700">
          {message}
        </p>
        {error && (
          <p role="alert" className="mt-3 rounded-xl bg-bd-red-soft p-2 text-sm text-bd-red-dark">
            {error}
          </p>
        )}
        <div className="mt-4 flex gap-2">
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="min-h-12 flex-1 rounded-xl bg-bd-red px-3 font-bold text-white hover:bg-bd-red-dark disabled:opacity-60"
          >
            {busy && busyLabel ? busyLabel : confirmLabel}
          </button>
          <button
            ref={cancelRef}
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="min-h-12 flex-1 rounded-xl border-2 border-gray-300 bg-white px-3 font-bold text-gray-700 hover:bg-gray-50 disabled:opacity-60"
          >
            {cancelLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
