<template>
  <main class="auth-page">
    <el-card class="auth-card register-card" shadow="always">
      <div class="auth-heading">
        <h1>注册高校问答系统账号</h1>
      </div>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="submit">
        <el-form-item label="账号" prop="username">
          <el-input v-model="form.username" autocomplete="username" placeholder="请输入账号" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" autocomplete="new-password" show-password placeholder="请输入密码" />
        </el-form-item>
        <el-form-item label="昵称（可选）" prop="display_name">
          <el-input v-model="form.display_name" placeholder="请输入昵称" />
        </el-form-item>
        <el-form-item label="邮箱（可选）" prop="email">
          <el-input v-model="form.email" type="email" autocomplete="email" placeholder="请输入邮箱" @keyup.enter="submit" />
        </el-form-item>
        <el-button class="auth-submit" type="primary" native-type="submit" :loading="submitting">注册并登录</el-button>
      </el-form>
      <p class="auth-switch">已有账号？<RouterLink to="/login">返回登录</RouterLink></p>
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
const form = reactive({ username: '', password: '', display_name: '', email: '' })
const rules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function submit() {
  if (submitting.value) return
  try {
    await formRef.value.validate()
    submitting.value = true
    const payload = { username: form.username, password: form.password }
    for (const key of ['display_name', 'email']) {
      const value = form[key].trim()
      if (value) payload[key] = value
    }
    await authStore.register(payload)
    await router.replace('/chat')
  } catch (error) {
    if (error?.response) ElMessage.error(error.response.data?.detail || '注册失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped src="../styles/auth.css"></style>
