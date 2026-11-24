// Bangla and English names of the services, from GET /api/v1/services (loaded once per page).

import { useEffect, useState } from 'react'
import type { Language } from '../domain/messages'
import type { Service } from '../domain/types'
import { usePorts } from './portsContext'

export type ServiceNames = (id: string | null | undefined, lang: Language) => string

export function useServiceNames(): ServiceNames {
  const { api } = usePorts()
  const [services, setServices] = useState<Record<string, Service>>({})

  useEffect(() => {
    let cancelled = false
    api
      .listServices()
      .then((list) => {
        if (!cancelled) setServices(Object.fromEntries(list.map((s) => [s.id, s])))
      })
      .catch(() => undefined) // names fall back to the id; the page itself still works
    return () => {
      cancelled = true
    }
  }, [api])

  return (id, lang) => {
    if (!id) return ''
    const service = services[id]
    if (!service) return id
    return lang === 'en' ? service.name_en : service.name_bn
  }
}
