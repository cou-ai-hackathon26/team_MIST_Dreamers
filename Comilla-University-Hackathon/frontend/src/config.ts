// App settings read from Vite env variables (frontend/.env). Only this file reads import.meta.env.

const DEFAULT_API_URL = 'http://localhost:8000'

function trimSlash(url: string): string {
  return url.replace(/\/+$/, '')
}

export const config = {
  /** Backend base URL without a trailing slash, e.g. http://localhost:8000 */
  apiUrl: trimSlash(import.meta.env.VITE_API_URL || DEFAULT_API_URL),
  /** How long the app waits for one answer before showing an error (the first answer can be slow). */
  requestTimeoutMs: 60_000,
  /** Rebuilding the question clusters embeds every question; the first run also loads the model. */
  rebuildTimeoutMs: 120_000,
} as const
