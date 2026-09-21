import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import { useChatStore } from './stores/chat'
import './style.css'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(router)
app.use(ElementPlus, { locale: zhCn })

window.addEventListener('auth:unauthorized', () => {
  const authStore = useAuthStore(pinia)
  const chatStore = useChatStore(pinia)
  authStore.clearCurrentUser()
  chatStore.clearUserData()
  if (router.currentRoute.value.name !== 'login') router.replace('/login')
})
app.mount('#app')
