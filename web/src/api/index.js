import axios from 'axios'

const api = axios.create({
  baseURL: '/v1',
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
})

export async function chatCompletions(messages, conversationId = null, model = 'Arch-Agent-3B') {
  const payload = { model, messages, stream: false, max_tokens: 2048 }
  if (conversationId) payload.conversation_id = conversationId
  const { data } = await api.post('/chat/completions', payload)
  return data
}

export async function chatCompletionsStream(messages, conversationId = null, model = 'Arch-Agent-3B', onChunk = () => {}, onDone = () => {}, onError = () => {}) {
  const payload = { model, messages, stream: true, max_tokens: 2048 }
  if (conversationId) payload.conversation_id = conversationId

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

export async function listConversations(userId = 'default', limit = 20, offset = 0) {
  const { data } = await api.get('/conversations', { params: { user_id: userId, limit, offset } })
  return data
}

export async function getConversation(conversationId) {
  const { data } = await api.get(`/conversations/${conversationId}`)
  return data
}

export async function deleteConversation(conversationId) {
  await api.delete(`/conversations/${conversationId}`)
}

export async function listModels() {
  const { data } = await api.get('/models')
  return data
}

export async function listTools() {
  const { data } = await api.get('/tools')
  return data
}

export async function scoreEvaluation(model, prompt, response, criteria = ['相关性', '准确性', '完整性']) {
  const { data } = await api.post('/score/evaluation', { model, prompt, response, criteria })
  return data
}
