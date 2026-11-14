<template>
  <div class="chat-area">
    <div class="chat-header">
      <span v-if="chatStore.currentSessionId" class="chat-title">
        {{ chatStore.currentSession?.title || '会话 ' + chatStore.currentSessionId.slice(0, 8) }}
      </span>
      <button
        v-if="chatStore.currentSessionId"
        class="university-toggle-btn"
        type="button"
        title="展开/收起高校面板"
        aria-label="展开或收起高校面板"
        @click="emit('toggle-university')"
      >
        🏫
      </button>
    </div>

    <div class="chat-main" :class="{ 'new-session': isNewSession }">
      <section v-if="isNewSession" class="new-session-welcome">
        <h1>想了解什么高校信息呢？</h1>
        <div class="recommended-questions">
          <button
            v-for="question in recommendedQuestions"
            :key="question"
            type="button"
            :disabled="chatStore.loading || !chatStore.currentModel"
            @click="sendRecommendation(question)"
          >
            {{ question }}
          </button>
        </div>
      </section>

      <div v-show="!isNewSession" ref="messageListRef" class="message-list scrollable" @scroll="handleScroll">
      <div v-if="messages.length === 0" class="empty-state">
        <el-icon :size="48" color="#c0c4cc"><ChatDotRound /></el-icon>
        <p>开始一段新对话吧</p>
      </div>

      <MessageList :messages="messages" @rollback="onRollback" />
      </div>

      <MsgDotNav :messages="messages" :scroll-el-fn="getMessageListEl" @jump="scrollToMessage" />

    <!-- Todo 面板：输入框上方，可折叠 -->
    <div v-if="chatStore.currentTodos" class="todo-panel-wrapper">
      <el-collapse v-model="todoExpanded">
        <el-collapse-item name="todo">
          <template #title>
            <span class="todo-panel-title">📋 任务计划</span>
          </template>
          <div class="todo-list">
            <div
              v-for="(todo, tIdx) in chatStore.currentTodos.todos"
              :key="tIdx"
              class="todo-item"
              :class="todo.status"
            >
              <span class="todo-status" :class="todo.status"></span>
              <span class="todo-action">{{ todo.action }}</span>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </div>

    <div class="chat-input-wrapper">
      <div class="chat-input">
        <el-input
          ref="inputRef"
          v-model="inputText"
          type="textarea"
          :rows="2"
          placeholder="输入消息，按 Enter 发送，Shift+Enter 换行..."
          resize="none"
          @keydown="handleKeydown"
          @input="autoResize"
        />
      </div>
      <div class="input-actions">
        <div class="model-selector-inline">
          <el-select v-model="chatStore.currentModel" size="small">
            <el-option
              v-for="m in chatStore.models"
              :key="m.id"
              :label="m.name"
              :value="m.id"
            />
          </el-select>
        </div>
        <button
          v-if="isDeepThinkModel"
          class="action-btn deep-thinking-btn"
          :class="{ active: chatStore.deepThinking }"
          @click="chatStore.deepThinking = !chatStore.deepThinking"
        >
          <span class="action-icon">💭</span>
          <span class="action-label">深度思考</span>
        </button>
        <el-button
          type="primary"
          :icon="Promotion"
          :loading="chatStore.loading"
          :disabled="!inputText.trim() || chatStore.loading || !chatStore.currentModel"
          @click="handleSend"
        >
          发送
        </el-button>
      </div>
    </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { Promotion, ChatDotRound } from '@element-plus/icons-vue'
import { useChatStore } from '../stores/chat'
import MessageList from './MessageList.vue'
import MsgDotNav from './MsgDotNav.vue'

const emit = defineEmits(['toggle-university'])
const chatStore = useChatStore()
const inputText = ref('')
const messageListRef = ref(null)
const inputRef = ref(null)
const isUserAtBottom = ref(true)
const todoExpanded = ref(['todo'])

const MAX_INPUT_HEIGHT = 300 // px，约12行

function autoResize() {
  nextTick(() => {
    const textarea = inputRef.value?.textarea
    if (!textarea) return
    textarea.style.height = 'auto'
    const newHeight = Math.min(textarea.scrollHeight, MAX_INPUT_HEIGHT)
    textarea.style.height = newHeight + 'px'
    // 内容溢出时添加 scrollable 类以显示滚动条，否则移除
    if (textarea.scrollHeight > MAX_INPUT_HEIGHT) {
      textarea.classList.add('scrollable')
      textarea.style.overflowY = 'scroll'
    } else {
      textarea.classList.remove('scrollable')
      textarea.style.overflowY = 'hidden'
    }
  })
}

onMounted(() => {
  autoResize()
})

const recommendedQuestions = [
  '介绍一下你自己',
  '帮我对比浙江大学和南京大学',
  '哪些高校的人工智能专业比较强？',
]

const messages = computed(() => chatStore.messages)
const isNewSession = computed(() => !chatStore.currentSessionId && messages.value.length === 0)

const isDeepThinkModel = computed(() => {
  const model = chatStore.models.find(m => m.id === chatStore.currentModel)
  return model?.capabilities?.deep_thinking === true
})

// 切换模型时，如果新模型不支持深度思考，自动关闭
watch(isDeepThinkModel, (val) => {
  if (!val) chatStore.deepThinking = false
})

// 回退到该用户消息：软删其及之后全部消息，原文本回填输入框
async function onRollback(msg) {
  const content = await chatStore.rollbackToMessage(msg.id)
  if (content !== null) {
    inputText.value = content
    autoResize()
    focusInput()
  }
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

function scrollToMessage(msgId) {
  const message = messageListRef.value?.querySelector(`.message-item[data-key="${msgId}"]`)
  message?.scrollIntoView({ behavior: 'instant', block: 'center' })
}

/** 圆点导航滚动联动：返回消息列表滚动容器（模板 ref） */
function getMessageListEl() {
  return messageListRef.value
}

function handleScroll() {
  const el = messageListRef.value
  if (!el) return
  const threshold = 50
  isUserAtBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight < threshold
}

function smartScrollToBottom() {
  if (isUserAtBottom.value) {
    scrollToBottom()
  }
}

watch(
  () => chatStore.messages.length,
  () => smartScrollToBottom()
)

watch(
  () => {
    const last = chatStore.messages[chatStore.messages.length - 1]
    if (!last) return ''
    const textBlock = last.blocks?.find(b => b.type === 'text')
    return textBlock ? textBlock.content : ''
  },
  () => smartScrollToBottom()
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

function sendRecommendation(question) {
  if (chatStore.loading || !chatStore.currentModel) return
  isUserAtBottom.value = true
  chatStore.sendMessage(question)
}

function handleSend() {
  const text = inputText.value.trim()
  if (!text || chatStore.loading) return
  inputText.value = ''
  isUserAtBottom.value = true
  chatStore.sendMessage(text)
  autoResize()
}
</script>

<style scoped>
.chat-area {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  position: relative;
  background: #fff;
  overflow: hidden !important;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px 20px;
  background: #fff;
  flex-shrink: 0;
  position: relative;
}

.chat-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.university-toggle-btn {
  position: absolute;
  right: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border: 0;
  border-radius: 8px;
  background: #fff;
  font-size: 18px;
  cursor: pointer;
  transition: background 0.2s;
}

.university-toggle-btn:hover {
  background: #ecf5ff;
}

.chat-main {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.chat-main.new-session {
  justify-content: center;
  padding-bottom: 8vh;
}

.new-session-welcome {
  width: min(720px, calc(100% - 40px));
  margin: 0 auto 10px;
  text-align: center;
}

.new-session-welcome h1 {
  margin: 0 0 24px;
  color: #303133;
  font-size: 28px;
  font-weight: 600;
}

.recommended-questions {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.recommended-questions button {
  padding: 5px 8px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #606266;
  font: inherit;
  line-height: 1.5;
  text-align: left;
  cursor: pointer;
  transition: color 0.2s, background-color 0.2s;
}

.recommended-questions button:hover:not(:disabled) {
  background: #f5f7fa;
  color: #409eff;
}

.recommended-questions button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.new-session .chat-input-wrapper {
  width: min(720px, calc(100% - 40px));
  margin: 0 auto;
}

.message-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden !important;
  padding: 16px 48px;
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

/* 拉踩原因弹窗（el-dialog append-to-body 挂在 body 下，需全局样式） */

/* Todo 面板 */
.todo-panel-wrapper {
  flex-shrink: 0;
  margin: 0 92px 0 48px;
  box-sizing: border-box;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  background: #f9fafb;
  max-height: 240px;
  overflow-y: auto;
}

.todo-panel-wrapper :deep(.el-collapse) {
  border: none;
}

.todo-panel-wrapper :deep(.el-collapse-item__header) {
  background: transparent;
  border-bottom: 1px solid #ebeef5;
  padding: 0 16px;
  height: 38px;
  line-height: 38px;
}

.todo-panel-wrapper :deep(.el-collapse-item__wrap) {
  border-bottom: none;
  background: transparent;
}

.todo-panel-wrapper :deep(.el-collapse-item__content) {
  padding: 10px 16px 12px;
}

.todo-panel-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.todo-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.todo-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  line-height: 1.5;
}

.todo-item .todo-status {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}

.todo-item.pending .todo-status {
  border: 2px solid #c0c4cc;
  background: transparent;
}

.todo-item.in_progress .todo-status {
  border: 2px solid #409eff;
  background: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
}

.todo-item.completed .todo-status {
  border: 2px solid #67c23a;
  background: #67c23a;
}

.todo-item.completed .todo-action {
  color: #909399;
  text-decoration: line-through;
}

.todo-item.in_progress .todo-action {
  color: #303133;
  font-weight: 500;
}

.todo-item.pending .todo-action {
  color: #909399;
}

.chat-input-wrapper {
  position: relative;
  z-index: 50;
  flex-shrink: 0;
  margin: 16px 92px 12px 48px;
  overflow: hidden;
  border: 1px solid #dcdfe6;
  border-radius: 12px;
  background: #fff;
}

.chat-input {
  display: flex;
  padding: 10px 12px 0;
}

.chat-input :deep(.el-textarea) {
  flex: 1;
}

.chat-input :deep(.el-textarea__inner) {
  padding: 5px 0;
  border: 0;
  box-shadow: none;
  font-size: 14px;
}

.input-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px 10px;
}

.input-actions .el-button {
  margin-left: auto;
}

.model-selector-inline {
  flex-shrink: 0;
}

.model-selector-inline :deep(.el-select) {
  width: 140px;
}

.model-selector-inline :deep(.el-select__caret) {
  transform: rotate(-90deg) !important;
  transition: none;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border-radius: 16px;
  border: 1px solid #dcdfe6;
  background: #fff;
  color: #909399;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.25s ease;
  user-select: none;
  line-height: 1.4;
}

.action-btn:hover {
  border-color: #c0c4cc;
  color: #606266;
}

.action-icon {
  font-size: 14px;
}

.action-label {
  font-size: 12px;
}

/* 深度思考按钮 - 激活状态：紫色 */
.deep-thinking-btn.active {
  background: #f3e8ff;
  border-color: #8b5cf6;
  color: #8b5cf6;
}

.deep-thinking-btn.active:hover {
  background: #ede4ff;
  border-color: #7c3aed;
}
</style>
