// ApiPort over fetch. Turns every failure into an ApiError with a Bangla message (FR-APP-08).

import type { ApiPort } from '../application/ports'
import { MSG } from '../domain/messages'
import {
  ApiError,
  type AdminLoginResponse,
  type AdminQuestion,
  type AdminStats,
  type AnswerStatus,
  type ChatRequest,
  type ChatResponse,
  type HistoryResponse,
  type QuestionCluster,
  type RebuildResult,
  type Service,
} from '../domain/types'

interface ErrorBody {
  error?: { code?: string; message_bn?: string; message_en?: string }
}

/**
 * @param adminToken returns the current admin session token (or null). It is read on every admin
 *   request, so a new login or a logout takes effect at once. The admin password is never stored here.
 */
export function createApiClient(
  baseUrl: string,
  timeoutMs: number,
  adminToken: () => string | null = () => null,
  rebuildTimeoutMs = timeoutMs,
): ApiPort {
  async function request<T>(path: string, init: RequestInit = {}, waitMs = timeoutMs): Promise<T> {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), waitMs)
    let res: Response
    try {
      res = await fetch(`${baseUrl}${path}`, {
        ...init,
        headers: { 'Content-Type': 'application/json', ...init.headers },
        signal: controller.signal,
      })
    } catch (err) {
      // Server down, no network, CORS blocked, or our timeout fired.
      const code = controller.signal.aborted ? 'TIMEOUT' : 'NETWORK'
      throw new ApiError(code, MSG.ERROR, 0, String(err))
    } finally {
      clearTimeout(timer)
    }

    if (!res.ok) {
      const body = (await res.json().catch(() => ({}))) as ErrorBody
      throw new ApiError(
        body.error?.code ?? `HTTP_${res.status}`,
        body.error?.message_bn || MSG.ERROR,
        res.status,
        body.error?.message_en,
      )
    }
    return (await res.json()) as T
  }

  const phonePath = (phone: string) => `/api/v1/conversations/${encodeURIComponent(phone)}`
  const adminHeaders = (): Record<string, string> => {
    const token = adminToken()
    return token ? { Authorization: `Bearer ${token}` } : {}
  }

  return {
    chat: (body: ChatRequest) =>
      request<ChatResponse>('/api/v1/chat', {
        method: 'POST',
        body: JSON.stringify({ channel: 'app', ...body }),
      }),
    listServices: () => request<Service[]>('/api/v1/services'),
    getHistory: (phone: string, limit = 50) =>
      request<HistoryResponse>(`${phonePath(phone)}?limit=${limit}`),
    deleteHistory: async (phone: string) =>
      (await request<{ deleted: boolean }>(phonePath(phone), { method: 'DELETE' })).deleted,
    deleteChecklist: async (phone: string, checklistId: string) =>
      (
        await request<{ deleted: boolean }>(`${phonePath(phone)}/checklists/${encodeURIComponent(checklistId)}`, {
          method: 'DELETE',
        })
      ).deleted,
    adminLogin: (password: string) =>
      request<AdminLoginResponse>('/api/v1/admin/login', { method: 'POST', body: JSON.stringify({ password }) }),
    adminStats: () => request<AdminStats>('/api/v1/admin/stats', { headers: adminHeaders() }),
    adminQuestions: async (options: { status?: AnswerStatus; limit?: number } = {}) => {
      const query = new URLSearchParams({ limit: String(options.limit ?? 20) })
      if (options.status) query.set('status', options.status)
      const body = await request<{ questions: AdminQuestion[] }>(`/api/v1/admin/questions?${query}`, {
        headers: adminHeaders(),
      })
      return body.questions
    },
    adminClusters: async () =>
      (await request<{ clusters: QuestionCluster[] }>('/api/v1/admin/clusters', { headers: adminHeaders() })).clusters,
    rebuildClusters: () =>
      request<RebuildResult>(
        '/api/v1/admin/clusters/rebuild',
        { method: 'POST', headers: adminHeaders() },
        rebuildTimeoutMs,
      ),
  }
}
