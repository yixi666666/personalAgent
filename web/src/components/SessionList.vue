<template>
  <div class="sidebar">
    <div class="sidebar-header">
      <div class="sidebar-brand">
        <span class="sidebar-brand-name">小忆</span>
        <div class="sidebar-brand-actions">
          <button class="header-icon-btn" type="button" title="收件箱" aria-label="收件箱" @click="emit('open-inbox')">
            <el-icon><Message /></el-icon>
          </button>
          <button class="header-icon-btn" type="button" title="搜索会话" aria-label="搜索会话" @click="emit('open-search')">
            <el-icon><Search /></el-icon>
          </button>
        </div>
      </div>
      <el-button type="primary" class="new-chat-btn" @click="chatStore.newSession()">
        <el-icon><Plus /></el-icon>
        <span>新建会话</span>
      </el-button>
    </div>

    <div ref="listRef" class="session-list scrollable" @scroll="handleScroll">
      <div class="session-group-label">置顶</div>
      <div
        v-for="p in pinnedSessions"
        :key="p.id"
        class="session-item pinned"
      >
        <el-icon class="session-icon pinned-icon"><StarFilled /></el-icon>
        <div class="session-info">
          <div class="session-title">{{ p.title }}</div>
        </div>
        <el-dropdown
          class="session-menu"
          trigger="click"
          placement="bottom-end"
          @command="handlePinnedCommand"
        >
          <el-button class="more-btn" text size="small" @click.stop>
            <el-icon><MoreFilled /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="unpin">
                <el-icon><StarFilled /></el-icon>取消置顶
              </el-dropdown-item>
              <el-dropdown-item command="delete" divided style="color: var(--el-color-danger)">
                <el-icon><Delete /></el-icon>删除
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>

      <template v-for="group in sessionGroups" :key="group.key">
        <div v-if="group.items.length > 0" class="session-group-label">{{ group.label }}</div>
        <div
          v-for="s in group.items"
          :key="s.id"
          class="session-item"
          :class="{ active: s.id === chatStore.currentSessionId }"
          @click="chatStore.selectSession(s.id)"
        >
          <el-icon class="session-icon"><ChatDotRound /></el-icon>
          <div class="session-info">
            <div class="session-title">{{ s.title || '会话 ' + s.id.slice(0, 8) }}</div>
          </div>
          <el-dropdown
            class="session-menu"
            trigger="click"
            placement="bottom-end"
            @command="command => handleSessionCommand(command, s.id)"
          >
            <el-button class="more-btn" text size="small" @click.stop>
              <el-icon><MoreFilled /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="pin">
                  <el-icon><Star /></el-icon>置顶
                </el-dropdown-item>
                <el-dropdown-item command="delete" divided style="color: var(--el-color-danger)">
                  <el-icon><Delete /></el-icon>删除
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </template>
      <div v-if="chatStore.sessionsLoading" class="session-list-status">加载中...</div>
      <div
        v-else-if="chatStore.sessions.length > 0 && !chatStore.sessionsHasMore"
        class="session-list-status"
      >没有更多了</div>
      <el-empty v-if="chatStore.sessions.length === 0" description="暂无会话" :image-size="60" />
    </div>

    <div
      class="sidebar-footer"
      role="button"
      tabindex="0"
      aria-label="打开设置"
      @click="emit('open-settings')"
      @keydown.enter="emit('open-settings')"
      @keydown.space.prevent="emit('open-settings')"
    >
      <div class="user-profile">
        <el-avatar :size="36" style="background: #409eff">忆</el-avatar>
        <span class="user-nickname">忆昔</span>
      </div>
      <button class="settings-btn" type="button" title="设置" aria-label="设置" tabindex="-1">
        <el-icon><Setting /></el-icon>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { Plus, Delete, ChatDotRound, MoreFilled, Star, StarFilled, Setting, Search, Message } from '@element-plus/icons-vue'
import { useChatStore } from '../stores/chat'

const emit = defineEmits(['open-inbox', 'open-search', 'open-settings'])
const chatStore = useChatStore()

const listRef = ref(null)
// 距底部多少像素时触发加载下一页
const LOAD_MORE_THRESHOLD = 60

function handleScroll(event) {
  const el = event.target
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - LOAD_MORE_THRESHOLD) {
    chatStore.loadMoreSessions()
  }
}

// 首屏内容不足以撑出滚动条时（大屏 + 会话较多），滚动事件永远不会触发，
// 这里主动续页直到出现滚动条或没有更多数据
async function fillViewport() {
  await nextTick()
  const el = listRef.value
  if (!el) return
  if (el.scrollHeight <= el.clientHeight + 1) chatStore.loadMoreSessions()
}

onMounted(fillViewport)
watch(() => chatStore.sessions.length, fillViewport)

// 置顶会话：当前为前端写死的占位数据，后续接入后端后替换
const pinnedSessions = [
  { id: 'pinned-1', title: '2026 高考志愿方案咨询' },
]

const DAY_MS = 24 * 60 * 60 * 1000

// display_time 格式为后端输出的 'YYYY-MM-DD HH:MM'（UTC+8，与浏览器本地时区一致）
function sessionTimeMs(session) {
  if (!session.display_time) return null
  const t = new Date(session.display_time.replace(' ', 'T')).getTime()
  return Number.isNaN(t) ? null : t
}

// 会话按时间分组：最近（7 天内）/ 30 天内 / 更早，空分组不渲染
const sessionGroups = computed(() => {
  const now = Date.now()
  const groups = [
    { key: 'recent', label: '最近', items: [] },
    { key: 'month', label: '30 天内', items: [] },
    { key: 'older', label: '更早', items: [] },
  ]
  for (const s of chatStore.sessions) {
    const t = sessionTimeMs(s)
    const age = t === null ? Infinity : now - t
    if (age <= 7 * DAY_MS) groups[0].items.push(s)
    else if (age <= 30 * DAY_MS) groups[1].items.push(s)
    else groups[2].items.push(s)
  }
  return groups
})

function handleSessionCommand(command, sessionId) {
  if (command === 'delete') chatStore.removeSession(sessionId)
  // command === 'pin'：置顶功能待接入，暂不处理
}

// 置顶条目菜单（取消置顶/删除）：当前只放按钮，功能待接入
function handlePinnedCommand() {}
</script>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  background: #f5f7fa;
  border-right: 1px solid #e4e7ed;
  overflow: hidden !important;
}

.sidebar-header {
  padding: 12px 16px 16px;
  flex-shrink: 0;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 36px;
  margin-bottom: 10px;
}

.sidebar-brand-name {
  color: #303133;
  font-size: 18px;
  font-weight: 600;
}

.sidebar-brand-actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

.header-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #606266;
  font-size: 18px;
  cursor: pointer;
}

.header-icon-btn:hover {
  background: #e8eaed;
  color: #409eff;
}

.new-chat-btn {
  width: 100%;
}

.user-profile {
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-nickname {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden !important;
  padding: 0 8px;
}

.session-list-status {
  padding: 10px 12px 14px;
  font-size: 11px;
  color: #909399;
  text-align: center;
}

.session-item {
  position: relative;
  display: flex;
  align-items: center;
  padding: 10px 12px;
  margin-bottom: 4px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.session-item:hover {
  background: #e8eaed;
}

.session-item.active {
  background: #d9ecff;
}

.session-icon {
  font-size: 18px;
  color: #409eff;
  margin-right: 10px;
  flex-shrink: 0;
}

.session-info {
  flex: 1;
  min-width: 0;
}

.session-title {
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
}

.session-group-label {
  padding: 10px 12px 4px;
  font-size: 11px;
  font-weight: 600;
  color: #909399;
  letter-spacing: 0.5px;
}

.session-group-label:first-child {
  padding-top: 4px;
}

.session-item.pinned {
  cursor: default;
}

.session-item.pinned:hover {
  background: transparent;
}

.pinned-icon {
  color: #e6a23c;
}

/* 三点菜单不占布局空间，悬停时浮在条目右侧内容之上 */
.session-menu {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
  line-height: 1;
  opacity: 0;
  transition: opacity 0.2s;
}

.session-item:hover .session-menu {
  opacity: 1;
}

.more-btn {
  color: #909399;
}

/* 按钮背景与条目当前背景一致，避免文字从三点下透出 */
.session-item:hover .more-btn {
  background: #e8eaed;
}

.session-item.active:hover .more-btn {
  background: #d9ecff;
}

.session-item.pinned:hover .more-btn {
  background: #f5f7fa;
}

.more-btn:hover {
  color: #409eff;
}

.sidebar-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  border-top: 1px solid #e4e7ed;
  cursor: pointer;
}

.sidebar-footer:hover,
.sidebar-footer:focus-visible {
  background: #e8eaed;
  outline: none;
}

.settings-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #606266;
  font-size: 18px;
  cursor: pointer;
}

.settings-btn:hover {
  background: #e8eaed;
  color: #409eff;
}
</style>
