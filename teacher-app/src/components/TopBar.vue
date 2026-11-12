<template>
  <header class="top-bar">
    <!-- 左侧：头像 + 教师姓名 -->
    <div class="top-left">
      <div class="avatar" :style="avatarStyle">{{ avatarChar }}</div>
      <span v-if="teacherName" class="teacher-name">{{ teacherName }}</span>
    </div>

    <!-- 中间：页面标题 -->
    <h1 class="page-title">{{ title }}</h1>

    <!-- 右侧：操作按钮 -->
    <div class="top-right">
      <slot name="right">
        <router-link v-if="backTo" :to="backTo" class="btn-back">← 返回</router-link>
        <button v-else-if="showLogout" class="btn-logout" @click="$emit('logout')">退出</button>
      </slot>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useTeacherName } from "@/composables/useTeacherName";

defineProps<{
  title: string;
  /** Route path for back button, e.g. "/" */
  backTo?: string;
  /** Show logout button (only for Home page) */
  showLogout?: boolean;
}>();

defineEmits<{
  (e: "logout"): void;
}>();

const { teacherName } = useTeacherName();

// Generate avatar from first character of teacher name
const avatarChar = computed(() => {
  const name = teacherName.value || "?";
  return name.charAt(0);
});

// Deterministic color from teacher name
const avatarStyle = computed(() => {
  const colors = [
    "#667eea", "#764ba2", "#f093fb", "#4facfe",
    "#43e97b", "#fa709a", "#fee140", "#a18cd1",
    "#fbc2eb", "#ff9a9e", "#fad0c4", "#a1c4fd",
  ];
  const name = teacherName.value || "default";
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  const color = colors[Math.abs(hash) % colors.length];
  return { background: color };
});
</script>

<style scoped>
.top-bar {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  background: #fff;
  border-bottom: 1px solid #eee;
  min-height: 52px;
  gap: 8px;
}

/* 左侧：头像 + 姓名 */
.top-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  min-width: 0;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 0.85rem;
  font-weight: 700;
  flex-shrink: 0;
}

.teacher-name {
  font-size: 0.82rem;
  color: #555;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 80px;
}

/* 中间：标题 */
.page-title {
  flex: 1;
  text-align: center;
  font-size: 1.05rem;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 右侧：按钮 */
.top-right {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.btn-back {
  color: #667eea;
  text-decoration: none;
  font-size: 0.85rem;
  font-weight: 500;
  white-space: nowrap;
}

.btn-back:hover {
  opacity: 0.8;
}

.btn-logout {
  background: none;
  border: none;
  color: #e74c3c;
  font-size: 0.85rem;
  cursor: pointer;
  font-weight: 500;
  white-space: nowrap;
}

.btn-logout:hover {
  opacity: 0.8;
}
</style>
