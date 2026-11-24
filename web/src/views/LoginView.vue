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
          <el-input
            v-model="form.password"
            type="password"
            autocomplete="off"
            :show-password="passwordManuallyEntered"
            placeholder="请输入密码"
            @input="passwordManuallyEntered = true"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-button class="auth-submit" type="primary" native-type="submit" :loading="submitting">登录</el-button>
      </el-form>
      <div class="auth-forgot"><a href="#" @click.prevent="openForgot">忘记密码？</a></div>
      <div class="auth-divider">免注册体验</div>
      <el-button class="auth-guest" :loading="guestLoading" @click="guestEnter">游客登录</el-button>
      <p class="auth-switch">还没有账号？<RouterLink to="/register">立即注册</RouterLink></p>
    </el-card>

    <el-dialog v-model="forgotVisible" title="忘记密码" width="400px" align-center @closed="forgotFormRef?.resetFields()">
      <el-form ref="forgotFormRef" :model="forgotForm" :rules="forgotRules" label-position="top" @submit.prevent="submitForgot">
        <el-form-item label="账号" prop="username">
          <el-input v-model="forgotForm.username" autocomplete="username" placeholder="请输入账号" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="forgotForm.email" type="email" autocomplete="email" placeholder="请输入注册时绑定的邮箱" />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input
            v-model="forgotForm.new_password"
            type="password"
            autocomplete="new-password"
            show-password
            placeholder="请输入新密码"
            @keyup.enter="submitForgot"
          />
        </el-form-item>
      </el-form>
      <p class="forgot-tip">账号与邮箱匹配后将直接设置新密码并登录。</p>
      <template #footer>
        <el-button @click="forgotVisible = false">取消</el-button>
        <el-button type="primary" :loading="forgotSubmitting" @click="submitForgot">重置并登录</el-button>
      </template>
    </el-dialog>
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
const guestLoading = ref(false)
const passwordManuallyEntered = ref(false)
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
    form.password = ''
    passwordManuallyEntered.value = false
    await router.replace('/chat')
  } catch (error) {
    if (error?.response) ElMessage.error(error.response.data?.detail || '登录失败，请检查账号和密码')
  } finally {
    submitting.value = false
  }
}

// 游客登录：后端自动生成临时账号，无需任何输入直接进入聊天页
async function guestEnter() {
  if (guestLoading.value) return
  guestLoading.value = true
  try {
    await authStore.guestLogin()
    await router.replace('/chat')
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '游客登录失败，请稍后重试')
  } finally {
    guestLoading.value = false
  }
}

// 忘记密码：账号+邮箱匹配后直接设置新密码并登录
const forgotVisible = ref(false)
const forgotFormRef = ref(null)
const forgotSubmitting = ref(false)
const forgotForm = reactive({ username: '', email: '', new_password: '' })
const forgotRules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  new_password: [{ required: true, message: '请输入新密码', trigger: 'blur' }],
}

function openForgot() {
  forgotForm.username = form.username
  forgotForm.email = ''
  forgotForm.new_password = ''
  forgotVisible.value = true
}

async function submitForgot() {
  if (forgotSubmitting.value) return
  try {
    await forgotFormRef.value.validate()
    forgotSubmitting.value = true
    await authStore.resetPassword({
      username: forgotForm.username.trim(),
      email: forgotForm.email.trim(),
      new_password: forgotForm.new_password,
    })
    forgotVisible.value = false
    form.password = ''
    passwordManuallyEntered.value = false
    await router.replace('/chat')
  } catch (error) {
    if (error?.response) ElMessage.error(error.response.data?.detail || '重置失败，请检查账号和邮箱')
  } finally {
    forgotSubmitting.value = false
  }
}
</script>

<style scoped src="../styles/auth.css"></style>
