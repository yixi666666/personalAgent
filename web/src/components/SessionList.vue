<template>
  <div class="sidebar">
    <div class="sidebar-header">
      <el-button type="primary" class="new-chat-btn" @click="chatStore.newSession()">
        <el-icon><Plus /></el-icon>
        <span>新建会话</span>
      </el-button>
    </div>

    <div class="session-list scrollable">
      <div
        v-for="s in chatStore.sessions"
        :key="s.id"
        class="session-item"
        :class="{ active: s.id === chatStore.currentSessionId }"
        @click="chatStore.selectSession(s.id)"
      >
        <el-icon class="session-icon"><ChatDotRound /></el-icon>
        <div class="session-info">
          <div class="session-title">{{ s.title || '会话 ' + s.id.slice(0, 8) }}</div>
          <div class="session-meta">
            <span>{{ s.message_count }} 条消息</span>
            <span v-if="s.display_time" class="session-time">{{ s.display_time }}</span>
          </div>
        </div>
        <el-button
          class="delete-btn"
          type="danger"
          text
          size="small"
          @click.stop="chatStore.removeSession(s.id)"
        >
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>
      <el-empty v-if="chatStore.sessions.length === 0" description="暂无会话" :image-size="60" />
    </div>

    <div class="sidebar-footer">
      <div class="model-selector">
        <span class="model-label">模型</span>
        <el-select v-model="chatStore.currentModel" size="small" style="width: 100%">
          <el-option
            v-for="m in chatStore.models"
            :key="m.id"
            :label="m.name"
            :value="m.id"
          />
        </el-select>
      </div>
      <div v-if="isDeepSeekModel" class="deep-thinking-toggle">
        <span class="toggle-label">深度思考</span>
        <el-switch
          v-model="chatStore.deepThinking"
          size="small"
          active-text="开"
          inactive-text="关"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Plus, Delete, ChatDotRound } from '@element-plus/icons-vue'
import { useChatStore } from '../stores/chat'

const chatStore = useChatStore()

const isDeepSeekModel = computed(() => {
  return chatStore.currentModel.startsWith('deepseek')
})
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
  padding: 16px;
  flex-shrink: 0;
}

.new-chat-btn {
  width: 100%;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden !important;
  padding: 0 8px;
}

.session-item {
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
  text-overflow: ellipsis;
}

.session-meta {
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.session-time {
  color: #c0c4cc;
}

.delete-btn {
  opacity: 0;
  transition: opacity 0.2s;
  flex-shrink: 0;
}

.session-item:hover .delete-btn {
  opacity: 1;
}

.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid #e4e7ed;
}

.model-selector {
  display: flex;
  align-items: center;
  gap: 8px;
}

.model-label {
  font-size: 12px;
  color: #606266;
  white-space: nowrap;
}

.deep-thinking-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
}

.toggle-label {
  font-size: 12px;
  color: #606266;
}
</style>
