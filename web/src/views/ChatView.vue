<template>
  <div
    class="app-container"
    :class="{ resizing: resizingSide, 'university-fullscreen': universityFullscreen }"
    :style="{
      '--sidebar-width': sidebarWidth + 'px',
      '--university-panel-width': universityPanelWidth + 'px'
    }"
  >
    <aside
      class="app-sidebar"
      :class="{ hidden: sidebarCollapsed && !sidebarPreview, preview: sidebarPreview }"
      @mouseenter="handleSidebarEnter"
      @mouseleave="handleSidebarLeave"
    >
      <SessionList
        :unread-count="unreadCount"
        @open-search="openSearchPanel"
        @open-settings="settingsVisible = true"
        @open-inbox="openInbox"
        @open-upgrade="upgradeVisible = true"
        @open-admin="goAdmin"
      />
      <div
        class="panel-resize-handle left-resize-handle"
        :class="{ dragging: resizingSide === 'left' }"
        title="拖动调整会话列表宽度，双击恢复默认宽度"
        @pointerdown.stop.prevent="startResize('left', $event)"
        @dblclick.stop="resetPanelWidth('left')"
      ></div>
    </aside>
    <main
      class="app-main"
      :class="{ 'left-expanded': sidebarCollapsed, 'right-expanded': universityPanelCollapsed }"
    >
      <ChatArea @toggle-university="toggleUniversityPanel" />
    </main>
    <aside
      class="university-panel"
      :class="{ hidden: universityPanelCollapsed }"
    >
      <div
        class="panel-resize-handle right-resize-handle"
        :class="{ dragging: resizingSide === 'right' }"
        title="拖动调整高校列表宽度，双击恢复默认宽度"
        @pointerdown.stop.prevent="startResize('right', $event)"
        @dblclick.stop="resetPanelWidth('right')"
      ></div>
      <div class="university-panel-header">
        <nav class="university-panel-breadcrumb" aria-label="当前位置">
          <template v-for="(item, index) in breadcrumbLevels" :key="item.nodeId">
            <span v-if="index > 0" class="university-panel-breadcrumb-separator">/</span>
            <el-dropdown trigger="click" @command="selectBreadcrumbNode">
              <button class="university-panel-breadcrumb-trigger" type="button">
                <span>{{ item.label }}</span>
              </button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item
                    v-for="option in item.options"
                    :key="option.id"
                    :command="option.id"
                    :class="{ 'is-current': option.id === item.nodeId }"
                  >
                    {{ option.label }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
          <button
            v-if="currentBreadcrumbNode?.data?.children?.length"
            class="university-panel-breadcrumb-next"
            type="button"
            title="进入第一个叶子节点"
            aria-label="进入第一个叶子节点"
            @click="selectFirstBreadcrumbLeaf"
          >
            ›
          </button>
        </nav>
        <div class="university-panel-actions">
          <button
            v-if="!universityFullscreen"
            type="button"
            title="全屏展开高校面板"
            aria-label="全屏展开高校面板"
            @click="enterUniversityFullscreen"
          >
            <svg class="fullscreen-icon" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M9 4H4v5" />
              <path d="M15 4h5v5" />
              <path d="M9 20H4v-5" />
              <path d="M15 20h5v-5" />
            </svg>
          </button>
          <button
            v-else
            type="button"
            title="解除全屏展开"
            aria-label="解除全屏展开"
            @click="exitUniversityFullscreen"
          >
            <svg class="fullscreen-icon" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4 9h5V4" />
              <path d="M20 9h-5V4" />
              <path d="M4 15h5v5" />
              <path d="M20 15h-5v5" />
            </svg>
          </button>
          <button
            type="button"
            title="全部展开"
            aria-label="全部展开"
            @click="setAllUniversityNodesExpanded(true)"
          >
            <svg class="double-chevron expand-icon" viewBox="0 0 24 24" aria-hidden="true">
              <polyline points="6 9 12 3 18 9" />
              <polyline points="6 15 12 21 18 15" />
            </svg>
          </button>
          <button
            type="button"
            title="全部收起"
            aria-label="全部收起"
            @click="setAllUniversityNodesExpanded(false)"
          >
            <svg class="double-chevron collapse-icon" viewBox="0 0 24 24" aria-hidden="true">
              <polyline points="6 3.5 12 9.5 18 3.5" />
              <polyline points="6 20.5 12 14.5 18 20.5" />
            </svg>
          </button>
          <button
            type="button"
            title="收起高校面板"
            aria-label="收起高校面板"
            @click="collapseUniversityPanel"
          >
            <svg class="double-chevron" viewBox="0 0 24 24" aria-hidden="true">
              <polyline points="6 6 12 12 6 18" />
              <polyline points="12 6 18 12 12 18" />
            </svg>
          </button>
        </div>
      </div>
      <div class="university-panel-body">
        <div class="university-detail-pane">
          <template v-if="universityDetail">
            <div class="university-detail-header">
              <img
                v-if="universityDetail.logo_url && !universityLogoFailed"
                class="university-detail-logo"
                :src="universityLogoSrc"
                :alt="universityDetail.name"
                @error="universityLogoFailed = true"
              >
              <div class="university-detail-head-info">
                <h3 class="university-detail-title">{{ universityDetail.name }}</h3>
                <div v-if="universityTagTexts.length" class="university-detail-tags">
                  <span v-for="text in universityTagTexts" :key="text" class="university-tag">{{ text }}</span>
                </div>
              </div>
            </div>
            <div v-if="universityDetail.official_website" class="university-detail-website-row">
              <span class="university-info-label">官网</span>
              <a
                class="university-detail-website"
                :href="universityDetail.official_website"
                target="_blank"
                rel="noopener noreferrer"
              >{{ universityDetail.official_website }}</a>
            </div>
            <div class="university-info-list">
              <div v-for="row in universityInfoRows" :key="row.label" class="university-info-row">
                <span class="university-info-label">{{ row.label }}</span>
                <span class="university-info-value">{{ row.value }}</span>
              </div>
            </div>
            <div v-if="universityRankingRows.length" class="university-strength-section">
              <div class="university-strength-title-row">
                <span class="university-strength-title">排名榜单</span>
                <el-popover placement="bottom-start" trigger="click" :width="420">
                  <template #reference>
                    <svg class="university-strength-hint" viewBox="0 0 1024 1024" aria-label="榜单说明">
                      <path fill="currentColor" d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64z m-32 232c0-4.4 3.6-8 8-8h48c4.4 0 8 3.6 8 8v272c0 4.4-3.6 8-8 8h-48c-4.4 0-8-3.6-8-8V296z m32 440c-26.5 0-48-21.5-48-48s21.5-48 48-48 48 21.5 48 48-21.5 48-48 48z" />
                    </svg>
                  </template>
                  <div class="ranking-detail">
                    <div v-for="row in universityRankingRows" :key="row.key" class="ranking-detail-item">
                      <a v-if="rankingSourceUrl(row)" class="ranking-detail-head ranking-detail-link" :href="rankingSourceUrl(row)" target="_blank" rel="noopener">{{ row.label }} · {{ row.year || '年份未知' }}</a>
                      <p v-else class="ranking-detail-head">{{ row.label }} · {{ row.year || '年份未知' }}</p>
                      <p class="ranking-detail-score">排名 {{ row.value }} · 分数 {{ row.score != null ? row.score : '-' }} / {{ row.maxScore != null ? row.maxScore : '-' }}</p>
                      <p class="ranking-detail-intro">{{ RANKING_SOURCE_INTRO[row.sourceKey] || '暂无介绍' }}</p>
                    </div>
                    <p class="ranking-detail-note">说明：分数中的分母为该榜单当年榜首对应的分数</p>
                  </div>
                </el-popover>
              </div>
              <div class="ranking-chip-list">
                <div v-for="row in universityRankingRows" :key="row.key" class="ranking-chip">
                  <span class="ranking-chip-source">{{ row.label }}</span>
                  <span class="ranking-chip-rank" :class="{ 'ranking-chip-rank-sm': row.value.length > 5 }">
                    <span v-if="medalSvg(row.rankNum)" class="ranking-medal" v-html="medalSvg(row.rankNum)"></span>{{ row.value }}
                  </span>
                </div>
              </div>
            </div>
            <div v-if="universityDoubleFirstRows.length" class="university-strength-section">
              <div class="university-strength-title">双一流建设学科</div>
              <div v-for="row in universityDoubleFirstRows" :key="row.label" class="university-info-row">
                <span class="university-info-label">{{ row.label }}</span>
                <span class="university-info-value">{{ row.value }}</span>
              </div>
            </div>
            <div v-if="universityEvaluationRows.length" class="university-strength-section">
              <div class="university-strength-title">学科评估</div>
              <div v-for="row in universityEvaluationRows" :key="row.label" class="university-info-row">
                <span class="university-info-label">{{ row.label }}</span>
                <span class="university-info-value">{{ row.value }}</span>
              </div>
            </div>
          </template>
          <template v-else-if="selectedNodeDetail">
            <h3 class="university-detail-title">{{ selectedNodeDetail.label }}</h3>
          </template>
          <div v-else class="university-detail-empty">请点击右侧节点查看详情</div>
        </div>
        <div
          class="inner-resize-handle"
          :class="{ dragging: resizingInner, hidden: universityTreeCollapsed }"
          title="拖动调整详情与高校的宽度比例"
          @pointerdown.stop.prevent="startInnerResize($event)"
        ></div>
        <div
          class="university-tree-pane"
          :class="{
            collapsed: universityTreeCollapsed && !universityTreePreview,
            preview: universityTreePreview
          }"
          :style="{ width: treePaneWidth + 'px' }"
          @mouseenter="handleUniversityTreeEnter"
          @mouseleave="handleUniversityTreeLeave"
        >
          <nav class="university-tree" aria-label="高校节点">
            <el-tree
              ref="universityTreeRef"
              :data="universityTree"
              :props="{ label: 'label', children: 'children' }"
              :indent="14"
              node-key="id"
              highlight-current
              :expand-on-click-node="false"
              :current-node-key="currentUniversityNodeId"
              @node-click="onUniversityNodeClick"
            >
              <template #default="{ data }">
                <span class="university-tree-label">
                  <span v-if="data.isUniversity" class="university-symbol">🏫</span>
                  <span>{{ data.label }}</span>
                </span>
              </template>
            </el-tree>
          </nav>
        </div>
      </div>
    </aside>
    <button
      v-if="universityTree.length > 0 && !universityPanelCollapsed"
      class="university-tree-edge-handle"
      :class="{ open: !universityTreeCollapsed }"
      type="button"
      title="展开/收起高校节点列表"
      aria-label="展开或收起高校节点列表"
      @pointerdown.prevent="toggleUniversityTree"
      @mouseenter="handleUniversityTreeEdgeEnter"
      @mouseleave="handleUniversityTreeEdgeLeave"
    >
      <span class="university-tree-edge-pill">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6" />
        </svg>
      </span>
    </button>
    <button
      class="sidebar-edge-handle"
      :class="{ open: !sidebarCollapsed }"
      type="button"
      title="展开/收起会话列表"
      aria-label="展开或收起会话列表"
      @pointerdown.prevent="toggleSidebar"
      @mouseenter="handleEdgeEnter"
      @mouseleave="handleEdgeLeave"
    >
      <span class="edge-pill">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="9 18 15 12 9 6" />
        </svg>
      </span>
    </button>

    <el-dialog
      v-model="searchVisible"
      class="search-dialog"
      width="min(57vw, 700px)"
      top="10vh"
      :show-close="false"
      @opened="focusSearchInput"
    >
      <div class="search-bar">
        <svg class="search-bar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-4-4" />
        </svg>
        <input
          ref="searchInputRef"
          v-model="searchKeyword"
          type="search"
          placeholder="搜索对话内容..."
          aria-label="搜索对话内容"
        />
        <button type="button" aria-label="关闭搜索" @click="searchVisible = false">×</button>
      </div>
    </el-dialog>

    <el-dialog
      v-model="settingsVisible"
      class="settings-dialog"
      :title="settingsView === 'profile' ? '个人信息' : '设置'"
      width="600px"
      align-center
    >
      <div v-if="settingsView === 'main'" class="settings-list">
        <button class="settings-item" type="button" @click="settingsView = 'profile'">
          <strong>个人信息</strong>
          <span class="settings-arrow">›</span>
        </button>
        <button class="settings-item" type="button" @click="handleShortcutsClick">
          <strong>快捷键设置</strong>
          <span class="settings-arrow">›</span>
        </button>
        <button class="settings-item settings-item-danger" type="button" @click="handleSettingsLogout">
          <strong>退出登录</strong>
          <span class="settings-arrow">›</span>
        </button>
      </div>

      <div v-else class="profile-panel">
        <button class="profile-back" type="button" @click="settingsView = 'main'">‹ 返回设置</button>
        <div class="profile-hero">
          <span class="profile-avatar">{{ profileInitial }}</span>
          <div class="profile-hero-text">
            <strong>{{ profileForm.display_name || profileForm.username || '用户' }}</strong>
            <small>@{{ profileForm.username || 'guest' }}</small>
          </div>
          <span class="profile-role">{{ profileRoleLabel }}</span>
        </div>
        <el-form label-position="top" class="profile-form">
          <el-form-item label="用户名">
            <el-input v-model="profileForm.username" disabled />
          </el-form-item>
          <el-form-item label="显示名称">
            <el-input v-model="profileForm.display_name" placeholder="设置你的显示名称" />
          </el-form-item>
          <el-form-item label="邮箱">
            <el-input v-model="profileForm.email" placeholder="绑定邮箱" />
          </el-form-item>
        </el-form>
        <div class="profile-actions">
          <el-button @click="settingsView = 'main'">取消</el-button>
          <el-button type="primary" @click="handleSaveProfile">保存</el-button>
        </div>
      </div>
    </el-dialog>

    <el-dialog v-model="upgradeVisible" class="upgrade-dialog" title="完善账号信息" width="440px" align-center>
      <p class="upgrade-tip">
        你正在以游客身份使用，关闭浏览器后本次会话将无法找回。设置账号和密码即可长期保留聊天记录。
      </p>
      <el-form ref="upgradeFormRef" :model="upgradeForm" :rules="upgradeRules" label-position="top">
        <el-form-item label="账号" prop="username">
          <el-input v-model="upgradeForm.username" autocomplete="username" placeholder="请输入账号" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="upgradeForm.password"
            type="password"
            autocomplete="new-password"
            show-password
            placeholder="请输入密码"
          />
        </el-form-item>
        <el-form-item prop="email">
          <template #label>
            邮箱 <span class="upgrade-email-tip">（选填，用于账号召回）</span>
          </template>
          <el-input v-model="upgradeForm.email" type="email" autocomplete="email" placeholder="请输入邮箱" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="upgradeVisible = false">稍后再说</el-button>
        <el-button type="primary" :loading="upgrading" @click="submitUpgrade">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="inboxVisible" class="inbox-dialog" title="通知" width="600px" align-center @closed="selectedAnnouncement = null">
      <div v-if="announcementsLoading" class="inbox-empty">加载中...</div>
      <div v-else-if="!selectedAnnouncement && announcements.length === 0" class="inbox-empty">暂无通知</div>
      <template v-else-if="!selectedAnnouncement">
        <button
          v-for="item in announcements"
          :key="item.id"
          class="mail-item"
          :class="{ 'is-read': item.is_read }"
          type="button"
          @click="openAnnouncement(item)"
        >
          <span v-if="!item.is_read" class="mail-unread-dot"></span>
          <span v-else class="mail-read-placeholder"></span>
          <span class="mail-summary">
            <strong>
              <span v-if="item.is_pinned" class="mail-pin-tag">置顶</span>
              {{ item.title }}
            </strong>
            <small>{{ summarizeAnnouncement(item.content) }}</small>
          </span>
          <time>{{ formatAnnouncementTime(item.publish_time || item.created_time) }}</time>
        </button>
      </template>
      <article v-else class="mail-detail">
        <button class="mail-back" type="button" @click="selectedAnnouncement = null">‹ 返回</button>
        <h3>
          <span v-if="selectedAnnouncement.is_pinned" class="mail-pin-tag">置顶</span>
          {{ selectedAnnouncement.title }}
        </h3>
        <div class="mail-meta">发布时间：{{ formatAnnouncementTime(selectedAnnouncement.publish_time || selectedAnnouncement.created_time) }}</div>
        <div class="mail-body" v-html="renderAnnouncement(selectedAnnouncement.content)"></div>
      </article>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import SessionList from '../components/SessionList.vue'
import ChatArea from '../components/ChatArea.vue'
import { useChatStore } from '../stores/chat'
import { useAuthStore } from '../stores/auth'
import { getUniversity, listAnnouncements, getUnreadAnnouncementCount, markAnnouncementRead } from '../api'

const router = useRouter()
const chatStore = useChatStore()
const authStore = useAuthStore()
const searchVisible = ref(false)
const searchKeyword = ref('')
const searchInputRef = ref(null)
const settingsVisible = ref(false)
// 设置弹窗视图：'main' 主列表 | 'profile' 个人信息面板
const settingsView = ref('main')
const profileForm = reactive({ username: '', display_name: '', email: '' })
const profileRoleLabels = { guest: '游客', user: '普通用户', admin: '管理员', super_admin: '超级管理员' }
const profileRoleLabel = computed(() => profileRoleLabels[authStore.currentUser?.role] || '用户')

function goAdmin() {
  settingsVisible.value = false
  router.push('/admin')
}
const profileInitial = computed(() => {
  const name = profileForm.display_name || profileForm.username || '用户'
  return Array.from(name)[0].toUpperCase()
})

watch(settingsVisible, (visible) => {
  if (!visible) return
  settingsView.value = 'main'
  const user = authStore.currentUser || {}
  profileForm.username = user.username || ''
  profileForm.display_name = user.display_name || ''
  profileForm.email = user.email || ''
})

function handleShortcutsClick() {
  ElMessage.info('快捷键设置开发中，敬请期待')
}

function handleSaveProfile() {
  ElMessage.info('保存接口暂未接入，当前为前端演示')
}
const inboxVisible = ref(false)
const announcements = ref([])
const unreadCount = ref(0)
const announcementsLoading = ref(false)
const selectedAnnouncement = ref(null)

// 游客转正引导：内存标记触发，每次游客登录只弹一次，叉掉后可靠侧边栏入口再次打开
const upgradeVisible = ref(false)
const upgrading = ref(false)
const upgradeFormRef = ref(null)
const upgradeForm = reactive({ username: '', password: '', email: '' })
const upgradeRules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

import MarkdownIt from 'markdown-it'

// 公告 Markdown 渲染：html 关闭防 XSS，链接新窗口打开；图片走 Markdown 语法并自适应宽度
const announcementMd = new MarkdownIt({ html: false, linkify: true, breaks: true })
const defaultLinkOpen = announcementMd.renderer.rules.link_open
  || ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options))
announcementMd.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  tokens[idx].attrSet('target', '_blank')
  tokens[idx].attrSet('rel', 'noopener noreferrer')
  return defaultLinkOpen(tokens, idx, options, env, self)
}

function renderAnnouncement(content) {
  return announcementMd.render(content || '')
}

// 列表摘要：纯文本单行截断，图片语法折叠为占位符
function summarizeAnnouncement(content) {
  return (content || '').replace(/!\[[^\]]*\]\([^)]*\)/g, '[图片]')
}

// 公告时间展示：今天显示 HH:MM，今年显示 MM-DD，更早显示完整日期
function formatAnnouncementTime(timestamp) {
  if (!timestamp) return ''
  const d = new Date(timestamp * 1000)
  const now = new Date()
  const pad = n => String(n).padStart(2, '0')
  const hm = `${pad(d.getHours())}:${pad(d.getMinutes())}`
  if (d.toDateString() === now.toDateString()) return hm
  if (d.getFullYear() === now.getFullYear()) return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${hm}`
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

async function loadUnreadCount() {
  try {
    const data = await getUnreadAnnouncementCount()
    unreadCount.value = data.unread_count || 0
  } catch {
    // 红点拉取失败静默处理，不影响主流程
  }
}

async function loadAnnouncements() {
  announcementsLoading.value = true
  try {
    const data = await listAnnouncements()
    announcements.value = data.announcements || []
    unreadCount.value = data.unread_count || 0
  } catch {
    ElMessage.error('公告加载失败')
  } finally {
    announcementsLoading.value = false
  }
}

async function openAnnouncement(item) {
  selectedAnnouncement.value = item
  if (item.is_read) return
  try {
    await markAnnouncementRead(item.id)
    item.is_read = true
    unreadCount.value = Math.max(0, unreadCount.value - 1)
  } catch {
    // 已读上报失败不阻断详情展示，下次打开会重试
  }
}

const sidebarCollapsed = ref(false)
const sidebarPreview = ref(false)
const edgeHovered = ref(false)
const sidebarHovered = ref(false)
let hideTimer = null
let previewBlockedUntil = 0
const universityPanelCollapsed = ref(true)
const universityTreeCollapsed = ref(false)
const universityTreePreview = ref(false)
const universityTreeEdgeHovered = ref(false)
const universityTreeHovered = ref(false)
let universityTreeHideTimer = null
let universityTreePreviewBlockedUntil = 0
const universityFullscreen = ref(false)
const DEFAULT_PANEL_WIDTH = 260
const MIN_PANEL_WIDTH = 180
const MAX_PANEL_WIDTH = 560
const DEFAULT_UNIVERSITY_PANEL_WIDTH = 670
const MIN_UNIVERSITY_PANEL_WIDTH = 360
const MAX_UNIVERSITY_PANEL_WIDTH = 1120
const MIN_MAIN_WIDTH = 320
const sidebarWidth = ref(DEFAULT_PANEL_WIDTH)
const universityPanelWidth = ref(DEFAULT_UNIVERSITY_PANEL_WIDTH)
const resizingSide = ref(null)
const universityTreeRef = ref(null)
let resizeStartX = 0
let resizeStartWidth = 0

const universityTopics = [
  {
    label: '学校本体',
    children: [
      { label: '学校身份标识' },
      {
        label: '历史沿革',
        children: [
          { label: '创校与早期变迁' },
          { label: '更名与合并史' },
          { label: '重大里程碑' }
        ]
      },
      { label: '学校荣誉与资质' },
      {
        label: '组织治理架构',
        children: [
          { label: '历任领导' },
          { label: '现任领导' },
          { label: '管理机构与制度改革' }
        ]
      },
      {
        label: '校区与区位',
        children: [{ label: '主校区' }]
      },
      { label: '附属与直属机构' }
    ]
  },
  {
    label: '教学培养',
    children: [
      {
        label: '院系与专业设置',
        children: [
          { label: '本科专业目录' },
          { label: '优势专业与王牌学科' },
          { label: '专业新增、撤销与动态调整' }
        ]
      },
      {
        label: '本科培养方案与课程',
        children: [
          { label: '通识与公共课程' },
          { label: '专业课程体系' },
          { label: '实践、实验与实习环节' },
          { label: '毕业与学位要求' }
        ]
      },
      {
        label: '研究生培养与学位',
        children: [
          { label: '硕士培养' },
          { label: '博士培养' },
          { label: '导师制度与学位授予' }
        ]
      },
      {
        label: '教学运行与学业管理',
        children: [
          { label: '选课与学分制度' },
          { label: '考试与成绩评定' },
          { label: '学籍异动（休学、复学、退学）' }
        ]
      },
      {
        label: '学习资源与学业支持',
        children: [
          { label: '图书馆资源与服务' },
          { label: '在线学习平台' }
        ]
      },
      {
        label: '转专业与专项培养',
        children: [
          { label: '转专业规则与通过情况' },
          { label: '辅修与双学位' },
          { label: '特色实验班与拔尖计划（强基班、书院等）' }
        ]
      }
    ]
  },
  {
    label: '招生入学',
    children: [
      {
        label: '本科招生规则',
        children: [
          { label: '招生计划与招生章程' },
          { label: '选科与体检要求' },
          { label: '特殊类型招生（强基、综评、艺术体育、专项计划）' },
          { label: '调剂规则与录取流程' }
        ]
      },
      {
        label: '本科录取数据',
        children: [
          { label: '历年分数线与位次' },
          { label: '分省分专业录取情况' }
        ]
      },
      { label: '硕士招生' },
      { label: '博士招生与博士后' },
      {
        label: '新生入学流程',
        children: [
          { label: '录取通知与报到注册' },
          { label: '军训与入学教育' }
        ]
      }
    ]
  },
  {
    label: '毕业发展',
    children: [
      { label: '升学与深造' },
      { label: '就业质量' },
      {
        label: '就业服务与职业发展',
        children: [
          { label: '就业指导与校园招聘' },
          { label: '实习基地与实践机会' }
        ]
      }
    ]
  },
  {
    label: '科研学术',
    children: [
      {
        label: '学科建设',
        children: [
          { label: '学科评估结果' },
          { label: '双一流建设学科' },
          { label: 'ESI 与学科排名' }
        ]
      },
      { label: '科研平台' },
      { label: '科研成果' },
      {
        label: '师资队伍',
        children: [
          { label: '院士与高层次人才' },
          { label: '人才计划（长江、杰青等）' },
          { label: '师资规模与结构' }
        ]
      }
    ]
  },
  {
    label: '合作交流',
    children: [
      { label: '国际交流与合作办学' },
      {
        label: '产学研合作与成果转化',
        children: [
          { label: '校企合作项目' },
          { label: '科技园与孵化器' }
        ]
      },
      { label: '校友网络' }
    ]
  },
  {
    label: '校园生活',
    children: [
      { label: '校园环境与公共设施' },
      { label: '住宿条件与宿舍管理' },
      { label: '校内餐饮与日常服务' },
      { label: '校园周边与交通' },
      { label: '数字校园与信息服务' }
    ]
  },
  {
    label: '学生支持',
    children: [
      { label: '学费与收费' },
      { label: '奖助学金与资助体系' },
      { label: '校园安全与应急' },
      { label: '心理健康服务' },
      { label: '学生权益与申诉' }
    ]
  },
  {
    label: '校园文化',
    children: [
      { label: '文化标识与传统' },
      { label: '社团与文体活动' },
      { label: '学生组织与校园治理' },
      { label: '学生体验与风险提示' }
    ]
  },
  {
    label: '动态与入口',
    children: [
      { label: '近期动态与重大事件' },
      { label: '继续教育与社会培训' },
      { label: '官方入口与联络方式' }
    ]
  },
  { label: '未分类' }
]

function cloneTopicsWithIds(topics, prefix) {
  return topics.map((topic, index) => {
    const id = prefix + '-' + index
    return {
      ...topic,
      id,
      children: topic.children ? cloneTopicsWithIds(topic.children, id) : undefined
    }
  })
}

const universityTree = computed(() =>
  chatStore.confirmedUniversities.map((uni, index) => ({
    id: `uni-${index}`,
    label: uni.name,
    isUniversity: true,
    children: cloneTopicsWithIds(universityTopics, `uni-${index}`),
  }))
)

const currentUniversityNodeId = ref(null)
const selectedNodeDetail = ref(null)
const universityDetail = ref(null)
const universityLogoFailed = ref(false)

// 校徽走后端图片接口，logo_url 本身仅作为有无校徽的标志
const universityLogoSrc = computed(() => {
  if (!universityDetail.value) return ''
  return `/v1/universities/logo?name=${encodeURIComponent(universityDetail.value.name)}`
})

// 切换学校时重置图片加载失败标记
watch(universityDetail, () => {
  universityLogoFailed.value = false
})

const currentBreadcrumbNode = computed(() =>
  currentUniversityNodeId.value
    ? universityTreeRef.value?.getNode(currentUniversityNodeId.value)
    : null
)

const breadcrumbLevels = computed(() => {
  if (!currentUniversityNodeId.value) {
    return [{ nodeId: 'university-root', label: '高校', options: universityTree.value }]
  }
  const node = currentBreadcrumbNode.value
  if (!node) return [{ nodeId: 'university-root', label: '高校', options: universityTree.value }]

  const levels = []
  let current = node
  while (current && current.level > 0) {
    const siblings = current.parent?.level === 0
      ? universityTree.value
      : (current.parent?.data?.children || [])
    levels.unshift({
      nodeId: current.data.id,
      label: current.data.label,
      options: siblings,
    })
    current = current.parent
  }
  return levels
})
const lastClickedNodeKey = ref(null)
let universityDetailSeq = 0
const universityDetailCache = new Map()
const universityDetailInflight = new Map()

const CATEGORY_TEXT = { ordinary: '普通高校', adult: '成人高校' }

// tags 字段代码 → 展示名称，顺序即展示顺序
const TAG_TEXT_ORDER = ['985', '211', 'c9', 'double_first', 'qiangji', 'moe', 'mep', 'miit', 'mps', 'nhc', 'baoyan', 'double_high']
const TAG_TEXT = {
  985: '985',
  211: '211',
  c9: 'C9联盟',
  double_first: '双一流',
  double_high: '双高计划',
  qiangji: '强基计划',
  moe: '教育部直属',
  mep: '电力部直属',
  miit: '工信部直属',
  mps: '公安部直属',
  nhc: '卫健委直属',
  baoyan: '保研资格',
}

const universityTagTexts = computed(() => {
  const info = universityDetail.value
  if (!info) return []
  return (info.tags || [])
    .slice()
    .sort((a, b) => {
      const ia = TAG_TEXT_ORDER.indexOf(a)
      const ib = TAG_TEXT_ORDER.indexOf(b)
      return (ia === -1 ? TAG_TEXT_ORDER.length : ia) - (ib === -1 ? TAG_TEXT_ORDER.length : ib)
    })
    .map(code => TAG_TEXT[code] || code)
})

const universityInfoRows = computed(() => {
  const info = universityDetail.value
  if (!info) return []
  return [
    { label: '别名', value: (info.aliases || []).join('、') },
    // 普通高校为默认类型不展示，仅成人高校需要标识
    { label: '学校类型', value: info.category === 'adult' ? CATEGORY_TEXT[info.category] || info.category : '' },
    { label: '主管部门', value: info.competent_department },
    { label: '所在地', value: [info.province, info.city].filter(Boolean).join(' ') },
    { label: '办学层次', value: info.edu_level },
    { label: '办学性质', value: info.school_nature },
    { label: '一级学科硕士点', value: info.master_first },
    { label: '一级学科博士点', value: info.doctor_first },
    { label: '备注', value: info.raw_remark },
  ].filter(row => row.value)
})

// 榜单来源代码 → 展示名称
const RANKING_SOURCE_TEXT = { qs: 'QS', the: '泰晤士', usnews: 'U.S. News', ruanke: '软科', xyh: '校友会' }

// 榜单来源代码 → 介绍文案
const RANKING_SOURCE_INTRO = {
  qs: 'QS世界大学排名，由英国Quacquarelli Symonds发布，指标涵盖学术声誉、雇主声誉、师生比、论文引用率与国际化的强调。',
  the: '泰晤士高等教育世界大学排名（THE），由英国泰晤士高等教育发布，侧重教学（学习环境）、研究（数量与收入）、引文、国际视野与产业收入五大维度。',
  usnews: 'U.S. News全球最佳大学排名，由美国《美国新闻与世界报道》发布，侧重全球/地区研究声誉与文献计量指标（论文发表、引用、高被引论文等）。',
  ruanke: '软科世界大学学术排名（ARWU），由上海软科教育信息咨询有限公司发布，侧重校友获奖、教师获奖、高被引科学家、N&S论文与国际论文总量等硬指标。',
  xyh: '校友会中国大学排名，由艾瑞深校友会网发布，结合人才培养质量、科研成果与校友社会贡献等中国本土化评价指标。',
}

// 榜单官网链接（与数据采集源一致），参数为榜单年份
const RANKING_SOURCE_URL = {
  qs: () => 'https://www.topuniversities.com/world-university-rankings',
  the: () => 'https://www.timeshighereducation.com/world-university-rankings',
  usnews: () => 'https://www.usnews.com/education/best-global-universities/rankings',
  ruanke: y => `https://www.shanghairanking.cn/rankings/bcur/${y || ''}`,
  xyh: () => 'http://www.cuaa.net',
}

function rankingSourceUrl(row) {
  const fn = RANKING_SOURCE_URL[row.sourceKey]
  return fn ? fn(row.year) : ''
}

// 双一流建设轮次 → 年份
const DOUBLE_FIRST_ROUND_YEAR = { 1: 2017, 2: 2022 }

const universityRankingRows = computed(() => {
  const info = universityDetail.value
  if (!info) return []
  return (info.rankings || []).map(r => {
    const source = RANKING_SOURCE_TEXT[r.source] || r.source || '未知榜单'
    const rank = r.rank_raw || (r.rank_num != null ? String(r.rank_num) : '')
    return {
      key: `${r.source}-${r.year}`,
      sourceKey: r.source,
      label: source,
      year: r.year,
      value: rank || '-',
      rankNum: r.rank_num,
      score: r.score,
      maxScore: r.max_score,
    }
  })
})

// 前三名奖牌图标：红绶带 + 金属渐变圆盘 + 内环 + 五角星
function medalSvg(rankNum) {
  const conf = {
    1: { id: 'md-gold', stops: [['0%', '#fff3b8'], ['55%', '#ffc72e'], ['100%', '#f39c07']] },
    2: { id: 'md-silver', stops: [['0%', '#ffffff'], ['55%', '#dde7f2'], ['100%', '#b0c1d4']] },
    3: { id: 'md-bronze', stops: [['0%', '#ffd9a8'], ['55%', '#e8a24e'], ['100%', '#c9772f']] },
  }[rankNum]
  if (!conf) return ''
  const stops = conf.stops.map(([o, c]) => `<stop offset="${o}" stop-color="${c}"/>`).join('')
  return `<svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true">`
    + `<defs><linearGradient id="${conf.id}" x1="0" y1="0" x2="0" y2="1">${stops}</linearGradient></defs>`
    + `<path fill="#e5544b" d="M7.2 1.5h3.4l1.2 8H8.4z"/>`
    + `<path fill="#d64541" d="M16.8 1.5h-3.4l-1.2 8h3.4z"/>`
    + `<circle cx="12" cy="15" r="7" fill="url(#${conf.id})" stroke="rgba(0,0,0,.15)" stroke-width="0.8"/>`
    + `<circle cx="12" cy="15" r="5.4" fill="none" stroke="rgba(255,255,255,.5)" stroke-width="1"/>`
    + `<path fill="rgba(255,255,255,.9)" d="M12 11.4l.85 2.23 2.38.12-1.85 1.5.62 2.3L12 16.25l-2 1.3.62-2.3-1.85-1.5 2.38-.12z"/>`
    + `</svg>`
}

const universityDoubleFirstRows = computed(() => {
  const info = universityDetail.value
  if (!info) return []
  return (info.double_first_subjects || []).map(entry => {
    const year = DOUBLE_FIRST_ROUND_YEAR[entry.round]
    const label = year ? `第${entry.round}轮(${year})` : `第${entry.round}轮`
    let value
    if ((entry.subjects || []).length) {
      value = entry.subjects.map(s => s.name).filter(Boolean).join('、')
    } else if (entry.autonomous === 1) {
      value = '自主确定建设学科'
    } else {
      value = entry.note || '-'
    }
    return { label, value }
  })
})

const universityEvaluationRows = computed(() => {
  const info = universityDetail.value
  if (!info) return []
  const rows = []
  for (const entry of (info.discipline_evaluations || [])) {
    // 数据已按档位降序排列，分组时保留首次出现的档位顺序
    const gradeOrder = []
    const gradeMap = new Map()
    for (const d of (entry.disciplines || [])) {
      if (!d.grade || !d.name) continue
      if (!gradeMap.has(d.grade)) {
        gradeMap.set(d.grade, [])
        gradeOrder.push(d.grade)
      }
      gradeMap.get(d.grade).push(d.name)
    }
    for (const grade of gradeOrder) {
      const label = entry.round === 4 ? grade : `第${entry.round}轮 ${grade}`
      rows.push({ label, value: gradeMap.get(grade).join('、') })
    }
  }
  return rows
})

/**
 * 加载高校基础信息，name 为空时清空（点击子节点回退到面包屑展示）
 */
async function loadUniversityDetail(name) {
  const seq = ++universityDetailSeq
  if (!name) {
    universityDetail.value = null
    return
  }

  const cached = universityDetailCache.get(name)
  if (cached) {
    universityDetail.value = cached
    return
  }

  universityDetail.value = null
  try {
    let request = universityDetailInflight.get(name)
    if (!request) {
      request = getUniversity(name)
      universityDetailInflight.set(name, request)
    }
    const data = await request
    universityDetailCache.set(name, data)
    if (seq === universityDetailSeq) universityDetail.value = data
  } catch (err) {
    console.error('加载高校信息失败:', err)
  } finally {
    universityDetailInflight.delete(name)
  }
}

function selectTreeNode(node) {
  if (!node) return
  currentUniversityNodeId.value = node.data.id
  universityTreeRef.value?.setCurrentKey(node.data.id)

  const ancestors = []
  let parent = node.parent
  while (parent && parent.level > 0) {
    ancestors.unshift(parent)
    parent = parent.parent
  }
  ancestors.forEach(ancestor => ancestor.expand())

  if (node.data.isUniversity) {
    chatStore.selectedUniversity = node.data.label
    chatStore.universitySelectSeq++
    return
  }

  const path = []
  let current = node
  while (current && current.level > 0) {
    path.unshift(current.label)
    current = current.parent
  }
  lastClickedNodeKey.value = node.data.id
  selectedNodeDetail.value = { label: node.data.label, path }
  loadUniversityDetail(null)
}

function selectBreadcrumbNode(nodeId) {
  selectTreeNode(universityTreeRef.value?.getNode(nodeId))
}

function selectFirstBreadcrumbLeaf() {
  let node = currentBreadcrumbNode.value?.childNodes?.[0]
  if (!node) return
  while (node.childNodes?.length) node = node.childNodes[0]
  selectTreeNode(node)
}

function onUniversityNodeClick(nodeData, node) {
  // 第一次点击只选中，第二次点击同一节点才展开/收起（点击展开箭头由 el-tree 自行处理）
  if (lastClickedNodeKey.value === nodeData.id && !node.isLeaf) {
    if (node.expanded) node.collapse()
    else node.expand()
  }
  selectTreeNode(node)
}

watch([() => chatStore.selectedUniversity, () => chatStore.universitySelectSeq], ([name]) => {
  if (!name) return
  const idx = chatStore.confirmedUniversities.findIndex(u => u.name === name)
  if (idx === -1) return
  universityPanelCollapsed.value = false
  currentUniversityNodeId.value = `uni-${idx}`
  // 节点已置为选中态，随后在树上点击它即视为第二次点击，直接展开
  lastClickedNodeKey.value = `uni-${idx}`
  selectedNodeDetail.value = { label: name, path: [name] }
  loadUniversityDetail(name)
  nextTick(() => {
    universityTreeRef.value?.setCurrentKey(`uni-${idx}`)
  })
})

watch(() => chatStore.currentSessionId, () => {
  universityTreePreview.value = false
  currentUniversityNodeId.value = null
  lastClickedNodeKey.value = null
  selectedNodeDetail.value = null
  loadUniversityDetail(null)
  universityTreeRef.value?.setCurrentKey(null)
})

function clearHideTimer() {
  if (hideTimer !== null) {
    clearTimeout(hideTimer)
    hideTimer = null
  }
}

function schedulePreviewHide() {
  clearHideTimer()
  hideTimer = setTimeout(() => {
    if (sidebarCollapsed.value && !edgeHovered.value && !sidebarHovered.value) {
      sidebarPreview.value = false
    }
  }, 160)
}

function handleEdgeEnter() {
  edgeHovered.value = true
  clearHideTimer()
  if (sidebarCollapsed.value && Date.now() >= previewBlockedUntil) {
    sidebarPreview.value = true
  }
}

function handleEdgeLeave() {
  edgeHovered.value = false
  schedulePreviewHide()
}

function handleSidebarEnter() {
  sidebarHovered.value = true
  clearHideTimer()
}

function handleSidebarLeave() {
  sidebarHovered.value = false
  schedulePreviewHide()
}

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
  sidebarPreview.value = false
  if (sidebarCollapsed.value) previewBlockedUntil = Date.now() + 500
}

function clearUniversityTreeHideTimer() {
  if (universityTreeHideTimer !== null) {
    clearTimeout(universityTreeHideTimer)
    universityTreeHideTimer = null
  }
}

function scheduleUniversityTreePreviewHide() {
  clearUniversityTreeHideTimer()
  universityTreeHideTimer = setTimeout(() => {
    if (universityTreeCollapsed.value && !universityTreeEdgeHovered.value && !universityTreeHovered.value) {
      universityTreePreview.value = false
    }
  }, 160)
}

function handleUniversityTreeEdgeEnter() {
  universityTreeEdgeHovered.value = true
  clearUniversityTreeHideTimer()
  if (universityTreeCollapsed.value && Date.now() >= universityTreePreviewBlockedUntil) {
    universityTreePreview.value = true
  }
}

function handleUniversityTreeEdgeLeave() {
  universityTreeEdgeHovered.value = false
  scheduleUniversityTreePreviewHide()
}

function handleUniversityTreeEnter() {
  universityTreeHovered.value = true
  clearUniversityTreeHideTimer()
}

function handleUniversityTreeLeave() {
  universityTreeHovered.value = false
  scheduleUniversityTreePreviewHide()
}

function toggleUniversityTree() {
  universityTreeCollapsed.value = !universityTreeCollapsed.value
  universityTreePreview.value = false
  if (universityTreeCollapsed.value) universityTreePreviewBlockedUntil = Date.now() + 500
}

function openSearchPanel() {
  searchVisible.value = true
}

function focusSearchInput() {
  searchInputRef.value?.focus()
}

function openInbox() {
  selectedAnnouncement.value = null
  inboxVisible.value = true
  loadAnnouncements()
}

async function handleSettingsLogout() {
  chatStore.clearUserData()
  settingsVisible.value = false
  try {
    await authStore.logout()
  } finally {
    await router.replace('/login')
  }
}

async function submitUpgrade() {
  if (upgrading.value) return
  try {
    await upgradeFormRef.value.validate()
  } catch {
    return
  }
  upgrading.value = true
  try {
    const payload = { username: upgradeForm.username.trim(), password: upgradeForm.password }
    const email = upgradeForm.email.trim()
    if (email) payload.email = email
    await authStore.upgrade(payload)
    upgradeVisible.value = false
    upgradeForm.password = ''
    ElMessage.success('账号已完善，聊天记录已保留')
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '保存失败，请稍后重试')
  } finally {
    upgrading.value = false
  }
}

function toggleUniversityPanel() {
  universityPanelCollapsed.value = !universityPanelCollapsed.value
}

function enterUniversityFullscreen() {
  universityFullscreen.value = true
  universityPanelCollapsed.value = false
}

function exitUniversityFullscreen() {
  universityFullscreen.value = false
}

// 收起整个高校面板；全屏态下先退出全屏，避免面板隐藏后主区域仍被全屏样式遮挡
function collapseUniversityPanel() {
  universityFullscreen.value = false
  universityPanelCollapsed.value = true
}

function setAllUniversityNodesExpanded(expanded) {
  const nodes = universityTreeRef.value?.store?._getAllNodes?.() || []
  nodes.forEach(node => {
    node.expanded = expanded
  })
}

const SIDEBAR_EDGE_WIDTH = 11
const INNER_HANDLE_WIDTH = 6
const INITIAL_TREE_RATIO = 0.4
const MIN_INNER_PANE_WIDTH = 120
const treePaneWidth = ref((DEFAULT_UNIVERSITY_PANEL_WIDTH - SIDEBAR_EDGE_WIDTH - INNER_HANDLE_WIDTH) * INITIAL_TREE_RATIO)
const resizingInner = ref(false)
let innerResizeStartX = 0
let innerResizeStartWidth = 0
let innerBodyWidth = 0

function maxTreePaneWidth(bodyWidth) {
  return bodyWidth - INNER_HANDLE_WIDTH - MIN_INNER_PANE_WIDTH
}

function minUniversityPanelWidth() {
  return Math.max(
    MIN_UNIVERSITY_PANEL_WIDTH,
    treePaneWidth.value + INNER_HANDLE_WIDTH + MIN_INNER_PANE_WIDTH + SIDEBAR_EDGE_WIDTH
  )
}

function startInnerResize(event) {
  resizingInner.value = true
  innerResizeStartX = event.clientX
  innerResizeStartWidth = treePaneWidth.value
  innerBodyWidth = event.currentTarget.parentElement.getBoundingClientRect().width
  window.addEventListener('pointermove', handleInnerResize)
  window.addEventListener('pointerup', stopInnerResize, { once: true })
}

function handleInnerResize(event) {
  if (!resizingInner.value || innerBodyWidth <= 0) return
  const delta = event.clientX - innerResizeStartX
  const next = innerResizeStartWidth - delta
  treePaneWidth.value = Math.min(maxTreePaneWidth(innerBodyWidth), Math.max(MIN_INNER_PANE_WIDTH, next))
}

function stopInnerResize() {
  resizingInner.value = false
  window.removeEventListener('pointermove', handleInnerResize)
}

function minPanelWidth(side) {
  return side === 'left' ? MIN_PANEL_WIDTH : minUniversityPanelWidth()
}

function maxPanelWidth(side) {
  const oppositeWidth = side === 'left'
    ? (universityPanelCollapsed.value ? 0 : universityPanelWidth.value)
    : (sidebarCollapsed.value ? 0 : sidebarWidth.value)
  const maxWidth = side === 'left' ? MAX_PANEL_WIDTH : MAX_UNIVERSITY_PANEL_WIDTH
  return Math.max(minPanelWidth(side), Math.min(maxWidth, window.innerWidth - oppositeWidth - MIN_MAIN_WIDTH))
}

function startResize(side, event) {
  resizingSide.value = side
  resizeStartX = event.clientX
  resizeStartWidth = side === 'left' ? sidebarWidth.value : universityPanelWidth.value
  window.addEventListener('pointermove', handleResize)
  window.addEventListener('pointerup', stopResize, { once: true })
}

function handleResize(event) {
  if (!resizingSide.value) return
  const direction = resizingSide.value === 'left' ? 1 : -1
  const width = resizeStartWidth + direction * (event.clientX - resizeStartX)
  const nextWidth = Math.min(maxPanelWidth(resizingSide.value), Math.max(minPanelWidth(resizingSide.value), width))
  if (resizingSide.value === 'left') sidebarWidth.value = nextWidth
  else universityPanelWidth.value = nextWidth
}

function stopResize() {
  resizingSide.value = null
  window.removeEventListener('pointermove', handleResize)
}

function resetPanelWidth(side) {
  const defaultWidth = side === 'left' ? DEFAULT_PANEL_WIDTH : DEFAULT_UNIVERSITY_PANEL_WIDTH
  const width = Math.max(minPanelWidth(side), Math.min(defaultWidth, maxPanelWidth(side)))
  if (side === 'left') sidebarWidth.value = width
  else universityPanelWidth.value = width
}

onMounted(async () => {
  if (authStore.consumeGuestLoginFlag() && authStore.isGuest) {
    upgradeVisible.value = true
  }
  await Promise.all([
    chatStore.loadSessions(),
    chatStore.loadModels(),
    chatStore.loadTools(),
    loadUnreadCount()
  ])
  const savedSessionId = localStorage.getItem('currentSessionId')
  if (savedSessionId && chatStore.sessions.some(session => session.id === savedSessionId)) {
    chatStore.selectSession(savedSessionId)
  } else {
    localStorage.removeItem('currentSessionId')
  }
})

onBeforeUnmount(() => {
  clearHideTimer()
  clearUniversityTreeHideTimer()
  window.removeEventListener('pointermove', handleResize)
  window.removeEventListener('pointerup', stopResize)
})
</script>

<style scoped>
.app-container {
  --sidebar-edge-width: 11px;
  position: fixed;
  inset: 0;
  overflow: hidden !important;
  margin: 0;
  padding: 0;
}

.app-sidebar {
  position: fixed;
  left: var(--sidebar-edge-width);
  top: 0;
  bottom: 0;
  z-index: 70;
  width: calc(var(--sidebar-width) - var(--sidebar-edge-width));
  overflow: hidden !important;
  transform: translateX(0);
  transition: width 0.05s linear, transform 0.25s ease;
}

.app-sidebar.hidden {
  transform: translateX(calc(-1 * var(--sidebar-width)));
}

.app-sidebar.preview {
  box-shadow: 4px 0 18px rgba(0, 0, 0, 0.1);
}

.app-main {
  min-width: 0;
  height: 100%;
  margin-left: var(--sidebar-width);
  margin-right: var(--university-panel-width);
  overflow: hidden !important;
  transition: margin-left 0.25s ease, margin-right 0.25s ease;
}

.app-container.resizing,
.app-container.resizing * {
  cursor: col-resize !important;
  user-select: none !important;
}

.app-container.resizing .app-main {
  transition: none;
}

.app-main.left-expanded {
  margin-left: 0;
}

.app-main.right-expanded {
  margin-right: 0;
}

.university-panel {
  position: fixed;
  right: var(--sidebar-edge-width);
  top: 0;
  bottom: 0;
  z-index: 70;
  width: calc(var(--university-panel-width) - var(--sidebar-edge-width));
  display: flex;
  flex-direction: column;
  background: #fff;
  border-left: 1px solid #e4e7ed;
  overflow: hidden !important;
  transform: translateX(0);
  transition: width 0.05s linear, transform 0.25s ease;
}

.panel-resize-handle {
  position: absolute;
  top: 0;
  bottom: 0;
  z-index: 90;
  width: 6px;
  cursor: col-resize;
}

.left-resize-handle {
  right: 0;
}

.right-resize-handle {
  left: 0;
}

.panel-resize-handle:hover,
.panel-resize-handle.dragging {
  background: #409eff;
  opacity: 0.35;
}

.university-panel.hidden {
  transform: translateX(var(--university-panel-width));
}

.app-container.university-fullscreen .app-sidebar,
.app-container.university-fullscreen .sidebar-edge-handle,
.app-container.university-fullscreen .app-main,
.app-container.university-fullscreen .right-resize-handle {
  display: none;
}

/* 全屏时右边缘保持与普通态一致（right 不变），仅左边界扩展到 0，
   避免贴右布局的头部按钮和树区发生位置偏移 */
.app-container.university-fullscreen .university-panel {
  left: 0;
  width: auto;
  border-left: none;
}

.university-panel-body {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
}

.university-detail-pane {
  flex: 1 1 auto;
  min-width: 120px;
  display: flex;
  flex-direction: column;
  padding: 12px;
  border-right: 1px solid #e4e7ed;
  overflow: auto;
}

.university-detail-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 16px;
}

.university-detail-head-info {
  min-width: 0;
}

.university-detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.university-tag {
  padding: 1px 8px;
  border: 1px solid #d9ecff;
  border-radius: 3px;
  background: #ecf5ff;
  color: #409eff;
  font-size: 12px;
  line-height: 20px;
  white-space: nowrap;
}

.university-detail-logo {
  flex-shrink: 0;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  object-fit: contain;
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
}

.university-detail-title {
  margin: 0;
  font-size: 18px;
  line-height: 1.4;
  font-weight: 600;
  color: #303133;
  word-break: break-all;
}

.university-detail-website-row {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
  font-size: 13px;
  line-height: 1.6;
}

.university-detail-website {
  flex: 1;
  min-width: 0;
  color: #409eff;
  font-size: 13px;
  word-break: break-all;
}

.university-info-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.university-info-row {
  display: flex;
  gap: 10px;
  font-size: 13px;
  line-height: 1.6;
}

.university-info-label {
  flex-shrink: 0;
  width: 92px;
  color: #909399;
}

.university-info-value {
  flex: 1;
  min-width: 0;
  color: #303133;
  word-break: break-all;
}

.university-strength-section {
  margin-top: 14px;
  padding-top: 10px;
  border-top: 1px solid #ebeef5;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.university-strength-title {
  font-size: 13px;
  font-weight: 600;
  color: #606266;
}

.university-strength-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.university-strength-hint {
  width: 13px;
  height: 13px;
  color: #c0c4cc;
  cursor: pointer;
  transition: color 0.2s;
}

.university-strength-hint:hover {
  color: #909399;
}

.ranking-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.ranking-chip {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  width: 75px;
  height: 44px;
  padding: 4px 2px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #fafafa;
}

.ranking-chip-source {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
  white-space: nowrap;
}

.ranking-chip-rank {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
  max-width: 100%;
  overflow: hidden;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  line-height: 1.4;
  white-space: nowrap;
}

.ranking-medal {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
}

.ranking-medal svg {
  width: 13px;
  height: 13px;
  display: block;
}

.ranking-detail {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 300px;
  overflow-y: auto;
  font-size: 13px;
  color: #303133;
}

.ranking-detail-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.ranking-detail-item + .ranking-detail-item {
  padding-top: 10px;
  border-top: 1px solid #ebeef5;
}

.ranking-detail-head {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.5;
}

.ranking-detail-link {
  color: #409eff;
  text-decoration: none;
}

.ranking-detail-link:hover {
  text-decoration: underline;
}

.ranking-detail-score {
  margin: 0;
  font-size: 12px;
  color: #606266;
  line-height: 1.5;
}

.ranking-detail-intro {
  margin: 0;
  font-size: 12px;
  color: #909399;
  line-height: 1.6;
}

.ranking-detail-note {
  margin: 0;
  padding-top: 8px;
  border-top: 1px solid #ebeef5;
  font-size: 12px;
  color: #a8abb2;
  line-height: 1.6;
}

.university-detail-empty {
  margin: auto;
  padding: 0 12px;
  color: #a8abb2;
  font-size: 13px;
  text-align: center;
}

.inner-resize-handle {
  flex: 0 0 6px;
  cursor: col-resize;
}

.inner-resize-handle:hover,
.inner-resize-handle.dragging {
  background: #409eff;
  opacity: 0.35;
}

.inner-resize-handle.hidden {
  display: none;
}

.university-tree-pane {
  position: relative;
  z-index: 20;
  flex: 0 0 auto;
  min-width: 120px;
  display: flex;
  flex-direction: column;
  background: #fff;
  transition: width 0.25s ease, min-width 0.25s ease, transform 0.25s ease;
}

.university-tree-pane.collapsed {
  width: 0 !important;
  min-width: 0;
  overflow: hidden;
}

.university-tree-pane.preview {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  box-shadow: -4px 0 18px rgba(0, 0, 0, 0.1);
}

.university-panel-header {
  position: relative;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  min-height: 43px;
  padding: 7px 104px 7px 12px;
  border-bottom: 1px solid #e4e7ed;
}

.university-panel-breadcrumb {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  overflow: hidden;
  color: #909399;
  font-size: 13px;
  line-height: 1.5;
  white-space: nowrap;
}

.university-panel-breadcrumb-trigger {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  min-width: 0;
  max-width: 180px;
  padding: 2px 4px;
  overflow: hidden;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: #606266;
  font: inherit;
  cursor: pointer;
}

.university-panel-breadcrumb-trigger > span:first-child {
  overflow: hidden;
  text-overflow: ellipsis;
}

.university-panel-breadcrumb-trigger:hover {
  background: #f5f7fa;
  color: #409eff;
}

.university-panel-breadcrumb-next {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  padding: 0;
  border: 1px solid #dcdfe6;
  border-radius: 50%;
  background: #fff;
  color: #909399;
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
}

.university-panel-breadcrumb-next:hover {
  border-color: #409eff;
  color: #409eff;
  background: #ecf5ff;
}

.university-panel-breadcrumb-separator {
  flex-shrink: 0;
  color: #c0c4cc;
}

.university-panel-actions {
  position: absolute;
  right: 10px;
  top: 50%;
  display: flex;
  gap: 5px;
  transform: translateY(-50%);
}

.university-panel-actions button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 28px;
  padding: 2px 0;
  border: 1px solid #dcdfe6;
  border-radius: 5px;
  background: #fff;
  color: #606266;
  cursor: pointer;
}

.double-chevron {
  width: 18px;
  height: 22px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.fullscreen-icon {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2.2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.university-panel-actions button:hover {
  border-color: #409eff;
  color: #409eff;
  background: #ecf5ff;
}

.university-tree {
  flex: 1;
  overflow: auto;
  padding: 10px 8px 30px;
}

.university-tree :deep(.el-tree) {
  min-width: max-content;
  background: transparent;
  color: #3c3c43;
  font-size: 14px;
}

.university-tree :deep(.el-tree-node__content) {
  height: auto;
  min-height: 31px;
  margin: 1px 0;
  padding: 1px 10px 1px 0;
  border-radius: 6px;
  line-height: 1.5;
}

.university-tree :deep(.el-tree-node__content:hover) {
  background: rgba(46, 53, 56, 0.06);
}

.university-tree :deep(.el-tree-node.is-current > .el-tree-node__content) {
  color: #409eff;
  font-weight: 600;
  background: #ecf5ff;
}

.university-tree :deep(.el-tree-node__expand-icon) {
  color: rgba(60, 60, 67, 0.5);
}

.university-tree :deep(.el-tree-node__label) {
  white-space: nowrap;
}

.university-tree-label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.university-symbol {
  font-size: 15px;
  line-height: 1;
}

.university-tree-edge-handle {
  position: fixed;
  right: 0;
  top: 0;
  bottom: 0;
  z-index: 80;
  width: var(--sidebar-edge-width);
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #606266;
}

.university-tree-edge-pill {
  width: var(--sidebar-edge-width);
  height: 64px;
  border: 1px solid #e4e7ed;
  border-right: none;
  border-radius: 10px 0 0 10px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: -2px 0 8px rgba(0, 0, 0, 0.06);
  transition: color 0.2s, background-color 0.2s;
}

.university-tree-edge-handle:hover .university-tree-edge-pill {
  color: #409eff;
  background: #ecf5ff;
}

.university-tree-edge-handle svg {
  width: 15px;
  height: 15px;
  transition: transform 0.3s ease;
}

.university-tree-edge-handle.open svg {
  transform: rotate(180deg);
}

.sidebar-edge-handle {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 80;
  width: var(--sidebar-edge-width);
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #606266;
}

.edge-pill {
  width: var(--sidebar-edge-width);
  height: 64px;
  border: 1px solid #e4e7ed;
  border-left: none;
  border-radius: 0 10px 10px 0;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.06);
  transition: color 0.2s, background-color 0.2s;
}

.sidebar-edge-handle:hover .edge-pill {
  color: #409eff;
  background: #ecf5ff;
}

.sidebar-edge-handle svg {
  width: 15px;
  height: 15px;
  transition: transform 0.3s ease;
}

.sidebar-edge-handle.open svg {
  transform: rotate(180deg);
}

:deep(.search-dialog) {
  overflow: hidden;
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.16);
}

:deep(.search-dialog .el-dialog__header) {
  display: none;
}

:deep(.search-dialog .el-dialog__body) {
  padding: 0;
}

.search-bar {
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr) 32px;
  align-items: center;
  gap: 8px;
  height: 25px;
  padding: 0 8px 0 14px;
  background: #fff;
}

.search-bar-icon {
  width: 20px;
  height: 20px;
  color: #303133;
}

.search-bar input {
  width: 100%;
  min-width: 0;
  padding: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: #303133;
  font: inherit;
  font-size: 15px;
}

.search-bar input::placeholder {
  color: #909399;
}

.search-bar input::-webkit-search-cancel-button {
  display: none;
}

.search-bar button {
  width: 30px;
  height: 30px;
  padding: 0;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #909399;
  font-size: 26px;
  font-weight: 300;
  line-height: 1;
  cursor: pointer;
}

.search-bar button:hover {
  background: #f5f7fa;
  color: #606266;
}

:deep(.settings-dialog),
:deep(.inbox-dialog) {
  height: 620px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

:deep(.settings-dialog .el-dialog__header),
:deep(.inbox-dialog .el-dialog__header) {
  flex-shrink: 0;
}

:deep(.settings-dialog .el-dialog__body),
:deep(.inbox-dialog .el-dialog__body) {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.settings-list {
  display: grid;
  gap: 10px;
}

.settings-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 16px;
  border: 1px solid #e4e7ed;
  border-radius: 10px;
  background: #fff;
  color: #303133;
  text-align: left;
  cursor: pointer;
}

.settings-item:hover {
  border-color: #409eff;
  background: #ecf5ff;
}

.settings-item-danger {
  border-color: #f56c6c;
  color: #f56c6c;
}

.settings-item-danger:hover {
  border-color: #f56c6c;
  background: #fef0f0;
}

.settings-item-danger .settings-arrow {
  color: #f56c6c;
}

.mail-summary strong {
  font-size: 14px;
  font-weight: 600;
}

.mail-summary small {
  color: #909399;
  font-size: 12px;
}

/* 个人信息面板 */
.profile-panel {
  display: flex;
  flex-direction: column;
}

.profile-back {
  align-self: flex-start;
  border: none;
  background: none;
  padding: 4px 8px;
  margin: -4px 0 8px -8px;
  color: #909399;
  font-size: 13px;
  cursor: pointer;
  border-radius: 6px;
}

.profile-back:hover {
  color: #409eff;
  background: #ecf5ff;
}

.profile-hero {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  background: #f8f9fb;
}

.profile-avatar {
  width: 56px;
  height: 56px;
  flex-shrink: 0;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #409eff, #7b5cff);
  color: #fff;
  font-size: 22px;
  font-weight: 600;
}

.profile-hero-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.profile-hero-text strong {
  font-size: 16px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.profile-hero-text small {
  color: #909399;
  font-size: 12px;
}

.profile-role {
  flex-shrink: 0;
  padding: 4px 10px;
  border-radius: 999px;
  background: #ecf5ff;
  color: #409eff;
  font-size: 12px;
}

.profile-form {
  margin-top: 16px;
}

.profile-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.settings-arrow {
  color: #909399;
  font-size: 24px;
}

.mail-item {
  display: grid;
  grid-template-columns: 8px minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 16px;
  border: 1px solid #e4e7ed;
  border-radius: 10px;
  background: #fff;
  color: #303133;
  text-align: left;
  cursor: pointer;
}

.mail-item:hover {
  border-color: #409eff;
  background: #ecf5ff;
}

.mail-unread-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #409eff;
}

.mail-read-placeholder {
  width: 8px;
  height: 8px;
}

.mail-item.is-read .mail-summary strong {
  font-weight: normal;
  color: #909399;
}

.mail-pin-tag {
  display: inline-block;
  margin-right: 6px;
  padding: 1px 6px;
  border-radius: 4px;
  background: #ecf5ff;
  color: #409eff;
  font-size: 12px;
  font-weight: normal;
}

.inbox-empty {
  padding: 32px 0;
  text-align: center;
  color: #909399;
  font-size: 14px;
}

.mail-summary {
  display: grid;
  gap: 6px;
  min-width: 0;
}

/* 列表项正文单行截断，全文在详情页查看 */
.mail-summary small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mail-item time,
.mail-meta {
  color: #909399;
  font-size: 12px;
}

.mail-back {
  padding: 0;
  border: 0;
  background: transparent;
  color: #409eff;
  cursor: pointer;
}

.mail-detail h3 {
  margin: 18px 0 8px;
  font-size: 18px;
}

.mail-detail p {
  margin: 20px 0 0;
  color: #606266;
  line-height: 1.8;
}

/* 公告正文 Markdown 排版：段落、图片、列表、代码块 */
.mail-body {
  margin-top: 20px;
  color: #606266;
  font-size: 14px;
  line-height: 1.8;
  word-break: break-word;
}

.mail-body p {
  margin: 0 0 12px;
}

.mail-body p:last-child {
  margin-bottom: 0;
}

.mail-body img {
  max-width: 100%;
  border-radius: 8px;
}

.mail-body ul,
.mail-body ol {
  margin: 0 0 12px;
  padding-left: 22px;
}

.mail-body h1,
.mail-body h2,
.mail-body h3,
.mail-body h4 {
  margin: 16px 0 8px;
  color: #303133;
  font-size: 16px;
}

.mail-body code {
  padding: 1px 5px;
  border-radius: 4px;
  background: #f5f7fa;
  font-size: 13px;
}

.mail-body pre {
  margin: 0 0 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #f5f7fa;
  overflow-x: auto;
}

.mail-body pre code {
  padding: 0;
  background: none;
}

.mail-body blockquote {
  margin: 0 0 12px;
  padding-left: 12px;
  border-left: 3px solid #dcdfe6;
  color: #909399;
}

.mail-body a {
  color: #409eff;
  text-decoration: none;
}

.upgrade-tip {
  margin: 0 0 18px;
  color: #909399;
  font-size: 13px;
  line-height: 1.7;
}

.upgrade-email-tip {
  color: #909399;
  font-size: 12px;
}

@media (max-width: 640px) {
  :deep(.el-dialog) {
    width: calc(100% - 32px) !important;
  }
}

</style>
