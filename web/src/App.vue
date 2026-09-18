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
      <SessionList />
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
        <span class="university-panel-title">高校</span>
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
            <div class="university-detail-path">{{ selectedNodeDetail.path.join(' / ') }}</div>
          </template>
          <div v-else class="university-detail-empty">请点击右侧节点查看详情</div>
        </div>
        <div
          class="inner-resize-handle"
          :class="{ dragging: resizingInner }"
          title="拖动调整详情与高校的宽度比例"
          @pointerdown.stop.prevent="startInnerResize($event)"
        ></div>
        <div class="university-tree-pane" :style="{ width: treePaneWidth + 'px' }">
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
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import SessionList from './components/SessionList.vue'
import ChatArea from './components/ChatArea.vue'
import { useChatStore } from './stores/chat'
import { getUniversity } from './api'

const chatStore = useChatStore()
const sidebarCollapsed = ref(false)
const sidebarPreview = ref(false)
const edgeHovered = ref(false)
const sidebarHovered = ref(false)
let hideTimer = null
let previewBlockedUntil = 0
const universityPanelCollapsed = ref(true)
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
const lastClickedNodeKey = ref(null)
let universityDetailSeq = 0

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
  universityDetail.value = null
  if (!name) return
  try {
    const data = await getUniversity(name)
    if (seq === universityDetailSeq) universityDetail.value = data
  } catch (err) {
    console.error('加载高校信息失败:', err)
  }
}

function onUniversityNodeClick(nodeData, node) {
  // 第一次点击只选中，第二次点击同一节点才展开/收起（点击展开箭头由 el-tree 自行处理）
  if (lastClickedNodeKey.value === nodeData.id && !node.isLeaf) {
    if (node.expanded) node.collapse()
    else node.expand()
  }
  lastClickedNodeKey.value = nodeData.id

  if (nodeData.isUniversity) {
    // 高校根节点：统一交给 watch 处理（展开面板 + 选中节点 + 加载真实信息）
    chatStore.selectedUniversity = nodeData.label
    chatStore.universitySelectSeq++
    return
  }
  const path = []
  let cur = node
  while (cur && cur.level > 0) {
    path.unshift(cur.label)
    cur = cur.parent
  }
  selectedNodeDetail.value = { label: nodeData.label, path }
  loadUniversityDetail(null)
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

function clampTreePaneWidth(panelWidth) {
  const maxTree = maxTreePaneWidth(panelWidth - SIDEBAR_EDGE_WIDTH)
  treePaneWidth.value = Math.min(treePaneWidth.value, Math.max(MIN_INNER_PANE_WIDTH, maxTree))
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
  return side === 'left' ? MIN_PANEL_WIDTH : MIN_UNIVERSITY_PANEL_WIDTH
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
  else {
    universityPanelWidth.value = nextWidth
    clampTreePaneWidth(nextWidth)
  }
}

function stopResize() {
  resizingSide.value = null
  window.removeEventListener('pointermove', handleResize)
}

function resetPanelWidth(side) {
  const defaultWidth = side === 'left' ? DEFAULT_PANEL_WIDTH : DEFAULT_UNIVERSITY_PANEL_WIDTH
  const width = Math.min(defaultWidth, maxPanelWidth(side))
  if (side === 'left') sidebarWidth.value = width
  else {
    universityPanelWidth.value = width
    clampTreePaneWidth(width)
  }
}

onMounted(async () => {
  await Promise.all([
    chatStore.loadSessions(),
    chatStore.loadModels(),
    chatStore.loadTools()
  ])
  const savedSessionId = localStorage.getItem('currentSessionId')
  if (savedSessionId) {
    chatStore.selectSession(savedSessionId)
  }
})

onBeforeUnmount(() => {
  clearHideTimer()
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

.university-detail-path {
  font-size: 12px;
  color: #909399;
  line-height: 1.6;
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

.university-tree-pane {
  flex: 0 0 auto;
  min-width: 120px;
  display: flex;
  flex-direction: column;
}

.university-panel-header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 43px;
  padding: 7px 10px 7px 12px;
  border-bottom: 1px solid #e4e7ed;
}

.university-panel-title {
  flex-shrink: 0;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.university-panel-actions {
  display: flex;
  gap: 5px;
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

</style>
