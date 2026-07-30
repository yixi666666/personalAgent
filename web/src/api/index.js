import axios from 'axios'

const api = axios.create({
  baseURL: '/v1',
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
})

export async function chatCompletionsStream(prompt, sessionId = '', model = 'glm-4.7-flash', deepThinking = false, onChunk = () => {}, onDone = () => {}, onError = () => {}) {
  const payload = { session_id: sessionId, model, prompt, deep_thinking: deepThinking }

  try {
    const response = await fetch('/v1/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })

    if (!response.ok) {
      const errText = await response.text()
      onError(`请求失败: ${response.status} ${errText}`)
      return
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed || !trimmed.startsWith('data: ')) continue
        const data = trimmed.slice(6)
        if (data === '[DONE]') {
          onDone()
          return
        }
        try {
          const parsed = JSON.parse(data)
          if (parsed.error) {
            onError(parsed.error)
            return
          }
          onChunk(parsed)
        } catch {
          // skip malformed JSON
        }
      }
    }

    onDone()
  } catch (err) {
    onError(err.message || '未知错误')
  }
}

export async function listSessions(limit = 20, offset = 0) {
  const { data } = await api.get('/sessions', { params: { limit, offset } })
  return data
}

export async function getSession(sessionId) {
  const { data } = await api.get(`/sessions/${sessionId}`)
  return data
}

export async function deleteSession(sessionId) {
  await api.delete(`/sessions/${sessionId}`)
}

export async function getToolCalls(messageId) {
  const { data } = await api.get('/tool-calls', { params: { message_id: messageId } })
  return data
}

export async function listModels() {
  const { data } = await api.get('/models')
  return data
}

export async function listTools() {
  const { data } = await api.get('/tools')
  return data
}
