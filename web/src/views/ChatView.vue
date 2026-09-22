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
        @open-search="openSearchPanel"
        @open-settings="settingsVisible = true"
        @open-inbox="openInbox"
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
        </div>
      </div>
      <div class="university-panel-body">
        <div class="university-detail-pane">
          <template v-if="universityDetail">
            <h3 class="university-detail-title">{{ universityDetail.name }}</h3>
            <a
              v-if="universityDetail.official_website"
              class="university-detail-website"
              :href="universityDetail.official_website"
              target="_blank"
              rel="noopener noreferrer"
            >{{ universityDetail.official_website }}</a>
            <div class="university-info-list">
              <div v-for="row in universityInfoRows" :key="row.label" class="university-info-row">
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

    <el-dialog v-model="settingsVisible" class="settings-dialog" title="设置" width="600px" align-center>
      <div class="settings-list">
        <button class="settings-item" type="button">
          <span>
            <strong>个人信息</strong>
            <small>修改头像、昵称和个人资料</small>
          </span>
          <span class="settings-arrow">›</span>
        </button>
        <button class="settings-item" type="button">
          <span>
            <strong>主题</strong>
            <small>切换浅色、深色或跟随系统</small>
          </span>
          <span class="settings-arrow">›</span>
        </button>
        <button class="settings-item settings-item-danger" type="button" @click="handleSettingsLogout">
          <span>
            <strong>退出登录</strong>
            <small>退出当前账号并返回登录页</small>
          </span>
          <span class="settings-arrow">›</span>
        </button>
      </div>
    </el-dialog>

    <el-dialog v-model="inboxVisible" class="inbox-dialog" title="通知" width="600px" align-center @closed="selectedMail = null">
      <button v-if="!selectedMail" class="mail-item" type="button" @click="selectedMail = demoMail">
        <span class="mail-unread-dot"></span>
        <span class="mail-summary">
          <strong>{{ demoMail.title }}</strong>
          <small>{{ demoMail.preview }}</small>
        </span>
        <time>{{ demoMail.time }}</time>
      </button>
      <article v-else class="mail-detail">
        <button class="mail-back" type="button" @click="selectedMail = null">‹ 返回</button>
        <h3>{{ selectedMail.title }}</h3>
        <div class="mail-meta">来自：{{ selectedMail.sender }} · {{ selectedMail.time }}</div>
        <p>{{ selectedMail.content }}</p>
      </article>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import SessionList from '../components/SessionList.vue'
import ChatArea from '../components/ChatArea.vue'
import { useChatStore } from '../stores/chat'
import { useAuthStore } from '../stores/auth'
import { getUniversity } from '../api'

const router = useRouter()
const chatStore = useChatStore()
const authStore = useAuthStore()
const searchVisible = ref(false)
const searchKeyword = ref('')
const searchInputRef = ref(null)
const settingsVisible = ref(false)
const inboxVisible = ref(false)
const selectedMail = ref(null)
const demoMail = {
  title: '我发送的更新详情',
  preview: '查看本次个人信息与偏好设置的更新内容',
  sender: '小忆',
  time: '刚刚',
  content: '你的更新请求已经记录。这里将展示个人信息、主题偏好等设置的更新详情。',
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

const universityInfoRows = computed(() => {
  const info = universityDetail.value
  if (!info) return []
  return [
    { label: '学校标识码', value: info.code },
    { label: '别名', value: (info.aliases || []).join('、') },
    { label: '学校类型', value: CATEGORY_TEXT[info.category] || info.category },
    { label: '主管部门', value: info.competent_department },
    { label: '所在地', value: [info.province, info.city].filter(Boolean).join(' ') },
    { label: '办学层次', value: info.edu_level },
    { label: '办学性质', value: info.school_nature },
    { label: '备注', value: info.raw_remark },
  ].filter(row => row.value)
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
  selectedMail.value = null
  inboxVisible.value = true
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
  await Promise.all([
    chatStore.loadSessions(),
    chatStore.loadModels(),
    chatStore.loadTools()
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

.university-detail-title {
  margin: 2px 0 6px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  word-break: break-all;
}

.university-detail-website {
  display: inline-block;
  margin-bottom: 10px;
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
  width: 76px;
  color: #909399;
}

.university-info-value {
  flex: 1;
  min-width: 0;
  color: #303133;
  word-break: break-all;
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

.settings-item-danger small,
.settings-item-danger .settings-arrow {
  color: #f56c6c;
}

.settings-item > span:first-child {
  display: grid;
  gap: 6px;
}

.settings-item strong,
.mail-summary strong {
  font-size: 14px;
  font-weight: 600;
}

.settings-item small,
.mail-summary small {
  color: #909399;
  font-size: 12px;
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

.mail-summary {
  display: grid;
  gap: 6px;
  min-width: 0;
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

@media (max-width: 640px) {
  :deep(.el-dialog) {
    width: calc(100% - 32px) !important;
  }
}

</style>
