<template>
  <main class="auth-page">
    <el-card class="auth-card" shadow="always">
      <div class="auth-heading">
        <h1>登录高校问答系统</h1>
      </div>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="submit">
        <el-form-item label="账号" prop="username">
          <el-input v-model="form.username" autocomplete="username" placeholder="请输入账号" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" autocomplete="current-password" show-password placeholder="请输入密码" @keyup.enter="submit" />
        </el-form-item>
        <el-button class="auth-submit" type="primary" native-type="submit" :loading="submitting">登录</el-button>
      </el-form>
      <p class="auth-switch">还没有账号？<RouterLink to="/register">立即注册</RouterLink></p>
    </el-card>
  </main>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const formRef = ref(null)
const submitting = ref(false)
const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function submit() {
  if (submitting.value) return
  try {
    await formRef.value.validate()
    submitting.value = true
    await authStore.login(form)
    await router.replace('/chat')
  } catch (error) {
    if (error?.response) ElMessage.error(error.response.data?.detail || '登录失败，请检查账号和密码')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped src="../styles/auth.css"></style>
