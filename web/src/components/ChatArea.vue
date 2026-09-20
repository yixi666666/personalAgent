<template>
  <div class="chat-area" @mousemove="handleDotPriority">
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

      <div
        v-for="msg in processedMessages"
        :key="msg.id"
        class="message-item"
        :class="msg.role"
        :data-key="msg.id"
      >
        <div class="message-body">
          <!-- 折叠面板固定在助手正文之前 -->
          <div v-if="msg.role === 'assistant'" class="reasoning-section">
            <el-collapse
              :model-value="getCollapseExpanded(msg)"
              @update:model-value="setCollapseExpanded(msg, $event)"
            >
              <el-collapse-item name="1">
                <template #title>
                  <span class="reasoning-title">
                    <span v-if="msg.isStreaming && chatStore.processingStage" class="processing-dot"></span>
                    {{ msg.isStreaming && chatStore.processingStage
                      ? chatStore.processingStage
                      : `使用了 ${msg.collapsePanel.toolCount} 次工具` }}
                  </span>
                </template>
                <div class="reasoning-flow">
                  <div v-if="msg.collapsePanel.universities.length" class="message-universities">
                    <template v-for="uni in msg.collapsePanel.universities" :key="uni.name">
                      <button
                        v-if="!uni.suspicious"
                        class="uni-chip"
                        type="button"
                        :title="'查看 ' + uni.name"
                        @click="selectUniversity(uni.name)"
                      >
                        {{ uni.name }}
                      </button>
                      <span v-else class="uni-chip suspicious" title="疑似高校">{{ uni.name }}</span>
                    </template>
                  </div>
                  <template v-for="(part, pIdx) in msg.collapsePanel.parts" :key="pIdx">
                    <span v-if="part.type === 'text'" class="markdown-body" v-html="renderMarkdown(part.content)"></span>
                    <el-popover
                      v-else-if="part.type === 'tool_symbol'"
                      trigger="click"
                      :width="360"
                      placement="top"
                      @before-enter="onToolSymbolClick(msg, part)"
                    >
                      <template #reference>
                        <span class="tool-symbol" :title="part.toolCall.function?.name || part.toolCall.id">🔧</span>
                      </template>
                      <div class="tool-popover-content">
                        <div class="tool-popover-row"><span class="tp-label">名称:</span>{{ part.toolCall.function?.name || part.toolCall.id }}</div>
                        <div v-if="part.toolCall.result" class="tool-popover-row">
                          <span class="tp-label">结果:</span>
                          <div class="tool-scroll-box" v-html="renderToolContent(part.toolCall.result)"></div>
                        </div>
                        <div class="tool-popover-row">
                          <span class="tp-label">参数:</span>
                          <div class="tool-scroll-box" v-html="renderToolContent(part.toolCall.function?.arguments)"></div>
                        </div>
                      </div>
                    </el-popover>
                  </template>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>
          <template v-for="(segment, sIdx) in msg.segments" :key="sIdx">
            <!-- Text segment: 正文气泡，正文阶段工具符号内联 -->
            <div v-if="segment.type === 'text'" class="message-content" :class="{ error: msg.isError }">
              <div class="content-flow">
                <template v-for="(part, pIdx) in segment.parts" :key="pIdx">
                  <span v-if="part.type === 'text'" class="markdown-body" v-html="renderMarkdown(part.content)"></span>
                  <el-popover
                    v-else-if="part.type === 'tool_symbol'"
                    trigger="click"
                    :width="360"
                    placement="top"
                    @before-enter="onToolSymbolClick(msg, part)"
                  >
                    <template #reference>
                      <span class="tool-symbol" :title="part.toolCall.function?.name || part.toolCall.id">🔧</span>
                    </template>
                    <div class="tool-popover-content">
                      <div class="tool-popover-row"><span class="tp-label">名称:</span>{{ part.toolCall.function?.name || part.toolCall.id }}</div>
                      <div v-if="part.toolCall.result" class="tool-popover-row">
                        <span class="tp-label">结果:</span>
                        <div class="tool-scroll-box" v-html="renderToolContent(part.toolCall.result)"></div>
                      </div>
                      <div class="tool-popover-row">
                        <span class="tp-label">参数:</span>
                        <div class="tool-scroll-box" v-html="renderToolContent(part.toolCall.function?.arguments)"></div>
                      </div>
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
          <div v-if="messageText(msg)" class="message-actions">
            <button
              class="message-action-btn copy-message-btn"
              type="button"
              :title="copiedMessageId === msg.id ? '已复制' : '复制内容'"
              @click="copyMessage(msg)"
            >
              <span v-if="copiedMessageId === msg.id" class="copy-success">🗸</span>
              <el-icon v-else><CopyDocument /></el-icon>
            </button>
            <template v-if="msg.role === 'assistant'">
              <button
                class="message-action-btn"
                :class="{ active: messageFeedback[msg.id] === 'like' }"
                type="button"
                title="喜欢"
                :aria-pressed="messageFeedback[msg.id] === 'like'"
                @click="setMessageFeedback(msg.id, 'like')"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path class="thumb-cuff" d="M7 10v12H3V10h4Z" />
                  <path class="thumb-body" d="M7 10 11.4 2a2.3 2.3 0 0 1 4.4 1.8L15 7h4.7a2 2 0 0 1 2 2.3l-1.5 9a2 2 0 0 1-2 1.7H7Z" />
                </svg>
              </button>
              <button
                class="message-action-btn"
                :class="{ active: messageFeedback[msg.id] === 'dislike' }"
                type="button"
                title="不喜欢"
                :aria-pressed="messageFeedback[msg.id] === 'dislike'"
                @click="setMessageFeedback(msg.id, 'dislike')"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path class="thumb-cuff" d="M7 14V2H3v12h4Z" />
                  <path class="thumb-body" d="M7 14 11.4 22a2.3 2.3 0 0 0 4.4-1.8L15 17h4.7a2 2 0 0 0 2-2.3l-1.5-9a2 2 0 0 0-2-1.7H7Z" />
                </svg>
              </button>
              <button
                class="message-action-btn"
                type="button"
                title="在新对话中继续"
                aria-label="在新对话中继续"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M3 12h8" />
                  <path d="m11 12 9-8" />
                  <path d="m11 12 9 8" />
                  <path d="M15 4h5v5" />
                  <path d="M15 20h5v-5" />
                </svg>
              </button>
              <button
                class="message-action-btn"
                type="button"
                title="重试"
                aria-label="重试"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
                  <path d="M21 3v5h-5" />
                  <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
                  <path d="M8 16H3v5" />
                </svg>
              </button>
            </template>
            <el-popconfirm
              v-else
              title="确认回退吗？之后的消息将消失不可见"
              confirm-button-text="确认"
              cancel-button-text="取消"
              placement="bottom-end"
              :offset="6"
              popper-class="rollback-popconfirm"
              width="320"
            >
              <template #reference>
                <button
                  class="message-action-btn"
                  type="button"
                  title="回退"
                  aria-label="回退"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M9 14 4 9l5-5" />
                    <path d="M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5a5.5 5.5 0 0 1-5.5 5.5H11" />
                  </svg>
                </button>
              </template>
            </el-popconfirm>
          </div>
        </div>
      </div>

      <div v-if="chatStore.loading && !chatStore.streaming" class="message-item assistant">
        <div class="message-body">
          <div v-if="chatStore.processingStage" class="processing-stage">
            <span class="processing-dot"></span>
            {{ chatStore.processingStage }}
          </div>
          <div class="message-role">助手</div>
          <div class="message-content typing">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
          </div>
        </div>
      </div>
    </div>

    <div
      v-if="userMessages.length > 2"
      class="msg-dot-column"
      :class="{ prioritized: dotPrioritized }"
    >
      <div
        class="msg-dot-track"
        :class="{ expanded: dotListVisible }"
        @mouseenter="showDotList"
        @mouseleave="hideDotList"
      >
        <button
          v-for="(msg, idx) in userMessages"
          :key="msg.id"
          class="msg-dot"
          type="button"
          :aria-label="`跳转到第 ${idx + 1} 条用户消息`"
          @click="scrollToMessage(msg.id)"
        >
          <span class="dot-list-text">{{ messageText(msg) }}</span>
        </button>
      </div>
    </div>

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
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { Promotion, ChatDotRound, CopyDocument } from '@element-plus/icons-vue'
import { useChatStore } from '../stores/chat'
import MarkdownIt from 'markdown-it'
import tm from 'markdown-it-texmath'
import hljs from 'highlight.js'
import katex from 'katex'
import 'highlight.js/styles/github.css'
import 'katex/dist/katex.min.css'
import 'markdown-it-texmath/css/texmath.css'

// 配置 markdown-it + texmath + 代码高亮
const md = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
  typographer: true,
  highlight(str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try { return hljs.highlight(str, { language: lang }).value } catch {}
    }
    try { return hljs.highlightAuto(str).value } catch {}
    return ''
  }
})
md.use(tm, { engine: katex, delimiters: ['dollars', 'brackets', 'beg_end'] })

const emit = defineEmits(['toggle-university'])
const chatStore = useChatStore()
const inputText = ref('')
const messageListRef = ref(null)
const inputRef = ref(null)
const isUserAtBottom = ref(true)
const todoExpanded = ref(['todo'])
const copiedMessageId = ref(null)
const messageFeedback = ref({})
const collapseExpandedByMessage = ref({})
const dotListVisible = ref(false)
const dotPrioritized = ref(false)
let copyResetTimer = null
let dotHideTimer = null

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
const userMessages = computed(() => messages.value.filter(msg => msg.role === 'user'))
const isNewSession = computed(() => !chatStore.currentSessionId && messages.value.length === 0)

const isDeepThinkModel = computed(() => {
  const model = chatStore.models.find(m => m.id === chatStore.currentModel)
  return model?.capabilities?.deep_thinking === true
})

// 切换模型时，如果新模型不支持深度思考，自动关闭
watch(isDeepThinkModel, (val) => {
  if (!val) chatStore.deepThinking = false
})

function getCollapseExpanded(msg) {
  const saved = collapseExpandedByMessage.value[msg.id]
  if (saved !== undefined) return saved ? ['1'] : []
  return (msg.isStreaming || msg._wasStreaming) ? ['1'] : []
}

function setCollapseExpanded(msg, value) {
  collapseExpandedByMessage.value[msg.id] = value.includes('1')
}

/**
 * 将消息块整理为固定在正文前的折叠面板和正文区域。
 * 工具调用跟随最近的内容阶段；前置工具默认属于折叠面板。
 */
const processedMessages = computed(() => {
  return messages.value.map(msg => {
    const collapsePanel = {
      parts: [],
      universities: [],
      toolCount: 0,
    }
    const textSegment = { type: 'text', parts: [] }
    const seenUniversity = new Set()
    let lastType = null

    for (const block of msg.blocks || []) {
      if (block.type === 'reasoning') {
        if (block.content) {
          collapsePanel.parts.push({ type: 'text', content: block.content })
        }
        lastType = 'reasoning'
      } else if (block.type === 'text') {
        if (block.content) {
          textSegment.parts.push({ type: 'text', content: block.content })
        }
        lastType = 'text'
      } else if (block.type === 'tool_call') {
        // 高校识别结果固定放在折叠面板顶部，不显示为工具符号。
        if (block.toolCall?.function?.name === 'query_understanding') {
          collapsePanel.toolCount++
          const uniData = parseUniversityResult(block.toolCall.result)
          for (const uni of uniData?.confirmed || []) {
            if (uni.name && !seenUniversity.has(uni.name)) {
              seenUniversity.add(uni.name)
              collapsePanel.universities.push({ name: uni.name, suspicious: false })
            }
          }
          for (const uni of uniData?.suspicious || []) {
            if (uni.name && !seenUniversity.has(uni.name)) {
              seenUniversity.add(uni.name)
              collapsePanel.universities.push({ name: uni.name, suspicious: true })
            }
          }
          continue
        }

        const toolPart = {
          type: 'tool_symbol',
          toolCall: block.toolCall,
          _messageId: block._messageId,
        }
        if (lastType === 'text') {
          textSegment.parts.push(toolPart)
        } else {
          collapsePanel.parts.push(toolPart)
          collapsePanel.toolCount++
        }
      }
    }

    const segments = textSegment.parts.length > 0 ? [textSegment] : []
    return { ...msg, collapsePanel, segments }
  })
})

function formatToolText(text) {
  if (!text) return ''
  try {
    const parsed = JSON.parse(text)
    return JSON.stringify(parsed, null, 2)
  } catch {
    return text
  }
}

function renderToolContent(text) {
  if (!text) return ''
  // 尝试 JSON 解析（可能是对象/数组）
  try {
    const parsed = JSON.parse(text)
    if (typeof parsed === 'string') {
      // 解析后是字符串，渲染换行
      return `<div style="white-space:pre-wrap;word-break:break-word;">${escapeHtml(parsed)}</div>`
    }
    // 是对象/数组，格式化展示
    const formatted = JSON.stringify(parsed, null, 2)
    return `<pre style="margin:0;white-space:pre-wrap;word-break:break-word;">${escapeHtml(formatted)}</pre>`
  } catch {
    // 非 JSON，将 \n 转为真正换行后渲染
    const realText = text.replace(/\\n/g, '\n')
    return `<div style="white-space:pre-wrap;word-break:break-word;">${escapeHtml(realText)}</div>`
  }
}

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

function parseUniversityResult(resultStr) {
  if (!resultStr) return null
  try {
    const parsed = JSON.parse(resultStr)
    return parsed?.universities || null
  } catch {
    return null
  }
}

function selectUniversity(name) {
  chatStore.selectedUniversity = name
  chatStore.universitySelectSeq++
}

function renderMarkdown(text) {
  if (!text) return ''
  // 预处理：将 LaTeX 分隔符转为 $ 格式，避免 markdown-it 转义 \( \) \[ \]
  let processed = text
  // 块级公式：\[...\] → $$...$$（先处理，避免部分匹配行内）
  processed = processed.replace(/\\\[([\s\S]*?)\\\]/g, (_, formula) => `$$${formula.trim()}$$`)
  // 行内公式：\(...\) → $...$
  processed = processed.replace(/\\\(([\s\S]*?)\\\)/g, (_, formula) => `$${formula.trim()}$`)
  // 独占一行的裸 [ 转为 $$（模型有时不用 \[ 而用 [ ）
  processed = processed.replace(/^(\s*)\[\s*$/gm, '$1$$')
  processed = processed.replace(/^\s*\](\s*)$/gm, '$$$1')
  // 行内裸 ( ... ) 包含 LaTeX 命令时转为 $...$
  // 排除 \left( 和 \right) 的情况，避免破坏块级公式
  // 先用占位符保护已有的 $...$ 和 $$...$$ 内容，防止裸括号正则误匹配公式内部的括号
  const mathPlaceholders = []
  const placeholder = (idx) => `\x00MATH${idx}\x00`
  processed = processed.replace(/\$\$[\s\S]+?\$\$|\$[^$\n]+?\$/g, (match) => {
    const idx = mathPlaceholders.length
    mathPlaceholders.push(match)
    return placeholder(idx)
  })
  processed = processed.replace(/(?<!\\left)\(([^)]*?\\(?:frac|sqrt|dfrac|text|quad|cdot|times|alpha|beta|gamma|delta|epsilon|theta|lambda|mu|pi|sigma|omega|sum|prod|int|lim|infty|partial|nabla|mathbb|operatorname|mathrm|mathbf|overline|underline|vec|hat|bar|dot|ddot|tilde|widehat|widetilde)[^)]*?)(?<!\\right)\)/g, (_, formula) => `$${formula.trim()}$`)
  // 还原占位符
  processed = processed.replace(/\x00MATH(\d+)\x00/g, (_, idx) => mathPlaceholders[parseInt(idx)])
  // 清理 $/$$ 与公式内容之间的空格（texmath dollars 规则要求 $ 紧跟非空格字符）
  // 处理 $$ ... $$
  processed = processed.replace(/\$\$\s*([\s\S]+?)\s*\$\$/g, '$$$1$$')
  // 处理 $ ... $（单 $，需排除 $$ 的干扰）
  processed = processed.replace(/(?<!\$)\$(?!\$)\s*([^$\n]+?)\s*\$(?!\$)/g, '$$$1$$')
  return md.render(processed)
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

function messageText(msg) {
  return (msg.blocks || [])
    .filter(block => block.type === 'text' && block.content)
    .map(block => block.content)
    .join('\n')
    .trim()
}

function setMessageFeedback(messageId, feedback) {
  messageFeedback.value[messageId] = messageFeedback.value[messageId] === feedback ? null : feedback
}

async function copyMessage(msg) {
  const text = messageText(msg)
  if (!text) return
  copiedMessageId.value = msg.id
  clearTimeout(copyResetTimer)
  copyResetTimer = setTimeout(() => {
    copiedMessageId.value = null
  }, 1500)
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    textarea.remove()
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

function handleDotPriority(event) {
  const track = event.currentTarget.querySelector('.msg-dot-track')
  if (!track) {
    dotPrioritized.value = false
    return
  }
  const rect = track.getBoundingClientRect()
  dotPrioritized.value = event.clientX >= rect.left && event.clientX <= rect.right
    && event.clientY >= rect.top && event.clientY <= rect.bottom
}

function showDotList() {
  clearTimeout(dotHideTimer)
  dotListVisible.value = true
}

function hideDotList() {
  dotHideTimer = setTimeout(() => {
    dotListVisible.value = false
  }, 200)
}

function scrollToMessage(msgId) {
  const message = messageListRef.value?.querySelector(`.message-item[data-key="${msgId}"]`)
  message?.scrollIntoView({ behavior: 'instant', block: 'center' })
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

onBeforeUnmount(() => {
  clearTimeout(dotHideTimer)
})
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

.msg-dot-column {
  position: absolute;
  right: 36px;
  top: 56px;
  bottom: 80px;
  z-index: 40;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
}

.msg-dot-column.prioritized {
  z-index: 60;
}

/* 最多展示 8 个圆点的高度，更多则在轨道内滚动 */
.msg-dot-track {
  position: absolute;
  right: 0;
  top: 50%;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: center;
  justify-content: safe center;
  width: 32px;
  transform: translateY(-50%);
  box-sizing: border-box;
  max-height: 288px;
  overflow-y: auto;
  overflow-x: hidden;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  scrollbar-width: none;
  transition: width 0.15s ease, background 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
}

.msg-dot-track.expanded {
  width: 314px;
  border-color: #e4e7ed;
  background: #fff;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.12);
}

.msg-dot-track::-webkit-scrollbar {
  width: 0;
  height: 0;
}

/* 圆点始终固定在按钮右侧，不参与任何悬浮变化 */
.msg-dot {
  position: relative;
  display: flex;
  flex: 0 0 36px;
  align-items: center;
  width: 312px;
  height: 36px;
  padding: 0 22px 0 12px;
  border: 0;
  background: transparent;
  color: #606266;
  text-align: left;
  cursor: pointer;
}

.msg-dot::after {
  content: '';
  position: absolute;
  right: 11px;
  top: 50%;
  width: 10px;
  height: 10px;
  margin-top: -5px;
  border-radius: 50%;
  background: #dcdfe6;
}

.msg-dot:hover {
  background: #f5f7fa;
}

.dot-list-text {
  min-width: 0;
  overflow: hidden;
  opacity: 0;
  font-size: 14px;
  line-height: 1.5;
  white-space: nowrap;
  text-overflow: ellipsis;
  transition: opacity 0.1s ease;
}

.msg-dot-track.expanded .dot-list-text {
  opacity: 1;
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
}

.message-item.user {
  flex-direction: row-reverse;
}

.message-body {
  max-width: 70%;
}

.message-item.user .message-body {
  margin-right: 44px;
  text-align: right;
}

.processing-stage {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-bottom: 6px;
  padding: 4px 12px;
  border-radius: 16px;
  background: #f0f9ff;
  color: #409eff;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.4;
  user-select: none;
  width: fit-content;
}

.processing-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #409eff;
  animation: processing-pulse 1s ease-in-out infinite;
}

@keyframes processing-pulse {
  0%, 100% { opacity: 0.3; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.2); }
}

.message-actions {
  display: flex;
  gap: 2px;
  margin-top: 2px;
}

.message-item.user .message-actions {
  justify-content: flex-end;
}

:global(.rollback-popconfirm) {
  --el-bg-color-overlay: #f2f3f5;
  background: #f2f3f5 !important;
  border-color: #dcdfe6 !important;
}

:global(.rollback-popconfirm .el-popconfirm__main) {
  white-space: nowrap;
}

:global(.rollback-popconfirm .el-popconfirm__action) {
  margin-top: 4px;
}

:global(.rollback-popconfirm .el-popper__arrow::before) {
  background: #f2f3f5 !important;
  border-color: #dcdfe6 !important;
}

.message-action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  border: 0;
  background: transparent;
  color: #79bbff;
  font-size: 16px;
  cursor: pointer;
}

.message-action-btn:hover {
  color: #66b1ff;
  background: transparent;
}

.copy-message-btn {
  color: #409eff;
}

.copy-message-btn:hover {
  color: #337ecc;
}

.message-action-btn.active {
  color: #409eff;
  background: transparent;
}

.message-action-btn svg {
  width: 16px;
  height: 16px;
}

.message-action-btn.active .thumb-body {
  fill: currentColor;
}

.message-action-btn.active .thumb-cuff {
  fill: #fff;
}

.copy-success {
  font-weight: 600;
  line-height: 1;
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

.content-flow {
  word-break: break-word;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.6;
}

.reasoning-flow {
  word-break: break-word;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.5;
  color: #6b7280;
  padding: 4px 0 8px;
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
  margin-bottom: 6px;
  word-break: break-all;
}

.tool-scroll-box {
  max-height: 200px;
  overflow-y: auto;
  overflow-x: hidden;
  white-space: pre-wrap;
  word-break: break-word;
  background: #f5f7fa;
  border-radius: 4px;
  padding: 6px 8px;
  margin-top: 2px;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.4;
}

.tp-label {
  font-weight: 600;
  margin-right: 4px;
  color: #909399;
}

/* 已识别高校名称 */
.message-universities {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 6px;
}

.uni-chip {
  padding: 4px 10px;
  border: none;
  border-radius: 6px;
  background: #f0f9eb;
  color: #303133;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.5;
  cursor: pointer;
  transition: background 0.15s;
}

.uni-chip:hover {
  background: #e1f3d8;
}

.uni-chip.suspicious {
  border: 1px dashed #b3e19d;
  color: #e6a23c;
  cursor: default;
}

.uni-chip.suspicious:hover {
  background: #f0f9eb;
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

.reasoning-section :deep(.el-collapse) {
  border: none;
}

.reasoning-section :deep(.el-collapse-item__header) {
  justify-content: flex-start;
  height: 34px;
  line-height: 34px;
  padding: 0;
  border: none;
  background: transparent;
}

.reasoning-section :deep(.el-collapse-item__title) {
  flex: 0 0 auto;
}

.reasoning-section :deep(.el-collapse-item__arrow) {
  flex: 0 0 auto;
  margin: 0 0 0 6px;
  color: #909399;
}

.reasoning-section :deep(.el-collapse-item__wrap) {
  border: none;
  background: transparent;
}

.reasoning-section :deep(.el-collapse-item__content) {
  padding: 0;
}

/* Todo 面板 */
.todo-panel-wrapper {
  flex-shrink: 0;
  border-top: 1px solid #e4e7ed;
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

.reasoning-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: #909399;
  font-weight: 400;
}

/* Markdown 渲染样式 */
.markdown-body { display: inline; }
.markdown-body :deep(p:first-child) { display: inline; }
.markdown-body :deep(h1) { font-size: 1.5em; margin: 0.6em 0 0.4em; font-weight: 700; border-bottom: 1px solid #e4e7ed; padding-bottom: 0.3em; }
.markdown-body :deep(h2) { font-size: 1.3em; margin: 0.5em 0 0.3em; font-weight: 700; border-bottom: 1px solid #e4e7ed; padding-bottom: 0.3em; }
.markdown-body :deep(h3) { font-size: 1.15em; margin: 0.4em 0 0.2em; font-weight: 600; }
.markdown-body :deep(h4) { font-size: 1em; margin: 0.4em 0 0.2em; font-weight: 600; }
.markdown-body :deep(p) { margin: 0.4em 0; }
.markdown-body :deep(ul), .markdown-body :deep(ol) { padding-left: 1.5em; margin: 0.4em 0; }
.markdown-body :deep(li) { margin: 0.15em 0; }
.markdown-body :deep(table) { border-collapse: collapse; margin: 0.5em 0; width: 100%; }
.markdown-body :deep(th), .markdown-body :deep(td) { border: 1px solid #dcdfe6; padding: 6px 10px; text-align: left; font-size: 13px; }
.markdown-body :deep(th) { background: #f5f7fa; font-weight: 600; }
.markdown-body :deep(tr:nth-child(even)) { background: #fafafa; }
.markdown-body :deep(blockquote) { border-left: 3px solid #dcdfe6; padding: 4px 12px; margin: 0.5em 0; color: #606266; background: #fafafa; }
.markdown-body :deep(code) { background: #f0f2f5; padding: 2px 5px; border-radius: 3px; font-size: 0.9em; font-family: 'Menlo', 'Monaco', 'Courier New', monospace; }
.markdown-body :deep(pre) { background: #f0f2f5; padding: 10px 12px; border-radius: 6px; overflow-x: auto; margin: 0.5em 0; }
.markdown-body :deep(pre code) { background: none; padding: 0; font-size: 0.9em; }
.markdown-body :deep(hr) { border: none; border-top: 1px solid #e4e7ed; margin: 0.8em 0; }
.markdown-body :deep(strong) { font-weight: 700; }
.markdown-body :deep(em) { font-style: italic; }
.markdown-body :deep(a) { color: #409eff; text-decoration: none; }
.markdown-body :deep(a:hover) { text-decoration: underline; }

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
