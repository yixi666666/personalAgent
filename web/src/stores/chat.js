import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { chatCompletionsStream, listSessions, getSession, deleteSession, listModels, listTools, getToolCalls } from '../api'

export const useChatStore = defineStore('chat', () => {
  const sessions = ref([])
  const currentSessionId = ref(null)
  const messages = ref([])
  const loading = ref(false)
  const currentModel = ref('xop3qwen1b7')
  const models = ref([])
  const tools = ref([])
  const streamingContent = ref('')
  const streamingReasoning = ref('')
  const streaming = ref(false)
  const deepThinking = ref(false)

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

  /**
   * 从后端 contents 数组构建有序 blocks 数组
   * blocks: [{ type: 'reasoning'|'text'|'tool_call', content?, toolCall? }, ...]
   */
  function buildBlocksFromContents(contents, toolCallsMap = {}, messageId = '') {
    const blocks = []
    for (const c of contents) {
      if (c.type === 'reasoning') {
        blocks.push({ type: 'reasoning', content: c.content || '' })
      } else if (c.type === 'text') {
        blocks.push({ type: 'text', content: c.content || '' })
      } else if (c.type === 'tool_call') {
        const callId = c.content
        const tc = toolCallsMap[callId]
        blocks.push({
          type: 'tool_call',
          _messageId: messageId,
          toolCall: tc || {
            id: callId,
            type: 'function',
            function: { name: '未知', arguments: '{}' },
            result: null,
            status: 'unknown',
          },
        })
      }
    }
    return blocks
  }

  async function loadSessionData(sessionId) {
    try {
      const data = await getSession(sessionId)
      currentSessionId.value = sessionId
      const rawMessages = data.messages || []
      const processed = []
      let pendingBlocks = []

      for (const m of rawMessages) {
        const contents = m.contents || []
        const hasToolCall = contents.some(c => c.type === 'tool_call')
        const hasText = contents.some(c => c.type === 'text')

        // 不在这里请求工具详情，tool_call 块只存 call_id
        // 用户点击工具符号时再懒加载
        const currentBlocks = buildBlocksFromContents(contents, {}, m.id)

        // 有 tool_call 的 assistant 消息暂存，等下一条 assistant 消息合并
        // 这样工具调用和后续回复在同一个消息气泡中显示
        if (m.role === 'assistant' && hasToolCall) {
          pendingBlocks = pendingBlocks.concat(currentBlocks)
          continue
        }

        // 合并暂存的 blocks + 当前 blocks
        const allBlocks = pendingBlocks.length > 0
          ? pendingBlocks.concat(currentBlocks)
          : currentBlocks
        pendingBlocks = []

        const msg = {
          id: m.id,
          role: m.role,
          blocks: allBlocks,
          display_time: m.created_time || '',
        }

        processed.push(msg)
      }

      // 如果最后还有未合并的工具调用
      if (pendingBlocks.length > 0) {
        processed.push({
          id: `pending_tc_${Date.now()}`,
          role: 'assistant',
          blocks: pendingBlocks,
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
    streamingReasoning.value = ''

    // 先在本地添加用户消息
    const now = new Date()
    const displayTime = now.toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    })
    const userMsg = {
      id: `temp_${Date.now()}`,
      role: 'user',
      blocks: [{ type: 'text', content: prompt }],
      display_time: displayTime,
    }
    messages.value.push(userMsg)

    // 添加助手消息占位
    const assistantIdx = messages.value.length
    messages.value.push({
      id: `temp_assistant_${Date.now()}`,
      role: 'assistant',
      blocks: [],
      isStreaming: true,
      display_time: displayTime,
    })

    // 暂存工具调用信息
    let pendingStreamToolCalls = null

    try {
      await chatCompletionsStream(
        prompt,
        currentSessionId.value || '',
        currentModel.value,
        deepThinking.value,
        (chunk) => {
          if (chunk.session_id && !currentSessionId.value) {
            currentSessionId.value = chunk.session_id
            loadSessionsData()
          }
          const blocks = messages.value[assistantIdx].blocks
          if (chunk.reasoning_delta && chunk.reasoning_delta.content) {
            streamingReasoning.value += chunk.reasoning_delta.content
            // 更新或追加 reasoning block
            const lastBlock = blocks[blocks.length - 1]
            if (lastBlock && lastBlock.type === 'reasoning') {
              lastBlock.content = streamingReasoning.value
            } else {
              blocks.push({ type: 'reasoning', content: streamingReasoning.value })
            }
          }
          if (chunk.delta && chunk.delta.content) {
            streamingContent.value += chunk.delta.content
            // 更新或追加 text block
            const lastBlock = blocks[blocks.length - 1]
            if (lastBlock && lastBlock.type === 'text') {
              lastBlock.content = streamingContent.value
            } else {
              blocks.push({ type: 'text', content: streamingContent.value })
            }
          }
          if (chunk.content_replace) {
            streamingContent.value = chunk.content_replace.content
            const lastBlock = blocks[blocks.length - 1]
            if (lastBlock && lastBlock.type === 'text') {
              lastBlock.content = streamingContent.value
            } else {
              blocks.push({ type: 'text', content: streamingContent.value })
            }
          }
          if (chunk.tool_calls) {
            pendingStreamToolCalls = chunk.tool_calls
            // 插入 tool_call blocks
            for (const tc of chunk.tool_calls) {
              blocks.push({ type: 'tool_call', toolCall: tc })
            }
            // 重置流式状态，下一轮重新开始
            streamingReasoning.value = ''
            streamingContent.value = ''
          }
          if (chunk.tool_results && pendingStreamToolCalls) {
            for (const tr of chunk.tool_results) {
              const tc = pendingStreamToolCalls.find(c => c.id === tr.id)
              if (tc) {
                tc.result = tr.result
                tc.status = tr.status
              }
              // 同步更新 blocks 中的 toolCall 引用
              for (const b of blocks) {
                if (b.type === 'tool_call' && b.toolCall.id === tr.id) {
                  b.toolCall.result = tr.result
                  b.toolCall.status = tr.status
                }
              }
            }
          }
        },
        () => {
          streaming.value = false
          loading.value = false
          messages.value[assistantIdx].isStreaming = false
          messages.value[assistantIdx]._wasStreaming = true
          streamingContent.value = ''
          streamingReasoning.value = ''
          loadSessionsData()
        },
        (error) => {
          streaming.value = false
          loading.value = false
          // 添加错误 text block
          const blocks = messages.value[assistantIdx].blocks
          blocks.push({ type: 'text', content: `错误: ${error}` })
          messages.value[assistantIdx].isStreaming = false
          messages.value[assistantIdx]._wasStreaming = true
          streamingContent.value = ''
          streamingReasoning.value = ''
        }
      )
    } catch (err) {
      streaming.value = false
      loading.value = false
      const blocks = messages.value[assistantIdx].blocks
      blocks.push({ type: 'text', content: `请求失败: ${err.message}` })
      messages.value[assistantIdx].isStreaming = false
      messages.value[assistantIdx]._wasStreaming = true
      streamingContent.value = ''
      streamingReasoning.value = ''
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

  /**
   * 懒加载：用户点击工具符号时，按 message_id 请求工具详情并更新对应 block
   * messageId 是 tool_call 所属的原始消息ID（通过 block._messageId 传递）
   */
  async function loadToolCallDetail(messageId, callId) {
    // 在所有消息的 blocks 中查找 _messageId 匹配的 tool_call block
    let alreadyLoaded = false
    for (const msg of messages.value) {
      for (const b of msg.blocks || []) {
        if (b.type === 'tool_call' && b._messageId === messageId && b.toolCall?.id === callId) {
          if (b.toolCall.status !== 'unknown' && b.toolCall.result !== null) {
            alreadyLoaded = true
          }
          break
        }
      }
      if (alreadyLoaded) return null
    }
    try {
      const toolCallsData = await getToolCalls(messageId)
      // 更新所有 _messageId 匹配的 tool_call blocks（就地更新属性，保持引用不变）
      for (const msg of messages.value) {
        for (const b of msg.blocks || []) {
          if (b.type !== 'tool_call' || b._messageId !== messageId) continue
          const tc = toolCallsData.find(t => t.call_id === b.toolCall?.id)
          if (tc) {
            b.toolCall.function = { name: tc.tool_name, arguments: tc.parameters }
            b.toolCall.result = tc.result
            b.toolCall.status = tc.status
          }
        }
      }
      return toolCallsData.find(t => t.call_id === callId) || null
    } catch (err) {
      console.error('懒加载工具详情失败:', err)
      return null
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
    streamingReasoning,
    streaming,
    deepThinking,
    currentSession,
    loadSessions: loadSessionsData,
    loadSession: loadSessionData,
    removeSession,
    newSession,
    selectSession,
    sendMessage,
    loadToolCallDetail,
    loadModels: loadModelsData,
    loadTools: loadToolsData,
  }
})
