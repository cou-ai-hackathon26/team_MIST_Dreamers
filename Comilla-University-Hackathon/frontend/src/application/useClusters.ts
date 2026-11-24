// Use case: the question topics on the admin dashboard and the slow "rebuild" (FR-ADM-03, 04).
// Topics only change on a rebuild, so they are loaded once, not every 10 s like the KPIs.

import { useCallback, useEffect, useRef, useState } from 'react'
import type { LocalText } from '../domain/messages'
import { ApiError, errorText, type QuestionCluster, type RebuildResult } from '../domain/types'
import { usePorts } from './portsContext'

export interface Clusters {
  /** Biggest first, as the API returns them. Empty before the first rebuild. */
  clusters: QuestionCluster[]
  loading: boolean
  rebuilding: boolean
  /** Error in both languages, or null. */
  error: LocalText | null
  unauthorized: boolean
  /** Result of the last rebuild in this session (how many topics, how they were labelled). */
  lastRebuild: RebuildResult | null
  rebuild(): void
}

export function useClusters(): Clusters {
  const { api } = usePorts()
  const [clusters, setClusters] = useState<QuestionCluster[]>([])
  const [loading, setLoading] = useState(true)
  const [rebuilding, setRebuilding] = useState(false)
  const [error, setError] = useState<LocalText | null>(null)
  const [unauthorized, setUnauthorized] = useState(false)
  const [lastRebuild, setLastRebuild] = useState<RebuildResult | null>(null)
  const mounted = useRef(true)
  const busy = useRef(false) // one rebuild at a time, even with fast double clicks

  const fail = useCallback((err: unknown) => {
    if (!mounted.current) return
    setUnauthorized(err instanceof ApiError && err.status === 401)
    setError(errorText(err))
  }, [])

  useEffect(() => {
    mounted.current = true
    api
      .adminClusters()
      .then((list) => {
        if (mounted.current) setClusters(list)
      })
      .catch(fail)
      .finally(() => {
        if (mounted.current) setLoading(false)
      })
    return () => {
      mounted.current = false
    }
  }, [api, fail])

  const rebuild = useCallback(async () => {
    if (busy.current) return
    busy.current = true
    setRebuilding(true)
    setError(null)
    try {
      const result = await api.rebuildClusters()
      const list = await api.adminClusters()
      if (!mounted.current) return
      setLastRebuild(result)
      setClusters(list)
      setUnauthorized(false)
    } catch (err) {
      fail(err)
    } finally {
      busy.current = false
      if (mounted.current) setRebuilding(false)
    }
  }, [api, fail])

  return { clusters, loading, rebuilding, error, unauthorized, lastRebuild, rebuild: () => void rebuild() }
}
