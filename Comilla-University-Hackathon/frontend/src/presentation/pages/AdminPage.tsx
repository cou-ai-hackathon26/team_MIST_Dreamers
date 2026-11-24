// Admin (FR-ADM-01, 02, 05, 06; SRS 3.4; scenario S6): the sign-in, then the dashboard.
// Dashboard order as in SRS 3.4: KPIs, per service, per channel, topics, unanswered, recent activity.
// It refreshes itself every 10 s. If the server refuses the session, the page goes back to the sign-in.

import { useCallback, useEffect } from 'react'
import { useLanguage } from '../../application/languageContext'
import { useAdmin } from '../../application/useAdmin'
import { useAdminSession } from '../../application/useAdminSession'
import { useServiceNames } from '../../application/useServiceNames'
import { AppHeader } from '../components/AppHeader'
import { ClusterList } from '../components/ClusterList'
import { QuestionList } from '../components/QuestionList'
import { ServiceBarChart } from '../components/ServiceBarChart'
import { StatCard } from '../components/StatCard'
import { useFormat } from '../format'
import { AdminLoginPage } from './AdminLoginPage'

export function AdminPage() {
  const session = useAdminSession()
  const { logout } = session
  const sessionEnded = useCallback(() => logout(true), [logout])
  const signOut = useCallback(() => logout(false), [logout])

  if (!session.loggedIn) return <AdminLoginPage session={session} />
  return <AdminDashboard onSessionEnded={sessionEnded} onSignOut={signOut} />
}

function AdminDashboard({ onSessionEnded, onSignOut }: { onSessionEnded: () => void; onSignOut: () => void }) {
  const { stats, recent, unanswered, loading, error, unauthorized, updatedAt } = useAdmin()
  const { t, pick } = useLanguage()
  const format = useFormat()
  const serviceName = useServiceNames()
  const voice = stats?.by_channel.voice ?? 0
  const app = stats?.by_channel.app ?? 0
  const channelTotal = voice + app

  useEffect(() => {
    if (unauthorized) onSessionEnded()
  }, [unauthorized, onSessionEnded])

  return (
    <div className="flex min-h-svh flex-col">
      <AppHeader logoTo="/" />

      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-4 px-4 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-2xl font-bold text-bd-green">{t.adminTitle}</h1>
            <p className="text-gray-600">
              {t.adminSubtitle} · {t.adminAutoRefresh}
              {updatedAt && (
                <span className="block text-sm">
                  {t.adminUpdated}: {format.time(updatedAt)}
                </span>
              )}
            </p>
          </div>
          <div className="flex shrink-0 gap-2">
            <button
              type="button"
              // Reloads the whole page (numbers, questions and topics). The sign-in is kept in this tab.
              onClick={() => window.location.reload()}
              className="min-h-12 rounded-xl border-2 border-bd-green bg-white px-4 font-bold text-bd-green hover:bg-bd-green-soft"
            >
              {t.adminRefresh}
            </button>
            <button
              type="button"
              onClick={onSignOut}
              className="min-h-12 rounded-xl bg-bd-green px-4 font-bold text-white hover:bg-bd-green-dark"
            >
              {t.adminLogout}
            </button>
          </div>
        </div>

        {error && !unauthorized && (
          <p role="alert" className="rounded-2xl border-2 border-bd-red-dark bg-bd-red-soft p-4 text-bd-red-dark">
            {pick(error)}
          </p>
        )}

        {loading && !stats && (
          <p role="status" className="rounded-2xl bg-white p-4 text-center text-gray-700 shadow-sm">
            {t.adminLoading}
          </p>
        )}

        {stats && (
          <>
            <section className="grid grid-cols-2 gap-3 md:grid-cols-5" aria-label={t.adminTitle}>
              <StatCard label={t.kpiTotal} value={format.number(stats.total_questions)} />
              <StatCard label={t.kpiAnswered} value={format.percent(stats.answered_pct)} />
              <StatCard label={t.kpiFallback} value={format.percent(stats.fallback_pct)} />
              <StatCard label={t.kpiLatency} value={format.seconds(stats.avg_latency_ms)} unit={t.secondsShort} />
              <StatCard label={t.kpiCallsToday} value={format.number(stats.calls_today)} />
            </section>

            <div className="grid gap-4 lg:grid-cols-3">
              <div className="lg:col-span-2">
                <ServiceBarChart data={stats.by_service} serviceName={serviceName} />
              </div>
              <section className="rounded-2xl bg-white p-4 shadow-sm">
                <h2 className="mb-3 text-lg font-bold text-bd-green">{t.byChannelTitle}</h2>
                <div className="grid grid-cols-2 gap-3">
                  <StatCard label={t.channelVoice} value={format.number(voice)} />
                  <StatCard label={t.channelApp} value={format.number(app)} />
                </div>
                {channelTotal > 0 && (
                  <p className="mt-3 text-sm text-gray-600">
                    {t.channelVoice} {format.percent((100 * voice) / channelTotal)} · {t.channelApp}{' '}
                    {format.percent((100 * app) / channelTotal)}
                  </p>
                )}
              </section>
            </div>

            <ClusterList onUnauthorized={onSessionEnded} />

            <div className="grid gap-4 lg:grid-cols-2">
              <QuestionList
                title={t.unansweredTitle}
                rows={unanswered}
                empty={t.noUnanswered}
                serviceName={serviceName}
              />
              <QuestionList title={t.recentTitle} rows={recent} empty={t.noQuestions} serviceName={serviceName} />
            </div>
          </>
        )}
      </main>
    </div>
  )
}
