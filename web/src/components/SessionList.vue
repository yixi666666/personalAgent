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
      <div class="user-profile">
        <el-avatar :size="36" style="background: #409eff">忆</el-avatar>
        <span class="user-nickname">忆昔</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Plus, Delete, ChatDotRound } from '@element-plus/icons-vue'
import { useChatStore } from '../stores/chat'

const chatStore = useChatStore()
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
  padding: 8px 16px;
  border-top: 1px solid #e4e7ed;
}
</style>
