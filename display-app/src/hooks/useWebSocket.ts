/**
 * WebSocket 连接管理 hook
 *
 * 协议对齐 docs/02 §5:
 * - 连接后发送 join_class 鉴权
 * - 30s 心跳保活
 * - 接收 new_message 事件
 * - 断线自动重连 + 消息补发
 *
 * 重连机制设计：
 * - 使用 ref 存储最新参数，避免闭包陈旧问题
 * - connect 函数通过 ref 调用，不依赖 React 状态
 * - cleanup 函数被正确保存和管理
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  ConnectionStatus,
  DisplayMessage,
  NewMessageEvent,
  RecallMessageEvent,
  ServerEvent,
} from "../types/ws";

const HEARTBEAT_INTERVAL = 30_000;
const RECONNECT_BASE_DELAY = 2_000;
const RECONNECT_MAX_DELAY = 30_000;
const JOIN_TIMEOUT = 10_000;
const LAST_MSG_ID_KEY = "horn_last_message_id";

interface UseWebSocketOptions {
  backendUrl: string;
  classId: number | null;
  token: string | null;
  onMessage: (msg: DisplayMessage) => void;
  onRecall?: (messageId: number) => void;
  onUnauthorized?: () => void; // Called when token is invalid (4401)
}

export function useWebSocket({
  backendUrl,
  classId,
  token,
  onMessage,
  onRecall,
  onUnauthorized,
}: UseWebSocketOptions) {
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [className, setClassName] = useState<string>("");
  const [lastMessageId, setLastMessageIdState] = useState<number>(
    () => Number(localStorage.getItem(LAST_MSG_ID_KEY) || "0"),
  );

  // Refs for latest values (avoid stale closures)
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;
  const onRecallRef = useRef(onRecall);
  onRecallRef.current = onRecall;
  const onUnauthorizedRef = useRef(onUnauthorized);
  onUnauthorizedRef.current = onUnauthorized;

  // Connection state refs
  const wsRef = useRef<WebSocket | null>(null);
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const joinTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptRef = useRef(0);
  const statusRef = useRef<ConnectionStatus>("disconnected");
  const activeRef = useRef(false); // Prevents stale handlers after HMR/unmount

  // Store latest params in refs to avoid stale closures
  const paramsRef = useRef({ backendUrl, classId, token });
  paramsRef.current = { backendUrl, classId, token };

  // Stable setLastMessageId
  const setLastMessageId = useCallback((id: number) => {
    setLastMessageIdState(id);
    localStorage.setItem(LAST_MSG_ID_KEY, String(id));
  }, []);

  // Stable setStatusSync
  const setStatusSync = useCallback((s: ConnectionStatus) => {
    statusRef.current = s;
    setStatus(s);
  }, []);

  // Stop heartbeat
  const stopHeartbeat = useCallback(() => {
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }
  }, []);

  // Start heartbeat
  const startHeartbeat = useCallback(() => {
    stopHeartbeat();
    heartbeatRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            type: "heartbeat",
            timestamp_ms: Date.now(),
          }),
        );
      }
    }, HEARTBEAT_INTERVAL);
  }, [stopHeartbeat]);

  // Handle server events
  const handleEvent = useCallback(
    (event: ServerEvent) => {
      switch (event.type) {
        case "connection_ack":
          console.log("[WS] connection_ack received, class:", event.class_name);
          setStatusSync("connected");
          setClassName(event.class_name);
          reconnectAttemptRef.current = 0;
          startHeartbeat();
          break;

        case "reconnect_hint":
          setLastMessageId(event.last_message_id);
          break;

        case "new_message": {
          console.log("[WS] new_message event:", JSON.stringify(event));
          const msg: DisplayMessage = {
            id: event.id,
            content: event.content,
            display_mode: event.display_mode,
            reminder_level: event.reminder_level,
            duration: event.duration,
            tts_enabled: event.tts_enabled,
            tts_repeat: event.tts_repeat || 1,
            image_path: event.image_path || null,
            sent_at: event.sent_at || null,
            teacher_name: event.teacher_name || null,
            receivedAt: Date.now(),
          };
          console.log("[WS] DisplayMessage:", { id: msg.id, teacher_name: msg.teacher_name, sent_at: msg.sent_at, tts_repeat: msg.tts_repeat });
          setLastMessageId(event.id);
          onMessageRef.current(msg);
          break;
        }

        case "recall_message": {
          const recallEvt = event as RecallMessageEvent;
          if (onRecallRef.current) {
            onRecallRef.current(recallEvt.message_id);
          }
          break;
        }

        case "pong":
          // Heartbeat response, no action needed
          break;
      }
    },
    [setStatusSync, setClassName, startHeartbeat, setLastMessageId],
  );

  // Refs for connect/scheduleReconnect to avoid stale closures in event handlers
  const connectRef = useRef<() => (() => void) | void>(() => {});
  const scheduleReconnectRef = useRef<() => void>(() => {});

  // Core connect function (uses refs to avoid stale closures)
  const connect = useCallback(() => {
    const { backendUrl: url, classId: cid, token: tok } = paramsRef.current;

    if (!cid || !tok || !url) {
      console.warn("[WS] connect() skipped: classId=", cid, "token=", tok ? "present" : "missing", "backendUrl=", url);
      return;
    }

    const currentWsUrl = url.replace(/^http/, "ws") + `/ws/class/${cid}`;
    console.log("[WS] connect() initiating: wsUrl=", currentWsUrl, "classId=", cid, "attempt=", reconnectAttemptRef.current);

    // Clear previous timers
    if (joinTimerRef.current) {
      clearTimeout(joinTimerRef.current);
      joinTimerRef.current = null;
    }
    stopHeartbeat();

    // Mark previous connection as inactive
    activeRef.current = false;
    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current.onmessage = null;
      wsRef.current.onopen = null;
      wsRef.current.close(1000);
      wsRef.current = null;
    }

    // Mark new connection as active
    activeRef.current = true;
    setStatusSync("connecting");

    const ws = new WebSocket(currentWsUrl);
    wsRef.current = ws;

    // Join timeout
    joinTimerRef.current = setTimeout(() => {
      if (statusRef.current === "connecting" || statusRef.current === "authenticating") {
        console.warn("[WS] join timeout after", JOIN_TIMEOUT, "ms, closing");
        if (wsRef.current === ws) {
          ws.close(4408, "join timeout");
        }
      }
    }, JOIN_TIMEOUT);

    ws.onopen = () => {
      console.log("[WS] onopen: connection established to", currentWsUrl);
      setStatusSync("authenticating");
      ws.send(
        JSON.stringify({
          type: "join_class",
          class_id: cid,
          token: tok,
        }),
      );
    };

    ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data) as ServerEvent;
        if (event.type !== "pong") {
          console.log("[WS] onmessage: type=", event.type);
        }
        handleEvent(event);
      } catch {
        // Ignore non-JSON messages
      }
    };

    ws.onclose = (e) => {
      console.log("[WS] onclose: code=", e.code, "reason=", e.reason, "wasClean=", e.wasClean, "active=", activeRef.current);
      
      // Clear timers
      if (joinTimerRef.current) {
        clearTimeout(joinTimerRef.current);
        joinTimerRef.current = null;
      }
      stopHeartbeat();
      
      // Only clear wsRef if this is the current connection
      if (wsRef.current === ws) {
        wsRef.current = null;
      }

      // Only auto-reconnect if this connection is still active
      if (!activeRef.current) {
        console.log("[WS] onclose: inactive, not reconnecting");
        setStatusSync("disconnected");
        return;
      }

      // Non-permanent close → auto-reconnect
      if (e.code !== 1000 && e.code !== 4401 && e.code !== 4403) {
        console.log("[WS] onclose: scheduling reconnect");
        scheduleReconnectRef.current();
      } else if (e.code === 4401) {
        // Token invalid - try to re-authenticate
        console.log("[WS] onclose: 4401 unauthorized, calling onUnauthorized");
        if (onUnauthorizedRef.current) {
          onUnauthorizedRef.current();
        } else {
          setStatusSync("disconnected");
        }
      } else {
        console.log("[WS] onclose: permanent close code", e.code);
        setStatusSync("disconnected");
      }
    };

    ws.onerror = (e) => {
      console.error("[WS] onerror:", e);
      // onerror will trigger onclose automatically
    };

    // Return cleanup function
    return () => {
      activeRef.current = false;
      if (joinTimerRef.current) {
        clearTimeout(joinTimerRef.current);
        joinTimerRef.current = null;
      }
      if (wsRef.current === ws) {
        ws.close(1000);
        wsRef.current = null;
      }
    };
  }, [stopHeartbeat, setStatusSync, handleEvent]);

  // Keep refs in sync
  connectRef.current = connect;

  // Schedule reconnect with exponential backoff
  const scheduleReconnect = useCallback(() => {
    setStatusSync("reconnecting");
    const delay = Math.min(
      RECONNECT_BASE_DELAY * Math.pow(2, reconnectAttemptRef.current),
      RECONNECT_MAX_DELAY,
    );
    reconnectAttemptRef.current++;
    console.log("[WS] scheduleReconnect: attempt=", reconnectAttemptRef.current, "delay=", delay, "ms");

    // Clear previous reconnect timer
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
    }

    reconnectTimerRef.current = setTimeout(() => {
      console.log("[WS] reconnect timer fired");
      reconnectTimerRef.current = null;
      connectRef.current();
    }, delay);
  }, [setStatusSync]);

  // Keep reconnect ref in sync
  scheduleReconnectRef.current = scheduleReconnect;

  // Main connection effect: only reconnect when classId/token changes
  useEffect(() => {
    if (!classId || !token) {
      console.log("[WS] effect: no classId or token, staying disconnected");
      setStatusSync("disconnected");
      return;
    }

    console.log("[WS] effect: connecting (classId=", classId, "token=", token ? "present" : "missing", ")");
    
    // Clear any pending reconnect
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    const cleanup = connect();

    return () => {
      console.log("[WS] effect cleanup: tearing down connection");
      if (cleanup) cleanup();
      stopHeartbeat();
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };
  }, [classId, token, connect, stopHeartbeat, setStatusSync]);

  // Fetch missed messages after reconnection
  const fetchMissedMessages = useCallback(
    async (sinceId: number) => {
      if (!classId || !token) return;
      try {
        const res = await fetch(
          `${backendUrl}/api/messages/latest?class_id=${classId}&since=${sinceId}`,
          {
            headers: { Authorization: `Bearer ${token}` },
          },
        );
        if (res.ok) {
          const messages: NewMessageEvent[] = await res.json();
          for (const msg of messages) {
            const display: DisplayMessage = {
              id: msg.id,
              content: msg.content,
              display_mode: msg.display_mode,
              reminder_level: msg.reminder_level,
              duration: msg.duration,
              tts_enabled: msg.tts_enabled,
              tts_repeat: msg.tts_repeat || 1,
              image_path: msg.image_path || null,
              sent_at: msg.sent_at || null,
              teacher_name: msg.teacher_name || null,
              receivedAt: Date.now(),
            };
            onMessageRef.current(display);
          }
          if (messages.length > 0) {
            setLastMessageId(messages[messages.length - 1].id);
          }
        }
      } catch {
        // Fetch failure doesn't affect main connection
      }
    },
    [backendUrl, classId, token, setLastMessageId],
  );

  return {
    status,
    className,
    lastMessageId,
    fetchMissedMessages,
    reconnect: connect,
  };
}
