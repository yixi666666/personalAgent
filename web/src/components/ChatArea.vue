<template>
  <div class="chat-area">
    <div class="chat-header">
      <span class="chat-title">
        {{ chatStore.currentConversationId
          ? '会话 ' + chatStore.currentConversationId.slice(0, 8)
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
        v-for="msg in messages"
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
          <div class="message-role">{{ msg.role === 'user' ? '我' : '助手' }}</div>
          <div class="message-content" :class="{ error: msg.isError }">
            <pre class="content-text">{{ msg.content }}</pre>
            <span v-if="msg.isStreaming" class="streaming-cursor"></span>
          </div>
          <div v-if="msg.toolCalls && msg.toolCalls.length > 0" class="tool-calls">
            <el-collapse>
              <el-collapse-item title="🔧 工具调用">
                <div v-for="(tc, idx) in msg.toolCalls" :key="idx" class="tool-call-item">
                  <el-tag size="small" type="warning">{{ tc.tool_name }}</el-tag>
                  <span class="tool-args">{{ JSON.stringify(tc.tool_args) }}</span>
                  <div v-if="tc.result" class="tool-result">
                    <strong>结果：</strong>{{ tc.result }}
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>
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
    return last ? last.content : ''
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

.message-role {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.message-content {
  display: inline-block;
  padding: 10px 14px;
  border-radius: 12px;
  background: #f4f4f5;
  text-align: left;
  max-width: 100%;
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

.content-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.6;
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

.tool-calls {
  margin-top: 8px;
}

.tool-call-item {
  margin-bottom: 8px;
  font-size: 13px;
}

.tool-args {
  color: #606266;
  margin-left: 6px;
  font-family: monospace;
  font-size: 12px;
}

.tool-result {
  margin-top: 4px;
  color: #67c23a;
  font-size: 12px;
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
