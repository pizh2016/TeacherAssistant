<template>
  <div class="dashboard">
    <header class="header">
      <h1>喊话小喇叭 · 管理后台</h1>
      <div class="header-actions">
        <button class="btn-print" @click="printPairingCodes">🖨️ 打印配对码</button>
        <button class="btn-export" @click="exportMessages">📥 导出消息</button>
      </div>
    </header>

    <!-- Tab 导航 -->
    <nav class="tabs">
      <button :class="{ active: tab === 'classes' }" @click="tab = 'classes'">班级管理</button>
      <button :class="{ active: tab === 'audit' }" @click="tab = 'audit'">消息审计</button>
    </nav>

    <!-- 班级管理 -->
    <section v-if="tab === 'classes'" class="panel">
      <div class="panel-header">
        <h2>班级列表</h2>
        <button class="btn-add" @click="showCreateClass = true">+ 新建班级</button>
      </div>
      <table class="data-table">
        <thead>
          <tr><th>ID</th><th>班级名称</th><th>配对码</th><th>创建时间</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="cls in classes" :key="cls.id">
            <td>{{ cls.id }}</td>
            <td>
              <input v-if="editingClassId === cls.id" v-model="editClassName" class="inline-input" />
              <span v-else>{{ cls.name }}</span>
            </td>
            <td><code class="pairing-code">{{ cls.pairing_code }}</code></td>
            <td>-</td>
            <td>
              <button v-if="editingClassId === cls.id" class="btn-sm save" @click="saveClass(cls.id)">保存</button>
              <button v-if="editingClassId === cls.id" class="btn-sm" @click="editingClassId = null">取消</button>
              <button v-if="editingClassId !== cls.id" class="btn-sm" @click="startEditClass(cls)">编辑</button>
              <button class="btn-sm" @click="regenCode(cls.id)">换码</button>
              <button class="btn-sm danger" @click="deleteClass(cls.id)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="classes.length === 0" class="empty">暂无班级</div>
    </section>

    <!-- 消息审计 -->
    <section v-if="tab === 'audit'" class="panel">
      <div class="panel-header">
        <h2>消息记录</h2>
        <div class="filters">
          <select v-model.number="auditClassId" @change="loadAudit">
            <option :value="null">全部班级</option>
            <option v-for="cls in classes" :key="cls.id" :value="cls.id">{{ cls.name }}</option>
          </select>
        </div>
      </div>
      <table class="data-table">
        <thead>
          <tr><th>ID</th><th>班级</th><th>内容</th><th>方式</th><th>时间</th></tr>
        </thead>
        <tbody>
          <tr v-for="msg in auditItems" :key="msg.id">
            <td>{{ msg.id }}</td>
            <td>{{ classNameMap[msg.class_id] || msg.class_id }}</td>
            <td>{{ msg.content }}</td>
            <td>{{ msg.display_mode === 'popup' ? '弹窗' : '跑马灯' }}</td>
            <td>{{ formatTime(msg.sent_at) }}</td>
          </tr>
        </tbody>
      </table>
      <div class="pagination">
        <span>共 {{ auditTotal }} 条</span>
        <button :disabled="auditPage <= 1" @click="auditPage--; loadAudit()">上一页</button>
        <span>{{ auditPage }} / {{ Math.ceil(auditTotal / auditLimit) || 1 }}</span>
        <button :disabled="auditPage * auditLimit >= auditTotal" @click="auditPage++; loadAudit()">下一页</button>
      </div>
    </section>

    <!-- 新建班级弹窗 -->
    <div v-if="showCreateClass" class="modal" @click.self="showCreateClass = false">
      <div class="modal-card">
        <h3>新建班级</h3>
        <input v-model="newClassName" placeholder="班级名称" class="modal-input" />
        <div class="modal-actions">
          <button @click="showCreateClass = false">取消</button>
          <button class="btn-primary" @click="createClass">创建</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from "vue";

interface ClassInfo { id: number; name: string; pairing_code: string; }
interface AuditItem { id: number; class_id: number; content: string; display_mode: string; sent_at: string; }

const tab = ref<"classes" | "audit">("classes");
const classes = ref<ClassInfo[]>([]);
const classNameMap = computed(() => Object.fromEntries(classes.value.map(c => [c.id, c.name])));

// Class management
const showCreateClass = ref(false);
const newClassName = ref("");
const editingClassId = ref<number | null>(null);
const editClassName = ref("");

// Audit
const auditClassId = ref<number | null>(null);
const auditItems = ref<AuditItem[]>([]);
const auditTotal = ref(0);
const auditPage = ref(1);
const auditLimit = 50;

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString("zh-CN");
}

async function apiRequest(method: string, url: string, body?: any) {
  const opts: RequestInit = { method, headers: { "Content-Type": "application/json" } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(`${method} ${url} failed: ${res.status}`);
  if (res.status === 204) return null;
  return res.json();
}

async function loadClasses() {
  try {
    // Use teacher login to get classes - admin uses a special teacher account
    const loginRes = await apiRequest("POST", "/api/auth/teacher-login", { name: "管理员" });
    const token = loginRes.token;
    const res = await fetch("/api/classes", { headers: { Authorization: `Bearer ${token}` } });
    if (res.ok) classes.value = await res.json();
  } catch { /* ignore */ }
}

async function createClass() {
  if (!newClassName.value.trim()) return;
  try {
    const loginRes = await apiRequest("POST", "/api/auth/teacher-login", { name: "管理员" });
    await fetch("/api/classes", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${loginRes.token}` },
      body: JSON.stringify({ name: newClassName.value.trim() }),
    });
    newClassName.value = "";
    showCreateClass.value = false;
    await loadClasses();
  } catch { /* ignore */ }
}

function startEditClass(cls: ClassInfo) {
  editingClassId.value = cls.id;
  editClassName.value = cls.name;
}

async function saveClass(id: number) {
  try {
    const loginRes = await apiRequest("POST", "/api/auth/teacher-login", { name: "管理员" });
    await fetch(`/api/classes/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${loginRes.token}` },
      body: JSON.stringify({ name: editClassName.value.trim() }),
    });
    editingClassId.value = null;
    await loadClasses();
  } catch { /* ignore */ }
}

async function deleteClass(id: number) {
  if (!confirm("确定删除该班级？相关消息也会被删除。")) return;
  try {
    const loginRes = await apiRequest("POST", "/api/auth/teacher-login", { name: "管理员" });
    await fetch(`/api/classes/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${loginRes.token}` },
    });
    await loadClasses();
  } catch { /* ignore */ }
}

async function regenCode(id: number) {
  try {
    const loginRes = await apiRequest("POST", "/api/auth/teacher-login", { name: "管理员" });
    await fetch(`/api/classes/${id}/regenerate-code`, {
      method: "POST",
      headers: { Authorization: `Bearer ${loginRes.token}` },
    });
    await loadClasses();
  } catch { /* ignore */ }
}

async function loadAudit() {
  try {
    const loginRes = await apiRequest("POST", "/api/auth/teacher-login", { name: "管理员" });
    const params = new URLSearchParams({ page: String(auditPage.value), limit: String(auditLimit) });
    if (auditClassId.value) params.set("class_id", String(auditClassId.value));
    const res = await fetch(`/api/messages/audit?${params}`, {
      headers: { Authorization: `Bearer ${loginRes.token}` },
    });
    if (res.ok) {
      const data = await res.json();
      auditItems.value = data.items;
      auditTotal.value = data.total;
    }
  } catch { /* ignore */ }
}

function exportMessages() {
  const params = new URLSearchParams();
  if (auditClassId.value) params.set("class_id", String(auditClassId.value));
  window.open(`/api/messages/export?${params}`, "_blank");
}

function printPairingCodes() {
  const printWindow = window.open("", "_blank");
  if (!printWindow) return;
  const rows = classes.value.map(c => `<tr><td>${c.name}</td><td style="font-size:24px;font-weight:bold;letter-spacing:0.3em">${c.pairing_code}</td></tr>`).join("");
  printWindow.document.write(`<html><head><title>配对码清单</title><style>body{font-family:system-ui;padding:20px}table{width:100%;border-collapse:collapse}th,td{border:1px solid #ddd;padding:12px;text-align:left}th{background:#f5f5f5}</style></head><body><h1>配对码清单</h1><table><tr><th>班级</th><th>配对码</th></tr>${rows}</table></body></html>`);
  printWindow.document.close();
  printWindow.print();
}

onMounted(async () => {
  await loadClasses();
  await loadAudit();
});
</script>

<style scoped>
.dashboard { max-width: 1000px; margin: 0 auto; padding: 16px; }
.header { display: flex; align-items: center; justify-content: space-between; padding: 16px 0; }
.header h1 { font-size: 1.2rem; color: #1a1a2e; }
.header-actions { display: flex; gap: 8px; }
.btn-print, .btn-export { padding: 8px 14px; border: 1px solid #c5cae9; border-radius: 8px; background: #fff; color: #667eea; font-size: 0.82rem; cursor: pointer; }
.tabs { display: flex; gap: 4px; margin-bottom: 16px; }
.tabs button { flex: 1; padding: 10px; border: none; background: #e8eaf6; border-radius: 8px 8px 0 0; cursor: pointer; font-size: 0.9rem; }
.tabs button.active { background: #fff; font-weight: 600; color: #667eea; }
.panel { background: #fff; border-radius: 0 0 12px 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.panel-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.panel-header h2 { font-size: 1rem; color: #333; }
.btn-add { padding: 6px 14px; background: #667eea; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 0.82rem; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { padding: 10px 12px; border-bottom: 1px solid #f0f0f0; text-align: left; font-size: 0.85rem; }
.data-table th { background: #fafafa; font-weight: 600; color: #666; }
.pairing-code { font-family: monospace; font-size: 1rem; background: #f5f5f5; padding: 2px 8px; border-radius: 4px; }
.inline-input { padding: 4px 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 0.85rem; }
.btn-sm { padding: 3px 8px; border: 1px solid #ddd; border-radius: 4px; background: #fff; font-size: 0.75rem; cursor: pointer; margin-right: 4px; }
.btn-sm.save { background: #667eea; color: #fff; border-color: #667eea; }
.btn-sm.danger { color: #e74c3c; }
.filters select { padding: 6px 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 0.85rem; }
.empty { text-align: center; padding: 20px; color: #aaa; }
.pagination { display: flex; align-items: center; justify-content: center; gap: 12px; margin-top: 16px; font-size: 0.82rem; }
.pagination button { padding: 4px 12px; border: 1px solid #ddd; border-radius: 4px; background: #fff; cursor: pointer; }
.pagination button:disabled { opacity: 0.4; }
.modal { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal-card { background: #fff; border-radius: 12px; padding: 24px; width: 90%; max-width: 360px; }
.modal-card h3 { margin-bottom: 16px; }
.modal-input { width: 100%; padding: 10px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 0.9rem; outline: none; box-sizing: border-box; margin-bottom: 16px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; }
.modal-actions button { padding: 8px 16px; border-radius: 6px; cursor: pointer; }
.modal-actions button:first-child { border: 1px solid #ddd; background: #fff; }
.btn-primary { background: #667eea; color: #fff; border: none; }
</style>
