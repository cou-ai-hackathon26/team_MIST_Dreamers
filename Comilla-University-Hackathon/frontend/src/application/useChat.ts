// Use case: ask Ek Call a question and keep the conversation on screen (FR-APP-02, FR-APP-08).

import { useCallback, useRef, useState } from 'react'
import { errorText, type ChatMessage } from '../domain/types'
import { usePorts } from './portsContext'

/** Same limit as the API (ChatRequest.message, 500 characters). */
export const MAX_QUESTION_LENGTH = 500

export interface Chat {
  messages: ChatMessage[]
  loading: boolean
  /** Sends a question. Ignored while an answer is loading or when the text is empty. */
  send(text: string): Promise<void>
}

let nextId = 0
const newId = () => `m${Date.now()}-${nextId++}`

export function useChat(phone: string): Chat {
  const { api } = usePorts()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  // A ref, not state, so two fast taps cannot send the same question twice.
  const busy = useRef(false)

  const send = useCallback(
    async (text: string) => {
      const question = text.trim().slice(0, MAX_QUESTION_LENGTH)
      if (!question || busy.current) return
      busy.current = true
      setLoading(true)
      setMessages((list) => [...list, { id: newId(), role: 'user', text: question }])
      try {
        // The agent keeps the conversation context on the server (by phone number),
        // so a short reply to a follow-up question ("হ্যাঁ") is understood there.
        const answer = await api.chat({ phone, message: question })
        setMessages((list) => [...list, { id: newId(), role: 'assistant', answer }])
      } catch (err) {
        setMessages((list) => [...list, { id: newId(), role: 'error', text: errorText(err) }])
      } finally {
        busy.current = false
        setLoading(false)
      }
    },
    [api, phone],
  )

  return { messages, loading, send }
}
