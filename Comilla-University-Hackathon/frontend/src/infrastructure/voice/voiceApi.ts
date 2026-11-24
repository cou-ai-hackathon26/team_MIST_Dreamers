// VoiceApi over fetch: /api/v1/tts and /api/v1/callback (SRS 8). Errors become ApiError with the
// server's Bangla message, the same way apiClient.ts does it for the other endpoints.

import type { VoiceApi } from '../../application/voice/voicePorts'
import { config } from '../../config'
import { MSG } from '../../domain/messages'
import { ApiError } from '../../domain/types'

interface ErrorBody {
  error?: { code?: string; message_bn?: string; message_en?: string }
}

async function post(path: string, body: unknown, signal?: AbortSignal): Promise<Response> {
  let res: Response
  try {
    res = await fetch(`${config.apiUrl}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })
  } catch (err) {
    throw new ApiError(signal?.aborted ? 'TIMEOUT' : 'NETWORK', MSG.ERROR, 0, String(err))
  }
  if (!res.ok) {
    const error = ((await res.json().catch(() => ({}))) as ErrorBody).error
    throw new ApiError(error?.code ?? `HTTP_${res.status}`, error?.message_bn || MSG.ERROR, res.status, error?.message_en)
  }
  return res
}

export const voiceApi: VoiceApi = {
  speech: async (text, signal) => (await post('/api/v1/tts', { text }, signal)).blob(),
  callMe: async (phone) => {
    const body = (await (await post('/api/v1/callback', { phone })).json()) as { call_sid: string }
    return body.call_sid
  },
}
