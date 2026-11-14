<template>
  <div
    v-if="userMessages.length > 2"
    class="msg-dot-column"
    :class="{ prioritized: dotPrioritized, panel: variant === 'panel' }"
    @mousemove="handleDotPriority"
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
        :class="{ active: msg.id === activeId, current: msg.id === currentId }"
        type="button"
        :aria-label="`跳转到第 ${idx + 1} 条用户消息`"
        @click="emit('jump', msg.id)"
      >
        <span class="dot-list-text">{{ chatStore.messageText(msg) }}</span>
      </button>
    </div>
  </div>
</template>

<script setup>
/**
 * 用户消息快速定位圆点导航：聊天区与后台「反馈上下文」弹窗共用。
 * 悬浮展开消息文本列表，点击通过 jump 事件交给父组件滚动到对应消息。
 */
import { computed, nextTick, onBeforeUnmount, ref, watch, watchEffect } from 'vue'
import { useChatStore } from '../stores/chat'

const props = defineProps({
  /** 消息数组（含 blocks，与 MessageList 同源） */
  messages: { type: Array, default: () => [] },
  /** chat: 聊天区定位；panel: 弹窗内定位（轨道贴边、占满高度） */
  variant: { type: String, default: 'chat' },
  /** 需要特殊标记的用户消息ID（如反馈上下文中被评价回复对应的提问） */
  activeId: { type: String, default: null },
  /** 滚动容器获取函数（返回模板 ref 指向的元素）：联动计算当前视口对应的用户消息 */
  scrollElFn: { type: Function, default: null },
})

const emit = defineEmits(['jump'])
const chatStore = useChatStore()

const userMessages = computed(() => props.messages.filter(msg => msg.role === 'user'))
const dotListVisible = ref(false)
const dotPrioritized = ref(false)
/** 当前视口对应的用户消息ID（随滚动联动） */
const currentId = ref(null)
let dotHideTimer = null

/* ---- 滚动联动：计算视口内“最后一条已滚过的用户消息”作为当前消息 ---- */
let rafId = null

function updateCurrent() {
  const el = props.scrollElFn?.()
  if (!el || !userMessages.value.length) return
  const rect = el.getBoundingClientRect()
  if (!rect.width && !rect.height) return
  let found = null
  for (const msg of userMessages.value) {
    const node = el.querySelector(`.message-item[data-key="${msg.id}"]`)
    if (!node) continue
    const nodeRect = node.getBoundingClientRect()
    // 消息顶部已滚过容器顶部下方 120px 内视为“当前”
    if (nodeRect.top - rect.top <= 120) found = msg.id
    else break
  }
  currentId.value = found || userMessages.value[0]?.id || null
}

function onScroll() {
  if (rafId) return
  rafId = requestAnimationFrame(() => {
    rafId = null
    updateCurrent()
  })
}

// watchEffect 内调用 scrollElFn 会追踪父组件的模板 ref，
// 元素挂载后自动挂上滚动监听（无需父组件重渲染）
watchEffect((onCleanup) => {
  const el = props.scrollElFn?.()
  if (!el) return
  el.addEventListener('scroll', onScroll, { passive: true })
  nextTick(updateCurrent)
  onCleanup(() => el.removeEventListener('scroll', onScroll))
})

watch(userMessages, () => nextTick(updateCurrent))

onBeforeUnmount(() => {
  if (rafId) cancelAnimationFrame(rafId)
  clearTimeout(dotHideTimer)
})

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
</script>

<style scoped>
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

/* 弹窗内：轨道贴边、占满内容区高度 */
.msg-dot-column.panel {
  top: 4px;
  bottom: 4px;
  right: 4px;
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

/* 特殊标记：被评价回复对应的提问圆点（橙色实心 + 展开时文字橙色） */
.msg-dot.active::after {
  background: #e6a23c;
  box-shadow: 0 0 0 3px rgba(230, 162, 60, 0.25);
}

.msg-dot.active .dot-list-text {
  color: #e6a23c;
  font-weight: 600;
}

/* 当前视口对应的圆点：保持原灰色，仅用淡光晕提亮 */
.msg-dot.current::after {
  background: #dcdfe6;
  box-shadow: 0 0 0 3px rgba(220, 223, 230, 0.5);
}

.msg-dot.current .dot-list-text {
  font-weight: 600;
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
</style>
