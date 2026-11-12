<template>
  <div class="admin-layout">
    <!-- 左侧导航 -->
    <aside class="admin-aside">
      <div class="admin-brand">
        <span class="admin-brand-name">管理控制台</span>
        <button
          class="header-icon-btn"
          type="button"
          title="返回聊天"
          aria-label="返回聊天"
          @click="router.replace('/chat')"
        >
          <el-icon><ChatDotRound /></el-icon>
        </button>
      </div>
      <el-menu :default-active="activeTab" class="admin-menu" @select="key => (activeTab = key)">
        <el-menu-item index="configs">
          <el-icon><Setting /></el-icon>
          <span>系统配置</span>
        </el-menu-item>
        <el-menu-item index="models">
          <el-icon><Cpu /></el-icon>
          <span>模型配置</span>
        </el-menu-item>
        <el-menu-item index="users">
          <el-icon><User /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
        <el-menu-item index="announcements">
          <el-icon><Bell /></el-icon>
          <span>公告管理</span>
        </el-menu-item>
      </el-menu>
      <div class="admin-aside-footer">
        <el-button class="admin-footer-btn" type="danger" plain :loading="loggingOut" @click="handleLogout">退出登录</el-button>
      </div>
    </aside>

    <!-- 右侧内容 -->
    <main class="admin-content">
      <!-- 系统配置 -->
      <template v-if="activeTab === 'configs'">
        <header class="content-header">
          <div>
            <h2>系统配置</h2>
            <p class="content-desc">key 规范：{group}.{name}，如 llm.default_model；改动保存后立即对后端生效</p>
          </div>
          <div class="content-actions">
            <el-button @click="loadConfigs">刷新</el-button>
            <el-button type="primary" @click="openConfigDialog()">新增配置</el-button>
          </div>
        </header>
        <el-table v-loading="configsLoading" :data="configs" size="small" border class="content-table">
          <el-table-column prop="key" label="Key" min-width="200" show-overflow-tooltip />
          <el-table-column prop="label" label="名称" min-width="120" show-overflow-tooltip />
          <el-table-column prop="value" label="值" min-width="200" show-overflow-tooltip />
          <el-table-column prop="value_type" label="类型" width="90" />
          <el-table-column prop="group_name" label="分组" width="100" />
          <el-table-column label="公开" width="70" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_public ? 'success' : 'info'" size="small">{{ row.is_public ? '是' : '否' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="说明" min-width="150" show-overflow-tooltip />
          <el-table-column label="更新时间" width="160">
            <template #default="{ row }">{{ formatTime(row.updated_time) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="130" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openConfigDialog(row)">编辑</el-button>
              <el-button link type="danger" @click="removeConfig(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <!-- 模型配置 -->
      <template v-else-if="activeTab === 'models'">
        <header class="content-header">
          <div>
            <h2>模型配置</h2>
            <p class="content-desc">api_key 加密存储；启用/停用与能力修改保存后立即生效</p>
          </div>
          <div class="content-actions">
            <el-button @click="loadModels">刷新</el-button>
            <el-button type="primary" @click="openModelDialog()">新增模型</el-button>
          </div>
        </header>
        <el-table v-loading="modelsLoading" :data="models" size="small" border class="content-table">
          <el-table-column prop="name" label="名称" min-width="130" show-overflow-tooltip />
          <el-table-column prop="model_id" label="模型ID" min-width="160" show-overflow-tooltip />
          <el-table-column prop="model_type" label="类型" width="95" />
          <el-table-column prop="provider" label="提供商" width="100" />
          <el-table-column label="API Key" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="row.has_api_key ? 'success' : 'info'" size="small">{{ row.has_api_key ? '已配置' : '无' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="启用" width="70" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_enabled ? 'success' : 'danger'" size="small">{{ row.is_enabled ? '启用' : '停用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="priority" label="优先级" width="80" align="center" />
          <el-table-column label="能力" min-width="220">
            <template #default="{ row }">
              <el-tag
                v-for="cap in capabilityTags(row.capabilities)"
                :key="cap"
                size="small"
                class="cap-tag"
              >{{ cap }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="130" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openModelDialog(row)">编辑</el-button>
              <el-button link type="danger" @click="removeModel(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <!-- 用户管理 -->
      <template v-else-if="activeTab === 'users'">
        <header class="content-header">
          <div>
            <h2>用户管理</h2>
            <p class="content-desc">不能修改自己的角色/状态；禁用后该用户下次请求即失效</p>
          </div>
          <div class="content-actions">
            <el-button @click="loadUsers">刷新</el-button>
          </div>
        </header>
        <el-table v-loading="usersLoading" :data="pagedUsers" size="small" border class="content-table">
          <el-table-column prop="username" label="账号" min-width="140" show-overflow-tooltip />
          <el-table-column prop="display_name" label="显示名" min-width="120" show-overflow-tooltip />
          <el-table-column prop="email" label="邮箱" min-width="160" show-overflow-tooltip />
          <el-table-column label="角色" width="150">
            <template #default="{ row }">
              <el-select
                :model-value="row.role"
                size="small"
                :disabled="isSelf(row)"
                @change="role => updateUserRole(row, role)"
              >
                <el-option label="普通用户" value="user" />
                <el-option label="管理员" value="admin" />
                <el-option label="超级管理员" value="super_admin" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="110" align="center">
            <template #default="{ row }">
              <el-switch
                :model-value="row.status === 'active'"
                :disabled="isSelf(row)"
                inline-prompt
                active-text="正常"
                inactive-text="禁用"
                @change="v => updateUserStatus(row, v)"
              />
            </template>
          </el-table-column>
          <el-table-column label="最后登录" width="160">
            <template #default="{ row }">{{ formatTime(row.last_login_time) }}</template>
          </el-table-column>
          <el-table-column label="注册时间" width="160">
            <template #default="{ row }">{{ formatTime(row.created_time) }}</template>
          </el-table-column>
        </el-table>
        <div class="table-pagination">
          <el-pagination
            v-model:current-page="userPage"
            :total="users.length"
            :page-size="USER_PAGE_SIZE"
            layout="total, prev, pager, next"
            background
          />
        </div>
      </template>

      <!-- 公告管理 -->
      <template v-else-if="activeTab === 'announcements'">
        <header class="content-header">
          <div>
            <h2>公告管理</h2>
            <p class="content-desc">仅 published 且到达发布时间的公告对用户可见</p>
          </div>
          <div class="content-actions">
            <el-button @click="loadAnnouncements">刷新</el-button>
            <el-button type="primary" @click="openAnnouncementDialog()">发布公告</el-button>
          </div>
        </header>
        <el-table v-loading="announcementsLoading" :data="announcements" size="small" border class="content-table">
          <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="announcementStatusType(row.status)" size="small">{{ announcementStatusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="置顶" width="70" align="center">
            <template #default="{ row }">{{ row.is_pinned ? '是' : '否' }}</template>
          </el-table-column>
          <el-table-column label="发布时间" width="160">
            <template #default="{ row }">{{ formatTime(row.publish_time) }}</template>
          </el-table-column>
          <el-table-column label="弹窗时段" min-width="200">
            <template #default="{ row }">{{ formatPopupRange(row) }}</template>
          </el-table-column>
          <el-table-column label="更新时间" width="160">
            <template #default="{ row }">{{ formatTime(row.updated_time) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="130" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openAnnouncementDialog(row)">编辑</el-button>
              <el-button link type="danger" @click="removeAnnouncement(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </main>

    <!-- 系统配置编辑弹窗 -->
    <el-dialog v-model="configDialogVisible" :title="configForm.id ? '编辑配置' : '新增配置'" width="560px" align-center>
      <el-form :model="configForm" label-width="90px">
        <el-form-item label="Key" required>
          <el-input v-model="configForm.key" :disabled="Boolean(configForm.id)" placeholder="如 chat.recommended_questions" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="configForm.label" placeholder="展示名称" />
        </el-form-item>
        <el-form-item label="值">
          <el-input v-model="configForm.value" type="textarea" :rows="3" placeholder="统一存字符串" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="configForm.value_type">
            <el-option v-for="t in ['string', 'number', 'boolean', 'json', 'array']" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="分组">
          <el-input v-model="configForm.group_name" placeholder="chat / feature / security / llm / embedding / tool" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="configForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="公开">
          <el-switch v-model="configForm.is_public" />
          <span class="form-hint">开启后前端未登录也可读取</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="configDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="configSaving" @click="saveConfig">保存</el-button>
      </template>
    </el-dialog>

    <!-- 模型配置编辑弹窗 -->
    <el-dialog v-model="modelDialogVisible" :title="modelForm.id ? '编辑模型' : '新增模型'" width="620px" align-center>
      <el-form :model="modelForm" label-width="100px">
        <el-form-item label="模型ID" required>
          <el-input v-model="modelForm.model_id" placeholder="如 deepseek-v4-flash" />
        </el-form-item>
        <el-form-item label="展示名称">
          <el-input v-model="modelForm.name" />
        </el-form-item>
        <el-form-item label="模型类型">
          <el-select v-model="modelForm.model_type">
            <el-option label="chat" value="chat" />
            <el-option label="embedding" value="embedding" />
          </el-select>
        </el-form-item>
        <el-form-item label="提供商">
          <el-input v-model="modelForm.provider" placeholder="如 openai / deepseek / local" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input
            v-model="modelForm.api_key"
            type="password"
            show-password
            :placeholder="modelForm.id ? '留空保持不变' : '明文，保存后加密存储'"
            autocomplete="off"
          />
        </el-form-item>
        <el-form-item label="API 地址">
          <el-input v-model="modelForm.base_url" placeholder="如 https://api.deepseek.com" />
        </el-form-item>
        <el-form-item label="路径前缀">
          <el-input v-model="modelForm.api_prefix" placeholder="如 /v1" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="modelForm.is_enabled" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="modelForm.priority" :min="0" />
          <span class="form-hint">数值越小越优先</span>
        </el-form-item>
        <el-form-item label="最大Token">
          <el-input-number v-model="modelForm.max_tokens" :min="1" :step="256" />
        </el-form-item>
        <el-form-item label="温度">
          <el-input-number v-model="modelForm.temperature" :min="0" :max="2" :step="0.1" />
        </el-form-item>
        <el-form-item label="能力">
          <div class="capability-grid">
            <el-checkbox v-model="modelCapabilities.supports_tools">工具调用</el-checkbox>
            <el-checkbox v-model="modelCapabilities.deep_thinking">深度思考</el-checkbox>
            <el-checkbox v-model="modelCapabilities.web_search">联网搜索</el-checkbox>
            <el-checkbox v-model="modelCapabilities.structured_output">结构化输出</el-checkbox>
            <el-checkbox v-model="modelCapabilities.multimodal">多模态</el-checkbox>
            <el-checkbox v-model="modelCapabilities.streaming">流式</el-checkbox>
            <el-checkbox v-model="modelCapabilities.stop_anytime">随时停止</el-checkbox>
            <div class="capability-window">
              上下文窗口
              <el-input-number v-model="modelCapabilities.context_window" :min="1024" :step="1024" size="small" />
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="modelDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="modelSaving" @click="saveModel">保存</el-button>
      </template>
    </el-dialog>

    <!-- 公告编辑弹窗 -->
    <el-dialog v-model="announcementDialogVisible" :title="announcementForm.id ? '编辑公告' : '发布公告'" width="620px" align-center>
      <el-form :model="announcementForm" label-width="100px">
        <el-form-item label="标题" required>
          <el-input v-model="announcementForm.title" />
        </el-form-item>
        <el-form-item label="正文">
          <el-input v-model="announcementForm.content" type="textarea" :rows="5" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="announcementForm.status">
            <el-option label="草稿" value="draft" />
            <el-option label="已发布" value="published" />
            <el-option label="已下线" value="offline" />
          </el-select>
        </el-form-item>
        <el-form-item label="发布时间">
          <el-date-picker
            v-model="announcementForm.publish_time"
            type="datetime"
            placeholder="留空则立即展示"
            value-format="x"
          />
        </el-form-item>
        <el-form-item label="置顶">
          <el-switch v-model="announcementForm.is_pinned" />
        </el-form-item>
        <el-form-item label="弹窗时段">
          <el-date-picker
            v-model="announcementForm.popup_start_time"
            type="datetime"
            placeholder="开始时间"
            value-format="x"
          />
          <span class="form-sep">至</span>
          <el-date-picker
            v-model="announcementForm.popup_end_time"
            type="datetime"
            placeholder="结束时间"
            value-format="x"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="announcementDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="announcementSaving" @click="saveAnnouncement">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Bell, ChatDotRound, Cpu, Setting, User } from '@element-plus/icons-vue'
import {
  adminCreateAnnouncement,
  adminCreateConfig,
  adminCreateModel,
  adminDeleteAnnouncement,
  adminDeleteConfig,
  adminDeleteModel,
  adminListAnnouncements,
  adminListConfigs,
  adminListModels,
  adminListUsers,
  adminUpdateAnnouncement,
  adminUpdateConfig,
  adminUpdateModel,
  adminUpdateUser,
} from '../api'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const activeTab = ref('configs')
const loggingOut = ref(false)

// ==== 通用 ====

function formatTime(ts) {
  if (!ts) return '-'
  return new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false })
}

// 秒 → 毫秒（供 el-date-picker value-format="x" 使用）
const secToMs = ts => (ts ? String(ts * 1000) : null)
// 毫秒 → 秒
const msToSec = ms => (ms ? Math.floor(Number(ms) / 1000) : null)

async function handleApiError(error, fallback) {
  ElMessage.error(error?.response?.data?.detail || fallback)
}

// ==== 系统配置 ====

const configs = ref([])
const configsLoading = ref(false)
const configDialogVisible = ref(false)
const configSaving = ref(false)
const configForm = reactive({
  id: null, key: '', label: '', value: '', value_type: 'string', group_name: '', description: '', is_public: false,
})

async function loadConfigs() {
  configsLoading.value = true
  try {
    configs.value = await adminListConfigs()
  } catch (error) {
    handleApiError(error, '加载系统配置失败')
  } finally {
    configsLoading.value = false
  }
}

function openConfigDialog(row = null) {
  Object.assign(configForm, {
    id: row?.id || null,
    key: row?.key || '',
    label: row?.label || '',
    value: row?.value ?? '',
    value_type: row?.value_type || 'string',
    group_name: row?.group_name || '',
    description: row?.description || '',
    is_public: row?.is_public || false,
  })
  configDialogVisible.value = true
}

async function saveConfig() {
  if (!configForm.key.trim()) {
    ElMessage.warning('请填写配置 Key')
    return
  }
  configSaving.value = true
  try {
    const payload = {
      value: configForm.value || null,
      value_type: configForm.value_type,
      group_name: configForm.group_name || null,
      label: configForm.label || null,
      description: configForm.description || null,
      is_public: configForm.is_public,
    }
    if (configForm.id) {
      await adminUpdateConfig(configForm.id, payload)
    } else {
      await adminCreateConfig({ ...payload, key: configForm.key.trim() })
    }
    ElMessage.success('配置已保存')
    configDialogVisible.value = false
    await loadConfigs()
  } catch (error) {
    handleApiError(error, '保存配置失败')
  } finally {
    configSaving.value = false
  }
}

async function removeConfig(row) {
  try {
    await ElMessageBox.confirm(`确定删除配置「${row.key}」？`, '删除确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await adminDeleteConfig(row.id)
    ElMessage.success('配置已删除')
    await loadConfigs()
  } catch (error) {
    handleApiError(error, '删除配置失败')
  }
}

// ==== 模型配置 ====

const models = ref([])
const modelsLoading = ref(false)
const modelDialogVisible = ref(false)
const modelSaving = ref(false)
const modelForm = reactive({
  id: null, model_id: '', name: '', model_type: 'chat', provider: '', api_key: '',
  base_url: '', api_prefix: '', is_enabled: true, priority: 0, max_tokens: null, temperature: null,
})
const modelCapabilities = reactive({
  supports_tools: true, deep_thinking: false, web_search: false, structured_output: false,
  multimodal: false, streaming: true, stop_anytime: true, context_window: 4096,
})

const CAPABILITY_LABELS = {
  supports_tools: '工具调用', deep_thinking: '深度思考', web_search: '联网搜索',
  structured_output: '结构化输出', multimodal: '多模态', streaming: '流式', stop_anytime: '随时停止',
}

function capabilityTags(capabilities) {
  if (!capabilities) return []
  const tags = Object.entries(CAPABILITY_LABELS)
    .filter(([key]) => capabilities[key])
    .map(([, label]) => label)
  if (capabilities.context_window) tags.push(`${capabilities.context_window} 窗口`)
  return tags
}

async function loadModels() {
  modelsLoading.value = true
  try {
    models.value = await adminListModels()
  } catch (error) {
    handleApiError(error, '加载模型配置失败')
  } finally {
    modelsLoading.value = false
  }
}

function openModelDialog(row = null) {
  modelForm.id = row?.id || null
  modelForm.model_id = row?.model_id || ''
  modelForm.name = row?.name || ''
  modelForm.model_type = row?.model_type || 'chat'
  modelForm.provider = row?.provider || ''
  modelForm.api_key = '' // 编辑时留空表示不修改
  modelForm.base_url = row?.base_url || ''
  modelForm.api_prefix = row?.api_prefix || ''
  modelForm.is_enabled = row ? row.is_enabled : true
  modelForm.priority = row?.priority ?? 0
  modelForm.max_tokens = row?.max_tokens ?? null
  modelForm.temperature = row?.temperature ?? null
  const caps = row?.capabilities || {}
  Object.assign(modelCapabilities, {
    supports_tools: caps.supports_tools ?? true,
    deep_thinking: caps.deep_thinking ?? false,
    web_search: caps.web_search ?? false,
    structured_output: caps.structured_output ?? false,
    multimodal: caps.multimodal ?? false,
    streaming: caps.streaming ?? true,
    stop_anytime: caps.stop_anytime ?? true,
    context_window: caps.context_window ?? 4096,
  })
  modelDialogVisible.value = true
}

async function saveModel() {
  if (!modelForm.model_id.trim()) {
    ElMessage.warning('请填写模型ID')
    return
  }
  modelSaving.value = true
  try {
    const payload = {
      model_id: modelForm.model_id.trim(),
      name: modelForm.name || null,
      model_type: modelForm.model_type,
      provider: modelForm.provider || null,
      base_url: modelForm.base_url || null,
      api_prefix: modelForm.api_prefix || null,
      is_enabled: modelForm.is_enabled,
      priority: modelForm.priority,
      max_tokens: modelForm.max_tokens,
      temperature: modelForm.temperature,
      capabilities: { ...modelCapabilities },
    }
    if (modelForm.id) {
      if (modelForm.api_key) payload.api_key = modelForm.api_key
      await adminUpdateModel(modelForm.id, payload)
    } else {
      if (modelForm.api_key) payload.api_key = modelForm.api_key
      await adminCreateModel(payload)
    }
    ElMessage.success('模型配置已保存')
    modelDialogVisible.value = false
    await loadModels()
  } catch (error) {
    handleApiError(error, '保存模型配置失败')
  } finally {
    modelSaving.value = false
  }
}

async function removeModel(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除模型「${row.model_id}」？删除后使用该模型的对话将报错。`,
      '删除确认',
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await adminDeleteModel(row.id)
    ElMessage.success('模型配置已删除')
    await loadModels()
  } catch (error) {
    handleApiError(error, '删除模型配置失败')
  }
}

// ==== 用户管理 ====

const users = ref([])
const usersLoading = ref(false)
// 用户列表前端分页
const USER_PAGE_SIZE = 10
const userPage = ref(1)
const pagedUsers = computed(() => {
  const start = (userPage.value - 1) * USER_PAGE_SIZE
  return users.value.slice(start, start + USER_PAGE_SIZE)
})

function isSelf(row) {
  return row.id === authStore.currentUser?.id
}

async function loadUsers() {
  usersLoading.value = true
  try {
    users.value = await adminListUsers()
    // 数据刷新后若当前页越界则回退
    const maxPage = Math.max(1, Math.ceil(users.value.length / USER_PAGE_SIZE))
    if (userPage.value > maxPage) userPage.value = maxPage
  } catch (error) {
    handleApiError(error, '加载用户列表失败')
  } finally {
    usersLoading.value = false
  }
}

async function updateUserRole(row, role) {
  try {
    await adminUpdateUser(row.id, { role })
    row.role = role
    ElMessage.success(`已将「${row.username}」角色改为 ${role}`)
  } catch (error) {
    handleApiError(error, '修改角色失败')
    await loadUsers()
  }
}

async function updateUserStatus(row, active) {
  try {
    await adminUpdateUser(row.id, { status: active ? 'active' : 'disabled' })
    row.status = active ? 'active' : 'disabled'
    ElMessage.success(`已${active ? '启用' : '禁用'}账号「${row.username}」`)
  } catch (error) {
    handleApiError(error, '修改状态失败')
    await loadUsers()
  }
}

// ==== 公告管理 ====

const announcements = ref([])
const announcementsLoading = ref(false)
const announcementDialogVisible = ref(false)
const announcementSaving = ref(false)
const announcementForm = reactive({
  id: null, title: '', content: '', status: 'published',
  publish_time: null, is_pinned: false, popup_start_time: null, popup_end_time: null,
})

const ANNOUNCEMENT_STATUS_LABELS = { draft: '草稿', published: '已发布', offline: '已下线' }
const ANNOUNCEMENT_STATUS_TYPES = { draft: 'info', published: 'success', offline: 'warning' }

const announcementStatusLabel = status => ANNOUNCEMENT_STATUS_LABELS[status] || status
const announcementStatusType = status => ANNOUNCEMENT_STATUS_TYPES[status] || 'info'

function formatPopupRange(row) {
  if (!row.popup_start_time && !row.popup_end_time) return '-'
  return `${formatTime(row.popup_start_time)} ~ ${formatTime(row.popup_end_time)}`
}

async function loadAnnouncements() {
  announcementsLoading.value = true
  try {
    announcements.value = await adminListAnnouncements()
  } catch (error) {
    handleApiError(error, '加载公告列表失败')
  } finally {
    announcementsLoading.value = false
  }
}

function openAnnouncementDialog(row = null) {
  Object.assign(announcementForm, {
    id: row?.id || null,
    title: row?.title || '',
    content: row?.content || '',
    status: row?.status || 'published',
    publish_time: secToMs(row?.publish_time),
    is_pinned: row?.is_pinned || false,
    popup_start_time: secToMs(row?.popup_start_time),
    popup_end_time: secToMs(row?.popup_end_time),
  })
  announcementDialogVisible.value = true
}

async function saveAnnouncement() {
  if (!announcementForm.title.trim()) {
    ElMessage.warning('请填写公告标题')
    return
  }
  announcementSaving.value = true
  try {
    const payload = {
      title: announcementForm.title.trim(),
      content: announcementForm.content || null,
      status: announcementForm.status,
      publish_time: msToSec(announcementForm.publish_time),
      is_pinned: announcementForm.is_pinned,
      popup_start_time: msToSec(announcementForm.popup_start_time),
      popup_end_time: msToSec(announcementForm.popup_end_time),
    }
    if (announcementForm.id) {
      await adminUpdateAnnouncement(announcementForm.id, payload)
    } else {
      await adminCreateAnnouncement(payload)
    }
    ElMessage.success('公告已保存')
    announcementDialogVisible.value = false
    await loadAnnouncements()
  } catch (error) {
    handleApiError(error, '保存公告失败')
  } finally {
    announcementSaving.value = false
  }
}

async function removeAnnouncement(row) {
  try {
    await ElMessageBox.confirm(`确定删除公告「${row.title}」？所有已读记录将一并清除。`, '删除确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await adminDeleteAnnouncement(row.id)
    ElMessage.success('公告已删除')
    await loadAnnouncements()
  } catch (error) {
    handleApiError(error, '删除公告失败')
  }
}

// ==== 退出 ====

async function handleLogout() {
  loggingOut.value = true
  try {
    await authStore.logout()
    await router.replace('/login')
  } finally {
    loggingOut.value = false
  }
}

onMounted(() => {
  loadConfigs()
  loadModels()
  loadUsers()
  loadAnnouncements()
})
</script>

<style scoped>
.admin-layout {
  display: flex;
  /* 占满一屏的固定区域，内容区超高时内部滚动 */
  height: 100vh;
  background: #f5f7fa;
}

/* ===== 左侧导航 ===== */

.admin-aside {
  display: flex;
  flex-direction: column;
  /* 与聊天会话列表默认宽度一致（ChatView DEFAULT_PANEL_WIDTH = 260） */
  width: 260px;
  flex-shrink: 0;
  background: #fff;
  border-right: 1px solid #e4e7ed;
}

.admin-brand {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 14px 16px 14px 20px;
  border-bottom: 1px solid #f0f2f5;
}

.admin-brand-name {
  font-size: 17px;
  font-weight: 600;
  color: #303133;
}

/* 与聊天页侧边栏顶部图标按钮同款样式，保证两页切换按钮位置一致 */
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

.admin-menu {
  flex: 1;
  border-right: none;
  padding: 8px;
}

.admin-menu .el-menu-item {
  border-radius: 6px;
  margin-bottom: 4px;
  height: 44px;
}

.admin-menu .el-menu-item.is-active {
  background: #ecf5ff;
}

.admin-aside-footer {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px 20px;
  border-top: 1px solid #f0f2f5;
}

.admin-footer-btn {
  width: 100%;
  margin: 0;
}

.admin-footer-btn + .admin-footer-btn {
  margin-left: 0;
}

/* ===== 右侧内容 ===== */

.admin-content {
  flex: 1;
  min-width: 0;
  padding: 24px clamp(16px, 3vw, 40px);
  overflow-y: auto;
}

.table-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.content-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.content-header h2 {
  margin: 0 0 4px;
  font-size: 20px;
  color: #303133;
}

.content-desc {
  margin: 0;
  font-size: 12px;
  color: #909399;
}

.content-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.content-table {
  width: 100%;
  background: #fff;
  border-radius: 8px;
}

/* 统一各表格行高（对齐用户管理表内嵌控件时的行高观感） */
.content-table :deep(.el-table__cell) {
  padding: 14px 0;
}

.cap-tag {
  margin-right: 4px;
  margin-bottom: 2px;
}

.form-hint {
  margin-left: 10px;
  font-size: 12px;
  color: #909399;
}

.capability-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 4px 12px;
  width: 100%;
}

.capability-window {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #606266;
}

.form-sep {
  margin: 0 6px;
  color: #909399;
}
</style>
