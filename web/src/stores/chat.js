import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { chatCompletionsStream, listSessions, getSession, deleteSession, listModels, listTools } from '../api'

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
        display_time: s.updated_time || s.created_time || '',
      }))
    } catch (err) {
      console.error('加载会话列表失败:', err)
    }
  }

  async function loadSessionData(sessionId) {
    try {
      const data = await getSession(sessionId)
      currentSessionId.value = sessionId
      // 处理历史消息：将 role=tool 消息合并到对应 assistant 消息中
      const rawMessages = data.messages || []
      const processed = []
      const toolMsgMap = {} // call_id -> tool消息content

      // 第一遍：收集所有 tool 消息，按 tool_call_id 索引
      for (const m of rawMessages) {
        if (m.role === 'tool' && m.tool_call_id) {
          toolMsgMap[m.tool_call_id] = m.content
        }
      }

      // 第二遍：构建显示用的消息列表，将工具调用合并到下一条assistant文本回复中
      let pendingToolCalls = null

      for (const m of rawMessages) {
        if (m.role === 'tool') {
          // tool 消息不单独显示，已合并到 assistant 消息中
          continue
        }

        const msg = {
          ...m,
          display_time: m.created_time || '',
        }

        // assistant 消息：转换 tool_calls 字段名并附加工具结果
        if (m.role === 'assistant' && m.tool_calls && m.tool_calls.length > 0) {
          const toolCalls = m.tool_calls.map(tc => ({
            ...tc,
            result: toolMsgMap[tc.id] || null,
          }))

          // 有工具调用时，content 通常是原始工具调用标签文本，不应显示
          if (m.content && (m.content.includes('<tool_call') || m.content.includes('tool_calls'))) {
            msg.content = ''
          }

          if (msg.content && msg.content.trim()) {
            // 有文本内容：直接附加工具调用到当前消息
            msg.toolCalls = toolCalls
            pendingToolCalls = null
          } else {
            // 无文本内容：暂存工具调用，等下一条assistant文本回复消息
            pendingToolCalls = toolCalls
            continue // 不单独显示这条消息
          }
        }

        // assistant文本回复消息：如果有暂存的工具调用，附加到这条消息
        if (m.role === 'assistant' && pendingToolCalls) {
          msg.toolCalls = pendingToolCalls
          pendingToolCalls = null
        }

        processed.push(msg)
      }

      // 如果最后还有未合并的工具调用（没有后续文本回复），单独显示
      if (pendingToolCalls) {
        processed.push({
          id: `pending_tc_${Date.now()}`,
          role: 'assistant',
          content: '',
          toolCalls: pendingToolCalls,
          display_time: '',
        })
      }

      messages.value = processed
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
    const now = new Date()
    const displayTime = now.toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    })
    const userMsg = {
      id: `temp_${Date.now()}`,
      role: 'user',
      content: prompt,
      display_time: displayTime,
    }
    messages.value.push(userMsg)

    // 添加助手消息占位
    const assistantIdx = messages.value.length
    messages.value.push({
      id: `temp_assistant_${Date.now()}`,
      role: 'assistant',
      content: '',
      isStreaming: true,
      display_time: displayTime,
    })

    // 暂存工具调用信息，等最终文本回复时附加
    let pendingStreamToolCalls = null

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
            // 暂存工具调用，不立即显示
            pendingStreamToolCalls = chunk.tool_calls
          }
          if (chunk.tool_results && pendingStreamToolCalls) {
            // 将工具执行结果附加到暂存的 toolCall 上
            for (const tr of chunk.tool_results) {
              const tc = pendingStreamToolCalls.find(c => c.id === tr.id)
              if (tc) {
                tc.result = tr.result
                tc.status = tr.status
              }
            }
          }
        },
        () => {
          streaming.value = false
          loading.value = false
          if (streamingContent.value) {
            messages.value[assistantIdx].content = streamingContent.value
          }
          // 将暂存的工具调用附加到最终消息
          if (pendingStreamToolCalls) {
            messages.value[assistantIdx].toolCalls = pendingStreamToolCalls
            pendingStreamToolCalls = null
          }
          messages.value[assistantIdx].isStreaming = false
          streamingContent.value = ''
          loadSessionsData()
        },
        (error) => {
          streaming.value = false
          loading.value = false
          messages.value[assistantIdx].content = `错误: ${error}`
          // 即使出错也附加工具调用
          if (pendingStreamToolCalls) {
            messages.value[assistantIdx].toolCalls = pendingStreamToolCalls
            pendingStreamToolCalls = null
          }
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
