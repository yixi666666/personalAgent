<template>
  <div class="chat-area">
    <div class="chat-header">
      <el-button
        class="sidebar-toggle-btn"
        text
        @click="sidebarCollapsed = !sidebarCollapsed"
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="2" y="4" width="16" height="2" rx="1" fill="currentColor"/>
          <rect x="2" y="9" width="16" height="2" rx="1" fill="currentColor"/>
          <rect x="2" y="14" width="16" height="2" rx="1" fill="currentColor"/>
        </svg>
      </el-button>
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
            <!-- Text segment: 正文气泡，工具符号内联 -->
            <div v-else-if="segment.type === 'text'" class="message-content" :class="{ error: msg.isError }">
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
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, inject } from 'vue'
import { Promotion, ChatDotRound } from '@element-plus/icons-vue'
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

const chatStore = useChatStore()
const inputText = ref('')
const messageListRef = ref(null)
const inputRef = ref(null)
const sidebarCollapsed = inject('sidebarCollapsed')

const messages = computed(() => chatStore.messages)

const isDeepThinkModel = computed(() => {
  const model = chatStore.models.find(m => m.id === chatStore.currentModel)
  return model?.capabilities?.deep_thinking === true
})

// 切换模型时，如果新模型不支持深度思考，自动关闭
watch(isDeepThinkModel, (val) => {
  if (!val) chatStore.deepThinking = false
})

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
          reasoningSegment = { type: 'reasoning', parts: [], expanded: (msg.isStreaming || msg._wasStreaming) ? ['1'] : [] }
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
        let target = lastType === 'reasoning' ? reasoningSegment
          : lastType === 'text' ? textSegment
          : null
        // 如果前面没有 segment，创建一个 text segment 来挂载工具符号
        if (!target) {
          if (!textSegment) {
            textSegment = { type: 'text', parts: [] }
            segments.push(textSegment)
          }
          target = textSegment
        }
        target.parts.push({ type: 'tool_symbol', toolCall: block.toolCall, _messageId: block._messageId })
      }
    }

    return { ...msg, segments }
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
  processed = processed.replace(/(?<!\\left)\(([^)]*?\\(?:frac|sqrt|dfrac|text|quad|cdot|times|alpha|beta|gamma|delta|epsilon|theta|lambda|mu|pi|sigma|omega|sum|prod|int|lim|infty|partial|nabla|mathbb|operatorname|mathrm|mathbf|overline|underline|vec|hat|bar|dot|ddot|tilde|widehat|widetilde)[^)]*?)(?<!\\right)\)/g, (_, formula) => `$${formula.trim()}$`)
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
  justify-content: center;
  padding: 12px 20px;
  border-bottom: 1px solid #e4e7ed;
  background: #fff;
  flex-shrink: 0;
  position: relative;
}

.chat-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.chat-header .el-tag {
  position: absolute;
  right: 20px;
}

.sidebar-toggle-btn {
  position: absolute;
  left: 8px;
  padding: 6px 10px;
  color: #606266;
  background: #f5f7fa;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
}

.sidebar-toggle-btn:hover {
  color: #409eff;
  background: #ecf5ff;
  border-color: #b3d8ff;
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
  border-top: 1px solid #e4e7ed;
  background: #fff;
  flex-shrink: 0;
}

.chat-input {
  display: flex;
  gap: 10px;
  padding: 16px 20px 8px;
  align-items: flex-end;
}

.chat-input :deep(.el-textarea__inner) {
  font-size: 14px;
}

.input-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 20px 12px;
}

.model-selector-inline {
  flex-shrink: 0;
}

.model-selector-inline :deep(.el-select) {
  width: 140px;
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
