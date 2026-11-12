<template>
  <div class="schedule-page">
    <TopBar title="定时播报" back-to="/" />

    <!-- 创建定时任务 -->
    <section class="section">
      <h3 class="sub-title">新建定时任务</h3>
      <div class="form-group">
        <label>目标班级</label>
        <select v-model.number="form.class_id">
          <option v-for="cls in classes" :key="cls.id" :value="cls.id">{{ cls.name }}</option>
        </select>
      </div>
      <div class="form-group">
        <label>消息内容</label>
        <textarea v-model="form.content" rows="2" placeholder="如：放学注意安全" maxlength="500"></textarea>
      </div>
      <div class="form-group">
        <label>执行方式</label>
        <div class="option-row">
          <button v-for="opt in scheduleTypeOptions" :key="opt.value"
            class="option-btn" :class="{ active: form.schedule_type === opt.value }"
            @click="form.schedule_type = opt.value">{{ opt.label }}</button>
        </div>
      </div>
      <div class="form-group" v-if="form.schedule_type === 'once'">
        <label>执行时间</label>
        <input type="datetime-local" v-model="form.schedule_at_local" />
      </div>
      <button class="btn-create" :disabled="!canCreate" @click="handleCreate">创建定时任务</button>
    </section>

    <!-- 任务列表 -->
    <section class="section">
      <h3 class="sub-title">我的定时任务</h3>
      <div v-if="scheduled.length === 0" class="empty-state">暂无定时任务</div>
      <div v-for="item in scheduled" :key="item.id" class="schedule-item">
        <div class="schedule-info">
          <span class="schedule-class">{{ classNameMap[item.class_id] || `班级${item.class_id}` }}</span>
          <span class="schedule-content">{{ item.content }}</span>
          <span class="schedule-time">
            {{ item.schedule_type === 'once' ? formatTime(item.schedule_at) : item.schedule_type === 'daily' ? '每天 ' + item.cron_expression : '每周 ' + item.cron_expression }}
          </span>
        </div>
        <div class="schedule-actions">
          <button class="btn-toggle" :class="{ active: item.is_active }" @click="handleToggle(item.id)">
            {{ item.is_active ? '已启用' : '已停用' }}
          </button>
          <button class="btn-delete" @click="handleDelete(item.id)">删除</button>
        </div>
      </div>
    </section>

    <!-- 操作反馈 -->
    <div v-if="feedback" class="feedback" :class="feedback.type">
      {{ feedback.message }}
    </div>

    <nav class="bottom-nav">
      <router-link to="/" class="nav-item"><span class="nav-icon">✏️</span><span>发送</span></router-link>
      <router-link to="/history" class="nav-item"><span class="nav-icon">📋</span><span>历史</span></router-link>
      <router-link to="/classes" class="nav-item"><span class="nav-icon">🏫</span><span>班级</span></router-link>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from "vue";
import { getClasses, getScheduledMessages, createScheduledMessage, deleteScheduledMessage, toggleScheduledMessage } from "@/api";
import type { ClassInfo, ScheduledMessageOut, ScheduleType } from "@/types/api";
import TopBar from "@/components/TopBar.vue";

const classes = ref<ClassInfo[]>([]);
const scheduled = ref<ScheduledMessageOut[]>([]);
const classNameMap = ref<Record<number, string>>({});

const form = reactive({
  class_id: 0,
  content: "",
  schedule_type: "once" as ScheduleType,
  schedule_at_local: "",
});

const feedback = ref<{ type: "success" | "error"; message: string } | null>(null);

const scheduleTypeOptions = [
  { value: "once" as ScheduleType, label: "单次定时" },
  { value: "daily" as ScheduleType, label: "每天" },
  { value: "weekly" as ScheduleType, label: "每周" },
];

const canCreate = computed(() => form.class_id > 0 && form.content.trim().length > 0);

function formatTime(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

onMounted(async () => {
  try {
    classes.value = await getClasses();
    if (classes.value.length > 0) {
      form.class_id = classes.value[0].id;
    }
    classNameMap.value = Object.fromEntries(classes.value.map(c => [c.id, c.name]));
  } catch { /* ignore */ }
  try {
    scheduled.value = await getScheduledMessages();
  } catch { /* ignore */ }
});

async function handleCreate() {
  if (!canCreate.value) return;
  const payload: any = {
    class_id: form.class_id,
    content: form.content.trim(),
    display_mode: "popup",
    reminder_level: "normal",
    duration: 120,
    tts_enabled: true,
    schedule_type: form.schedule_type,
  };
  if (form.schedule_type === "once") {
    payload.schedule_at = new Date(form.schedule_at_local).toISOString();
  }
  try {
    await createScheduledMessage(payload);
    form.content = "";
    scheduled.value = await getScheduledMessages();
    feedback.value = { type: "success", message: "定时任务创建成功" };
  } catch {
    feedback.value = { type: "error", message: "创建失败，请重试" };
  }
  setTimeout(() => { feedback.value = null; }, 3000);
}

async function handleToggle(id: number) {
  try {
    await toggleScheduledMessage(id);
    scheduled.value = await getScheduledMessages();
  } catch {
    feedback.value = { type: "error", message: "操作失败，请重试" };
    setTimeout(() => { feedback.value = null; }, 3000);
  }
}

async function handleDelete(id: number) {
  if (!confirm("确定删除该定时任务？")) return;
  try {
    await deleteScheduledMessage(id);
    scheduled.value = await getScheduledMessages();
  } catch {
    feedback.value = { type: "error", message: "删除失败，请重试" };
    setTimeout(() => { feedback.value = null; }, 3000);
  }
}
</script>

<style scoped>
.schedule-page { min-height: 100vh; background: #f5f7fa; padding-bottom: 72px; }
.section { padding: 16px; }
.sub-title { font-size: 0.9rem; font-weight: 600; color: #333; margin: 0 0 12px; }
.form-group { margin-bottom: 12px; }
.form-group label { display: block; font-size: 0.8rem; color: #666; margin-bottom: 4px; }
.form-group select, .form-group textarea, .form-group input {
  width: 100%; padding: 10px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 0.9rem; outline: none; box-sizing: border-box; font-family: inherit;
}
.form-group select:focus, .form-group textarea:focus, .form-group input:focus { border-color: #667eea; }
.option-row { display: flex; gap: 8px; }
.option-btn { flex: 1; padding: 8px; border: 2px solid #e0e0e0; border-radius: 8px; background: #fff; font-size: 0.85rem; cursor: pointer; }
.option-btn.active { border-color: #667eea; background: #f0f2ff; color: #667eea; font-weight: 600; }
.btn-create { width: 100%; padding: 12px; background: #667eea; color: #fff; border: none; border-radius: 8px; font-size: 0.95rem; cursor: pointer; margin-top: 8px; }
.btn-create:disabled { opacity: 0.4; }
.empty-state { text-align: center; padding: 20px; color: #aaa; font-size: 0.85rem; }
.schedule-item { display: flex; align-items: center; justify-content: space-between; padding: 12px; background: #fff; border-radius: 8px; margin-bottom: 8px; }
.schedule-info { flex: 1; display: flex; flex-direction: column; gap: 4px; }
.schedule-class { font-size: 0.75rem; color: #667eea; font-weight: 600; }
.schedule-content { font-size: 0.9rem; color: #333; }
.schedule-time { font-size: 0.75rem; color: #999; }
.schedule-actions { display: flex; flex-direction: column; gap: 4px; }
.btn-toggle { padding: 4px 10px; border: 1px solid #c5cae9; border-radius: 6px; background: #fff; font-size: 0.72rem; cursor: pointer; color: #667eea; }
.btn-toggle.active { background: #f0f2ff; }
.btn-delete { padding: 4px 10px; border: 1px solid #f5c6cb; border-radius: 6px; background: #fff; font-size: 0.72rem; cursor: pointer; color: #e74c3c; }
.feedback { position: fixed; bottom: 80px; left: 16px; right: 16px; padding: 12px; border-radius: 8px; text-align: center; font-size: 0.9rem; z-index: 100; }
.feedback.success { background: #d4edda; color: #155724; }
.feedback.error { background: #f8d7da; color: #721c24; }
.bottom-nav { position: fixed; bottom: 0; left: 0; right: 0; display: flex; background: #fff; border-top: 1px solid #eee; padding: 8px 0; }
.nav-item { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 2px; text-decoration: none; color: #999; font-size: 0.75rem; }
.nav-item.active { color: #667eea; }
.nav-icon { font-size: 1.3rem; }
</style>
