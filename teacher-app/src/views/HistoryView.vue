<template>
  <div class="history-page">
    <!-- 顶部 -->
    <TopBar title="发送历史" back-to="/">
      <template #right>
        <router-link to="/" class="btn-back">← 返回</router-link>
        <select v-model="filterClassId" class="filter-select" @change="loadHistory">
          <option :value="undefined">全部班级</option>
          <option v-for="cls in classes" :key="cls.id" :value="cls.id">
            {{ cls.name }}
          </option>
        </select>
      </template>
    </TopBar>

    <!-- 列表 -->
    <div class="list" v-if="items.length > 0">
      <div v-for="msg in items" :key="msg.id" class="msg-card">
        <div class="msg-header">
          <span class="msg-class">{{ classNameOf(msg.class_id) }}</span>
          <span class="msg-time">{{ formatTime(msg.sent_at) }}</span>
        </div>
        <p class="msg-content">{{ msg.content }}</p>
        <div class="msg-footer">
          <span class="msg-tag">{{ msg.display_mode === "popup" ? "弹窗" : "跑马灯" }}</span>
          <span class="msg-tag" v-if="msg.reminder_level === 'strong'">强提醒</span>
          <span class="msg-tag" v-if="msg.tts_enabled">🔊 TTS</span>
          <span class="msg-tag">{{ msg.duration }}s</span>
          <span class="msg-tag msg-tag-image" v-if="msg.image_path">📷 图片</span>
          <div class="msg-actions">
            <button v-if="canRecall(msg)" class="btn-action btn-recall" @click="handleRecall(msg)">撤回</button>
            <button class="btn-action btn-edit" @click="handleEdit(msg)">编辑</button>
            <button class="btn-action btn-resend" @click="handleResend(msg)">重发</button>
            <button class="btn-action btn-delete" @click="handleDelete(msg)">删除</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!loading" class="empty">
      <p>暂无发送记录</p>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading">加载中...</div>

    <!-- 加载更多 -->
    <div v-if="hasMore && !loading" class="load-more">
      <button class="btn-load-more" @click="loadMore">加载更多</button>
    </div>

    <!-- 重发反馈 -->
    <div v-if="resendFeedback" class="feedback" :class="resendFeedback.type">
      {{ resendFeedback.message }}
    </div>

    <!-- 底部导航 -->
    <nav class="bottom-nav">
      <router-link to="/" class="nav-item">
        <span class="nav-icon">✏️</span>
        <span>发送</span>
      </router-link>
      <router-link to="/history" class="nav-item active">
        <span class="nav-icon">📋</span>
        <span>历史</span>
      </router-link>
      <router-link to="/classes" class="nav-item">
        <span class="nav-icon">🏫</span>
        <span>班级</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { getHistory, getClasses, sendMessage, deleteMessage, recallMessage } from "@/api";
import type { ClassInfo, MessageOut } from "@/types/api";
import { useRouter } from "vue-router";
import TopBar from "@/components/TopBar.vue";

const router = useRouter();

const classes = ref<ClassInfo[]>([]);
const items = ref<MessageOut[]>([]);
const filterClassId = ref<number | undefined>(undefined);
const page = ref(1);
const total = ref(0);
const loading = ref(false);
const resendFeedback = ref<{ type: "success" | "error"; message: string } | null>(null);

const LIMIT = 20;

const hasMore = computed(() => items.value.length < total.value);

// Check if a message can be recalled (within 60 seconds of sending)
function canRecall(msg: MessageOut): boolean {
  const sentTime = new Date(msg.sent_at).getTime();
  const elapsed = Date.now() - sentTime;
  return elapsed <= 60000;
}

// Auto-refresh recall buttons every 5 seconds
const recallTick = ref(0);
setInterval(() => {
  recallTick.value++;
}, 5000);

function classNameOf(classId: number): string {
  const cls = classes.value.find((c) => c.id === classId);
  return cls?.name ?? `班级#${classId}`;
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    const month = d.getMonth() + 1;
    const day = d.getDate();
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    return `${month}/${day} ${hh}:${mm}`;
  } catch {
    return iso;
  }
}

async function loadHistory() {
  loading.value = true;
  page.value = 1;
  try {
    const res = await getHistory(1, LIMIT, filterClassId.value);
    items.value = res.items;
    total.value = res.total;
  } catch {
    items.value = [];
  } finally {
    loading.value = false;
  }
}

async function loadMore() {
  loading.value = true;
  page.value++;
  try {
    const res = await getHistory(page.value, LIMIT, filterClassId.value);
    items.value.push(...res.items);
    total.value = res.total;
  } catch {
    page.value--;
  } finally {
    loading.value = false;
  }
}

async function handleResend(msg: MessageOut) {
  resendFeedback.value = null;
  try {
    await sendMessage({
      class_id: msg.class_id,
      content: msg.content,
      display_mode: msg.display_mode,
      reminder_level: msg.reminder_level,
      duration: msg.duration,
      tts_enabled: msg.tts_enabled,
      image_path: msg.image_path,
    });
    resendFeedback.value = { type: "success", message: "重发成功！" };
  } catch {
    resendFeedback.value = { type: "error", message: "重发失败" };
  }
  setTimeout(() => { resendFeedback.value = null; }, 3000);
}

function handleEdit(msg: MessageOut) {
  // Store message data for pre-filling on HomeView
  localStorage.setItem("horn_edit_message", JSON.stringify({
    content: msg.content,
    class_id: msg.class_id,
    display_mode: msg.display_mode,
    reminder_level: msg.reminder_level,
    duration: msg.duration,
    tts_enabled: msg.tts_enabled,
    image_path: msg.image_path,
  }));
  router.push("/");
}

async function handleRecall(msg: MessageOut) {
  resendFeedback.value = null;
  try {
    await recallMessage(msg.id);
    // Remove from local list
    items.value = items.value.filter(item => item.id !== msg.id);
    total.value = Math.max(0, total.value - 1);
    resendFeedback.value = { type: "success", message: "撤回成功" };
  } catch (e: any) {
    const errMsg = e?.error?.message || "撤回失败";
    resendFeedback.value = { type: "error", message: errMsg };
  }
  setTimeout(() => { resendFeedback.value = null; }, 3000);
}

async function handleDelete(msg: MessageOut) {
  if (!confirm(`确定要删除这条消息吗？\n\n「${msg.content}」`)) return;
  try {
    await deleteMessage(msg.id);
    // Remove from local list
    items.value = items.value.filter(item => item.id !== msg.id);
    total.value = Math.max(0, total.value - 1);
    resendFeedback.value = { type: "success", message: "删除成功" };
  } catch (e: any) {
    const errMsg = e?.error?.message || "删除失败";
    resendFeedback.value = { type: "error", message: errMsg };
  }
  setTimeout(() => { resendFeedback.value = null; }, 3000);
}

onMounted(async () => {
  // Refresh classes from API to keep filter dropdown in sync
  try {
    classes.value = await getClasses();
    localStorage.setItem("horn_classes", JSON.stringify(classes.value));
  } catch {
    const stored = localStorage.getItem("horn_classes");
    if (stored) classes.value = JSON.parse(stored);
  }
  loadHistory();
});
</script>

<style scoped>
.history-page {
  min-height: 100vh;
  background: #f5f7fa;
  padding-bottom: 72px;
}

.btn-back {
  color: #667eea;
  text-decoration: none;
  font-size: 0.85rem;
  font-weight: 500;
  white-space: nowrap;
  margin-right: 4px;
}

.filter-select {
  padding: 6px 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 0.82rem;
  background: #fff;
  margin-left: 8px;
}

.list {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.msg-card {
  background: #fff;
  border-radius: 10px;
  padding: 14px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.msg-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.msg-class {
  font-size: 0.8rem;
  font-weight: 600;
  color: #667eea;
}

.msg-time {
  font-size: 0.75rem;
  color: #aaa;
}

.msg-content {
  font-size: 0.95rem;
  color: #333;
  margin: 0 0 10px;
  line-height: 1.5;
  word-break: break-word;
}

.msg-footer {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.msg-actions {
  margin-left: auto;
  display: flex;
  gap: 6px;
}

.msg-tag {
  font-size: 0.72rem;
  padding: 2px 8px;
  background: #f0f2ff;
  color: #667eea;
  border-radius: 10px;
}

.msg-tag-image {
  background: #f0fdf4;
  color: #16a34a;
}

.btn-action {
  padding: 4px 12px;
  font-size: 0.78rem;
  border: 1px solid #667eea;
  color: #667eea;
  background: #fff;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-action:hover {
  background: #667eea;
  color: #fff;
}

.btn-edit {
  border-color: #f59e0b;
  color: #f59e0b;
}

.btn-edit:hover {
  background: #f59e0b;
  color: #fff;
}

.btn-recall {
  border-color: #f97316;
  color: #f97316;
  animation: pulse-recall 1.5s ease-in-out infinite;
}

.btn-recall:hover {
  background: #f97316;
  color: #fff;
}

@keyframes pulse-recall {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.btn-delete {
  border-color: #ef4444;
  color: #ef4444;
}

.btn-delete:hover {
  background: #ef4444;
  color: #fff;
}

.empty, .loading {
  text-align: center;
  padding: 48px 16px;
  color: #aaa;
  font-size: 0.9rem;
}

.load-more {
  text-align: center;
  padding: 16px;
}

.btn-load-more {
  padding: 10px 24px;
  border: 1px solid #ddd;
  background: #fff;
  border-radius: 8px;
  font-size: 0.85rem;
  cursor: pointer;
  color: #666;
}

.feedback {
  position: fixed;
  bottom: 80px;
  left: 16px;
  right: 16px;
  padding: 12px;
  border-radius: 8px;
  text-align: center;
  font-size: 0.9rem;
  z-index: 100;
}

.feedback.success {
  background: #d4edda;
  color: #155724;
}

.feedback.error {
  background: #f8d7da;
  color: #721c24;
}

.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  background: #fff;
  border-top: 1px solid #eee;
  padding: 8px 0;
}

.nav-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  text-decoration: none;
  color: #999;
  font-size: 0.75rem;
}

.nav-item.active {
  color: #667eea;
}

.nav-icon {
  font-size: 1.3rem;
}
</style>
