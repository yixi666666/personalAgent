<template>
  <div>
    <div
      v-for="msg in processedMessages"
      :key="msg.id"
      class="message-item"
      :class="[msg.role, { 'message-item-target': highlightId === msg.id }]"
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
                  <span v-if="msg.isStreaming" class="processing-dot"></span>
                  <span v-if="msg.isStreaming" class="streaming-stage-text">
                    {{ chatStore.processingStage }}
                  </span>
                  <span v-else>使用了 {{ msg.collapsePanel.toolCount }} 次工具</span>
                </span>
              </template>
              <div class="reasoning-flow">
                <div v-if="msg.collapsePanel.universities.length" class="message-universities">
                  <template v-for="uni in msg.collapsePanel.universities" :key="uni.name">
                    <button
                      v-if="!readonly && !uni.suspicious"
                      class="uni-chip"
                      type="button"
                      :title="'查看 ' + uni.name"
                      @click="selectUniversity(uni.name)"
                    >
                      {{ uni.name }}
                    </button>
                    <span v-else class="uni-chip" :class="{ suspicious: uni.suspicious }" :title="uni.suspicious ? '疑似高校' : ''">{{ uni.name }}</span>
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
                      <span class="tool-symbol" :data-tip="part.toolCall.function?.name || part.toolCall.id">🔧</span>
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
                    <span class="tool-symbol" :data-tip="part.toolCall.function?.name || part.toolCall.id">🔧</span>
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
          <template v-if="!readonly && msg.role === 'assistant'">
            <button
              class="message-action-btn"
              :class="{ active: feedbackType(msg.id) === 'like' }"
              type="button"
              title="喜欢"
              :aria-pressed="feedbackType(msg.id) === 'like'"
              @click="onLikeClick(msg.id)"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path class="thumb-cuff" d="M7 10v12H3V10h4Z" />
                <path class="thumb-body" d="M7 10 11.4 2a2.3 2.3 0 0 1 4.4 1.8L15 7h4.7a2 2 0 0 1 2 2.3l-1.5 9a2 2 0 0 1-2 1.7H7Z" />
              </svg>
            </button>
            <button
              class="message-action-btn"
              :class="{ active: feedbackType(msg.id) === 'dislike' }"
              type="button"
              title="不喜欢"
              :aria-pressed="feedbackType(msg.id) === 'dislike'"
              @click="onDislikeClick(msg.id)"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path class="thumb-cuff" d="M7 14V2H3v12h4Z" />
                <path class="thumb-body" d="M7 14 11.4 22a2.3 2.3 0 0 0 4.4-1.8L15 17h4.7a2 2 0 0 0 2-2.3l-1.5-9a2 2 0 0 0-2-1.7H7Z" />
              </svg>
            </button>
            <button
              v-if="msg.id === lastAssistantId && !chatStore.loading"
              class="message-action-btn"
              type="button"
              title="重试"
              aria-label="重试"
              @click="chatStore.retryLastAnswer()"
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
            v-else-if="!readonly"
            title="确认回退吗？之后的消息将消失不可见"
            confirm-button-text="确认"
            cancel-button-text="取消"
            placement="bottom-end"
            :offset="6"
            popper-class="rollback-popconfirm"
            width="320"
            @confirm="emit('rollback', msg)"
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

    <!-- 等待回复的加载气泡（仅聊天模式使用） -->
    <div v-if="!readonly && chatStore.loading && !chatStore.streaming" class="message-item assistant">
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

    <!-- 拉踩原因弹窗：屏幕正中央模态（仅聊天模式） -->
    <el-dialog
      v-if="!readonly"
      :model-value="feedbackPanelMessageId !== null"
      width="420px"
      align-center
      append-to-body
      class="feedback-dialog"
      @close="closeFeedbackPanel"
    >
      <template #header>
        <span class="feedback-panel-title">哪里不满意？</span>
      </template>
      <el-checkbox-group v-model="feedbackPanelReasons" class="feedback-panel-reasons">
        <el-checkbox v-for="r in chatStore.dislikeReasons" :key="r.code" :value="r.code">
          {{ r.label }}
        </el-checkbox>
      </el-checkbox-group>
      <el-input
        v-model="feedbackPanelComment"
        type="textarea"
        :rows="2"
        maxlength="200"
        show-word-limit
        placeholder="补充说明（可选）"
      />
      <template #footer>
        <div class="feedback-panel-actions">
          <span class="feedback-panel-spacer"></span>
          <el-button size="small" @click="closeFeedbackPanel">取消</el-button>
          <el-button size="small" type="primary" @click="onSubmitDislike(feedbackPanelMessageId)">提交</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
/**
 * 消息列表渲染组件：聊天区与后台「反馈上下文」共用。
 * - 聊天模式（readonly=false）：包含点赞/拉踩/重试/回退操作与拉踩弹窗，依赖 chatStore
 * - 只读模式（readonly=true）：仅渲染，highlightId 高亮被评价的消息，
 *   工具详情通过 toolDetailLoader(messageId) 懒加载（管理端走 /v1/admin/tool-calls）
 */
import { computed, ref } from 'vue'
import { CopyDocument } from '@element-plus/icons-vue'
import { useChatStore } from '../stores/chat'
import MarkdownIt from 'markdown-it'
import tm from 'markdown-it-texmath'
import hljs from 'highlight.js'
import katex from 'katex'
import 'highlight.js/styles/github.css'
import 'katex/dist/katex.min.css'
import 'markdown-it-texmath/css/texmath.css'

const props = defineProps({
  /** 消息数组：chatStore.messages 或 buildMessagesFromDetail 的产物（含 blocks） */
  messages: { type: Array, default: () => [] },
  /** 只读模式：隐藏交互按钮，仅渲染 */
  readonly: { type: Boolean, default: false },
  /** 需要高亮的消息ID（管理端被评价消息） */
  highlightId: { type: String, default: null },
  /** 只读模式下工具详情懒加载：async (messageId) => ToolCallDetail[] */
  toolDetailLoader: { type: Function, default: null },
})

const emit = defineEmits(['rollback'])

const chatStore = useChatStore()

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

const copiedMessageId = ref(null)
// 拉踩原因面板：当前打开面板的消息ID + 面板内编辑中的原因/备注
const feedbackPanelMessageId = ref(null)
const feedbackPanelReasons = ref([])
const feedbackPanelComment = ref('')
const collapseExpandedByMessage = ref({})
let copyResetTimer = null

// 最后一条助手回复的 id：重试按钮只显示在它上面
const lastAssistantId = computed(() => {
  for (let i = props.messages.length - 1; i >= 0; i--) {
    if (props.messages[i].role === 'assistant') return props.messages[i].id
  }
  return null
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
  return props.messages.map(msg => {
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
  if (props.readonly) {
    await loadReadonlyToolDetail(msg, messageId)
    return
  }
  await chatStore.loadToolCallDetail(messageId, callId)
}

/** 只读模式懒加载工具详情：就地更新匹配的 tool_call 块，保持引用不变 */
async function loadReadonlyToolDetail(msg, messageId) {
  if (!props.toolDetailLoader) return
  try {
    const toolCallsData = await props.toolDetailLoader(messageId)
    if (!toolCallsData) return
    for (const b of msg.blocks || []) {
      if (b.type !== 'tool_call' || b._messageId !== messageId) continue
      const tc = toolCallsData.find(t => t.call_id === b.toolCall?.id)
      if (tc) {
        b.toolCall.function = { name: tc.tool_name, arguments: tc.parameters }
        b.toolCall.result = tc.result
        b.toolCall.status = tc.status
      }
    }
  } catch (err) {
    console.error('懒加载工具详情失败:', err)
  }
}

function messageText(msg) {
  return chatStore.messageText(msg)
}

/** 当前用户对某消息的反馈类型：'like' | 'dislike' | null */
function feedbackType(messageId) {
  return chatStore.feedbacks[messageId]?.feedback_type || null
}

/** 点赞：未点赞则提交，已点赞则撤销（toggle） */
async function onLikeClick(messageId) {
  if (feedbackType(messageId) === 'like') {
    await chatStore.revokeFeedback(messageId)
  } else {
    await chatStore.submitFeedback(messageId, 'like')
  }
}

/** 拉踩：已激活则直接撤销（toggle），未激活则打开原因面板 */
async function onDislikeClick(messageId) {
  if (feedbackType(messageId) === 'dislike') {
    await chatStore.revokeFeedback(messageId)
    return
  }
  const current = chatStore.feedbacks[messageId]
  feedbackPanelMessageId.value = messageId
  feedbackPanelReasons.value = current?.feedback_type === 'dislike' ? [...(current.reason_codes || [])] : []
  feedbackPanelComment.value = current?.feedback_type === 'dislike' ? (current.comment || '') : ''
  chatStore.loadDislikeReasons()
}

function closeFeedbackPanel() {
  feedbackPanelMessageId.value = null
  feedbackPanelReasons.value = []
  feedbackPanelComment.value = ''
}

/** 提交拉踩反馈（原因与备注可选） */
async function onSubmitDislike(messageId) {
  const ok = await chatStore.submitFeedback(messageId, 'dislike', feedbackPanelReasons.value, feedbackPanelComment.value)
  if (ok) closeFeedbackPanel()
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
</script>

<style scoped>
.message-item {
  display: flex;
  margin-bottom: 20px;
}

.message-item.user {
  flex-direction: row-reverse;
}

/* 管理端高亮被评价的消息 */
.message-item-target .message-body {
  background: rgba(230, 162, 60, 0.08);
  border-radius: 10px;
  padding: 8px;
  margin: -8px;
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

/* 拉踩原因弹窗（el-dialog append-to-body 挂在 body 下，需全局样式） */
:global(.feedback-panel-title) {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

:global(.feedback-panel-reasons) {
  display: flex;
  flex-wrap: wrap;
  gap: 0 4px;
  margin-bottom: 10px;
}

:global(.feedback-panel-reasons .el-checkbox) {
  margin-right: 0;
  height: 26px;
}

:global(.feedback-panel-actions) {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

:global(.feedback-panel-spacer) {
  flex: 1;
}

.message-action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #79bbff;
  font-size: 16px;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.message-action-btn:hover {
  color: #409eff;
  background: rgba(64, 158, 255, 0.12);
}

.copy-message-btn {
  color: #409eff;
}

.copy-message-btn:hover {
  color: #337ecc;
  background: rgba(64, 158, 255, 0.12);
}

.message-action-btn.active {
  color: #409eff;
  background: rgba(64, 158, 255, 0.18);
}

.message-action-btn.active:hover {
  background: rgba(64, 158, 255, 0.28);
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

/* 内联工具符号 */
.tool-symbol {
  display: inline;
  position: relative;
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

/* 悬浮即时显示工具名（纯 CSS 实现，无延迟；浅色样式同原生提示） */
.tool-symbol::after {
  content: attr(data-tip);
  position: absolute;
  bottom: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
  background: #fff;
  color: #303133;
  border: 1px solid #dcdfe6;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  font-size: 12px;
  line-height: 1;
  padding: 5px 8px;
  border-radius: 4px;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.1s;
  z-index: 2000;
}

.tool-symbol:hover::after {
  opacity: 1;
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
</style>
