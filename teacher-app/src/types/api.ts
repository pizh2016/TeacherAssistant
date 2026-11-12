/**
 * API 类型定义 — 对齐 docs/02 后端 API 契约 (Phase 2)
 */

// ---- Auth ----
export interface PairingLoginRequest {
  pairing_code: string;
  role: "teacher" | "display";
}

export interface TeacherLoginRequest {
  name: string;
}

export interface ClassInfo {
  id: number;
  name: string;
  pairing_code: string;
}

export interface ClassCreateRequest {
  name: string;
}

export interface ClassCreateResponse {
  id: number;
  name: string;
  pairing_code: string;
  message: string;
}

export interface ClassUpdateRequest {
  name: string;
}

export interface LoginResponse {
  token: string;
  role: string;
  teacher_id: number | null;
  teacher_name: string;
  classes: ClassInfo[];
}

// ---- Messages ----
export type DisplayMode = "popup" | "marquee";
export type ReminderLevel = "normal" | "strong";
export type ScheduleType = "once" | "daily" | "weekly" | "cron";

export interface MessageCreate {
  class_id: number;
  content: string;
  display_mode: DisplayMode;
  reminder_level: ReminderLevel;
  duration: number;
  tts_enabled: boolean;
  tts_repeat?: number;
  image_path?: string | null;
}

export interface BatchMessageCreate {
  class_ids: number[];
  content: string;
  display_mode: DisplayMode;
  reminder_level: ReminderLevel;
  duration: number;
  tts_enabled: boolean;
  tts_repeat?: number;
  image_path?: string | null;
}

export interface MessageOut {
  id: number;
  teacher_id: number;
  class_id: number;
  content: string;
  display_mode: DisplayMode;
  reminder_level: ReminderLevel;
  duration: number;
  tts_enabled: boolean;
  tts_repeat: number;
  audio_path: string | null;
  image_path: string | null;
  sent_at: string;
  teacher_name: string | null;
}

export interface SendResponse {
  id: number;
  status: string;
  sent_at: string;
}

export interface BatchSendResponse {
  ids: number[];
  status: string;
  sent_at: string;
  class_count: number;
}

export interface HistoryPage {
  total: number;
  page: number;
  limit: number;
  items: MessageOut[];
}

// ---- Scheduled Messages ----
export interface ScheduledMessageCreate {
  class_id: number;
  content: string;
  display_mode: DisplayMode;
  reminder_level: ReminderLevel;
  duration: number;
  tts_enabled: boolean;
  image_path?: string | null;
  schedule_type: ScheduleType;
  schedule_at?: string | null;
  cron_expression?: string | null;
}

export interface ScheduledMessageOut {
  id: number;
  teacher_id: number;
  class_id: number;
  content: string;
  display_mode: string;
  reminder_level: string;
  duration: number;
  tts_enabled: boolean;
  image_path: string | null;
  schedule_type: string;
  schedule_at: string | null;
  cron_expression: string | null;
  is_active: boolean;
  created_at: string;
}

// ---- Templates ----
export interface TemplateOut {
  id: number;
  content: string;
  sort_order: number;
  created_at: string;
}

// ---- Image Upload ----
export interface ImageUploadResponse {
  image_path: string;
  url: string;
}

// ---- Error ----
export interface ApiError {
  error: {
    code: string;
    message: string;
    status: number;
  };
}
