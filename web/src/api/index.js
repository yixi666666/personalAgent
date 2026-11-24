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

export function retryChatStream(
  sessionId,
  model = 'glm-4.7-flash',
  deepThinking = false,
  handlers = {},
) {
  const payload = { session_id: sessionId, model, deep_thinking: deepThinking }
  return createSseStream(
    signal => fetch('/v1/chat/retry', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
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

export async function guestLogin() {
  const { data } = await api.post('/auth/guest')
  return data
}

export async function upgradeAccount(payload) {
  const { data } = await api.post('/auth/upgrade', payload)
  return data
}

export async function forgotPassword(payload) {
  const { data } = await api.post('/auth/forgot-password', payload)
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

export async function pinSession(sessionId, pinned) {
  await api.patch(`/sessions/${sessionId}`, { is_pinned: pinned })
}

export async function rollbackMessage(messageId) {
  const { data } = await api.post(`/messages/${messageId}/rollback`)
  return data
}

export async function getToolCalls(messageId) {
  const { data } = await api.get('/tool-calls', { params: { message_id: messageId } })
  return data
}

export async function getFeedbackReasons(feedbackType) {
  const { data } = await api.get('/feedbacks/reasons', {
    params: feedbackType ? { feedback_type: feedbackType } : {},
  })
  return data
}

export async function submitFeedback(messageId, feedbackType, reasonCodes = [], comment = '') {
  const { data } = await api.put('/feedbacks', {
    message_id: messageId,
    feedback_type: feedbackType,
    reason_codes: reasonCodes,
    comment,
  })
  return data
}

export async function revokeFeedback(messageId) {
  await api.delete(`/feedbacks/${messageId}`)
}

export async function listModels() {
  const { data } = await api.get('/models')
  return data
}

export async function getUniversity(name) {
  const { data } = await api.get('/universities', { params: { name } })
  return data
}

export async function listAnnouncements() {
  const { data } = await api.get('/announcements')
  return data
}

export async function getUnreadAnnouncementCount() {
  const { data } = await api.get('/announcements/unread-count')
  return data
}

export async function markAnnouncementRead(announcementId) {
  await api.post(`/announcements/${announcementId}/read`)
}

// ==== 管理端 ====

export async function adminListConfigs() {
  const { data } = await api.get('/admin/configs')
  return data
}

export async function adminCreateConfig(payload) {
  const { data } = await api.post('/admin/configs', payload)
  return data
}

export async function adminUpdateConfig(id, payload) {
  const { data } = await api.put(`/admin/configs/${id}`, payload)
  return data
}

export async function adminDeleteConfig(id) {
  await api.delete(`/admin/configs/${id}`)
}

export async function adminListModels() {
  const { data } = await api.get('/admin/models')
  return data
}

export async function adminCreateModel(payload) {
  const { data } = await api.post('/admin/models', payload)
  return data
}

export async function adminUpdateModel(id, payload) {
  const { data } = await api.put(`/admin/models/${id}`, payload)
  return data
}

export async function adminDeleteModel(id) {
  await api.delete(`/admin/models/${id}`)
}

export async function adminListUsers() {
  const { data } = await api.get('/admin/users')
  return data
}

export async function adminUpdateUser(id, payload) {
  const { data } = await api.patch(`/admin/users/${id}`, payload)
  return data
}

export async function adminListAnnouncements() {
  const { data } = await api.get('/admin/announcements')
  return data
}

export async function adminCreateAnnouncement(payload) {
  const { data } = await api.post('/admin/announcements', payload)
  return data
}

export async function adminUpdateAnnouncement(id, payload) {
  const { data } = await api.put(`/admin/announcements/${id}`, payload)
  return data
}

export async function adminDeleteAnnouncement(id) {
  await api.delete(`/admin/announcements/${id}`)
}

// ==== 反馈管理（点赞/拉踩）====

export async function adminFeedbackStats() {
  const { data } = await api.get('/admin/feedbacks/stats')
  return data
}

export async function adminListFeedbacks(params = {}) {
  const { data } = await api.get('/admin/feedbacks', { params })
  return data
}

export async function adminFeedbackContext(feedbackId) {
  const { data } = await api.get(`/admin/feedbacks/${feedbackId}/context`)
  return data
}

// 管理端工具详情懒加载（与用户侧 /tool-calls 同构，不做会话归属校验）
export async function adminToolCalls(messageId) {
  const { data } = await api.get('/admin/tool-calls', { params: { message_id: messageId } })
  return data
}

export async function adminListFeedbackReasons() {
  const { data } = await api.get('/admin/feedbacks/reasons')
  return data
}

export async function adminCreateFeedbackReason(payload) {
  const { data } = await api.post('/admin/feedbacks/reasons', payload)
  return data
}

export async function adminUpdateFeedbackReason(id, payload) {
  const { data } = await api.put(`/admin/feedbacks/reasons/${id}`, payload)
  return data
}

export async function adminDeleteFeedbackReason(id) {
  await api.delete(`/admin/feedbacks/reasons/${id}`)
}

export async function adminListUniversities(params = {}) {
  const { data } = await api.get('/admin/universities', { params })
  return data
}

export async function adminGetUniversitySummary() {
  const { data } = await api.get('/admin/universities/summary')
  return data
}

export async function adminGetUniversity(id) {
  const { data } = await api.get(`/admin/universities/${id}`)
  return data
}

export async function adminUpdateUniversity(id, payload) {
  const { data } = await api.patch(`/admin/universities/${id}`, payload)
  return data
}
