import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import type { Ports } from './application/ports'
import { PortsContext } from './application/portsContext'
import { config } from './config'
import { createApiClient } from './infrastructure/apiClient'
import { createAdminSessionStore, createLocalPreferences, createLocalSessionStore } from './infrastructure/storage'
import { LanguageProvider } from './presentation/LanguageProvider'

// Composition root of the app: the only place that builds the real adapters.
const adminSession = createAdminSessionStore()
const ports: Ports = {
  api: createApiClient(
    config.apiUrl,
    config.requestTimeoutMs,
    () => adminSession.load()?.token ?? null,
    config.rebuildTimeoutMs,
  ),
  session: createLocalSessionStore(),
  adminSession,
  preferences: createLocalPreferences(),
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <PortsContext value={ports}>
      <LanguageProvider>
        <App />
      </LanguageProvider>
    </PortsContext>
  </StrictMode>,
)
