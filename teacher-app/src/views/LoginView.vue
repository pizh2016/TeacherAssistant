<template>
  <div class="login-page">
    <div class="login-card">
      <h1 class="title">喊话小喇叭</h1>
      <p class="subtitle">教师端</p>

      <form @submit.prevent="handleLogin" class="login-form">
        <label class="field-label" for="teacher-name">您的姓名</label>
        <input
          id="teacher-name"
          v-model="teacherName"
          type="text"
          maxlength="20"
          placeholder="输入姓名即可使用"
          autocomplete="name"
          :disabled="loading"
          @input="errorMsg = ''"
        />

        <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>

        <button type="submit" class="btn-primary" :disabled="!canSubmit || loading">
          {{ loading ? "登录中..." : "进 入" }}
        </button>
      </form>

      <p class="hint">首次使用会自动注册，无需配对码</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { useRouter } from "vue-router";
import { teacherLogin, setToken } from "@/api";
import type { ApiError } from "@/types/api";

const router = useRouter();

const teacherName = ref("");
const loading = ref(false);
const errorMsg = ref("");

const canSubmit = computed(() => teacherName.value.trim().length >= 1);

async function handleLogin() {
  if (!canSubmit.value || loading.value) return;
  loading.value = true;
  errorMsg.value = "";

  try {
    const res = await teacherLogin(teacherName.value.trim());
    setToken(res.token);
    localStorage.setItem("horn_classes", JSON.stringify(res.classes));
    localStorage.setItem("horn_teacher_id", String(res.teacher_id));
    // Use the actual name from backend (may have suffix added for dedup)
    localStorage.setItem("horn_teacher_name", res.teacher_name || teacherName.value.trim());

    if (res.classes.length === 0) {
      // 没有班级，引导创建
      router.push({ name: "Classes" });
    } else {
      router.push({ name: "Home" });
    }
  } catch (err) {
    const apiErr = err as ApiError;
    if (apiErr?.error?.message) {
      errorMsg.value = apiErr.error.message;
    } else {
      errorMsg.value = "网络错误，请检查后端是否启动";
    }
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 16px;
}

.login-card {
  background: #fff;
  border-radius: 16px;
  padding: 40px 32px;
  width: 100%;
  max-width: 360px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
  text-align: center;
}

.title {
  font-size: 1.75rem;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0 0 4px;
}

.subtitle {
  font-size: 0.9rem;
  color: #888;
  margin: 0 0 32px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.field-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: #555;
  text-align: left;
}

input {
  width: 100%;
  padding: 14px 16px;
  font-size: 1.2rem;
  text-align: center;
  border: 2px solid #e0e0e0;
  border-radius: 10px;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

input:focus {
  border-color: #667eea;
}

input:disabled {
  background: #f5f5f5;
}

.error-msg {
  color: #e74c3c;
  font-size: 0.85rem;
  margin: 0;
  text-align: left;
}

.btn-primary {
  margin-top: 8px;
  padding: 14px;
  font-size: 1rem;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 10px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary:not(:disabled):hover {
  opacity: 0.9;
}

.hint {
  margin-top: 24px;
  font-size: 0.78rem;
  color: #aaa;
}
</style>
