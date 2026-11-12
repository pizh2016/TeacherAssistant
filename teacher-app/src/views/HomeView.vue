<template>
  <div class="home-page">
    <!-- Toast 通知 -->
    <Transition name="toast-fade">
      <div v-if="toast.show" :class="['toast-notification', toast.type]">
        {{ toast.message }}
      </div>
    </Transition>

    <!-- 顶部导航 -->
    <TopBar title="喊话小喇叭" :show-logout="true" @logout="handleLogout" />

    <!-- 班级选择（支持多选批量广播） -->
    <section class="section">
      <div class="section-header">
        <label class="section-label">目标班级</label>
        <button class="btn-toggle-select" @click="batchMode = !batchMode">
          {{ batchMode ? '单选模式' : '多选模式' }}
        </button>
      </div>
      <div class="class-chips">
        <button
          v-for="cls in classes"
          :key="cls.id"
          class="chip"
          :class="{ active: isClassSelected(cls.id) }"
          @click="toggleClass(cls.id)"
        >
          {{ cls.name }}
        </button>
        <router-link to="/classes" class="chip add-class-chip">+ 管理</router-link>
      </div>
      <div v-if="batchMode && selectedClassIds.length > 0" class="batch-hint">
        已选 {{ selectedClassIds.length }}/6 个班级
      </div>
      <div v-if="classes.length === 0" class="empty-guide">
        <p>还没有班级，请先 <router-link to="/classes">创建班级</router-link></p>
      </div>
    </section>

    <!-- 常用语模板（从后端加载） -->
    <section class="section" v-if="!content">
      <div class="section-header">
        <label class="section-label">常用语</label>
        <router-link to="/templates" class="btn-manage">管理</router-link>
      </div>
      <div class="template-chips">
        <button
          v-for="tpl in templates"
          :key="tpl.id"
          class="template-chip"
          @click="content = tpl.content"
        >{{ tpl.content }}</button>
      </div>
      <div v-if="templates.length === 0" class="template-hint">
        暂无自定义模板，<router-link to="/templates">去添加</router-link>
      </div>
    </section>

    <!-- 消息编辑 -->
    <section class="section">
      <label class="section-label">消息内容</label>
      <textarea
        v-model="content"
        maxlength="500"
        rows="4"
        placeholder="输入通知内容，最多 500 字..."
        class="msg-input"
      />
      <div class="char-count">{{ content.length }} / 500</div>
    </section>

    <!-- 图片附件 -->
    <section class="section">
      <label class="section-label">图片附件（可选）</label>
      <div class="image-upload-area">
        <div v-if="imagePreview" class="image-preview">
          <img :src="imagePreview" alt="预览" />
          <button class="btn-remove-image" @click="removeImage">×</button>
        </div>
        <label v-else class="upload-btn">
          <input type="file" accept="image/*" @change="handleImageSelect" hidden />
          📷 添加图片（≤5MB）
        </label>
        <span v-if="uploading" class="upload-status">上传中...</span>
      </div>
    </section>

    <!-- 展示设置 -->
    <section class="section">
      <label class="section-label">展示方式</label>
      <div class="option-row">
        <button
          v-for="opt in displayModeOptions"
          :key="opt.value"
          class="option-btn"
          :class="{ active: displayMode === opt.value }"
          @click="displayMode = opt.value"
        >{{ opt.label }}</button>
      </div>
    </section>

    <section class="section">
      <label class="section-label">提醒强度</label>
      <div class="option-row">
        <button
          v-for="opt in reminderOptions"
          :key="opt.value"
          class="option-btn"
          :class="{ active: reminderLevel === opt.value }"
          @click="reminderLevel = opt.value"
        >{{ opt.label }}</button>
      </div>
    </section>

    <section class="section">
      <div class="inline-options">
        <label class="toggle-label">
          <input type="checkbox" v-model="ttsEnabled" />
          <span>语音播报</span>
        </label>
        <div class="duration-control">
          <span>显示时长：</span>
          <select v-model.number="duration">
            <option :value="30">30 秒</option>
            <option :value="60">1 分钟</option>
            <option :value="120">2 分钟</option>
            <option :value="180">3 分钟</option>
            <option :value="300">5 分钟</option>
          </select>
        </div>
      </div>
      <!-- TTS 播报次数选择器 -->
      <div v-if="ttsEnabled" class="tts-repeat-row">
        <span class="tts-repeat-label">播报次数：</span>
        <div class="tts-repeat-stepper">
          <button class="stepper-btn" :class="{ active: ttsRepeat === 1 }" @click="ttsRepeat = 1">1</button>
          <button class="stepper-btn" :class="{ active: ttsRepeat === 2 }" @click="ttsRepeat = 2">2</button>
          <button class="stepper-btn" :class="{ active: ttsRepeat === 3 }" @click="ttsRepeat = 3">3</button>
        </div>
      </div>
    </section>

    <!-- 发送按钮 -->
    <button
      class="btn-send"
      :disabled="!canSend || sending"
      @click="handleSend"
    >
      {{ sending ? "发送中..." : (batchMode ? `批量发送 (${selectedClassIds.length} 班)` : "立即发送") }}
    </button>

    <!-- 定时播报快捷入口 -->
    <div class="schedule-entry">
      <router-link to="/schedule" class="btn-schedule">⏰ 定时播报</router-link>
    </div>

    <!-- 发送历史（最近 3 条） -->
    <section v-if="sentHistory.length > 0" class="section sent-history">
      <div class="section-header">
        <label class="section-label">最近发送</label>
      </div>
      <div class="history-list">
        <div v-for="(item, idx) in sentHistory" :key="idx" class="history-card">
          <div class="history-content">
            {{ item.content }}
            <span v-if="item.image_path" class="history-image-badge" title="含图片附件">📷</span>
          </div>
          <div class="history-meta">
            <span v-if="item.classes" class="history-class">{{ item.classes }}</span>
            <span class="history-time">{{ item.sentAt }}</span>
            <div class="history-actions">
              <button
                v-if="item.id && canRecallMap[item.id]"
                class="btn-mini btn-recall active-recall"
                @click="handleRecallFromHistory(item)"
                :disabled="recallingId === item.id"
              >
                {{ recallingId === item.id ? '撤回中...' : `撤回 (${formatRecallCountdown(item)})` }}
              </button>
              <button class="btn-mini btn-resend" @click="handleResendFromHistory(item)">重发</button>
              <button v-if="item.id" class="btn-mini btn-delete" @click="handleDeleteFromHistory(item)">删除</button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 底部导航 -->
    <nav class="bottom-nav">
      <router-link to="/" class="nav-item active">
        <span class="nav-icon">✏️</span>
        <span>发送</span>
      </router-link>
      <router-link to="/history" class="nav-item">
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
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import {
  getClasses, sendMessage, sendBatchMessage, uploadImage,
  getTemplates, getHistory, clearToken, deleteMessage, recallMessage,
} from "@/api";
import type { ClassInfo, DisplayMode, ReminderLevel, TemplateOut } from "@/types/api";
import TopBar from "@/components/TopBar.vue";

const router = useRouter();

const classes = ref<ClassInfo[]>([]);
const selectedClassIds = ref<number[]>([]);
const batchMode = ref(false);
const content = ref("");
const displayMode = ref<DisplayMode>("popup");
const reminderLevel = ref<ReminderLevel>("normal");
const duration = ref(120);
const ttsEnabled = ref(true);
const ttsRepeat = ref(1);
const sending = ref(false);
const sentHistory = ref<{ id: number | null; content: string; classId: number; classes: string; sentAt: string; sentAtIso: string; image_path: string | null }[]>([]);

// Image upload
const imagePath = ref<string | null>(null);
const imagePreview = ref<string | null>(null);
const uploading = ref(false);

// Templates
const templates = ref<TemplateOut[]>([]);

const displayModeOptions = [
  { value: "popup" as DisplayMode, label: "弹窗" },
  { value: "marquee" as DisplayMode, label: "跑马灯" },
];

const reminderOptions = [
  { value: "normal" as ReminderLevel, label: "普通" },
  { value: "strong" as ReminderLevel, label: "强提醒" },
];

const canSend = computed(
  () => selectedClassIds.value.length > 0 && content.value.trim().length > 0,
);

function isClassSelected(id: number): boolean {
  return selectedClassIds.value.includes(id);
}

function classNameOf(classId: number): string {
  const cls = classes.value.find((c) => c.id === classId);
  return cls?.name ?? `班级#${classId}`;
}

function toggleClass(id: number) {
  if (batchMode.value) {
    // Multi-select mode (max 6)
    const idx = selectedClassIds.value.indexOf(id);
    if (idx >= 0) {
      selectedClassIds.value.splice(idx, 1);
    } else if (selectedClassIds.value.length < 6) {
      selectedClassIds.value.push(id);
    }
  } else {
    // Single-select mode
    selectedClassIds.value = [id];
  }
}

async function handleImageSelect(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;

  if (file.size > 5 * 1024 * 1024) {
    sentHistory.value = [{ id: null, content: "图片大小不能超过 5MB", classId: 0, classes: "", sentAt: formatSentAt(new Date().toISOString()), sentAtIso: new Date().toISOString(), image_path: null }, ...sentHistory.value].slice(0, 3);
    return;
  }

  uploading.value = true;
  try {
    // Show preview
    imagePreview.value = URL.createObjectURL(file);
    const res = await uploadImage(file);
    imagePath.value = res.url;
  } catch {
    sentHistory.value = [{ id: null, content: "图片上传失败", classId: 0, classes: "", sentAt: formatSentAt(new Date().toISOString()), sentAtIso: new Date().toISOString(), image_path: null }, ...sentHistory.value].slice(0, 3);
    imagePreview.value = null;
  } finally {
    uploading.value = false;
    input.value = "";
  }
}

function removeImage() {
  imagePath.value = null;
  if (imagePreview.value) {
    // Only revoke blob URLs (created by URL.createObjectURL)
    if (imagePreview.value.startsWith('blob:')) {
      URL.revokeObjectURL(imagePreview.value);
    }
  }
  imagePreview.value = null;
}

onMounted(async () => {
  try {
    classes.value = await getClasses();
    localStorage.setItem("horn_classes", JSON.stringify(classes.value));
    if (classes.value.length > 0) {
      selectedClassIds.value = [classes.value[0].id];
    }
  } catch {
    const stored = localStorage.getItem("horn_classes");
    if (stored) {
      classes.value = JSON.parse(stored);
      if (classes.value.length > 0) {
        selectedClassIds.value = [classes.value[0].id];
      }
    }
  }

  // Load templates
  try {
    templates.value = await getTemplates();
  } catch {
    // Templates are optional
  }

  // Load recent sent messages for feedback area
  try {
    const res = await getHistory(1, 3);
    if (res.items.length > 0) {
      sentHistory.value = res.items.map(m => ({
        id: m.id,
        content: m.content,
        classId: m.class_id,
        classes: classNameOf(m.class_id),
        sentAt: formatSentAt(m.sent_at),
        sentAtIso: m.sent_at,
        image_path: m.image_path ?? null,
      }));
    }
  } catch {
    // Fallback: try localStorage cache
    const cached = localStorage.getItem("horn_sent_history");
    if (cached) {
      try {
        sentHistory.value = JSON.parse(cached);
      } catch {
        // Invalid cache, ignore
      }
    }
  }

  // Handle edit pre-fill from HistoryView
  const editData = localStorage.getItem("horn_edit_message");
  if (editData) {
    try {
      const edit = JSON.parse(editData);
      content.value = edit.content || "";
      displayMode.value = edit.display_mode || "popup";
      reminderLevel.value = edit.reminder_level || "normal";
      duration.value = edit.duration || 120;
      ttsEnabled.value = edit.tts_enabled ?? true;
      if (edit.class_id) {
        selectedClassIds.value = [edit.class_id];
      }
      // Restore image attachment if present
      if (edit.image_path) {
        imagePath.value = edit.image_path;
        imagePreview.value = edit.image_path; // server path works as same-origin URL
      }
    } catch {
      // Invalid edit data, ignore
    }
    localStorage.removeItem("horn_edit_message");
  }

  // Start recall countdown timer (updates every second)
  startRecallTimers();
});

async function handleSend() {
  if (!canSend.value || sending.value) return;
  sending.value = true;

  const messageContent = content.value.trim();
  const selectedClasses = classes.value.filter(c => selectedClassIds.value.includes(c.id));
  const classNames = selectedClasses.map(c => c.name).join("、");

  try {
    if (batchMode.value && selectedClassIds.value.length > 1) {
      // Batch send
      await sendBatchMessage({
        class_ids: selectedClassIds.value,
        content: messageContent,
        display_mode: displayMode.value,
        reminder_level: reminderLevel.value,
        duration: duration.value,
        tts_enabled: ttsEnabled.value,
        tts_repeat: ttsEnabled.value ? ttsRepeat.value : 1,
        image_path: imagePath.value,
      });
    } else {
      // Single send
      await sendMessage({
        class_id: selectedClassIds.value[0],
        content: messageContent,
        display_mode: displayMode.value,
        reminder_level: reminderLevel.value,
        duration: duration.value,
        tts_enabled: ttsEnabled.value,
        tts_repeat: ttsEnabled.value ? ttsRepeat.value : 1,
        image_path: imagePath.value,
      });
    }
    // Add to sent history (newest first, max 3)
    const sentTime = formatSentAt(new Date().toISOString());
    const sentTimeIso = new Date().toISOString();
    const entry = {
      id: null as number | null,
      content: messageContent,
      classId: selectedClassIds.value[0],
      classes: classNames,
      sentAt: sentTime,
      sentAtIso: sentTimeIso,
      image_path: imagePath.value,
    };
    sentHistory.value = [entry, ...sentHistory.value].slice(0, 3);
    // Also cache to localStorage as fallback
    localStorage.setItem("horn_sent_history", JSON.stringify(sentHistory.value));

    content.value = "";
    removeImage();
  } catch {
    // Show error feedback
    sentHistory.value = [{ id: null, content: "发送失败，请重试", classId: 0, classes: "", sentAt: formatSentAt(new Date().toISOString()), sentAtIso: new Date().toISOString(), image_path: null }, ...sentHistory.value].slice(0, 3);
  } finally {
    sending.value = false;
  }
}

function formatSentAt(iso: string): string {
  try {
    const d = new Date(iso);
    const month = d.getMonth() + 1;
    const day = d.getDate();
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    return `${month}/${day} ${hh}:${mm}`;
  } catch {
    return "";
  }
}

function handleResendFromHistory(item: { id: number | null; content: string; classId: number; image_path: string | null }) {
  content.value = item.content;
  if (item.classId) {
    selectedClassIds.value = [item.classId];
  }
  // Restore image attachment if present
  if (item.image_path) {
    imagePath.value = item.image_path;
    imagePreview.value = item.image_path; // server path works as same-origin URL
  }
}

async function handleDeleteFromHistory(item: { id: number | null; content: string }) {
  if (!item.id) return;
  if (!confirm(`确定要删除这条消息吗？\n\n「${item.content}」`)) return;
  try {
    await deleteMessage(item.id);
    sentHistory.value = sentHistory.value.filter(h => h.id !== item.id);
    localStorage.setItem("horn_sent_history", JSON.stringify(sentHistory.value));
  } catch {
    // Silently fail — user can retry or delete from HistoryView
  }
}

async function handleRecallFromHistory(item: { id: number | null; content: string }) {
  if (!item.id || recallingId.value === item.id) return;
  recallingId.value = item.id;
  try {
    await recallMessage(item.id);
    sentHistory.value = sentHistory.value.filter(h => h.id !== item.id);
    localStorage.setItem("horn_sent_history", JSON.stringify(sentHistory.value));
    showToast('✓ 消息已撤回', 'success');
  } catch (err: any) {
    const msg = err?.error?.message || '撤回失败，请重试';
    showToast(`✗ ${msg}`, 'error');
  } finally {
    recallingId.value = null;
  }
}

// Auto-refresh recall buttons
const recallTick = ref(0);
const recallTimers: Record<number, ReturnType<typeof setInterval>> = {};
const recallingId = ref<number | null>(null);
const toast = ref({ show: false, message: '', type: 'success' as 'success' | 'error' });
let toastTimer: ReturnType<typeof setTimeout> | null = null;

// Computed map for recall eligibility (reactive, updates every second)
const canRecallMap = computed(() => {
  // Access recallTick to trigger re-computation
  void recallTick.value;
  const map: Record<number, boolean> = {};
  for (const item of sentHistory.value) {
    if (item.id) {
      const sentTime = new Date(item.sentAtIso).getTime();
      const elapsed = Date.now() - sentTime;
      map[item.id] = elapsed <= 60000;
    }
  }
  return map;
});

function formatRecallCountdown(item: { sentAtIso: string }): string {
  const sentTime = new Date(item.sentAtIso).getTime();
  const elapsed = Date.now() - sentTime;
  const remaining = Math.max(0, Math.ceil((60000 - elapsed) / 1000));
  return `${remaining}s`;
}

function showToast(message: string, type: 'success' | 'error' = 'success') {
  if (toastTimer) clearTimeout(toastTimer);
  toast.value = { show: true, message, type };
  toastTimer = setTimeout(() => {
    toast.value.show = false;
  }, 3000);
}

function startRecallTimers() {
  // Clear existing timers
  Object.values(recallTimers).forEach(timer => clearInterval(timer));
  Object.keys(recallTimers).forEach(key => delete recallTimers[Number(key)]);
  
  // Start a single tick timer for all recall buttons
  recallTimers[0] = setInterval(() => {
    recallTick.value++;
  }, 1000);
}

onUnmounted(() => {
  // Clean up all timers
  Object.values(recallTimers).forEach(timer => clearInterval(timer));
  if (toastTimer) clearTimeout(toastTimer);
});

function handleLogout() {
  clearToken();
  localStorage.removeItem("horn_classes");
  localStorage.removeItem("horn_teacher_id");
  localStorage.removeItem("horn_teacher_name");
  router.push({ name: "Login" });
}
</script>

<style scoped>
.home-page {
  min-height: 100vh;
  background: #f5f7fa;
  padding-bottom: 72px;
}

.section { padding: 16px; }
.section-label { display: block; font-size: 0.82rem; font-weight: 600; color: #666; margin-bottom: 8px; }
.section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.section-header .section-label { margin-bottom: 0; }

.btn-toggle-select {
  padding: 4px 10px;
  border: 1px solid #c5cae9;
  border-radius: 12px;
  background: #f0f2ff;
  color: #667eea;
  font-size: 0.75rem;
  cursor: pointer;
}

.class-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip {
  padding: 8px 16px;
  border: 2px solid #e0e0e0;
  border-radius: 20px;
  background: #fff;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.2s;
}
.chip.active { border-color: #667eea; background: #667eea; color: #fff; }
.add-class-chip { border-color: #c5cae9; color: #667eea; text-decoration: none; font-weight: 600; }
.add-class-chip:hover { background: #f0f2ff; }
.batch-hint { font-size: 0.78rem; color: #667eea; margin-top: 6px; }

.empty-guide { margin-top: 12px; padding: 12px; background: #fff8e1; border-radius: 8px; text-align: center; }
.empty-guide p { margin: 0; font-size: 0.85rem; color: #f57f17; }
.empty-guide a { color: #667eea; font-weight: 600; text-decoration: underline; }

.btn-manage { font-size: 0.78rem; color: #667eea; text-decoration: none; }
.template-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.template-chip {
  padding: 6px 12px;
  border: 1px solid #e8e8e8;
  border-radius: 16px;
  background: #fafafa;
  font-size: 0.82rem;
  color: #555;
  cursor: pointer;
  transition: all 0.15s;
}
.template-chip:hover { background: #f0f2ff; border-color: #667eea; color: #667eea; }
.template-chip:active { transform: scale(0.96); }
.template-hint { font-size: 0.78rem; color: #aaa; margin-top: 6px; }
.template-hint a { color: #667eea; }

.msg-input {
  width: 100%;
  padding: 12px;
  font-size: 0.95rem;
  border: 2px solid #e0e0e0;
  border-radius: 10px;
  resize: vertical;
  outline: none;
  font-family: inherit;
  box-sizing: border-box;
}
.msg-input:focus { border-color: #667eea; }
.char-count { text-align: right; font-size: 0.75rem; color: #aaa; margin-top: 4px; }

.image-upload-area { display: flex; align-items: center; gap: 12px; }
.upload-btn {
  padding: 8px 16px;
  border: 2px dashed #c5cae9;
  border-radius: 8px;
  background: #f8f9ff;
  color: #667eea;
  font-size: 0.85rem;
  cursor: pointer;
}
.upload-btn:hover { background: #f0f2ff; }
.image-preview { position: relative; display: inline-block; }
.image-preview img { max-width: 120px; max-height: 80px; border-radius: 8px; }
.btn-remove-image {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #e74c3c;
  color: #fff;
  border: none;
  font-size: 0.7rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.upload-status { font-size: 0.78rem; color: #999; }

.option-row { display: flex; gap: 8px; }
.option-btn {
  flex: 1;
  padding: 10px;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  background: #fff;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.2s;
}
.option-btn.active { border-color: #667eea; background: #f0f2ff; color: #667eea; font-weight: 600; }

.inline-options { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }
.toggle-label { display: flex; align-items: center; gap: 6px; font-size: 0.9rem; cursor: pointer; }
.duration-control { display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: #666; }
.duration-control select { padding: 6px 8px; border: 1px solid #ddd; border-radius: 6px; font-size: 0.85rem; }

.btn-send {
  display: block;
  width: calc(100% - 32px);
  margin: 8px 16px 8px;
  padding: 16px;
  font-size: 1.1rem;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 12px;
  cursor: pointer;
  transition: opacity 0.2s;
}
.btn-send:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-send:not(:disabled):hover { opacity: 0.9; }

.schedule-entry { text-align: center; margin: 0 16px 12px; }
.btn-schedule {
  display: inline-block;
  padding: 8px 20px;
  border: 1px solid #c5cae9;
  border-radius: 20px;
  color: #667eea;
  font-size: 0.85rem;
  text-decoration: none;
  background: #f8f9ff;
}
.btn-schedule:hover { background: #f0f2ff; }

.sent-history { padding-top: 8px; }
.history-list { display: flex; flex-direction: column; gap: 8px; }
.history-card {
  padding: 10px 12px;
  background: #fff;
  border-radius: 8px;
  border-left: 3px solid #667eea;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}
.history-content {
  font-size: 0.88rem;
  color: #333;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.history-image-badge {
  font-size: 0.75rem;
  margin-left: 4px;
  vertical-align: middle;
}
.history-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  font-size: 0.75rem;
  color: #999;
}
.history-class { color: #667eea; font-weight: 500; }
.history-time { color: #aaa; }
.history-actions {
  margin-left: auto;
  display: flex;
  gap: 4px;
}
.btn-mini {
  padding: 2px 8px;
  font-size: 0.7rem;
  border-radius: 10px;
  cursor: pointer;
  background: #fff;
  transition: all 0.15s;
}
.btn-mini.btn-resend {
  border: 1px solid #667eea;
  color: #667eea;
}
.btn-mini.btn-resend:hover {
  background: #667eea;
  color: #fff;
}
.btn-mini.btn-recall {
  border: 1px solid #f97316;
  color: #fff;
  background: #f97316;
  font-weight: 600;
  animation: pulse-recall-home 1.5s ease-in-out infinite;
  min-width: 70px;
  text-align: center;
}
.btn-mini.btn-recall:hover {
  background: #ea580c;
  border-color: #ea580c;
}
.btn-mini.btn-recall:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  animation: none;
}
@keyframes pulse-recall-home {
  0%, 100% { box-shadow: 0 0 0 0 rgba(249, 115, 22, 0.4); }
  50% { box-shadow: 0 0 0 6px rgba(249, 115, 22, 0); }
}
.btn-mini.btn-delete {
  border: 1px solid #ef4444;
  color: #ef4444;
}
.btn-mini.btn-delete:hover {
  background: #ef4444;
  color: #fff;
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
.nav-item.active { color: #667eea; }
.nav-icon { font-size: 1.3rem; }

/* TTS 播报次数步进器 */
.tts-repeat-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}
.tts-repeat-label {
  font-size: 0.85rem;
  color: #666;
}
.tts-repeat-stepper {
  display: flex;
  gap: 4px;
}
.stepper-btn {
  width: 36px;
  height: 30px;
  border: 1.5px solid #ddd;
  border-radius: 6px;
  background: #fff;
  font-size: 0.9rem;
  font-weight: 500;
  color: #666;
  cursor: pointer;
  transition: all 0.15s;
}
.stepper-btn:hover {
  border-color: #667eea;
  color: #667eea;
}
.stepper-btn.active {
  border-color: #667eea;
  background: #667eea;
  color: #fff;
}

/* Toast 通知 */
.toast-notification {
  position: fixed;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  padding: 10px 24px;
  border-radius: 8px;
  font-size: 0.88rem;
  font-weight: 500;
  z-index: 10000;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  max-width: 90%;
  text-align: center;
}
.toast-notification.success {
  background: #22c55e;
  color: #fff;
}
.toast-notification.error {
  background: #ef4444;
  color: #fff;
}
.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.3s, transform 0.3s;
}
.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-10px);
}
</style>
