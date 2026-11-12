<template>
  <div class="templates-page">
    <TopBar title="常用语管理" back-to="/" />

    <!-- 添加新模板 -->
    <section class="section">
      <div class="add-form">
        <input
          v-model="newContent"
          type="text"
          maxlength="100"
          placeholder="输入新的常用语..."
          class="add-input"
          @keyup.enter="handleAdd"
        />
        <button class="btn-add" :disabled="!newContent.trim()" @click="handleAdd">添加</button>
      </div>
    </section>

    <!-- 模板列表 -->
    <section class="section">
      <div v-if="templates.length === 0" class="empty-state">
        <p>还没有自定义模板，添加一个吧</p>
      </div>
      <div v-for="tpl in templates" :key="tpl.id" class="template-item">
        <span class="template-text">{{ tpl.content }}</span>
        <div class="template-actions">
          <button class="btn-action" @click="startEdit(tpl)">编辑</button>
          <button class="btn-action danger" @click="handleDelete(tpl.id)">删除</button>
        </div>
      </div>
    </section>

    <!-- 编辑弹窗 -->
    <div v-if="editing" class="modal-overlay" @click.self="editing = null">
      <div class="modal-card">
        <h3>编辑模板</h3>
        <input v-model="editContent" type="text" maxlength="100" class="edit-input" />
        <div class="modal-actions">
          <button class="btn-cancel" @click="editing = null">取消</button>
          <button class="btn-save" @click="handleUpdate">保存</button>
        </div>
      </div>
    </div>

    <!-- 操作反馈 -->
    <div v-if="feedback" class="feedback-toast" :class="feedback.type">
      {{ feedback.message }}
    </div>

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
      <router-link to="/classes" class="nav-item">
        <span class="nav-icon">🏫</span>
        <span>班级</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { getTemplates, createTemplate, updateTemplate, deleteTemplate } from "@/api";
import type { TemplateOut } from "@/types/api";
import TopBar from "@/components/TopBar.vue";

const templates = ref<TemplateOut[]>([]);
const newContent = ref("");
const editing = ref<TemplateOut | null>(null);
const editContent = ref("");
const feedback = ref<{ type: "success" | "error"; message: string } | null>(null);

onMounted(async () => {
  await loadTemplates();
});

async function loadTemplates() {
  try {
    templates.value = await getTemplates();
  } catch {
    // ignore
  }
}

async function handleAdd() {
  if (!newContent.value.trim()) return;
  try {
    await createTemplate(newContent.value.trim());
    newContent.value = "";
    await loadTemplates();
    feedback.value = { type: "success", message: "模板添加成功" };
  } catch {
    feedback.value = { type: "error", message: "添加失败，请重试" };
  }
  setTimeout(() => { feedback.value = null; }, 3000);
}

function startEdit(tpl: TemplateOut) {
  editing.value = tpl;
  editContent.value = tpl.content;
}

async function handleUpdate() {
  if (!editing.value || !editContent.value.trim()) return;
  try {
    await updateTemplate(editing.value.id, editContent.value.trim());
    editing.value = null;
    await loadTemplates();
    feedback.value = { type: "success", message: "模板更新成功" };
  } catch {
    feedback.value = { type: "error", message: "更新失败，请重试" };
  }
  setTimeout(() => { feedback.value = null; }, 3000);
}

async function handleDelete(id: number) {
  if (!confirm("确定删除该模板？")) return;
  try {
    await deleteTemplate(id);
    await loadTemplates();
    feedback.value = { type: "success", message: "模板已删除" };
  } catch {
    feedback.value = { type: "error", message: "删除失败，请重试" };
  }
  setTimeout(() => { feedback.value = null; }, 3000);
}
</script>

<style scoped>
.templates-page { min-height: 100vh; background: #f5f7fa; padding-bottom: 72px; }
.section { padding: 16px; }
.add-form { display: flex; gap: 8px; }
.add-input { flex: 1; padding: 10px 12px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 0.9rem; outline: none; }
.add-input:focus { border-color: #667eea; }
.btn-add { padding: 10px 16px; background: #667eea; color: #fff; border: none; border-radius: 8px; font-size: 0.9rem; cursor: pointer; }
.btn-add:disabled { opacity: 0.4; }
.empty-state { text-align: center; padding: 24px; color: #aaa; font-size: 0.85rem; }
.template-item { display: flex; align-items: center; justify-content: space-between; padding: 12px; background: #fff; border-radius: 8px; margin-bottom: 8px; }
.template-text { flex: 1; font-size: 0.9rem; color: #333; }
.template-actions { display: flex; gap: 8px; }
.btn-action { padding: 4px 10px; border: 1px solid #ddd; border-radius: 6px; background: #fff; font-size: 0.78rem; cursor: pointer; color: #667eea; }
.btn-action.danger { color: #e74c3c; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal-card { background: #fff; border-radius: 12px; padding: 24px; width: 90%; max-width: 360px; }
.modal-card h3 { margin: 0 0 16px; font-size: 1rem; }
.edit-input { width: 100%; padding: 10px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 0.9rem; outline: none; box-sizing: border-box; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
.btn-cancel { padding: 8px 16px; border: 1px solid #ddd; border-radius: 6px; background: #fff; cursor: pointer; }
.btn-save { padding: 8px 16px; background: #667eea; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
.feedback-toast { position: fixed; bottom: 80px; left: 16px; right: 16px; padding: 12px; border-radius: 8px; text-align: center; font-size: 0.9rem; z-index: 200; }
.feedback-toast.success { background: #d4edda; color: #155724; }
.feedback-toast.error { background: #f8d7da; color: #721c24; }
.bottom-nav { position: fixed; bottom: 0; left: 0; right: 0; display: flex; background: #fff; border-top: 1px solid #eee; padding: 8px 0; }
.nav-item { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 2px; text-decoration: none; color: #999; font-size: 0.75rem; }
.nav-item.active { color: #667eea; }
.nav-icon { font-size: 1.3rem; }
</style>
