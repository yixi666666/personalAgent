import axios from 'axios'

const api = axios.create({
  baseURL: '/v1',
  timeout: 60000,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

function notifyUnauthorized() {
  window.dispatchEvent(new CustomEvent('auth:unauthorized'))
}

api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) notifyUnauthorized()
    return Promise.reject(error)
  },
)

export function createSseStream(fetcher, { onChunk = () => {}, onDone = () => {}, onError = () => {} } = {}) {
  const controller = new AbortController()
  const IDLE_TIMEOUT_MS = 300000
  let idleTimer = null
  let manuallyAborted = false
  let settled = false

  function resetIdleTimer() {
    if (idleTimer) clearTimeout(idleTimer)
    idleTimer = setTimeout(() => {
      if (settled) return
      controller.abort()
      settled = true
      onError('连接超时：服务器长时间无响应')
    }, IDLE_TIMEOUT_MS)
  }

  const promise = (async () => {
    try {
      resetIdleTimer()
      const response = await fetcher(controller.signal)
      if (!response.ok) {
        const errText = await response.text()
        settled = true
        if (response.status === 401) notifyUnauthorized()
        onError(`请求失败: ${response.status} ${errText}`)
        return
      }
      if (!response.body) {
        settled = true
        onError('请求失败：响应流不可用')
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          if (!settled) {
            settled = true
            onError('连接意外中断')
          }
          return
        }

        resetIdleTimer()
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed || !trimmed.startsWith('data: ')) continue
          const data = trimmed.slice(6)
          if (data === '[DONE]') {
            settled = true
            onDone()
            return
          }
          try {
            const parsed = JSON.parse(data)
            if (parsed.error) {
              settled = true
              onError(parsed.error)
              return
            }
            onChunk(parsed)
          } catch {
            // 跳过格式异常的单条事件
          }
        }
      }
    } catch (err) {
      if (!manuallyAborted && !settled) {
        settled = true
        onError(err.message || '未知错误')
      }
    } finally {
      if (idleTimer) clearTimeout(idleTimer)
    }
  })()

  return {
    promise,
    abort() {
      manuallyAborted = true
      controller.abort()
    },
  }
}

export function chatCompletionsStream(
  prompt,
  sessionId = '',
  model = 'glm-4.7-flash',
  deepThinking = false,
  handlers = {},
) {
  const payload = { session_id: sessionId, model, prompt, deep_thinking: deepThinking }
  return createSseStream(
    signal => fetch('/v1/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      credentials: 'include',
      signal,
    }),
    handlers,
  )
}

export function attachChatStream(streamId, handlers = {}) {
  return createSseStream(
    signal => fetch(`/v1/chat/stream/${encodeURIComponent(streamId)}`, {
      credentials: 'include',
      signal,
    }),
    handlers,
  )
}

export async function registerUser(payload) {
  const { data } = await api.post('/auth/register', payload)
  return data
}

export async function loginUser(payload) {
  const { data } = await api.post('/auth/login', payload)
  return data
}

export async function getCurrentUser() {
  const { data } = await api.get('/auth/me')
  return data
}

export async function logoutUser() {
  await api.post('/auth/logout')
}

export async function getActiveStream(sessionId) {
  const { data } = await api.get('/chat/streams/active', { params: { session_id: sessionId } })
  return data
}

export async function listSessions(limit = 30, offset = 0) {
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

export async function getUniversity(name) {
  const { data } = await api.get('/universities', { params: { name } })
  return data
}
