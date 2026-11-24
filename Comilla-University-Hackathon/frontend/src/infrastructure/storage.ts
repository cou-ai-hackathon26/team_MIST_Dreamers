// SessionStorePort over localStorage. Storage can be blocked (private mode, some in-app browsers),
// so every call is guarded and the app keeps working without it.

import type { AdminSessionStorePort, PreferencesPort, SessionStorePort } from '../application/ports'

const PHONE_KEY = 'ekcall.phone'
const NAMES_KEY = 'ekcall.names' // {"+8801...": "name"}: one name per number on this device

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) window.localStorage.removeItem(key)
    else window.localStorage.setItem(key, value)
  } catch {
    // storage blocked: the app keeps working, the value is just not remembered
  }
}

function readNames(): Record<string, string> {
  try {
    const parsed: unknown = JSON.parse(read(NAMES_KEY) ?? '{}')
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? (parsed as Record<string, string>) : {}
  } catch {
    return {}
  }
}

function writeNames(names: Record<string, string>): void {
  write(NAMES_KEY, Object.keys(names).length ? JSON.stringify(names) : null)
}

export function createLocalSessionStore(): SessionStorePort {
  return {
    loadName: (phone) => {
      const name = readNames()[phone]
      return typeof name === 'string' && name ? name : null
    },
    saveName: (phone, name) => writeNames({ ...readNames(), [phone]: name }),
    clearName: (phone) => {
      const names = readNames()
      delete names[phone]
      writeNames(names)
    },
    loadPhone() {
      try {
        return window.localStorage.getItem(PHONE_KEY)
      } catch {
        return null
      }
    },
    savePhone(phone) {
      try {
        window.localStorage.setItem(PHONE_KEY, phone)
      } catch {
        // not saved: the user types the number again next time
      }
    },
    clearPhone() {
      try {
        window.localStorage.removeItem(PHONE_KEY)
      } catch {
        // nothing to clear
      }
    },
  }
}

// ------------------------------------------------------------------ admin session (FR-ADM-05)

const ADMIN_KEY = 'ekcall.admin'

/** sessionStorage: the admin login ends when the tab closes. Expired sessions read as none. */
export function createAdminSessionStore(now: () => number = Date.now): AdminSessionStorePort {
  return {
    load() {
      try {
        const raw = window.sessionStorage.getItem(ADMIN_KEY)
        if (!raw) return null
        const parsed = JSON.parse(raw) as { token?: unknown; expiresAt?: unknown }
        if (typeof parsed.token !== 'string' || typeof parsed.expiresAt !== 'number') return null
        return parsed.expiresAt > now() ? { token: parsed.token, expiresAt: parsed.expiresAt } : null
      } catch {
        return null
      }
    },
    save(token, expiresAt) {
      try {
        window.sessionStorage.setItem(ADMIN_KEY, JSON.stringify({ token, expiresAt }))
      } catch {
        // not kept: the officer signs in again after a reload
      }
    },
    clear() {
      try {
        window.sessionStorage.removeItem(ADMIN_KEY)
      } catch {
        // nothing to clear
      }
    },
  }
}

// ------------------------------------------------------------------ language

const LANGUAGE_KEY = 'ekcall.language'

export function createLocalPreferences(): PreferencesPort {
  return {
    loadLanguage() {
      try {
        const value = window.localStorage.getItem(LANGUAGE_KEY)
        return value === 'bn' || value === 'en' ? value : null
      } catch {
        return null
      }
    },
    saveLanguage(language) {
      try {
        window.localStorage.setItem(LANGUAGE_KEY, language)
      } catch {
        // not kept: the app starts in Bangla next time
      }
    },
  }
}
