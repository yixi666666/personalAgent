<template>
  <div class="app-container">
    <div class="app-sidebar" :class="{ collapsed: sidebarCollapsed }">
      <SessionList v-show="!sidebarCollapsed" />
    </div>
    <div class="app-main">
      <ChatArea />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, provide } from 'vue'
import SessionList from './components/SessionList.vue'
import ChatArea from './components/ChatArea.vue'
import { useChatStore } from './stores/chat'

const chatStore = useChatStore()
const sidebarCollapsed = ref(false)

provide('sidebarCollapsed', sidebarCollapsed)

onMounted(() => {
  chatStore.loadSessions()
  chatStore.loadModels()
  chatStore.loadTools()
})
</script>

<style scoped>
.app-container {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden !important;
  margin: 0;
  padding: 0;
}

.app-sidebar {
  width: 260px;
  flex-shrink: 0;
  height: 100%;
  overflow: hidden !important;
  transition: width 0.3s ease;
}

.app-sidebar.collapsed {
  width: 0;
}

.app-main {
  flex: 1;
  min-width: 0;
  height: 100%;
  overflow: hidden !important;
}
</style>
