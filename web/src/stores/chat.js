import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as api from '../api'

export const useChatStore = defineStore('chat', () => {
  const conversations = ref([])
  const currentConversationId = ref(null)
  const messages = ref([])
  const loading = ref(false)
  const streaming = ref(false)
  const models = ref([])
  const currentModel = ref('Arch-Agent-3B')
  const tools = ref([])

  const currentConversation = computed(() =>
    conversations.value.find((c) => c.conversation_id === currentConversationId.value)
  )

  async function loadConversations() {
    try {
      const data = await api.listConversations('default')
      conversations.value = data.conversations || []
    } catch {
      conversations.value = []
    }
  }

  async function selectConversation(conversationId) {
    currentConversationId.value = conversationId
    messages.value = []
    if (conversationId) {
      try {
        const data = await api.getConversation(conversationId)
        messages.value = (data.messages || []).map((m) => ({
          id: m.message_id,
          role: m.role,
          content: m.content,
          timestamp: m.timestamp,
        }))
      } catch {
        messages.value = []
      }
    }
  }

  async function sendMessage(content) {
    if (!content.trim() || loading.value) return

    messages.value.push({
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    })

    loading.value = true
    streaming.value = true

    const assistantMsg = {
      id: 'streaming_' + Date.now(),
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      toolCalls: [],
      usage: {},
      isStreaming: true,
    }
    messages.value.push(assistantMsg)

    const apiMessages = messages.value
      .filter((m) => m.role === 'user' || (m.role === 'assistant' && !m.isStreaming))
      .map((m) => ({ role: m.role, content: m.content }))

    try {
      await api.chatCompletionsStream(
        apiMessages,
        currentConversationId.value,
        currentModel.value,
        (chunk) => {
          if (chunk.conversation_id && !currentConversationId.value) {
            currentConversationId.value = chunk.conversation_id
            loadConversations()
          }
          if (chunk.tool_calls) {
            const msg = messages.value.find((m) => m.id === assistantMsg.id)
            if (msg) msg.toolCalls = chunk.tool_calls
          }
          if (chunk.delta && chunk.delta.content) {
            const msg = messages.value.find((m) => m.id === assistantMsg.id)
            if (msg) msg.content += chunk.delta.content
          }
          if (chunk.finish_reason === 'stop') {
            const msg = messages.value.find((m) => m.id === assistantMsg.id)
            if (msg) {
              msg.isStreaming = false
              msg.id = chunk.id || msg.id
            }
          }
        },
        () => {
          const msg = messages.value.find((m) => m.id === assistantMsg.id)
          if (msg) msg.isStreaming = false
          loading.value = false
          streaming.value = false
        },
        (error) => {
          const msg = messages.value.find((m) => m.id === assistantMsg.id)
          if (msg) {
            msg.content = `请求失败: ${error}`
            msg.isStreaming = false
            msg.isError = true
          }
          loading.value = false
          streaming.value = false
        }
      )
    } catch (err) {
      const msg = messages.value.find((m) => m.id === assistantMsg.id)
      if (msg) {
        msg.content = `请求失败: ${err.message}`
        msg.isStreaming = false
        msg.isError = true
      }
      loading.value = false
      streaming.value = false
    }
  }

  function newConversation() {
    currentConversationId.value = null
    messages.value = []
  }

  async function removeConversation(conversationId) {
    try {
      await api.deleteConversation(conversationId)
      if (currentConversationId.value === conversationId) {
        newConversation()
      }
      await loadConversations()
    } catch {
      //
    }
  }

  async function loadModels() {
    try {
      const data = await api.listModels()
      models.value = data.models || []
      if (models.value.length > 0 && !models.value.find(m => m.id === currentModel.value)) {
        currentModel.value = models.value[0].id
      }
    } catch {
      models.value = [{ id: 'Arch-Agent-3B', name: 'Arch-Agent-3B' }]
    }
  }

  async function loadTools() {
    try {
      const data = await api.listTools()
      tools.value = data.tools || []
    } catch {
      tools.value = []
    }
  }

  return {
    conversations,
    currentConversationId,
    messages,
    loading,
    streaming,
    models,
    currentModel,
    tools,
    currentConversation,
    loadConversations,
    selectConversation,
    sendMessage,
    newConversation,
    removeConversation,
    loadModels,
    loadTools,
  }
})
