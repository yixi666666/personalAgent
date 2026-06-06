import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { chatCompletionsStream, listSessions, getSession, deleteSession, listModels, listTools } from '../api'

// UTC 时间戳转 UTC+8 可读字符串
function formatTime(ts) {
  if (!ts) return ''
  const date = new Date(ts * 1000)
  return date.toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

// UTC 时间戳转简短时间
function formatShortTime(ts) {
  if (!ts) return ''
  const date = new Date(ts * 1000)
  return date.toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

export const useChatStore = defineStore('chat', () => {
  const sessions = ref([])
  const currentSessionId = ref(null)
  const messages = ref([])
  const loading = ref(false)
  const currentModel = ref('xop3qwen1b7')
  const models = ref([])
  const tools = ref([])
  const streamingContent = ref('')
  const streaming = ref(false)

  const currentSession = computed(() => {
    return sessions.value.find(s => s.id === currentSessionId.value) || null
  })

  async function loadSessionsData() {
    try {
      const data = await listSessions()
      sessions.value = (data.sessions || []).map(s => ({
        ...s,
        display_time: formatShortTime(s.updated_time || s.created_time),
      }))
    } catch (err) {
      console.error('加载会话列表失败:', err)
    }
  }

  async function loadSessionData(sessionId) {
    try {
      const data = await getSession(sessionId)
      currentSessionId.value = sessionId
      messages.value = (data.messages || []).map(m => ({
        ...m,
        display_time: formatTime(m.created_time),
      }))
    } catch (err) {
      console.error('加载会话失败:', err)
    }
  }

  async function removeSession(sessionId) {
    try {
      await deleteSession(sessionId)
      sessions.value = sessions.value.filter(s => s.id !== sessionId)
      if (currentSessionId.value === sessionId) {
        currentSessionId.value = null
        messages.value = []
      }
    } catch (err) {
      console.error('删除会话失败:', err)
    }
  }

  function newSession() {
    currentSessionId.value = null
    messages.value = []
  }

  function selectSession(sessionId) {
    loadSessionData(sessionId)
  }

  async function sendMessage(prompt) {
    if (!prompt.trim() || loading.value) return

    loading.value = true
    streaming.value = true
    streamingContent.value = ''

    // 先在本地添加用户消息
    const userMsg = {
      id: `temp_${Date.now()}`,
      role: 'user',
      content: prompt,
      created_time: Math.floor(Date.now() / 1000),
      display_time: formatTime(Math.floor(Date.now() / 1000)),
    }
    messages.value.push(userMsg)

    // 添加助手消息占位
    const assistantIdx = messages.value.length
    messages.value.push({
      id: `temp_assistant_${Date.now()}`,
      role: 'assistant',
      content: '',
      isStreaming: true,
      created_time: Math.floor(Date.now() / 1000),
      display_time: formatTime(Math.floor(Date.now() / 1000)),
    })

    try {
      await chatCompletionsStream(
        prompt,
        currentSessionId.value || '',
        currentModel.value,
        (chunk) => {
          if (chunk.session_id && !currentSessionId.value) {
            currentSessionId.value = chunk.session_id
            loadSessionsData()
          }
          if (chunk.delta && chunk.delta.content) {
            streamingContent.value += chunk.delta.content
            messages.value[assistantIdx].content = streamingContent.value
          }
          if (chunk.content_replace) {
            streamingContent.value = chunk.content_replace.content
            messages.value[assistantIdx].content = streamingContent.value
          }
          if (chunk.tool_calls) {
            messages.value[assistantIdx].toolCalls = chunk.tool_calls
          }
        },
        () => {
          streaming.value = false
          loading.value = false
          if (streamingContent.value) {
            messages.value[assistantIdx].content = streamingContent.value
          }
          messages.value[assistantIdx].isStreaming = false
          streamingContent.value = ''
          loadSessionsData()
        },
        (error) => {
          streaming.value = false
          loading.value = false
          messages.value[assistantIdx].content = `错误: ${error}`
          messages.value[assistantIdx].isStreaming = false
          streamingContent.value = ''
        }
      )
    } catch (err) {
      streaming.value = false
      loading.value = false
      messages.value[assistantIdx].content = `请求失败: ${err.message}`
      messages.value[assistantIdx].isStreaming = false
      streamingContent.value = ''
    }
  }

  async function loadModelsData() {
    try {
      const data = await listModels()
      models.value = data.models || []
    } catch (err) {
      console.error('加载模型列表失败:', err)
    }
  }

  async function loadToolsData() {
    try {
      const data = await listTools()
      tools.value = data.tools || []
    } catch (err) {
      console.error('加载工具列表失败:', err)
    }
  }

  return {
    sessions,
    currentSessionId,
    messages,
    loading,
    currentModel,
    models,
    tools,
    streamingContent,
    streaming,
    currentSession,
    loadSessions: loadSessionsData,
    loadSession: loadSessionData,
    removeSession,
    newSession,
    selectSession,
    sendMessage,
    loadModels: loadModelsData,
    loadTools: loadToolsData,
  }
})
