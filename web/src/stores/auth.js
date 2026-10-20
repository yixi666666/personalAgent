import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getCurrentUser,
  guestLogin as requestGuestLogin,
  loginUser,
  logoutUser,
  registerUser,
  upgradeAccount,
} from '../api'

export const useAuthStore = defineStore('auth', () => {
  const currentUser = ref(null)
  const initialized = ref(false)
  const initializing = ref(null)
  // 内存态标记：本次会话是否刚以游客身份登录，用于触发一次性引导弹窗（刷新页面即丢失）
  const justGuestLoggedIn = ref(false)

  const isAuthenticated = computed(() => Boolean(currentUser.value))
  const isGuest = computed(() => currentUser.value?.role === 'guest')

  async function initialize() {
    if (initialized.value) return currentUser.value
    if (initializing.value) return initializing.value

    initializing.value = getCurrentUser()
      .then(user => {
        currentUser.value = user
        return user
      })
      .catch(error => {
        if (error.response?.status !== 401) throw error
        currentUser.value = null
        return null
      })
      .finally(() => {
        initialized.value = true
        initializing.value = null
      })
    return initializing.value
  }

  async function register(payload) {
    currentUser.value = await registerUser(payload)
    initialized.value = true
    return currentUser.value
  }

  async function login(payload) {
    currentUser.value = await loginUser(payload)
    initialized.value = true
    return currentUser.value
  }

  async function logout() {
    try {
      await logoutUser()
    } finally {
      currentUser.value = null
      initialized.value = true
      justGuestLoggedIn.value = false
    }
  }

  async function guestLogin() {
    currentUser.value = await requestGuestLogin()
    initialized.value = true
    justGuestLoggedIn.value = true
    return currentUser.value
  }

  async function upgrade(payload) {
    currentUser.value = await upgradeAccount(payload)
    justGuestLoggedIn.value = false
    return currentUser.value
  }

  // 读取并清除「刚以游客登录」标记，保证引导弹窗每次游客登录只弹一次
  function consumeGuestLoginFlag() {
    const flag = justGuestLoggedIn.value
    justGuestLoggedIn.value = false
    return flag
  }

  function clearCurrentUser() {
    currentUser.value = null
    initialized.value = true
  }

  return {
    currentUser,
    initialized,
    isAuthenticated,
    isGuest,
    justGuestLoggedIn,
    initialize,
    register,
    login,
    guestLogin,
    upgrade,
    consumeGuestLoginFlag,
    logout,
    clearCurrentUser,
  }
})
