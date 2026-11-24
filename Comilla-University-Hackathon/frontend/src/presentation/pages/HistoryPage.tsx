// History: past checklists for this phone number, newest first, from the app and from phone calls
// (FR-APP-05, SRS 3.3, scenario S5). In "delete" mode every checklist gets its own delete button,
// so the user chooses what to remove; each delete is confirmed first (NFR-PRIV-03).

import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useDeleteHistoryItem } from '../../application/useDeleteHistory'
import { useHistory } from '../../application/useHistory'
import { useLanguage } from '../../application/languageContext'
import { useServiceNames } from '../../application/useServiceNames'
import { fill } from '../../domain/messages'
import { localPhone } from '../../domain/phone'
import type { ChecklistRecord } from '../../domain/types'
import { AppHeader } from '../components/AppHeader'
import { ChecklistCard } from '../components/ChecklistCard'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { ServiceTag } from '../components/ServiceTag'
import { SourceList } from '../components/SourceList'
import { useFormat } from '../format'

function TrashIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function HistoryPage({ phone }: { phone: string }) {
  const { checklists, loading, error, reload, forget } = useHistory(phone)
  const { lang, t, pick } = useLanguage()
  const serviceName = useServiceNames()
  const format = useFormat()
  const deletion = useDeleteHistoryItem(phone)

  // "আগের উত্তর মুছে ফেলুন" in the profile menu opens this page in delete mode.
  const fromMenu = Boolean((useLocation().state as { askDelete?: boolean } | null)?.askDelete)
  const [deleting, setDeleting] = useState(fromMenu)
  const [asking, setAsking] = useState<ChecklistRecord | null>(null)

  const hasItems = !loading && !error && checklists.length > 0
  const deleteMode = deleting && hasItems // leaves delete mode by itself when nothing is left

  const describe = (r: ChecklistRecord) => ({
    service: serviceName(r.service_id, lang),
    date: format.dateTime(r.created_at),
  })

  function ask(record: ChecklistRecord) {
    deletion.reset()
    setAsking(record)
  }

  async function confirmDelete() {
    if (!asking?.id) return
    if (await deletion.remove(asking.id)) {
      forget(asking.id)
      setAsking(null)
    }
  }

  return (
    <div className="flex min-h-svh flex-col">
      <AppHeader
        right={
          <Link
            to="/chat"
            className="flex min-h-12 items-center rounded-lg px-3 font-bold text-white hover:bg-bd-green-dark"
          >
            {t.backToChat}
          </Link>
        }
      />

      <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-3 px-4 py-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h1 className="text-2xl font-bold text-bd-green">{t.historyTitle}</h1>
            <p className="text-gray-600">
              {localPhone(phone)}
              {t.historySub && ` · ${t.historySub}`}
            </p>
          </div>
          {hasItems && (
            <button
              type="button"
              onClick={() => {
                deletion.reset()
                setDeleting(!deleteMode)
              }}
              aria-pressed={deleteMode}
              className={
                deleteMode
                  ? 'min-h-12 rounded-xl bg-bd-green px-4 font-bold text-white hover:bg-bd-green-dark'
                  : 'min-h-12 rounded-xl border-2 border-bd-red-dark bg-white px-4 font-bold text-bd-red-dark hover:bg-bd-red-soft'
              }
            >
              {deleteMode ? t.deleteModeDone : t.deleteHistory}
            </button>
          )}
        </div>

        {deleteMode && (
          <p className="rounded-2xl bg-bd-red-soft p-3 text-bd-red-dark">{t.deleteModeHint}</p>
        )}

        {deletion.state === 'done' && (
          <p role="status" className="rounded-2xl bg-bd-green-soft p-3 text-center font-bold text-bd-green">
            {t.deleteDone}
          </p>
        )}

        {loading && (
          <p role="status" className="rounded-2xl bg-white p-4 text-center text-gray-700 shadow-sm">
            {t.historyLoading}
          </p>
        )}

        {!loading && error && (
          <div role="alert" className="rounded-2xl border-2 border-bd-red-dark bg-bd-red-soft p-4 text-bd-red-dark">
            <p>{pick(error)}</p>
            <button
              type="button"
              onClick={reload}
              className="mt-3 min-h-12 rounded-xl bg-bd-red px-5 font-bold text-white hover:bg-bd-red-dark"
            >
              {t.retry}
            </button>
          </div>
        )}

        {!loading && !error && checklists.length === 0 && (
          <p className="rounded-2xl bg-white p-4 text-center text-gray-700 shadow-sm">{t.historyEmpty}</p>
        )}

        {hasItems && (
          <ul className="flex flex-col gap-3">
            {checklists.map((record, i) => (
              <li key={record.id ?? `${record.created_at}-${i}`}>
                <article
                  className={`rounded-2xl bg-white p-4 shadow-sm ${deleteMode ? 'ring-2 ring-bd-red-soft' : ''}`}
                >
                  <div className="mb-3 flex flex-wrap items-center gap-2">
                    <ServiceTag name={serviceName(record.service_id, lang)} />
                    <span className="text-sm text-gray-600">{format.dateTime(record.created_at)}</span>
                    {record.sms_sent && (
                      <span className="rounded-full bg-bd-red-soft px-3 py-1 text-sm font-bold text-bd-red-dark">
                        {t.smsSentBadge}
                      </span>
                    )}
                    {deleteMode && record.id && (
                      <button
                        type="button"
                        onClick={() => ask(record)}
                        aria-label={fill(t.deleteOneLabel, describe(record))}
                        className="ml-auto flex min-h-12 items-center gap-1 rounded-xl bg-bd-red px-4 font-bold text-white hover:bg-bd-red-dark"
                      >
                        <TrashIcon />
                        {t.deleteOne}
                      </button>
                    )}
                  </div>
                  <ChecklistCard checklist={record.checklist} />
                  {record.citations.length > 0 && (
                    <div className="mt-3">
                      <SourceList citations={record.citations} />
                    </div>
                  )}
                </article>
              </li>
            ))}
          </ul>
        )}
      </main>

      {asking && (
        <ConfirmDialog
          title={t.deleteConfirmTitle}
          message={fill(t.deleteConfirm, describe(asking))}
          confirmLabel={t.deleteYes}
          cancelLabel={t.deleteNo}
          busy={deletion.state === 'deleting'}
          busyLabel={t.deleting}
          error={deletion.state === 'error' && deletion.error ? pick(deletion.error) : undefined}
          onConfirm={() => void confirmDelete()}
          onCancel={() => setAsking(null)}
        />
      )}
    </div>
  )
}
