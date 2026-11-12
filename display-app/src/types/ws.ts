/**
 * 大屏端类型定义 — 对齐 docs/02 后端 API 契约 (Phase 2)
 */

// ---- WebSocket 事件 ----
export interface JoinClassEvent {
  type: "join_class";
  class_id: number;
  token: string;
}

export interface HeartbeatEvent {
  type: "heartbeat";
  timestamp_ms: number;
}

export interface ConnectionAckEvent {
  type: "connection_ack";
  status: "ok";
  class_id: number;
  class_name: string;
}

export interface NewMessageEvent {
  type: "new_message";
  id: number;
  class_id: number;
  content: string;
  display_mode: "popup" | "marquee";
  reminder_level: "normal" | "strong";
  duration: number;
  tts_enabled: boolean;
  tts_repeat: number;
  audio_path: string | null;
  image_path: string | null;
  sent_at: string;
  teacher_name: string | null;
}

export interface RecallMessageEvent {
  type: "recall_message";
  message_id: number;
  class_id: number;
}

export interface PongEvent {
  type: "pong";
  timestamp_ms: number;
}

export interface ReconnectHintEvent {
  type: "reconnect_hint";
  last_message_id: number;
}

export type ServerEvent =
  | ConnectionAckEvent
  | NewMessageEvent
  | RecallMessageEvent
  | PongEvent
  | ReconnectHintEvent;

// ---- Auth ----
export interface LoginResponse {
  token: string;
  role: string;
  teacher_id: null;
  classes: { id: number; name: string; pairing_code: string }[];
}

// ---- 连接状态 ----
export type ConnectionStatus =
  | "disconnected"
  | "connecting"
  | "authenticating"
  | "connected"
  | "reconnecting";

// ---- 消息展示状态 ----
export interface DisplayMessage {
  id: number;
  content: string;
  display_mode: "popup" | "marquee";
  reminder_level: "normal" | "strong";
  duration: number;
  tts_enabled: boolean;
  tts_repeat: number;
  image_path: string | null;
  sent_at: string | null;
  teacher_name: string | null;
  receivedAt: number;
}
