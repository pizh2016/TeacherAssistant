<template>
  <div class="class-manage-page">
    <!-- 顶部导航 -->
    <TopBar title="班级管理" back-to="/" />

    <!-- 创建班级 -->
    <section class="section create-section">
      <label class="section-label">创建新班级</label>
      <div class="create-row">
        <input
          v-model="newClassName"
          type="text"
          placeholder="输入班级名称，如：二年级A班"
          maxlength="64"
          class="create-input"
          @keyup.enter="handleCreate"
        />
        <button
          class="btn-create"
          :disabled="!newClassName.trim() || creating"
          @click="handleCreate"
        >
          {{ creating ? "创建中..." : "+ 创建" }}
        </button>
      </div>
      <div v-if="createFeedback" class="create-feedback" :class="createFeedback.type">
        <span>{{ createFeedback.message }}</span>
        <span v-if="createFeedback.pairingCode" class="pairing-highlight">
          配对码：{{ createFeedback.pairingCode }}
          <button class="btn-copy-small" @click="copyCode(createFeedback.pairingCode)">复制</button>
        </span>
      </div>
    </section>

    <!-- 班级列表 -->
    <section class="section">
      <label class="section-label">我的班级（{{ classes.length }}）</label>

      <!-- 空状态 -->
      <div v-if="classes.length === 0" class="empty-state">
        <div class="empty-icon">📚</div>
        <p class="empty-text">还没有班级</p>
        <p class="empty-hint">在上方输入班级名称并点击"创建"即可开始</p>
      </div>

      <!-- 班级卡片 -->
      <div v-for="cls in classes" :key="cls.id" class="class-card">
        <div class="card-header">
          <!-- 编辑模式 -->
          <template v-if="editingId === cls.id">
            <input
              v-model="editName"
              type="text"
              class="edit-input"
              maxlength="64"
              @keyup.enter="handleUpdate(cls.id)"
              @keyup.escape="cancelEdit"
            />
            <div class="edit-actions">
              <button class="btn-save" @click="handleUpdate(cls.id)">保存</button>
              <button class="btn-cancel" @click="cancelEdit">取消</button>
            </div>
          </template>
          <!-- 展示模式 -->
          <template v-else>
            <h3 class="class-name">{{ cls.name }}</h3>
            <div class="card-actions">
              <button class="btn-icon" title="编辑" @click="startEdit(cls)">✏️</button>
              <button class="btn-icon" title="删除" @click="confirmDelete(cls)">🗑️</button>
            </div>
          </template>
        </div>

        <!-- 配对码展示 -->
        <div class="pairing-row">
          <span class="pairing-label">配对码</span>
          <span class="pairing-code">{{ cls.pairing_code }}</span>
          <button class="btn-copy" @click="copyCode(cls.pairing_code)">
            {{ copiedId === cls.id ? "✓ 已复制" : "📋 复制" }}
          </button>
          <button class="btn-regen" @click="handleRegenerate(cls)" title="重新生成配对码">
            🔄 换码
          </button>
        </div>

        <!-- 删除确认 -->
        <div v-if="deletingId === cls.id" class="delete-confirm">
          <span>确认删除「{{ cls.name }}」？此操作不可恢复。</span>
          <div class="delete-actions">
            <button class="btn-confirm-delete" @click="handleDelete(cls.id)">确认删除</button>
            <button class="btn-cancel-delete" @click="deletingId = null">取消</button>
          </div>
        </div>
      </div>
    </section>

    <!-- 使用说明 -->
    <section class="section help-section">
      <label class="section-label">使用说明</label>
      <div class="help-content">
        <p>📌 <strong>配对码</strong>用于大屏端登录连接班级。将配对码告知 IT 管理员，在大屏端输入即可绑定。</p>
        <p>🔄 <strong>换码</strong>会使旧配对码失效，已连接的大屏端需重新输入新码。</p>
        <p>📋 <strong>复制</strong>可一键复制配对码，方便通过微信或纸质方式分发。</p>
      </div>
    </section>

    <!-- 底部导航 -->
    <nav class="bottom-nav">
      <router-link to="/" class="nav-item">
        <span class="nav-icon">✏️</span>
        <span>发送</span>
      </router-link>
      <router-link to="/history" class="nav-item">
        <span class="nav-icon">📋</span>
        <span>历史</span>
      </router-link>
      <router-link to="/classes" class="nav-item active">
        <span class="nav-icon">🏫</span>
        <span>班级</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import {
  getClasses,
  createClass,
  updateClass,
  deleteClass,
  regeneratePairingCode,
} from "@/api";
import type { ClassInfo } from "@/types/api";
import TopBar from "@/components/TopBar.vue";

// ---- 班级列表 ----
const classes = ref<ClassInfo[]>([]);

// ---- 创建班级 ----
const newClassName = ref("");
const creating = ref(false);
const createFeedback = ref<{
  type: "success" | "error";
  message: string;
  pairingCode?: string;
} | null>(null);

// ---- 编辑班级 ----
const editingId = ref<number | null>(null);
const editName = ref("");

// ---- 删除班级 ----
const deletingId = ref<number | null>(null);

// ---- 复制状态 ----
const copiedId = ref<number | null>(null);

onMounted(async () => {
  await loadClasses();
});

async function loadClasses() {
  try {
    classes.value = await getClasses();
    // 同步到 localStorage 供其他页面使用
    localStorage.setItem("horn_classes", JSON.stringify(classes.value));
  } catch (err) {
    console.warn("[ClassManage] loadClasses API failed, falling back to localStorage", err);
    // Fallback: 从 localStorage 读取缓存的班级数据
    const stored = localStorage.getItem("horn_classes");
    if (stored) {
      try {
        classes.value = JSON.parse(stored);
      } catch {
        classes.value = [];
      }
    }
  }
}

// ---- 创建班级 ----
async function handleCreate() {
  const name = newClassName.value.trim();
  if (!name || creating.value) return;

  creating.value = true;
  createFeedback.value = null;

  try {
    const result = await createClass({ name });
    createFeedback.value = {
      type: "success",
      message: `班级「${result.name}」创建成功！`,
      pairingCode: result.pairing_code,
    };
    newClassName.value = "";
    await loadClasses();
    // 5 秒后清除反馈
    setTimeout(() => { createFeedback.value = null; }, 5000);
  } catch (err) {
    const msg = (err as any)?.error?.message || "创建失败，请重试";
    createFeedback.value = {
      type: "error",
      message: msg,
    };
  } finally {
    creating.value = false;
  }
}

// ---- 编辑班级 ----
function startEdit(cls: ClassInfo) {
  editingId.value = cls.id;
  editName.value = cls.name;
}

function cancelEdit() {
  editingId.value = null;
  editName.value = "";
}

async function handleUpdate(classId: number) {
  const name = editName.value.trim();
  if (!name) return;

  try {
    await updateClass(classId, { name });
    await loadClasses();
    cancelEdit();
  } catch (err) {
    const msg = (err as any)?.error?.message || "更新失败，请重试";
    alert(msg);
  }
}

// ---- 删除班级 ----
function confirmDelete(cls: ClassInfo) {
  deletingId.value = cls.id;
}

async function handleDelete(classId: number) {
  try {
    await deleteClass(classId);
    deletingId.value = null;
    await loadClasses();
  } catch {
    alert("删除失败，请重试");
  }
}

// ---- 重新生成配对码 ----
async function handleRegenerate(cls: ClassInfo) {
  const confirmed = confirm(
    `确认重新生成「${cls.name}」的配对码？\n\n旧配对码将立即失效，已连接的大屏端需要重新配置。`,
  );
  if (!confirmed) return;

  try {
    const result = await regeneratePairingCode(cls.id);
    // 更新本地列表
    const idx = classes.value.findIndex((c) => c.id === cls.id);
    if (idx !== -1) {
      classes.value[idx] = result;
      localStorage.setItem("horn_classes", JSON.stringify(classes.value));
    }
    alert(`配对码已更新为：${result.pairing_code}`);
  } catch {
    alert("重新生成失败，请重试");
  }
}

// ---- 复制配对码 ----
async function copyCode(code: string) {
  try {
    await navigator.clipboard.writeText(code);
    // 找到对应的 class id 来显示"已复制"
    const cls = classes.value.find((c) => c.pairing_code === code);
    if (cls) {
      copiedId.value = cls.id;
      setTimeout(() => { copiedId.value = null; }, 2000);
    }
  } catch {
    // fallback: 选中文本让用户手动复制
    alert(`配对码：${code}（请手动复制）`);
  }
}
</script>

<style scoped>
.class-manage-page {
  min-height: 100vh;
  background: #f5f7fa;
  padding-bottom: 72px;
}

.section {
  padding: 16px;
}

.section-label {
  display: block;
  font-size: 0.82rem;
  font-weight: 600;
  color: #666;
  margin-bottom: 8px;
}

/* ---- 创建班级 ---- */
.create-row {
  display: flex;
  gap: 8px;
}

.create-input {
  flex: 1;
  padding: 12px;
  font-size: 0.95rem;
  border: 2px solid #e0e0e0;
  border-radius: 10px;
  outline: none;
  font-family: inherit;
}

.create-input:focus {
  border-color: #667eea;
}

.btn-create {
  padding: 12px 20px;
  font-size: 0.95rem;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 10px;
  cursor: pointer;
  white-space: nowrap;
  transition: opacity 0.2s;
}

.btn-create:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.create-feedback {
  margin-top: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 0.85rem;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.create-feedback.success {
  background: #d4edda;
  color: #155724;
}

.create-feedback.error {
  background: #f8d7da;
  color: #721c24;
}

.pairing-highlight {
  font-weight: 700;
  font-size: 1rem;
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-copy-small {
  padding: 2px 8px;
  font-size: 0.75rem;
  border: 1px solid #155724;
  border-radius: 4px;
  background: transparent;
  color: #155724;
  cursor: pointer;
}

/* ---- 空状态 ---- */
.empty-state {
  text-align: center;
  padding: 40px 20px;
}

.empty-icon {
  font-size: 3rem;
  margin-bottom: 12px;
}

.empty-text {
  font-size: 1rem;
  color: #666;
  margin: 0 0 4px;
}

.empty-hint {
  font-size: 0.85rem;
  color: #999;
  margin: 0;
}

/* ---- 班级卡片 ---- */
.class-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.class-name {
  font-size: 1.05rem;
  font-weight: 600;
  color: #1a1a2e;
  margin: 0;
}

.card-actions {
  display: flex;
  gap: 4px;
}

.btn-icon {
  background: none;
  border: none;
  font-size: 1.1rem;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 4px;
  transition: background 0.15s;
}

.btn-icon:hover {
  background: #f0f0f0;
}

.edit-input {
  flex: 1;
  padding: 8px 10px;
  font-size: 0.95rem;
  border: 2px solid #667eea;
  border-radius: 6px;
  outline: none;
  font-family: inherit;
}

.edit-actions {
  display: flex;
  gap: 4px;
  margin-left: 8px;
}

.btn-save {
  padding: 6px 12px;
  font-size: 0.8rem;
  font-weight: 600;
  color: #fff;
  background: #667eea;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.btn-cancel {
  padding: 6px 12px;
  font-size: 0.8rem;
  color: #666;
  background: #f0f0f0;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

/* ---- 配对码展示 ---- */
.pairing-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #f8f9ff;
  border-radius: 8px;
  border: 1px dashed #c5cae9;
}

.pairing-label {
  font-size: 0.8rem;
  color: #888;
}

.pairing-code {
  font-size: 1.6rem;
  font-weight: 800;
  letter-spacing: 3px;
  color: #667eea;
  font-family: "Courier New", monospace;
}

.btn-copy {
  padding: 6px 12px;
  font-size: 0.8rem;
  border: 1px solid #667eea;
  border-radius: 6px;
  background: #fff;
  color: #667eea;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.btn-copy:hover {
  background: #667eea;
  color: #fff;
}

.btn-regen {
  padding: 6px 10px;
  font-size: 0.8rem;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  background: #fff;
  color: #888;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.btn-regen:hover {
  border-color: #ff9800;
  color: #ff9800;
}

/* ---- 删除确认 ---- */
.delete-confirm {
  margin-top: 12px;
  padding: 10px 12px;
  background: #fff3f3;
  border: 1px solid #ffcdd2;
  border-radius: 8px;
  font-size: 0.85rem;
  color: #c62828;
}

.delete-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.btn-confirm-delete {
  padding: 6px 14px;
  font-size: 0.8rem;
  font-weight: 600;
  color: #fff;
  background: #e53935;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.btn-cancel-delete {
  padding: 6px 14px;
  font-size: 0.8rem;
  color: #666;
  background: #f0f0f0;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

/* ---- 使用说明 ---- */
.help-section {
  background: #fff;
  margin: 0 16px 16px;
  border-radius: 12px;
  padding: 16px;
}

.help-content p {
  font-size: 0.82rem;
  color: #666;
  margin: 0 0 6px;
  line-height: 1.5;
}

/* ---- 底部导航 ---- */
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
