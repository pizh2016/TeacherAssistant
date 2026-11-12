/**
 * 大屏端主组件 — 状态机 + 双模式窗口策略
 *
 * 状态流转：
 *   pairing → standby → displaying → standby
 *     ↑                                  ↓
 *     └──── 配置清除 / token 失效 ───────┘
 *
 * - pairing:  输入配对码，获取 JWT + classId
 * - standby:  WebSocket 连接中/已连接，等待消息
 * - displaying: 收到消息，弹窗或跑马灯展示
 *
 * 双模式窗口策略：
 * - 模式一（pairing / standby）：普通窗口 1280×720，不全屏、不置顶，任务栏可见
 * - 模式二（displaying）：全屏 + screen-saver 级置顶，任务栏隐藏，防屏保
 * - 进入展示态：standby → displaying 时调用 enterStandby()
 * - 退出展示态：displaying → standby 时调用 exitFullscreen()，恢复普通窗口
 * - 回到配对态：standby → pairing 时调用 exitFullscreen()
 *
 * 系统安全接管保障（screen-saver 级别置顶）：
 * - ✅ Win 键可呼出开始菜单
 * - ✅ Ctrl+Shift+Esc 可打开任务管理器
 * - ✅ Ctrl+Alt+Del 可进入安全界面
 * - ❌ 不使用 kiosk 模式（会阻止系统操作）
 */

import { useCallback, useEffect, useRef, useState } from "react";
import PairingView from "./components/PairingView";
import StandbyView from "./components/StandbyView";
import MessageDisplay from "./components/MessageDisplay";
import { useWebSocket } from "./hooks/useWebSocket";
import { useTTS } from "./hooks/useTTS";
import {
  getBackendUrl,
  loadConfig,
  saveConfig,
  clearConfig,
} from "./config";
import type { DisplayConfig } from "./config";
import type { DisplayMessage } from "./types/ws";

type AppState = "pairing" | "standby" | "displaying";

// Maximum number of messages to queue (oldest dropped when exceeded)
const MAX_QUEUE_SIZE = 10;

export default function App() {
  // ---- 持久化配置 ----
  const [config, setConfig] = useState<DisplayConfig | null>(() => loadConfig());
  const [appState, setAppState] = useState<AppState>(
    () => (loadConfig() ? "standby" : "pairing"),
  );

  // ---- 消息队列（使用 ref 避免闭包陈旧值问题） ----
  const currentMessageRef = useRef<DisplayMessage | null>(null);
  const [currentMessage, setCurrentMessage] = useState<DisplayMessage | null>(null);
  const messageQueueRef = useRef<DisplayMessage[]>([]);
  const [queueCount, setQueueCount] = useState(0);

  // ---- 展示态标记（防止队列消息连续触发时重复调用 enterStandby） ----
  const isDisplayingRef = useRef(false);

  // ---- 最近展示过的消息（用于待机画面展示） ----
  const [recentMessages, setRecentMessages] = useState<DisplayMessage[]>([]);

  // ---- 后端健康状态 ----
  const [backendAlive, setBackendAlive] = useState(true);

  // ---- TTS ----
  const { speak, ttsRepeatCurrent, ttsRepeatTotal } = useTTS();

  // ---- 消息处理回调 ----
  const handleMessage = useCallback((msg: DisplayMessage) => {
    console.log('[App] handleMessage called: id=', msg.id, 'content=', msg.content?.substring(0, 30), 'tts_enabled=', msg.tts_enabled);
    if (currentMessageRef.current) {
      // 正在展示中，排队等待
      messageQueueRef.current.push(msg);
      console.log('[App] message queued, queue length=', messageQueueRef.current.length);
      // 超出队列上限时，丢弃最旧的消息
      if (messageQueueRef.current.length > MAX_QUEUE_SIZE) {
        const dropped = messageQueueRef.current.shift();
        if (dropped) {
          console.warn(`[Queue] 消息队列已满(${MAX_QUEUE_SIZE})，丢弃旧消息 id=${dropped.id}`);
        }
      }
      setQueueCount(messageQueueRef.current.length);
    } else {
      currentMessageRef.current = msg;
      setCurrentMessage(msg);
      console.log('[App] setting appState to displaying (new message)');
      setAppState("displaying");
      setQueueCount(0);
      // 新消息到来时清除最近消息列表
      setRecentMessages([]);
      // TTS 播报
      if (msg.tts_enabled) {
        speak(msg.content, msg.tts_repeat || 1);
      }
      // 注意：不在这里调用 enterStandby()，而是通过 useEffect 在 appState 变为 displaying 后触发
      // 这样可以确保 React 已完成 MessageDisplay 组件的渲染
    }
  }, [speak]);

  // ---- 消息撤回回调 ----
  const handleRecall = useCallback((messageId: number) => {
    console.log('[App] handleRecall called: messageId=', messageId);
    // 从队列中移除被撤回的消息（无论当前展示的是哪条）
    messageQueueRef.current = messageQueueRef.current.filter(m => m.id !== messageId);
    setQueueCount(messageQueueRef.current.length);

    // 如果当前展示的是被撤回的消息，立即移除（displaying → standby，退出全屏）
    if (currentMessageRef.current && currentMessageRef.current.id === messageId) {
      currentMessageRef.current = null;
      setCurrentMessage(null);
      setAppState("standby");
      isDisplayingRef.current = false;
      // 退出全屏恢复普通窗口
      window.electronAPI?.exitFullscreen();
      console.log('[App] handleRecall: current message recalled, exiting fullscreen');
    }
  }, []);

  // ---- Token 失效回调（4401）—— 使用配对码重新登录 ----
  const handleUnauthorized = useCallback(async () => {
    if (!config?.pairingCode) {
      console.warn("[App] handleUnauthorized: no pairingCode, cannot re-authenticate");
      return;
    }
    console.log("[App] handleUnauthorized: re-authenticating with pairingCode=", config.pairingCode);
    try {
      const res = await fetch(`${getBackendUrl()}/api/auth/pairing-login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pairing_code: config.pairingCode, role: "display" }),
      });
      if (!res.ok) {
        console.error("[App] handleUnauthorized: re-login failed, status=", res.status);
        return;
      }
      const data = await res.json();
      const cls = data.classes?.[0];
      if (!cls) {
        console.error("[App] handleUnauthorized: no class in response");
        return;
      }
      const newConfig: DisplayConfig = {
        classId: cls.id,
        className: cls.name,
        token: data.token,
        pairingCode: config.pairingCode,
      };
      console.log("[App] handleUnauthorized: re-login successful, updating config");
      saveConfig(newConfig);
      setConfig(newConfig);
      // config 更新后，useWebSocket 会自动重新连接
    } catch (err) {
      console.error("[App] handleUnauthorized: re-login error:", err);
    }
  }, [config]);

  // ---- WebSocket ----
  const ws = useWebSocket({
    backendUrl: config ? getBackendUrl() : "",
    classId: config?.classId ?? null,
    token: config?.token ?? null,
    onMessage: handleMessage,
    onRecall: handleRecall,
    onUnauthorized: handleUnauthorized,
  });

  // ---- 托盘提示文本随连接状态更新 ----
  useEffect(() => {
    const statusMap: Record<string, string> = {
      disconnected: "喊话小喇叭 - 未连接",
      connecting: "喊话小喇叭 - 连接中...",
      authenticating: "喊话小喇叭 - 鉴权中...",
      connected: `喊话小喇叭 - ${config?.className || "已连接"}`,
      reconnecting: "喊话小喇叭 - 重连中...",
    };
    const tooltip = statusMap[ws.status] || "喊话小喇叭 - 大屏端";
    window.electronAPI?.setTrayTooltip(tooltip);
  }, [ws.status, config?.className]);

  // ---- 配对成功回调 ----
  function handlePaired(newConfig: DisplayConfig) {
    console.log("[App] handlePaired: newConfig=", { classId: newConfig.classId, className: newConfig.className, pairingCode: newConfig.pairingCode });
    saveConfig(newConfig);
    setConfig(newConfig);
    setAppState("standby");
    // pairing → standby：保持普通窗口（不全屏、不置顶），等待消息到来时再切换展示态
  }

  // ---- 重置到配对模式 ----
  function handleReset() {
    console.log("[App] handleReset: clearing config and returning to pairing");
    clearConfig();
    setConfig(null);
    setAppState("pairing");
    // 退出全屏 → 普通窗口
    window.electronAPI?.exitFullscreen();
  }

  // ---- 仅退出全屏（保留配置，保持 standby 状态）----
  function handleExitFullscreen() {
    console.log("[App] handleExitFullscreen: exiting fullscreen, staying in standby");
    window.electronAPI?.exitFullscreen();
  }

  // ---- 消息展示结束 ----
  const handleDismiss = useCallback(() => {
    console.log('[App] handleDismiss called');
    const finished = currentMessageRef.current;
    currentMessageRef.current = null;
    setCurrentMessage(null);
    setAppState("standby");

    // 将刚展示完的消息加入最近消息列表（最多 5 条）
    if (finished) {
      setRecentMessages(prev => [finished, ...prev].slice(0, 5));
    }

    // 展示队列中的下一条
    const next = messageQueueRef.current.shift();
    setQueueCount(messageQueueRef.current.length);
    if (next) {
      // 有下一条消息 → 保持全屏，直接展示
      // 注意：不重置 isDisplayingRef，500ms 后 setAppState("displaying") 会触发 useEffect
      // 但 isDisplayingRef 仍为 true，所以不会重复调用 enterStandby()
      setTimeout(() => {
        currentMessageRef.current = next;
        setCurrentMessage(next);
        console.log('[App] setting appState to displaying (next message in queue)');
        setAppState("displaying");
        if (next.tts_enabled) {
          speak(next.content, next.tts_repeat || 1);
        }
        // 已在展示态（全屏+置顶），无需额外窗口操作
      }, 500);
    } else {
      // 队列空了 → displaying → standby，退出全屏恢复普通窗口
      isDisplayingRef.current = false;
      console.log('[App] queue empty, calling exitFullscreen()');
      window.electronAPI?.exitFullscreen();
    }
  }, [speak]);

  // ---- 进入展示态时触发全屏（useEffect 确保组件已渲染） ----
  useEffect(() => {
    if (appState === "displaying") {
      // 防止队列消息连续触发时重复调用 enterStandby
      if (isDisplayingRef.current) {
        console.log('[App] already in display mode, skipping enterStandby()');
        return;
      }
      console.log('[App] === appState changed to displaying ===');
      if (!window.electronAPI) {
        console.error('[App] window.electronAPI is undefined! Not running in Electron environment?');
        console.error('[App] window keys:', Object.keys(window).filter(k => k.toLowerCase().includes('electron')));
        return;
      }
      console.log('[App] calling window.electronAPI.enterStandby()...');
      isDisplayingRef.current = true;
      window.electronAPI.enterStandby();
      console.log('[App] enterStandby() call completed');
    }
  }, [appState]);

  // ---- 键盘快捷键 ----
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        if (appState === "displaying") {
          // Esc 在展示态 → 提前结束展示，回到待机态（退出全屏）
          handleDismiss();
        } else if (appState === "standby") {
          // Esc 在待机态 → 仅退出全屏，保留配置，保持 standby 状态
          handleExitFullscreen();
        }
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [appState, handleDismiss]);

  // ---- 后端健康检查（所有环境统一使用 HTTP 轮询） ----
  useEffect(() => {
    const checkHealth = async () => {
      const url = `${getBackendUrl()}/health`;
      try {
        const res = await fetch(url);
        setBackendAlive(res.ok);
        if (!res.ok) {
          console.warn("[App] Health check failed: status=", res.status, "url=", url);
        }
      } catch (err) {
        setBackendAlive(false);
        console.warn("[App] Health check error:", err, "url=", url);
      }
    };
    checkHealth();
    const timer = setInterval(checkHealth, 5000);
    return () => clearInterval(timer);
  }, []);

  // ---- 断线补发 ----
  useEffect(() => {
    if (ws.status === "connected" && config) {
      // 仅在已有游标（非首次启动）时补发，避免重启后重复播放全部历史
      if (ws.lastMessageId > 0) {
        ws.fetchMissedMessages(ws.lastMessageId);
      }
    }
  }, [ws.status]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- 渲染 ----
  if (appState === "pairing" || !config) {
    return <PairingView onPaired={handlePaired} />;
  }

  if (appState === "displaying" && currentMessage) {
    return (
      <MessageDisplay
        message={currentMessage}
        queueCount={queueCount}
        onDismiss={handleDismiss}
        ttsRepeatCurrent={ttsRepeatCurrent}
        ttsRepeatTotal={ttsRepeatTotal}
      />
    );
  }

  return (
    <StandbyView
      className={config.className}
      pairingCode={config.pairingCode}
      connectionStatus={ws.status}
      backendAlive={backendAlive}
      recentMessages={recentMessages}
      onReset={handleReset}
    />
  );
}
