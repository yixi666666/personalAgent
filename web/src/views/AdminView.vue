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
        <el-menu-item index="universities">
          <el-icon><School /></el-icon>
          <span>高校信息</span>
        </el-menu-item>
        <el-menu-item index="announcements">
          <el-icon><Bell /></el-icon>
          <span>公告管理</span>
        </el-menu-item>
        <el-menu-item index="feedbacks">
          <el-icon><Pointer /></el-icon>
          <span>反馈管理</span>
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
            <el-radio-group v-model="configViewMode" size="small">
              <el-radio-button value="quick">快捷</el-radio-button>
              <el-radio-button value="list">列表</el-radio-button>
            </el-radio-group>
            <el-button @click="loadConfigs">刷新</el-button>
            <el-button type="primary" @click="openConfigDialog()">新增配置</el-button>
          </div>
        </header>
        <!-- 快捷视图：单卡片分组，行内直接修改，完整编辑走弹窗 -->
        <div v-if="configViewMode === 'quick'" v-loading="configsLoading" class="config-quick-card">
          <div v-for="row in configs" :key="row.id" class="config-quick-item">
            <span class="config-quick-label">{{ row.label || row.key }}</span>
            <div class="config-quick-control">
              <el-select
                v-if="isModelConfig(row.key)"
                :model-value="row.value"
                filterable
                size="small"
                style="width: 320px"
                placeholder="从启用的模型中选择"
                @change="val => quickSaveConfig(row, val)"
              >
                <el-option
                  v-for="m in modelOptionsFor(row.key)"
                  :key="m.model_id"
                  :label="`${m.name} (${m.model_id})`"
                  :value="m.model_id"
                />
              </el-select>
              <el-switch
                v-else-if="row.value_type === 'boolean'"
                :model-value="row.value === 'true'"
                @change="val => quickSaveConfig(row, String(val))"
              />
              <el-input
                v-else-if="isSecretConfig(row.key)"
                type="password"
                size="small"
                style="width: 320px"
                placeholder="已加密存储，输入新值可更换"
                @change="val => quickSaveConfig(row, val)"
              />
              <el-input
                v-else-if="row.value_type === 'json' || row.value_type === 'array'"
                :model-value="row.value"
                type="textarea"
                :rows="2"
                autosize
                size="small"
                style="width: 480px"
                @change="val => quickSaveConfig(row, val)"
              />
              <el-input
                v-else
                :model-value="row.value"
                size="small"
                style="width: 320px"
                @change="val => quickSaveConfig(row, val)"
              />
            </div>
          </div>
          <p v-if="!configsLoading && !configs.length" class="stat-empty">暂无配置</p>
        </div>
        <el-table v-else v-loading="configsLoading" :data="configs" size="small" border class="content-table">
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
        <div class="users-tab">
          <header class="content-header">
            <div>
              <h2>用户管理</h2>
              <p class="content-desc">不能修改自己的角色/状态；仅超级管理员可将账号设为游客；禁用后该用户下次请求即失效</p>
            </div>
            <div class="content-actions">
              <el-button @click="loadUsers">刷新</el-button>
            </div>
          </header>
          <div class="users-table-wrap">
            <el-table v-loading="usersLoading" :data="pagedUsers" size="small" border height="100%" class="content-table users-table">
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
                <!-- 游客选项始终保留用于正确回显已有游客账号，仅超管可选 -->
                <el-option
                  label="游客"
                  value="guest"
                  :disabled="authStore.currentUser?.role !== 'super_admin'"
                />
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
          </div>
          <div class="table-pagination">
            <el-pagination
              v-model:current-page="userPage"
              :total="users.length"
              :page-size="USER_PAGE_SIZE"
              layout="total, prev, pager, next"
              background
            />
          </div>
        </div>
      </template>

      <!-- 高校信息 -->
      <template v-else-if="activeTab === 'universities'">
        <div class="universities-tab">
        <header class="content-header">
          <div>
            <h2>高校信息</h2>
            <p class="content-desc">全国高校基础数据总览与维护；修改名称/别名后需运行 sync_universities.py --rebuild-vec 同步向量索引</p>
          </div>
          <div class="content-actions">
            <el-button @click="loadUniversityTab">刷新</el-button>
          </div>
        </header>

        <div class="stat-cards">
          <div
            v-for="stat in universityStats"
            :key="stat.label"
            class="stat-card stat-card-clickable"
            :class="{ 'stat-card-active': isStatActive(stat) }"
            :title="stat.filter ? '点击筛选' : '点击清空筛选'"
            @click="toggleStatFilter(stat)"
          >
            <span class="stat-label">{{ stat.label }}</span>
            <span class="stat-value">{{ stat.value }}</span>
          </div>
        </div>

        <div class="feedback-filters">
          <el-input
            v-model="universityFilter.keyword"
            placeholder="搜索名称 / 别名 / 标识码"
            clearable
            style="width: 220px"
          />
          <el-select v-model="universityFilter.province" placeholder="全部省份" clearable filterable style="width: 150px">
            <el-option v-for="p in provinceOptions" :key="p" :label="p" :value="p" />
          </el-select>
          <el-select v-model="universityFilter.tag" placeholder="全部标签" clearable style="width: 140px">
            <el-option v-for="t in TAG_OPTIONS" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
          <el-select v-model="universityFilter.edu_level" placeholder="全部层次" clearable style="width: 120px">
            <el-option label="本科" value="本科" />
            <el-option label="专科" value="专科" />
          </el-select>
          <el-select v-model="universityFilter.category" placeholder="全部类型" clearable style="width: 130px">
            <el-option label="普通高校" value="ordinary" />
            <el-option label="成人高校" value="adult" />
          </el-select>
        </div>

        <div class="universities-table-wrap">
          <el-table v-loading="universitiesLoading" :data="universities" size="small" border height="100%" class="content-table universities-table">
            <el-table-column label="校徽" width="64" align="center">
              <template #default="{ row }">
                <el-image
                  v-if="row.has_logo"
                  :src="universityLogoSrc(row.name)"
                  fit="contain"
                  class="university-logo"
                  lazy
                />
                <span v-else class="stat-empty">-</span>
              </template>
            </el-table-column>
            <el-table-column label="名称" width="162" show-overflow-tooltip>
              <template #default="{ row }">{{ row.name }}</template>
            </el-table-column>
            <el-table-column prop="school_nature" label="性质" width="68" />
            <el-table-column prop="edu_level" label="层次" width="68" />
            <el-table-column label="所在地" width="130" show-overflow-tooltip>
              <template #default="{ row }">{{ [row.province, row.city].filter(Boolean).join(' ') || '-' }}</template>
            </el-table-column>
            <el-table-column prop="competent_department" label="主管部门" width="102" show-overflow-tooltip>
              <template #default="{ row }">{{ row.competent_department || '-' }}</template>
            </el-table-column>
            <el-table-column label="类型" width="90">
              <template #default="{ row }">{{ CATEGORY_TEXT[row.category] || row.category || '-' }}</template>
            </el-table-column>
            <el-table-column label="官网" width="150" show-overflow-tooltip>
              <template #default="{ row }">
                <a
                  v-if="row.official_website"
                  :href="row.official_website"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="university-link"
                >{{ row.official_website }}</a>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="标签" min-width="200">
              <template #default="{ row }">
                <template v-if="sortedTagTexts(row).length">
                  <el-tag v-for="text in sortedTagTexts(row)" :key="text" size="small" class="cap-tag">{{ text }}</el-tag>
                </template>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openUniversityDetail(row)">详情</el-button>
                <el-button link type="primary" @click="openUniversityDialog(row)">编辑</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <div class="table-pagination">
          <el-pagination
            v-model:current-page="universityPage"
            :total="universityTotal"
            :page-size="UNIVERSITY_PAGE_SIZE"
            layout="total, prev, pager, next"
            background
          />
        </div>
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

      <!-- 反馈管理（点赞/拉踩） -->
      <template v-else-if="activeTab === 'feedbacks'">
        <header class="content-header">
          <div>
            <h2>反馈管理</h2>
            <p class="content-desc">用户对助手回答的点赞/拉踩记录（只读）与原因字典；字典变更后立即对前端生效</p>
          </div>
          <div class="content-actions">
            <el-button @click="loadFeedbackAll">刷新</el-button>
          </div>
        </header>

        <div class="stat-cards">
          <div class="stat-card">
            <span class="stat-label">反馈总数</span>
            <span class="stat-value">{{ feedbackStats.total_count }}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">点赞</span>
            <span class="stat-value stat-value-like">{{ feedbackStats.like_count }}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">拉踩</span>
            <span class="stat-value stat-value-dislike">{{ feedbackStats.dislike_count }}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">参与用户</span>
            <span class="stat-value">{{ feedbackStats.user_count }}</span>
          </div>
          <div class="stat-card stat-card-reasons">
            <span class="stat-label">原因分布</span>
            <div class="reason-dist">
              <el-tag
                v-for="rs in feedbackStats.reason_stats"
                :key="rs.code"
                size="small"
                :type="rs.feedback_type === 'like' ? 'success' : 'danger'"
                class="cap-tag"
              >{{ rs.label }} × {{ rs.count }}</el-tag>
              <span v-if="!feedbackStats.reason_stats.length" class="stat-empty">暂无原因数据</span>
            </div>
          </div>
        </div>

        <el-tabs v-model="feedbackSubTab">
          <el-tab-pane label="反馈记录" name="records">
            <div class="feedback-filters">
              <el-select v-model="feedbackFilter.type" placeholder="全部类型" clearable style="width: 130px" @change="loadFeedbacks">
                <el-option label="点赞" value="like" />
                <el-option label="拉踩" value="dislike" />
              </el-select>
              <el-select v-model="feedbackFilter.reason" placeholder="全部原因" clearable filterable style="width: 180px" @change="loadFeedbacks">
                <el-option v-for="r in filterReasonOptions" :key="r.code" :label="r.label" :value="r.code" />
              </el-select>
              <el-select v-model="feedbackFilter.status" style="width: 130px" @change="loadFeedbacks">
                <el-option label="生效中" value="active" />
                <el-option label="已撤销" value="revoked" />
                <el-option label="全部状态" value="all" />
              </el-select>
            </div>
            <el-table v-loading="feedbacksLoading" :data="pagedFeedbacks" size="small" border class="content-table">
              <el-table-column label="用户" width="110" show-overflow-tooltip>
                <template #default="{ row }">{{ row.display_name || row.username || '-' }}</template>
              </el-table-column>
              <el-table-column prop="session_title" label="会话" min-width="130" show-overflow-tooltip />
              <el-table-column label="类型" width="75" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.feedback_type === 'like' ? 'success' : 'danger'" size="small">{{ row.feedback_type === 'like' ? '点赞' : '拉踩' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="原因" min-width="140">
                <template #default="{ row }">
                  <template v-if="row.reason_codes.length">
                    <el-tag v-for="code in row.reason_codes" :key="code" size="small" class="cap-tag">{{ reasonLabel(code) }}</el-tag>
                  </template>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column prop="comment" label="补充说明" min-width="130" show-overflow-tooltip />
              <el-table-column prop="message_preview" label="回答内容" min-width="220" class-name="preview-ellipsis" />
              <el-table-column label="状态" width="80" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">{{ row.status === 'active' ? '生效中' : '已撤销' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="提交时间" width="160">
                <template #default="{ row }">{{ formatTime(row.created_time) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="110" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" @click="openFeedbackContext(row)">查看上下文</el-button>
                </template>
              </el-table-column>
            </el-table>
            <div class="table-pagination">
              <el-pagination
                v-model:current-page="feedbackPage"
                :total="feedbacks.length"
                :page-size="FEEDBACK_PAGE_SIZE"
                layout="total, prev, pager, next"
                background
              />
            </div>
          </el-tab-pane>

          <el-tab-pane label="原因字典" name="reasons">
            <div class="reason-pane-header">
              <span class="content-desc">停用后的原因不再出现在用户反馈选择列表中；已被引用的原因不可删除，只能停用</span>
              <el-button type="primary" size="small" @click="openReasonDialog()">新增原因</el-button>
            </div>
            <el-table v-loading="reasonsLoading" :data="feedbackReasons" size="small" border class="content-table">
              <el-table-column prop="code" label="编码" min-width="150" show-overflow-tooltip />
              <el-table-column label="适用" width="80" align="center">
                <template #default="{ row }">{{ FEEDBACK_TYPE_LABELS[row.feedback_type] || row.feedback_type }}</template>
              </el-table-column>
              <el-table-column prop="label" label="名称" min-width="110" show-overflow-tooltip />
              <el-table-column prop="description" label="说明" min-width="160" show-overflow-tooltip />
              <el-table-column prop="sort_order" label="排序" width="70" align="center" />
              <el-table-column label="引用数" width="80" align="center">
                <template #default="{ row }">{{ row.used_count }}</template>
              </el-table-column>
              <el-table-column label="状态" width="80" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">{{ row.status === 'active' ? '启用' : '停用' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="更新时间" width="160">
                <template #default="{ row }">{{ formatTime(row.updated_time) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="130" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" @click="openReasonDialog(row)">编辑</el-button>
                  <el-button link type="danger" :disabled="row.used_count > 0" @click="removeReason(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
        </el-tabs>
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
          <el-radio-group v-if="configForm.value_type === 'boolean'" v-model="configForm.value">
            <el-radio value="true">true</el-radio>
            <el-radio value="false">false</el-radio>
          </el-radio-group>
          <el-select
            v-else-if="isModelConfig(configForm.key.trim())"
            v-model="configForm.value"
            filterable
            placeholder="从启用的模型中选择"
          >
            <el-option
              v-for="m in modelOptionsFor(configForm.key.trim())"
              :key="m.model_id"
              :label="`${m.name} (${m.model_id})`"
              :value="m.model_id"
            />
          </el-select>
          <el-input v-else v-model="configForm.value" type="textarea" :rows="3" placeholder="统一存字符串" />
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

    <!-- 反馈原因编辑弹窗 -->
    <el-dialog v-model="reasonDialogVisible" :title="reasonForm.id ? '编辑原因' : '新增原因'" width="520px" align-center>
      <el-form :model="reasonForm" label-width="90px">
        <el-form-item label="编码" required>
          <el-input v-model="reasonForm.code" :disabled="Boolean(reasonForm.id)" placeholder="稳定标识，如 insufficient_depth" />
        </el-form-item>
        <el-form-item label="适用类型" required>
          <el-select v-model="reasonForm.feedback_type">
            <el-option label="拉踩" value="dislike" />
            <el-option label="点赞" value="like" />
            <el-option label="通用" value="all" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="reasonForm.label" placeholder="前端展示名称" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="reasonForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="reasonForm.sort_order" :min="0" />
          <span class="form-hint">数值越小越靠前</span>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="reasonForm.status" active-value="active" inactive-value="disabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reasonDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="reasonSaving" @click="saveReason">保存</el-button>
      </template>
    </el-dialog>

    <!-- 反馈上下文弹窗：复用聊天区消息渲染组件，与用户看到的完全一致 -->
    <el-dialog v-model="contextDialogVisible" title="反馈上下文" width="860px" align-center top="4vh">
      <div v-loading="contextLoading" class="context-wrap">
        <template v-if="feedbackContextData">
          <p class="context-session">会话：{{ feedbackContextData.session?.title || '-' }}</p>
          <div class="context-body">
            <div ref="contextScrollRef" class="context-messages">
              <MessageList
                :messages="contextMessages"
                readonly
                :highlight-id="feedbackContextData.feedback_message_id"
                :tool-detail-loader="loadContextToolDetail"
              />
              <p v-if="!contextMessages.length" class="stat-empty">该会话暂无消息（可能已被删除）</p>
            </div>
            <MsgDotNav
              variant="panel"
              :messages="contextMessages"
              :active-id="feedbackUserMessageId"
              :scroll-el-fn="getContextScrollEl"
              @jump="scrollContextToMessage"
            />
          </div>
        </template>
      </div>
    </el-dialog>
    <!-- 高校详情弹窗 -->
    <el-dialog v-model="universityDetailVisible" width="780px" align-center top="4vh">
      <div v-loading="universityDetailLoading" class="context-wrap">
        <template v-if="universityDetailData">
          <div class="university-detail-head">
            <el-image
              v-if="universityDetailData.logo_url"
              :src="universityLogoSrc(universityDetailData.name)"
              fit="contain"
              class="university-logo university-logo-lg"
            />
            <div>
              <p class="university-detail-name">{{ universityDetailData.name }}</p>
              <div class="university-detail-tags">
                <el-tag v-for="text in sortedTagTexts(universityDetailData)" :key="text" size="small" class="cap-tag">{{ text }}</el-tag>
                <span v-if="!sortedTagTexts(universityDetailData).length" class="stat-empty">暂无标签</span>
              </div>
            </div>
          </div>

          <el-descriptions :column="2" size="small" border class="university-desc">
            <el-descriptions-item label="学校标识码">{{ universityDetailData.code || '-' }}</el-descriptions-item>
            <el-descriptions-item label="别名">{{ (universityDetailData.aliases || []).join('、') || '-' }}</el-descriptions-item>
            <el-descriptions-item label="学校类型">{{ CATEGORY_TEXT[universityDetailData.category] || universityDetailData.category || '-' }}</el-descriptions-item>
            <el-descriptions-item label="主管部门">{{ universityDetailData.competent_department || '-' }}</el-descriptions-item>
            <el-descriptions-item label="所在地">{{ [universityDetailData.province, universityDetailData.city].filter(Boolean).join(' ') || '-' }}</el-descriptions-item>
            <el-descriptions-item label="办学层次">{{ universityDetailData.edu_level || '-' }}</el-descriptions-item>
            <el-descriptions-item label="办学性质">{{ universityDetailData.school_nature || '-' }}</el-descriptions-item>
            <el-descriptions-item label="官方网站">
              <a v-if="universityDetailData.official_website" :href="universityDetailData.official_website" target="_blank" class="university-link">{{ universityDetailData.official_website }}</a>
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="一级学科硕士点">{{ universityDetailData.master_first ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="一级学科博士点">{{ universityDetailData.doctor_first ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="备注" :span="2">{{ universityDetailData.raw_remark || '-' }}</el-descriptions-item>
          </el-descriptions>

          <template v-if="universityRankingRows.length">
            <h3 class="university-section-title">排名榜单</h3>
            <el-descriptions :column="1" size="small" border class="university-desc">
              <el-descriptions-item v-for="row in universityRankingRows" :key="row.label" :label="row.label">{{ row.value }}</el-descriptions-item>
            </el-descriptions>
          </template>

          <template v-if="universityDoubleFirstRows.length">
            <h3 class="university-section-title">双一流建设学科</h3>
            <el-descriptions :column="1" size="small" border class="university-desc">
              <el-descriptions-item v-for="row in universityDoubleFirstRows" :key="row.label" :label="row.label">{{ row.value }}</el-descriptions-item>
            </el-descriptions>
          </template>

          <template v-if="universityEvaluationRows.length">
            <h3 class="university-section-title">学科评估</h3>
            <el-descriptions :column="1" size="small" border class="university-desc">
              <el-descriptions-item v-for="row in universityEvaluationRows" :key="row.label" :label="row.label">{{ row.value }}</el-descriptions-item>
            </el-descriptions>
          </template>
        </template>
      </div>
    </el-dialog>

    <!-- 高校编辑弹窗 -->
    <el-dialog v-model="universityDialogVisible" title="编辑高校" width="640px" align-center>
      <el-form :model="universityForm" label-width="120px">
        <el-form-item label="高校全称" required>
          <el-input v-model="universityForm.name" placeholder="全局唯一" />
        </el-form-item>
        <el-form-item label="别名">
          <el-input v-model="universityForm.aliasesText" type="textarea" :rows="2" placeholder="用顿号、逗号或空格分隔" />
        </el-form-item>
        <el-form-item label="标签">
          <el-checkbox-group v-model="universityForm.tags" class="university-tag-group">
            <el-checkbox v-for="t in TAG_OPTIONS" :key="t.value" :value="t.value">{{ t.label }}</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="官方网站">
          <el-input v-model="universityForm.official_website" />
        </el-form-item>
        <el-form-item label="学校类型">
          <el-select v-model="universityForm.category" clearable style="width: 200px">
            <el-option label="普通高校" value="ordinary" />
            <el-option label="成人高校" value="adult" />
          </el-select>
        </el-form-item>
        <el-form-item label="主管部门">
          <el-input v-model="universityForm.competent_department" />
        </el-form-item>
        <el-form-item label="所在省">
          <el-select v-model="universityForm.province" clearable filterable style="width: 200px">
            <el-option v-for="p in provinceOptions" :key="p" :label="p" :value="p" />
          </el-select>
        </el-form-item>
        <el-form-item label="所在市">
          <el-input v-model="universityForm.city" />
        </el-form-item>
        <el-form-item label="办学层次">
          <el-select v-model="universityForm.edu_level" clearable style="width: 200px">
            <el-option label="本科" value="本科" />
            <el-option label="专科" value="专科" />
          </el-select>
        </el-form-item>
        <el-form-item label="办学性质">
          <el-select v-model="universityForm.school_nature" clearable style="width: 200px">
            <el-option label="公办" value="公办" />
            <el-option label="民办" value="民办" />
          </el-select>
        </el-form-item>
        <el-form-item label="一级学科硕士点">
          <el-input-number v-model="universityForm.master_first" :min="0" />
        </el-form-item>
        <el-form-item label="一级学科博士点">
          <el-input-number v-model="universityForm.doctor_first" :min="0" />
        </el-form-item>
        <el-form-item label="校徽路径">
          <el-input v-model="universityForm.logo_url" placeholder="如 data/university_logos/{code}.jpg" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="universityForm.raw_remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="universityDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="universitySaving" @click="saveUniversity">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Bell, ChatDotRound, Cpu, Pointer, School, Setting, User } from '@element-plus/icons-vue'
import MessageList from '../components/MessageList.vue'
import MsgDotNav from '../components/MsgDotNav.vue'
import { useAuthStore } from '../stores/auth'
import { useChatStore } from '../stores/chat'
import {
  adminCreateAnnouncement,
  adminCreateConfig,
  adminCreateFeedbackReason,
  adminCreateModel,
  adminDeleteAnnouncement,
  adminDeleteConfig,
  adminDeleteFeedbackReason,
  adminDeleteModel,
  adminFeedbackContext,
  adminFeedbackStats,
  adminListAnnouncements,
  adminListConfigs,
  adminListFeedbackReasons,
  adminListFeedbacks,
  adminListModels,
  adminListUsers,
  adminUpdateAnnouncement,
  adminUpdateConfig,
  adminUpdateFeedbackReason,
  adminUpdateModel,
  adminUpdateUniversity,
  adminUpdateUser,
  adminToolCalls,
  adminGetUniversity,
  adminGetUniversitySummary,
  adminListUniversities,
} from '../api'

const router = useRouter()
const authStore = useAuthStore()
const chatStore = useChatStore()

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
const configViewMode = ref('quick')
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
  // 默认对话模型下拉需要模型列表，未加载时拉一次
  if (!models.value.length) loadModels()
  configDialogVisible.value = true
}

const chatModels = computed(() => models.value.filter(m => m.model_type === 'chat' && m.is_enabled))
const embeddingModels = computed(() => models.value.filter(m => m.model_type === 'embedding' && m.is_enabled))

// 模型类配置 key → 选项来源（对话 / 向量模型）
const MODEL_CONFIG_KEYS = {
  'llm.default_model': () => chatModels.value,
  'embedding.default_model': () => embeddingModels.value,
}
const isModelConfig = key => key in MODEL_CONFIG_KEYS
const modelOptionsFor = key => (MODEL_CONFIG_KEYS[key] || (() => []))()

// 密钥类配置库中为密文，快捷视图掩码展示，仅在输入新值时覆盖
const isSecretConfig = key => /api[_-]?key$/i.test(key)

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

/** 快捷视图内联保存：仅更新值，其余字段保持原样 */
async function quickSaveConfig(row, value) {
  // 密钥类配置输入为空视为未修改，避免误清空密文
  if (isSecretConfig(row.key) && !value) return
  try {
    await adminUpdateConfig(row.id, {
      value: value || null,
      value_type: row.value_type,
      group_name: row.group_name,
      label: row.label,
      description: row.description,
      is_public: row.is_public,
    })
    ElMessage.success('配置已保存')
    await loadConfigs()
  } catch (error) {
    handleApiError(error, '保存配置失败')
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

// ==== 反馈管理（点赞/拉踩） ====

const FEEDBACK_TYPE_LABELS = { like: '点赞', dislike: '拉踩', all: '通用' }
const FEEDBACK_PAGE_SIZE = 10

const feedbackStats = ref({ total_count: 0, like_count: 0, dislike_count: 0, user_count: 0, reason_stats: [] })
const feedbackSubTab = ref('records')
const feedbacks = ref([])
const feedbacksLoading = ref(false)
const feedbackPage = ref(1)
const feedbackFilter = reactive({ type: '', reason: '', status: 'active' })

const feedbackReasons = ref([])
const reasonsLoading = ref(false)
const reasonDialogVisible = ref(false)
const reasonSaving = ref(false)
const reasonForm = reactive({
  id: null, code: '', feedback_type: 'dislike', label: '', description: '', status: 'active', sort_order: 0,
})

const contextDialogVisible = ref(false)
const contextLoading = ref(false)
const feedbackContextData = ref(null)
const contextMessages = ref([])
const contextScrollRef = ref(null)

/** 被评价回复对应的用户提问：在上下文中向前找最近的一条 user 消息 */
const feedbackUserMessageId = computed(() => {
  const targetId = feedbackContextData.value?.feedback_message_id
  if (!targetId) return null
  const idx = contextMessages.value.findIndex(m => m.id === targetId)
  for (let i = idx < 0 ? contextMessages.value.length : idx; i >= 0; i--) {
    if (contextMessages.value[i].role === 'user') return contextMessages.value[i].id
  }
  return null
})

const pagedFeedbacks = computed(() => {
  const start = (feedbackPage.value - 1) * FEEDBACK_PAGE_SIZE
  return feedbacks.value.slice(start, start + FEEDBACK_PAGE_SIZE)
})

// 记录筛选联动：选了类型后原因下拉只显示适用该类型的原因
const filterReasonOptions = computed(() => {
  if (!feedbackFilter.type) return feedbackReasons.value
  return feedbackReasons.value.filter(r => r.feedback_type === feedbackFilter.type || r.feedback_type === 'all')
})

function reasonLabel(code) {
  const reason = feedbackReasons.value.find(r => r.code === code)
  return reason?.label || code
}

async function loadFeedbackStats() {
  try {
    feedbackStats.value = await adminFeedbackStats()
  } catch (error) {
    handleApiError(error, '加载反馈统计失败')
  }
}

async function loadFeedbacks() {
  feedbacksLoading.value = true
  try {
    const params = { status: feedbackFilter.status }
    if (feedbackFilter.type) params.feedback_type = feedbackFilter.type
    if (feedbackFilter.reason) params.reason_code = feedbackFilter.reason
    feedbacks.value = await adminListFeedbacks(params)
    const maxPage = Math.max(1, Math.ceil(feedbacks.value.length / FEEDBACK_PAGE_SIZE))
    if (feedbackPage.value > maxPage) feedbackPage.value = maxPage
  } catch (error) {
    handleApiError(error, '加载反馈记录失败')
  } finally {
    feedbacksLoading.value = false
  }
}

async function loadFeedbackReasons() {
  reasonsLoading.value = true
  try {
    feedbackReasons.value = await adminListFeedbackReasons()
  } catch (error) {
    handleApiError(error, '加载原因字典失败')
  } finally {
    reasonsLoading.value = false
  }
}

function loadFeedbackAll() {
  loadFeedbackStats()
  loadFeedbacks()
  loadFeedbackReasons()
}

async function openFeedbackContext(row) {
  contextDialogVisible.value = true
  contextLoading.value = true
  feedbackContextData.value = null
  contextMessages.value = []
  try {
    const data = await adminFeedbackContext(row.id)
    feedbackContextData.value = data
    // 复用聊天页同款转换逻辑，渲染效果与用户看到的完全一致
    contextMessages.value = chatStore.buildMessagesFromDetail(data.session)
    // 渲染完成后定位到该回复对应的用户提问（回复本身保持橙框高亮）
    await nextTick()
    scrollContextToMessage(feedbackUserMessageId.value || data.feedback_message_id)
  } catch (error) {
    handleApiError(error, '加载反馈上下文失败')
    contextDialogVisible.value = false
  } finally {
    contextLoading.value = false
  }
}

/** 在上下文弹窗内滚动到指定消息（圆点导航与自动定位共用） */
function scrollContextToMessage(msgId) {
  const message = contextScrollRef.value?.querySelector(`.message-item[data-key="${msgId}"]`)
  message?.scrollIntoView({ behavior: 'instant', block: 'center' })
}

/** 圆点导航滚动联动：返回上下文弹窗滚动容器（模板 ref） */
function getContextScrollEl() {
  return contextScrollRef.value
}

/** 只读模式的工具详情懒加载：走管理端接口（不做会话归属校验） */
async function loadContextToolDetail(messageId) {
  try {
    return await adminToolCalls(messageId)
  } catch (error) {
    console.error('懒加载工具详情失败:', error)
    return null
  }
}

function openReasonDialog(row = null) {
  Object.assign(reasonForm, {
    id: row?.id || null,
    code: row?.code || '',
    feedback_type: row?.feedback_type || 'dislike',
    label: row?.label || '',
    description: row?.description || '',
    status: row?.status || 'active',
    sort_order: row?.sort_order ?? 0,
  })
  reasonDialogVisible.value = true
}

async function saveReason() {
  if (!reasonForm.code.trim()) {
    ElMessage.warning('请填写原因编码')
    return
  }
  if (!reasonForm.label.trim()) {
    ElMessage.warning('请填写原因名称')
    return
  }
  reasonSaving.value = true
  try {
    const payload = {
      feedback_type: reasonForm.feedback_type,
      label: reasonForm.label.trim(),
      description: reasonForm.description || null,
      status: reasonForm.status,
      sort_order: reasonForm.sort_order,
    }
    if (reasonForm.id) {
      await adminUpdateFeedbackReason(reasonForm.id, payload)
    } else {
      await adminCreateFeedbackReason({ ...payload, code: reasonForm.code.trim() })
    }
    ElMessage.success('原因已保存')
    reasonDialogVisible.value = false
    await loadFeedbackReasons()
  } catch (error) {
    handleApiError(error, '保存原因失败')
  } finally {
    reasonSaving.value = false
  }
}

async function removeReason(row) {
  try {
    await ElMessageBox.confirm(`确定删除原因「${row.label || row.code}」？`, '删除确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await adminDeleteFeedbackReason(row.id)
    ElMessage.success('原因已删除')
    await loadFeedbackReasons()
  } catch (error) {
    handleApiError(error, '删除原因失败')
  }
}

// ==== 高校信息 ====

const CATEGORY_TEXT = { ordinary: '普通高校', adult: '成人高校' }

// tags 字段代码 → 展示名称，顺序即展示顺序（与聊天页高校面板一致）
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
const TAG_OPTIONS = TAG_TEXT_ORDER.map(code => ({ value: code, label: TAG_TEXT[code] }))

const RANKING_SOURCE_TEXT = { qs: 'QS', the: 'THE', usnews: 'U.S. News', ruanke: '软科', xyh: '校友会' }
const DOUBLE_FIRST_ROUND_YEAR = { 1: 2017, 2: 2022 }

const universities = ref([])
const universitiesLoading = ref(false)
const UNIVERSITY_PAGE_SIZE = 10
const universityPage = ref(1)
const universityTotal = ref(0)
const universityFilter = reactive({ keyword: '', province: '', tag: '', edu_level: '', category: '' })
const universitySummary = ref({ total: 0, edu_level_counts: {}, tag_counts: {}, provinces: [] })

const provinceOptions = computed(() => universitySummary.value.provinces || [])

/** 统计卡片：filter 描述点击后应用的筛选条件，null 表示点击清空全部筛选 */
const universityStats = computed(() => {
  const summary = universitySummary.value
  const tagCount = code => summary.tag_counts[code] || 0
  return [
    { label: '高校总数', value: summary.total, filter: null },
    { label: '本科', value: summary.edu_level_counts['本科'] || 0, filter: { key: 'edu_level', value: '本科' } },
    { label: '985工程', value: tagCount('985'), filter: { key: 'tag', value: '985' } },
    { label: '211工程', value: tagCount('211'), filter: { key: 'tag', value: '211' } },
    { label: '双一流', value: tagCount('double_first'), filter: { key: 'tag', value: 'double_first' } },
    { label: '保研资格', value: tagCount('baoyan'), filter: { key: 'tag', value: 'baoyan' } },
    { label: '双高计划', value: tagCount('double_high'), filter: { key: 'tag', value: 'double_high' } },
  ]
})

function isStatActive(stat) {
  return Boolean(stat.filter) && universityFilter[stat.filter.key] === stat.filter.value
}

/** 点击统计卡片切换筛选：再次点击当前卡片取消，点「高校总数」清空全部筛选 */
function toggleStatFilter(stat) {
  if (!stat.filter) {
    Object.assign(universityFilter, { keyword: '', province: '', tag: '', edu_level: '', category: '' })
    universityPage.value = 1
    return
  }
  const { key, value } = stat.filter
  const active = isStatActive(stat)
  universityFilter.tag = ''
  universityFilter.edu_level = ''
  universityFilter.category = ''
  if (!active) universityFilter[key] = value
  universityPage.value = 1
}

/** tags 代码列表 → 按固定顺序映射为展示名称 */
function sortedTagTexts(row) {
  return (row.tags || [])
    .slice()
    .sort((a, b) => {
      const ia = TAG_TEXT_ORDER.indexOf(a)
      const ib = TAG_TEXT_ORDER.indexOf(b)
      return (ia === -1 ? TAG_TEXT_ORDER.length : ia) - (ib === -1 ? TAG_TEXT_ORDER.length : ib)
    })
    .map(code => TAG_TEXT[code] || code)
}

function universityLogoSrc(name) {
  return `/v1/universities/logo?name=${encodeURIComponent(name)}`
}

async function loadUniversities() {
  universitiesLoading.value = true
  try {
    const data = await adminListUniversities({
      page: universityPage.value,
      page_size: UNIVERSITY_PAGE_SIZE,
      keyword: universityFilter.keyword.trim(),
      province: universityFilter.province,
      tag: universityFilter.tag,
      edu_level: universityFilter.edu_level,
      category: universityFilter.category,
    })
    universityTotal.value = data.total
    universities.value = data.items
    // 筛选后当前页越界时回退到最后一页再查一次
    const maxPage = Math.max(1, Math.ceil(data.total / UNIVERSITY_PAGE_SIZE))
    if (universityPage.value > maxPage) {
      universityPage.value = maxPage
      return loadUniversities()
    }
  } catch (error) {
    handleApiError(error, '加载高校列表失败')
  } finally {
    universitiesLoading.value = false
  }
}

async function loadUniversitySummary() {
  try {
    universitySummary.value = await adminGetUniversitySummary()
  } catch (error) {
    handleApiError(error, '加载高校统计失败')
  }
}

function loadUniversityTab() {
  loadUniversitySummary()
  loadUniversities()
}

// 筛选变化时回到第一页重新查询；翻页时查询当前页
watch(universityFilter, () => {
  if (universityPage.value === 1) {
    loadUniversities()
  } else {
    universityPage.value = 1
  }
})
watch(universityPage, () => {
  loadUniversities()
})

// ---- 高校详情 ----

const universityDetailVisible = ref(false)
const universityDetailLoading = ref(false)
const universityDetailData = ref(null)

const universityRankingRows = computed(() => {
  const info = universityDetailData.value
  if (!info) return []
  return (info.rankings || []).map(r => {
    const source = RANKING_SOURCE_TEXT[r.source] || r.source || '未知榜单'
    const rank = r.rank_raw || (r.rank_num != null ? String(r.rank_num) : '')
    const parts = []
    if (rank) parts.push(`第${rank}名`)
    if (r.score != null) parts.push(`${r.score}分`)
    return { label: `${source} ${r.year ?? ''}`.trim(), value: parts.join(' · ') || '-' }
  })
})

const universityDoubleFirstRows = computed(() => {
  const info = universityDetailData.value
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
  const info = universityDetailData.value
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

async function openUniversityDetail(row) {
  universityDetailVisible.value = true
  universityDetailLoading.value = true
  universityDetailData.value = null
  try {
    universityDetailData.value = await adminGetUniversity(row.id)
  } catch (error) {
    handleApiError(error, '加载高校详情失败')
    universityDetailVisible.value = false
  } finally {
    universityDetailLoading.value = false
  }
}

// ---- 高校编辑 ----

const universityDialogVisible = ref(false)
const universitySaving = ref(false)
const universityForm = reactive({
  id: null, name: '', aliasesText: '', official_website: '', category: '',
  competent_department: '', province: '', city: '', edu_level: '', school_nature: '',
  tags: [], master_first: null, doctor_first: null, logo_url: '', raw_remark: '',
})

function openUniversityDialog(row) {
  Object.assign(universityForm, {
    id: row?.id || null,
    name: row?.name || '',
    aliasesText: (row?.aliases || []).join('、'),
    official_website: row?.official_website || '',
    category: row?.category || '',
    competent_department: row?.competent_department || '',
    province: row?.province || '',
    city: row?.city || '',
    edu_level: row?.edu_level || '',
    school_nature: row?.school_nature || '',
    tags: [...(row?.tags || [])],
    master_first: row?.master_first ?? null,
    doctor_first: row?.doctor_first ?? null,
    logo_url: row?.logo_url || '',
    raw_remark: row?.raw_remark || '',
  })
  universityDialogVisible.value = true
}

async function saveUniversity() {
  if (!universityForm.name.trim()) {
    ElMessage.warning('请填写高校全称')
    return
  }
  universitySaving.value = true
  try {
    const aliases = universityForm.aliasesText.split(/[、,，;；\s]+/).map(s => s.trim()).filter(Boolean)
    const payload = {
      name: universityForm.name.trim(),
      aliases,
      official_website: universityForm.official_website || null,
      category: universityForm.category || null,
      competent_department: universityForm.competent_department || null,
      province: universityForm.province || null,
      city: universityForm.city || null,
      edu_level: universityForm.edu_level || null,
      school_nature: universityForm.school_nature || null,
      tags: universityForm.tags,
      master_first: universityForm.master_first,
      doctor_first: universityForm.doctor_first,
      logo_url: universityForm.logo_url || null,
      raw_remark: universityForm.raw_remark || null,
    }
    await adminUpdateUniversity(universityForm.id, payload)
    ElMessage.success('高校信息已保存')
    universityDialogVisible.value = false
    await loadUniversities()
  } catch (error) {
    handleApiError(error, '保存高校信息失败')
  } finally {
    universitySaving.value = false
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

// 各板块懒加载：首次切换到该板块时才请求数据，避免进入管理端一次性查询所有板块
const loadedTabs = new Set()
const TAB_LOADERS = {
  configs: loadConfigs,
  models: loadModels,
  users: loadUsers,
  universities: loadUniversityTab,
  announcements: loadAnnouncements,
  feedbacks: loadFeedbackAll,
}
watch(activeTab, tab => {
  if (!loadedTabs.has(tab)) {
    loadedTabs.add(tab)
    TAB_LOADERS[tab]?.()
  }
})

onMounted(() => {
  loadedTabs.add(activeTab.value)
  TAB_LOADERS[activeTab.value]?.()
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

/* 用户管理：表格区域预分配固定空间（占满内容区剩余高度），
   数据多时表体内部滚动、分页固定底部，不随内容撑开整页 */
.users-tab {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.users-tab .content-header {
  flex-shrink: 0;
}

.users-table-wrap {
  flex: 1;
  min-height: 0;
}

/* 用户管理：压缩内嵌控件与行距。
   el-switch 容器固定 32px（核心只有 20px）、el-select small 为 24px，
   都会把行高撑到 14×2+32=60px；压回 20px 并减小 cell 间距后约 40px */
.users-table :deep(.el-table__cell) {
  padding: 10px 0;
}

.users-table :deep(.el-switch) {
  height: 20px;
}

.users-table :deep(.el-select__wrapper) {
  min-height: 20px;
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

.config-quick-card {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #fff;
  overflow: hidden;
}

.config-quick-item {
  display: flex;
  align-items: flex-start;
  gap: 20px;
  padding: 12px 16px;
}

.config-quick-item + .config-quick-item {
  border-top: 1px solid #f2f4f7;
}

.config-quick-item:hover {
  background: #fafbfc;
}

.config-quick-label {
  flex-shrink: 0;
  width: 130px;
  padding-top: 4px;
  font-size: 13px;
  color: #303133;
  text-align: right;
}

.config-quick-control {
  flex: 1;
  min-width: 0;
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

/* ===== 高校信息 ===== */

/* 板块整体纵向布局：头部/统计/筛选固定，表格占满剩余高度、分页固定底部 */
.universities-tab {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.universities-tab .content-header {
  flex-shrink: 0;
}

/* 与用户管理一致：表格占满剩余高度、表体内滚动、分页固定底部 */
.universities-table-wrap {
  flex: 1;
  min-height: 0;
}

.university-logo {
  width: 36px;
  height: 36px;
}

.university-logo-lg {
  width: 56px;
  height: 56px;
}

.university-detail-head {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 14px;
}

.university-detail-name {
  margin: 0 0 6px;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.university-detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.university-desc {
  margin-bottom: 4px;
}

.university-section-title {
  margin: 14px 0 8px;
  font-size: 14px;
  color: #303133;
}

.university-link {
  color: #409eff;
  text-decoration: none;
  word-break: break-all;
}

.university-tag-group {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 2px 8px;
  width: 100%;
}

/* ===== 反馈管理 ===== */

.stat-cards {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.stat-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 18px;
  min-width: 110px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
}

.stat-card-clickable {
  cursor: pointer;
  transition: border-color 0.2s, background-color 0.2s;
}

.stat-card-clickable:hover {
  border-color: #409eff;
}

.stat-card-active {
  border-color: #409eff;
  background: #ecf5ff;
}

.stat-card-reasons {
  flex: 1;
  min-width: 240px;
}

.stat-label {
  font-size: 12px;
  color: #909399;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.stat-value-like {
  color: #67c23a;
}

.stat-value-dislike {
  color: #f56c6c;
}

.reason-dist {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  min-height: 24px;
  align-items: center;
}

.stat-empty {
  font-size: 12px;
  color: #909399;
}

.feedback-filters {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.reason-pane-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

/* 反馈记录「回答内容」：单行截断，不弹悬浮完整内容，保证行高与文本行一致 */
.content-table :deep(td.preview-ellipsis .cell) {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 上下文弹窗 */
.context-wrap {
  min-height: 120px;
}

.context-session {
  margin: 0 0 12px;
  font-size: 13px;
  color: #606266;
}

.context-body {
  position: relative;
}

.context-messages {
  max-height: 62vh;
  overflow-y: auto;
  padding: 4px 8px;
}
</style>
