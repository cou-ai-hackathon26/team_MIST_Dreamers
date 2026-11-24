// Hands the ports to the hooks through React context, so hooks never import infrastructure.
// main.tsx wraps the app in <PortsContext value={ports}>.

import { createContext, useContext } from 'react'
import type { Ports } from './ports'

export const PortsContext = createContext<Ports | null>(null)

export function usePorts(): Ports {
  const ports = useContext(PortsContext)
  if (!ports) throw new Error('usePorts must be used inside <PortsContext value={...}>')
  return ports
}
