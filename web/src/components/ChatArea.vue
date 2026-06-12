<template>
  <div class="chat-area">
    <div class="chat-header">
      <span class="chat-title">
        {{ chatStore.currentSessionId
          ? (chatStore.currentSession?.title || '会话 ' + chatStore.currentSessionId.slice(0, 8))
          : '新对话' }}
      </span>
      <el-tag size="small" type="info">{{ chatStore.currentModel }}</el-tag>
    </div>

    <div ref="messageListRef" class="message-list scrollable">
      <div v-if="messages.length === 0" class="empty-state">
        <el-icon :size="48" color="#c0c4cc"><ChatDotRound /></el-icon>
        <p>开始一段新对话吧</p>
      </div>

      <div
        v-for="msg in processedMessages"
        :key="msg.id"
        class="message-item"
        :class="msg.role"
      >
        <div class="message-avatar">
          <el-avatar :size="32" :style="avatarStyle(msg.role)">
            {{ msg.role === 'user' ? '我' : 'AI' }}
          </el-avatar>
        </div>
        <div class="message-body">
          <div class="message-meta">
            <span class="message-role">{{ msg.role === 'user' ? '我' : '助手' }}</span>
            <span v-if="msg.display_time" class="message-time">{{ msg.display_time }}</span>
          </div>
          <!-- 按 segments 顺序渲染 -->
          <template v-for="(segment, sIdx) in msg.segments" :key="sIdx">
            <!-- Reasoning segment: 深度思考折叠框，工具符号内联 -->
            <div v-if="segment.type === 'reasoning'" class="reasoning-section">
              <el-collapse v-model="segment.expanded">
                <el-collapse-item name="1">
                  <template #title>
                    <span class="reasoning-title">💭 深度思考</span>
                  </template>
                  <div class="reasoning-flow">
                    <template v-for="(part, pIdx) in segment.parts" :key="pIdx">
                      <span v-if="part.type === 'text'" class="flow-text">{{ part.content }}</span>
                      <el-popover
                        v-else-if="part.type === 'tool_symbol'"
                        trigger="click"
                        :width="320"
                        placement="top"
                        @before-enter="onToolSymbolClick(msg, part)"
                      >
                        <template #reference>
                          <span class="tool-symbol" :title="part.toolCall.function?.name || part.toolCall.id">🔧</span>
                        </template>
                        <div class="tool-popover-content">
                          <div class="tool-popover-row"><span class="tp-label">名称:</span>{{ part.toolCall.function?.name || part.toolCall.id }}</div>
                          <div v-if="part.toolCall.result" class="tool-popover-row"><span class="tp-label">结果:</span>{{ truncateText(part.toolCall.result, 200) }}</div>
                          <div class="tool-popover-row"><span class="tp-label">参数:</span>{{ truncateText(part.toolCall.function?.arguments, 200) }}</div>
                        </div>
                      </el-popover>
                    </template>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </div>
            <!-- Text segment: 正文气泡，工具符号内联 -->
            <div v-else-if="segment.type === 'text'" class="message-content" :class="{ error: msg.isError }">
              <div class="content-flow">
                <template v-for="(part, pIdx) in segment.parts" :key="pIdx">
                  <span v-if="part.type === 'text'" class="flow-text">{{ part.content }}</span>
                  <el-popover
                    v-else-if="part.type === 'tool_symbol'"
                    trigger="click"
                    :width="320"
                    placement="top"
                    @before-enter="onToolSymbolClick(msg, part)"
                  >
                    <template #reference>
                      <span class="tool-symbol" :title="part.toolCall.function?.name || part.toolCall.id">🔧</span>
                    </template>
                    <div class="tool-popover-content">
                      <div class="tool-popover-row"><span class="tp-label">名称:</span>{{ part.toolCall.function?.name || part.toolCall.id }}</div>
                      <div v-if="part.toolCall.result" class="tool-popover-row"><span class="tp-label">结果:</span>{{ truncateText(part.toolCall.result, 200) }}</div>
                      <div class="tool-popover-row"><span class="tp-label">参数:</span>{{ truncateText(part.toolCall.function?.arguments, 200) }}</div>
                    </div>
                  </el-popover>
                </template>
              </div>
              <span v-if="msg.isStreaming && sIdx === msg.segments.length - 1" class="streaming-cursor"></span>
            </div>
          </template>
          <!-- 流式光标：当只有 reasoning 还没有 text 时 -->
          <div v-if="msg.isStreaming && !msg.segments.some(s => s.type === 'text')" class="message-content">
            <span class="streaming-cursor"></span>
          </div>
        </div>
      </div>

      <div v-if="chatStore.loading && !chatStore.streaming" class="message-item assistant">
        <div class="message-avatar">
          <el-avatar :size="32" style="background: #409eff">AI</el-avatar>
        </div>
        <div class="message-body">
          <div class="message-role">助手</div>
          <div class="message-content typing">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
          </div>
        </div>
      </div>
    </div>

    <div class="chat-input">
      <el-input
        ref="inputRef"
        v-model="inputText"
        type="textarea"
        :rows="2"
        placeholder="输入消息，按 Enter 发送，Shift+Enter 换行..."
        resize="none"
        @keydown="handleKeydown"
      />
      <el-button
        type="primary"
        :icon="Promotion"
        :loading="chatStore.loading"
        :disabled="!inputText.trim() || chatStore.loading"
        @click="handleSend"
      >
        发送
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { Promotion, ChatDotRound } from '@element-plus/icons-vue'
import { useChatStore } from '../stores/chat'

const chatStore = useChatStore()
const inputText = ref('')
const messageListRef = ref(null)
const inputRef = ref(null)

const messages = computed(() => chatStore.messages)

/**
 * 将 blocks 数组转换为 segments 数组
 * 连续的 reasoning + tool_call 合并为一个 reasoning segment（工具符号内联）
 * tool_call + text 合并为一个 text segment（工具符号在文本前内联）
 */
const processedMessages = computed(() => {
  return messages.value.map(msg => {
    if (!msg.blocks || msg.blocks.length === 0) return { ...msg, segments: [] }

    // 先按类型分组：所有 reasoning → 一个 segment，所有 text → 一个 segment
    // tool_call 内联到它前一个块所属的 segment
    const segments = []
    let reasoningSegment = null
    let textSegment = null
    let lastType = null // 上一个非 tool_call 块的类型

    for (const block of msg.blocks) {
      if (block.type === 'reasoning') {
        if (!reasoningSegment) {
          reasoningSegment = { type: 'reasoning', parts: [], expanded: msg.isStreaming ? ['1'] : [] }
          segments.push(reasoningSegment)
        }
        if (block.content) {
          reasoningSegment.parts.push({ type: 'text', content: block.content })
        }
        lastType = 'reasoning'
      } else if (block.type === 'text') {
        if (!textSegment) {
          textSegment = { type: 'text', parts: [] }
          segments.push(textSegment)
        }
        if (block.content) {
          textSegment.parts.push({ type: 'text', content: block.content })
        }
        lastType = 'text'
      } else if (block.type === 'tool_call') {
        // tool_call 内联到前一个块所属的 segment
        const target = lastType === 'reasoning' ? reasoningSegment
          : lastType === 'text' ? textSegment
          : reasoningSegment || textSegment
        if (target) {
          target.parts.push({ type: 'tool_symbol', toolCall: block.toolCall, _messageId: block._messageId })
        }
      }
    }

    return { ...msg, segments }
  })
})

function truncateText(text, maxLen = 120) {
  if (!text) return ''
  try {
    const parsed = JSON.parse(text)
    text = JSON.stringify(parsed, null, 2)
  } catch {
    // 非 JSON，保持原样
  }
  if (text.length <= maxLen) return text
  return text.slice(0, maxLen) + '...'
}

async function onToolSymbolClick(msg, part) {
  const callId = part.toolCall?.id
  // 优先使用 block 中保存的原始 messageId（tool_call 所属的消息ID）
  const messageId = part._messageId || msg.id
  if (!callId || !messageId) return
  // 如果已有详情（流式时已填充），跳过
  if (part.toolCall.result !== null && part.toolCall.result !== undefined && part.toolCall.status !== 'unknown') return
  await chatStore.loadToolCallDetail(messageId, callId)
}

function avatarStyle(role) {
  return role === 'user'
    ? { background: '#67c23a' }
    : { background: '#409eff' }
}

function focusInput() {
  nextTick(() => {
    if (inputRef.value) {
      inputRef.value.focus()
    }
  })
}

function scrollToBottom() {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  })
}

watch(
  () => chatStore.messages.length,
  () => scrollToBottom()
)

watch(
  () => {
    const last = chatStore.messages[chatStore.messages.length - 1]
    if (!last) return ''
    const textBlock = last.blocks?.find(b => b.type === 'text')
    return textBlock ? textBlock.content : ''
  },
  () => scrollToBottom()
)

watch(
  () => chatStore.loading,
  (newVal) => {
    scrollToBottom()
    if (!newVal) {
      focusInput()
    }
  }
)

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    if (!chatStore.loading) {
      handleSend()
    }
  }
}

function handleSend() {
  const text = inputText.value.trim()
  if (!text || chatStore.loading) return
  inputText.value = ''
  chatStore.sendMessage(text)
}
</script>

<style scoped>
.chat-area {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  background: #fff;
  overflow: hidden !important;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-bottom: 1px solid #e4e7ed;
  background: #fff;
  flex-shrink: 0;
}

.chat-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden !important;
  padding: 16px 20px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #c0c4cc;
}

.empty-state p {
  margin-top: 12px;
  font-size: 14px;
}

.message-item {
  display: flex;
  margin-bottom: 20px;
  gap: 12px;
}

.message-item.user {
  flex-direction: row-reverse;
}

.message-avatar {
  flex-shrink: 0;
}

.message-body {
  max-width: 70%;
}

.message-item.user .message-body {
  text-align: right;
}

.message-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.message-role {
  font-size: 12px;
  color: #909399;
}

.message-time {
  font-size: 11px;
  color: #c0c4cc;
}

.message-content {
  display: inline-block;
  padding: 10px 14px;
  border-radius: 12px;
  background: #f4f4f5;
  text-align: left;
  max-width: 100%;
  margin-bottom: 4px;
}

.message-item.user .message-content {
  background: #409eff;
  color: #fff;
}

.message-content.error {
  background: #fef0f0;
  color: #f56c6c;
  border: 1px solid #fde2e2;
}

.content-flow,
.reasoning-flow {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.6;
}

.reasoning-flow {
  font-size: 13px;
  line-height: 1.5;
  color: #6b7280;
  background: #f9fafb;
  padding: 8px 12px;
  border-radius: 6px;
  border-left: 3px solid #8b5cf6;
}

.flow-text {
  /* inline text within flow */
}

/* 内联工具符号 */
.tool-symbol {
  display: inline;
  cursor: pointer;
  font-size: 14px;
  vertical-align: baseline;
  user-select: none;
  border-radius: 3px;
  padding: 0 1px;
  transition: background 0.15s;
}

.tool-symbol:hover {
  background: rgba(64, 158, 255, 0.15);
}

/* Popover 内容 */
.tool-popover-content {
  font-size: 13px;
  line-height: 1.5;
}

.tool-popover-row {
  margin-bottom: 4px;
  word-break: break-all;
}

.tp-label {
  font-weight: 600;
  margin-right: 4px;
  color: #909399;
}

.streaming-cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  background: #409eff;
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: cursor-blink 1s step-end infinite;
}

@keyframes cursor-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.message-content.typing {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 14px 18px;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #909399;
  animation: blink 1.4s infinite both;
}

.dot:nth-child(2) {
  animation-delay: 0.2s;
}

.dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes blink {
  0%, 80%, 100% {
    opacity: 0.2;
  }
  40% {
    opacity: 1;
  }
}

.reasoning-section {
  margin-bottom: 4px;
}

.reasoning-title {
  font-size: 13px;
  color: #8b5cf6;
  font-weight: 500;
}

.chat-input {
  display: flex;
  gap: 10px;
  padding: 16px 20px;
  border-top: 1px solid #e4e7ed;
  background: #fff;
  align-items: flex-end;
}

.chat-input :deep(.el-textarea__inner) {
  font-size: 14px;
}
</style>
