import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getCurrentUser, loginUser, logoutUser, registerUser } from '../api'

export const useAuthStore = defineStore('auth', () => {
  const currentUser = ref(null)
  const initialized = ref(false)
  const initializing = ref(null)

  const isAuthenticated = computed(() => Boolean(currentUser.value))

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
    }
  }

  function clearCurrentUser() {
    currentUser.value = null
    initialized.value = true
  }

  return {
    currentUser,
    initialized,
    isAuthenticated,
    initialize,
    register,
    login,
    logout,
    clearCurrentUser,
  }
})
