<template>
  <div class="sidebar">
    <div class="sidebar-header">
      <el-button type="primary" class="new-chat-btn" @click="chatStore.newConversation()">
        <el-icon><Plus /></el-icon>
        <span>新建会话</span>
      </el-button>
    </div>

    <div class="conversation-list scrollable">
      <div
        v-for="conv in chatStore.conversations"
        :key="conv.conversation_id"
        class="conversation-item"
        :class="{ active: conv.conversation_id === chatStore.currentConversationId }"
        @click="chatStore.selectConversation(conv.conversation_id)"
      >
        <el-icon class="conv-icon"><ChatDotRound /></el-icon>
        <div class="conv-info">
          <div class="conv-title">会话 {{ conv.conversation_id.slice(0, 8) }}</div>
          <div class="conv-meta">{{ conv.message_count }} 条消息</div>
        </div>
        <el-button
          class="delete-btn"
          type="danger"
          text
          size="small"
          @click.stop="chatStore.removeConversation(conv.conversation_id)"
        >
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>
      <el-empty v-if="chatStore.conversations.length === 0" description="暂无会话" :image-size="60" />
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

.conversation-list {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden !important;
  padding: 0 8px;
}

.conversation-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  margin-bottom: 4px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.conversation-item:hover {
  background: #e8eaed;
}

.conversation-item.active {
  background: #d9ecff;
}

.conv-icon {
  font-size: 18px;
  color: #409eff;
  margin-right: 10px;
  flex-shrink: 0;
}

.conv-info {
  flex: 1;
  min-width: 0;
}

.conv-title {
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-meta {
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
}

.delete-btn {
  opacity: 0;
  transition: opacity 0.2s;
  flex-shrink: 0;
}

.conversation-item:hover .delete-btn {
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
</style>
