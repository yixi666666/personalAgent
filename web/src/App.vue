<template>
  <div class="app-container">
    <SessionList class="app-sidebar" />
    <ChatArea class="app-main" />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import SessionList from './components/SessionList.vue'
import ChatArea from './components/ChatArea.vue'
import { useChatStore } from './stores/chat'

const chatStore = useChatStore()

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
}

.app-main {
  flex: 1;
  min-width: 0;
  height: 100%;
  overflow: hidden !important;
}
</style>
