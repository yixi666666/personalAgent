<template>
  <div class="app-container">
    <aside
      class="app-sidebar"
      :class="{ hidden: sidebarCollapsed && !sidebarPreview, preview: sidebarPreview }"
      @mouseenter="handleSidebarEnter"
      @mouseleave="handleSidebarLeave"
    >
      <SessionList />
    </aside>
    <main class="app-main" :class="{ expanded: sidebarCollapsed }">
      <ChatArea />
    </main>
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
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import SessionList from './components/SessionList.vue'
import ChatArea from './components/ChatArea.vue'
import { useChatStore } from './stores/chat'

const chatStore = useChatStore()
const sidebarCollapsed = ref(false)
const sidebarPreview = ref(false)
const edgeHovered = ref(false)
const sidebarHovered = ref(false)
let hideTimer = null
let previewBlockedUntil = 0

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

onMounted(() => {
  chatStore.loadSessions()
  chatStore.loadModels()
  chatStore.loadTools()
})

onBeforeUnmount(clearHideTimer)
</script>

<style scoped>
.app-container {
  --sidebar-width: 260px;
  position: fixed;
  inset: 0;
  overflow: hidden !important;
  margin: 0;
  padding: 0;
}

.app-sidebar {
  position: fixed;
  left: 22px;
  top: 0;
  bottom: 0;
  z-index: 70;
  width: calc(var(--sidebar-width) - 22px);
  overflow: hidden !important;
  transform: translateX(0);
  transition: transform 0.25s ease;
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
  overflow: hidden !important;
  transition: margin-left 0.25s ease;
}

.app-main.expanded {
  margin-left: 0;
}

.sidebar-edge-handle {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 80;
  width: 22px;
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
  width: 22px;
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
</style>
