// Question topics found by K-Means (FR-ADM-03, 04; SRS 3.4; scenario S6): label, size and 3 examples,
// biggest first, with a "rebuild" button. The share bar is one hue; the number is always written too.

import { useEffect } from 'react'
import { useLanguage } from '../../application/languageContext'
import { useClusters } from '../../application/useClusters'
import { fill } from '../../domain/messages'
import { useFormat } from '../format'

/** `onUnauthorized`: the server refused the admin session; the page goes back to the sign-in. */
export function ClusterList({ onUnauthorized }: { onUnauthorized: () => void }) {
  const { clusters, loading, rebuilding, error, unauthorized, lastRebuild, rebuild } = useClusters()
  const { t, pick } = useLanguage()
  const format = useFormat()
  const total = clusters.reduce((sum, c) => sum + c.size, 0)

  useEffect(() => {
    if (unauthorized) onUnauthorized()
  }, [unauthorized, onUnauthorized])

  return (
    <section className="rounded-2xl bg-white p-4 shadow-sm" aria-busy={rebuilding}>
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-lg font-bold text-bd-green">{t.clustersTitle}</h2>
          <p className="text-sm text-gray-600">{t.clustersExplain}</p>
        </div>
        <button
          type="button"
          onClick={rebuild}
          disabled={rebuilding}
          className="min-h-12 shrink-0 rounded-xl bg-bd-red px-4 font-bold text-white hover:bg-bd-red-dark disabled:opacity-60"
        >
          {rebuilding ? t.clustersRebuilding : t.clustersRebuild}
        </button>
      </div>

      {error && !unauthorized && (
        <p role="alert" className="mb-3 rounded-xl border-2 border-bd-red-dark bg-bd-red-soft p-3 text-bd-red-dark">
          {pick(error)}
        </p>
      )}

      {lastRebuild && !rebuilding && (
        <p role="status" className="mb-3 text-sm text-gray-700">
          {fill(t.clustersSummary, {
            questions: format.number(lastRebuild.questions),
            clusters: format.number(lastRebuild.clusters),
          })}{' '}
          · {lastRebuild.labelled_by === 'llm' ? t.clustersByLlm : t.clustersByKeywords}
        </p>
      )}

      {loading ? (
        <p className="text-gray-600">{t.clustersLoading}</p>
      ) : clusters.length === 0 ? (
        <p className="text-gray-600">{t.clustersEmpty}</p>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2">
          {clusters.map((c, i) => {
            const share = total ? (100 * c.size) / total : 0
            return (
              <li key={c.id ?? i} className="rounded-xl border border-gray-200 p-3">
                <div className="flex items-baseline justify-between gap-2">
                  <h3 lang="bn" className="min-w-0 font-bold break-words">
                    {c.label}
                  </h3>
                  <span className="shrink-0 text-sm text-gray-700">
                    {fill(t.clusterSize, { n: format.number(c.size) })}
                  </span>
                </div>
                <div
                  className="mt-2 h-2 w-full rounded-full bg-bd-green-soft"
                  role="img"
                  aria-label={format.percent(share)}
                >
                  <div className="h-2 rounded-full bg-bd-green" style={{ width: `${share}%` }} />
                </div>
                <p className="mt-1 text-right text-xs text-gray-600">{format.percent(share)}</p>
                {c.examples.length > 0 && (
                  <div className="mt-1">
                    <p className="text-sm font-bold text-gray-600">{t.clustersExamples}</p>
                    <ul lang="bn" className="ml-5 list-disc text-sm text-gray-800">
                      {c.examples.slice(0, 3).map((example, j) => (
                        <li key={j} className="break-words">
                          {example}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
