import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface ChatMsg {
  role: 'user' | 'assistant'
  content: string
  toolCalls?: ToolCallEvent[]
  streaming?: boolean
}

export interface ToolCallEvent {
  name: string
  args: Record<string, unknown>
  result?: Record<string, unknown>
  done: boolean
}

export interface ChatConfig {
  siteId?: string
  provider?: string
  apiKey?: string
  model?: string
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMsg[]>([])
  const isStreaming = ref(false)
  const config = ref<ChatConfig>({})
  const error = ref('')

  async function send(text: string) {
    if (isStreaming.value || !text.trim()) return

    error.value = ''
    messages.value.push({ role: 'user', content: text })

    const assistantMsg: ChatMsg = {
      role: 'assistant',
      content: '',
      toolCalls: [],
      streaming: true,
    }
    messages.value.push(assistantMsg)
    isStreaming.value = true

    const payload = {
      messages: messages.value
        .filter(m => !m.streaming)
        .concat({ role: 'user', content: text })
        .filter(m => m.role === 'user' || (m.role === 'assistant' && m.content))
        .map(m => ({ role: m.role, content: m.content })),
      site_id: config.value.siteId || undefined,
      provider: config.value.provider || undefined,
      api_key: config.value.apiKey || undefined,
      model: config.value.model || undefined,
    }

    // Rebuild correctly: exclude the streaming msg we just added
    payload.messages = messages.value
      .slice(0, -1)  // exclude the empty streaming assistant msg
      .filter(m => m.role === 'user' || (m.role === 'assistant' && m.content && !m.streaming))
      .map(m => ({ role: m.role, content: m.content }))

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: response.statusText }))
        assistantMsg.content = `Error: ${err.detail ?? response.statusText}`
        assistantMsg.streaming = false
        return
      }

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let currentToolCall: ToolCallEvent | null = null

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (!raw) continue

          let event: Record<string, unknown>
          try { event = JSON.parse(raw) } catch { continue }

          switch (event.type) {
            case 'text':
              assistantMsg.content += (event.delta as string) ?? ''
              break

            case 'tool_start':
              currentToolCall = {
                name: event.name as string,
                args: (event.args ?? {}) as Record<string, unknown>,
                done: false,
              }
              assistantMsg.toolCalls!.push(currentToolCall)
              break

            case 'tool_done':
              if (currentToolCall && currentToolCall.name === event.name) {
                currentToolCall.result = (event.result ?? {}) as Record<string, unknown>
                currentToolCall.done = true
                currentToolCall = null
              }
              break

            case 'error':
              error.value = (event.message as string) ?? 'Unknown error'
              assistantMsg.content = assistantMsg.content || `⚠ ${error.value}`
              break

            case 'done':
              break
          }
        }
      }
    } catch (e: any) {
      error.value = e.message
      assistantMsg.content = `⚠ ${e.message}`
    } finally {
      assistantMsg.streaming = false
      isStreaming.value = false
    }
  }

  function clear() {
    messages.value = []
    error.value = ''
  }

  return { messages, isStreaming, config, error, send, clear }
})
