/**
 * API 客户端 — 统一处理 JWT header、错误码、请求转发 (Phase 2)
 *
 * 开发时走 Vite 代理（相对路径 /api/...），
 * 生产时教师端由后端静态托管，同源直接请求。
 */

import type {
  LoginResponse,
  ClassInfo,
  ClassCreateRequest,
  ClassCreateResponse,
  ClassUpdateRequest,
  MessageCreate,
  BatchMessageCreate,
  SendResponse,
  BatchSendResponse,
  HistoryPage,
  MessageOut,
  ScheduledMessageCreate,
  ScheduledMessageOut,
  TemplateOut,
  ImageUploadResponse,
  ApiError,
} from "@/types/api";

const TOKEN_KEY = "horn_token";

// ---- Token 管理 ----
export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

// ---- 底层请求 ----
async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const token = getToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const err: ApiError = await res.json().catch(() => ({
      error: { code: "UNKNOWN", message: res.statusText, status: res.status },
    }));

    // 401 → token 失效，清除并跳转登录
    if (res.status === 401) {
      clearToken();
      window.location.hash = "#/login";
    }
    throw err;
  }

  // 204 No Content has no body — return undefined for void responses
  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

// ---- Auth API ----
export async function pairingLogin(
  pairingCode: string,
): Promise<LoginResponse> {
  return request<LoginResponse>("POST", "/api/auth/pairing-login", {
    pairing_code: pairingCode,
    role: "display",
  });
}

export async function teacherLogin(name: string): Promise<LoginResponse> {
  return request<LoginResponse>("POST", "/api/auth/teacher-login", {
    name,
  });
}

// ---- Classes API ----
export async function getClasses(): Promise<ClassInfo[]> {
  return request<ClassInfo[]>("GET", "/api/classes");
}

export async function createClass(
  payload: ClassCreateRequest,
): Promise<ClassCreateResponse> {
  return request<ClassCreateResponse>("POST", "/api/classes", payload);
}

export async function updateClass(
  classId: number,
  payload: ClassUpdateRequest,
): Promise<ClassInfo> {
  return request<ClassInfo>("PUT", `/api/classes/${classId}`, payload);
}

export async function deleteClass(classId: number): Promise<void> {
  return request<void>("DELETE", `/api/classes/${classId}`);
}

export async function regeneratePairingCode(
  classId: number,
): Promise<ClassInfo> {
  return request<ClassInfo>("POST", `/api/classes/${classId}/regenerate-code`);
}

// ---- Messages API ----
export async function sendMessage(payload: MessageCreate): Promise<SendResponse> {
  return request<SendResponse>("POST", "/api/messages", payload);
}

export async function sendBatchMessage(
  payload: BatchMessageCreate,
): Promise<BatchSendResponse> {
  return request<BatchSendResponse>("POST", "/api/messages/batch", payload);
}

export async function recallMessage(messageId: number): Promise<{ status: string; message_id: number }> {
  return request("POST", `/api/messages/${messageId}/recall`);
}

export async function deleteMessage(messageId: number): Promise<void> {
  return request<void>("DELETE", `/api/messages/${messageId}`);
}

export async function uploadImage(file: File): Promise<ImageUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch("/api/messages/upload", {
    method: "POST",
    headers,
    body: formData,
  });
  if (!res.ok) {
    const err: ApiError = await res.json().catch(() => ({
      error: { code: "UNKNOWN", message: res.statusText, status: res.status },
    }));
    throw err;
  }
  return res.json() as Promise<ImageUploadResponse>;
}

export async function getHistory(
  page = 1,
  limit = 20,
  classId?: number,
): Promise<HistoryPage> {
  const params = new URLSearchParams();
  params.set("page", String(page));
  params.set("limit", String(limit));
  if (classId !== undefined) {
    params.set("class_id", String(classId));
  }
  return request<HistoryPage>("GET", `/api/messages/history?${params}`);
}

export async function getLatest(
  classId: number,
  since?: number,
): Promise<MessageOut[]> {
  const params = new URLSearchParams();
  params.set("class_id", String(classId));
  if (since !== undefined) {
    params.set("since", String(since));
  }
  return request<MessageOut[]>("GET", `/api/messages/latest?${params}`);
}

// ---- Scheduled Messages API ----
export async function createScheduledMessage(
  payload: ScheduledMessageCreate,
): Promise<ScheduledMessageOut> {
  return request<ScheduledMessageOut>("POST", "/api/messages/scheduled", payload);
}

export async function getScheduledMessages(): Promise<ScheduledMessageOut[]> {
  return request<ScheduledMessageOut[]>("GET", "/api/messages/scheduled");
}

export async function deleteScheduledMessage(id: number): Promise<void> {
  return request<void>("DELETE", `/api/messages/scheduled/${id}`);
}

export async function toggleScheduledMessage(id: number): Promise<ScheduledMessageOut> {
  return request<ScheduledMessageOut>("PUT", `/api/messages/scheduled/${id}/toggle`);
}

// ---- Templates API ----
export async function getTemplates(): Promise<TemplateOut[]> {
  return request<TemplateOut[]>("GET", "/api/templates");
}

export async function createTemplate(content: string): Promise<TemplateOut> {
  return request<TemplateOut>("POST", "/api/templates", { content });
}

export async function updateTemplate(id: number, content: string): Promise<TemplateOut> {
  return request<TemplateOut>("PUT", `/api/templates/${id}`, { content });
}

export async function deleteTemplate(id: number): Promise<void> {
  return request<void>("DELETE", `/api/templates/${id}`);
}

// ---- Audit & Export API ----
export async function getAuditMessages(
  params: {
    class_id?: number;
    teacher_id?: number;
    start_time?: string;
    end_time?: string;
    page?: number;
    limit?: number;
  } = {},
): Promise<HistoryPage> {
  const sp = new URLSearchParams();
  if (params.class_id) sp.set("class_id", String(params.class_id));
  if (params.teacher_id) sp.set("teacher_id", String(params.teacher_id));
  if (params.start_time) sp.set("start_time", params.start_time);
  if (params.end_time) sp.set("end_time", params.end_time);
  sp.set("page", String(params.page || 1));
  sp.set("limit", String(params.limit || 50));
  return request<HistoryPage>("GET", `/api/messages/audit?${sp}`);
}

export function getExportUrl(params: {
  class_id?: number;
  teacher_id?: number;
  start_time?: string;
  end_time?: string;
} = {}): string {
  const sp = new URLSearchParams();
  if (params.class_id) sp.set("class_id", String(params.class_id));
  if (params.teacher_id) sp.set("teacher_id", String(params.teacher_id));
  if (params.start_time) sp.set("start_time", params.start_time);
  if (params.end_time) sp.set("end_time", params.end_time);
  return `/api/messages/export?${sp}`;
}
