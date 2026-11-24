// What the app needs from the outside world. Hooks use these interfaces only;
// infrastructure/ provides the real implementations, main.tsx plugs them in.

import type { Language } from '../domain/messages'
import type {
  AdminLoginResponse,
  AdminQuestion,
  AdminStats,
  AnswerStatus,
  ChatRequest,
  ChatResponse,
  HistoryResponse,
  QuestionCluster,
  RebuildResult,
  Service,
} from '../domain/types'

/** The Ek Call HTTP API (SRS Section 8). Every method throws ApiError on failure. */
export interface ApiPort {
  chat(request: ChatRequest): Promise<ChatResponse>
  listServices(): Promise<Service[]>
  getHistory(phone: string, limit?: number): Promise<HistoryResponse>
  deleteHistory(phone: string): Promise<boolean>
  /** Deletes one checklist of this number (404 if it is not this number's). */
  deleteChecklist(phone: string, checklistId: string): Promise<boolean>
  /** Admin dashboard (FR-ADM-01, 02). Sends X-Admin-Token when one is configured. */
  adminStats(): Promise<AdminStats>
  adminQuestions(options?: { status?: AnswerStatus; limit?: number }): Promise<AdminQuestion[]>
  /** Admin password -> session token. The token is then sent on every admin request (FR-ADM-05). */
  adminLogin(password: string): Promise<AdminLoginResponse>
  /** Question topics (FR-ADM-04). */
  adminClusters(): Promise<QuestionCluster[]>
  /** Regroups every logged question (FR-ADM-03). Slow: about 15 s, longer on the first run. */
  rebuildClusters(): Promise<RebuildResult>
}

/** Where the phone number of this browser is kept (FR-APP-01). */
export interface SessionStorePort {
  loadPhone(): string | null
  savePhone(phone: string): void
  clearPhone(): void
  /** The user's name for a phone number, optional, kept on this device only (never sent to the server). */
  loadName(phone: string): string | null
  saveName(phone: string, name: string): void
  clearName(phone: string): void
}

/** The admin session token of this browser tab (gone when the tab closes). */
export interface AdminSessionStorePort {
  load(): { token: string; expiresAt: number } | null
  save(token: string, expiresAt: number): void
  clear(): void
}

/** The chosen interface language of this browser. */
export interface PreferencesPort {
  loadLanguage(): Language | null
  saveLanguage(language: Language): void
}

export interface Ports {
  api: ApiPort
  session: SessionStorePort
  adminSession: AdminSessionStorePort
  preferences: PreferencesPort
}
