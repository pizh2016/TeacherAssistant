/**
 * 大屏端待机页面 — 等待消息
 *
 * 显示：
 * - 班级名称
 * - 配对码
 * - 连接状态
 * - 当前时间（时钟）
 * - 服务器地址（可修改）
 */

import { useEffect, useState } from "react";
import type { ConnectionStatus, DisplayMessage } from "../types/ws";
import { getBackendUrl, getStoredBackendUrl, setBackendUrl } from "../config";

/** Format ISO timestamp to readable date+time */
function formatTime(iso: string): string {
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

interface StandbyViewProps {
  className: string;
  pairingCode: string;
  connectionStatus: ConnectionStatus;
  backendAlive: boolean;
  recentMessages: DisplayMessage[];
  onReset?: () => void;
}

export default function StandbyView({
  className,
  pairingCode,
  connectionStatus,
  backendAlive,
  recentMessages,
  onReset,
}: StandbyViewProps) {
  const [time, setTime] = useState(new Date());
  const [fadeRecent, setFadeRecent] = useState(false);

  // 服务器地址编辑
  const [showServerEditor, setShowServerEditor] = useState(false);
  const [serverUrlInput, setServerUrlInput] = useState(getStoredBackendUrl() || "");
  const [serverUrlSaved, setServerUrlSaved] = useState(false);

  function handleServerUrlSave() {
    const url = serverUrlInput.trim().replace(/\/+$/, "");
    if (!url) return;
    setBackendUrl(url);
    setServerUrlSaved(true);
    setTimeout(() => {
      setServerUrlSaved(false);
      setShowServerEditor(false);
    }, 1500);
  }

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (recentMessages.length > 0) {
      setFadeRecent(false);
      const timer = setTimeout(() => setFadeRecent(true), 10000);
      return () => clearTimeout(timer);
    } else {
      setFadeRecent(false);
    }
  }, [recentMessages]);

  const statusText = {
    disconnected: "未连接",
    connecting: "连接中...",
    authenticating: "鉴权中...",
    connected: "已连接",
    reconnecting: "重连中...",
  }[connectionStatus];

  const statusColor =
    connectionStatus === "connected"
      ? "#4ade80"
      : connectionStatus === "reconnecting"
        ? "#fbbf24"
        : "#ef4444";

  const timeStr = time.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

  const dateStr = time.toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  });

  return (
    <div style={styles.page}>
      {/* 上半区：时钟 + 日期 */}
      <div style={styles.clockBlock}>
        <div style={styles.clock}>{timeStr}</div>
        <div style={styles.date}>{dateStr}</div>
      </div>

      {/* 班级信息 */}
      <div style={styles.classInfo}>
        <div style={styles.classLabel}>当前班级</div>
        <div style={styles.className}>{className}</div>
      </div>

      {/* 最近消息 */}
      {recentMessages.length > 0 && (
        <div
          style={{
            ...styles.recentSection,
            opacity: fadeRecent ? 0 : 1,
            transition: "opacity 1.5s ease",
          }}
        >
          <div style={styles.recentTitle}>最近播报</div>
          {recentMessages.slice(0, 3).map((msg) => (
            <div key={msg.id} style={styles.recentItem}>
              <span style={styles.recentContent}>
                {msg.content.length > 30
                  ? msg.content.slice(0, 30) + "…"
                  : msg.content}
              </span>
              {(msg.teacher_name || msg.sent_at) && (
                <span style={styles.recentMeta}>
                  {msg.teacher_name && <span>{msg.teacher_name}</span>}
                  {msg.teacher_name && msg.sent_at && <span> · </span>}
                  {msg.sent_at && <span>{formatTime(msg.sent_at)}</span>}
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 配对码 */}
      <div style={styles.pairingBox}>
        <div style={styles.pairingLabel}>配对码</div>
        <div style={styles.pairingCode}>{pairingCode}</div>
      </div>

      {/* 底部操作栏 */}
      <div style={styles.footer}>
        {/* 状态 + 服务器地址（紧凑左右布局） */}
        <div style={styles.footerLeft}>
          <div style={styles.statusInline}>
            <div style={{ ...styles.statusDot, background: statusColor }} />
            <span style={{ color: statusColor, fontSize: "0.82rem" }}>
              {statusText}
            </span>
            {!backendAlive && (
              <span style={{ color: "#ef4444", fontSize: "0.75rem", marginLeft: 8 }}>
                后端离线
              </span>
            )}
          </div>

          {/* 服务器地址 */}
          {!showServerEditor ? (
            <button
              onClick={() => {
                setServerUrlInput(getStoredBackendUrl() || "");
                setShowServerEditor(true);
              }}
              style={styles.serverLink}
              title="点击修改服务器地址"
            >
              🌐 {getBackendUrl()}
            </button>
          ) : (
            <div style={styles.serverEditor}>
              <input
                type="text"
                value={serverUrlInput}
                onChange={(e) => setServerUrlInput(e.target.value)}
                placeholder="http://192.168.1.100:18800"
                style={styles.serverInput}
                autoFocus
              />
              <button
                onClick={handleServerUrlSave}
                disabled={!serverUrlInput.trim()}
                style={{
                  ...styles.serverSaveBtn,
                  opacity: !serverUrlInput.trim() ? 0.4 : 1,
                }}
              >
                {serverUrlSaved ? "✓" : "保存"}
              </button>
              <button
                onClick={() => setShowServerEditor(false)}
                style={styles.serverCancelBtn}
              >
                ✕
              </button>
            </div>
          )}
        </div>

        {/* 右侧操作提示 */}
        <div style={styles.footerRight}>
          <span style={styles.footerText}>Ctrl+Q 退出 · Esc 退出全屏</span>
          {onReset && (
            <button
              onClick={onReset}
              style={styles.resetButton}
              title="清除配对信息，返回配置页面"
            >
              重新配置
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    width: "100vw",
    height: "100vh",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    background: "linear-gradient(180deg, #0f0c29 0%, #1a1a2e 50%, #16213e 100%)",
    color: "#eee",
    fontFamily: "system-ui, -apple-system, sans-serif",
    padding: "2vh 24px",
    boxSizing: "border-box",
    overflow: "hidden",
  },

  // ---- 时钟区 ----
  clockBlock: {
    textAlign: "center",
    marginBottom: "2vh",
  },
  clock: {
    fontSize: "clamp(3.5rem, 7vw, 6rem)",
    fontWeight: 200,
    letterSpacing: "0.05em",
    color: "#fff",
    lineHeight: 1,
  },
  date: {
    fontSize: "clamp(0.85rem, 1.2vw, 1.1rem)",
    color: "rgba(255, 255, 255, 0.35)",
    marginTop: 8,
  },

  // ---- 班级信息 ----
  classInfo: {
    textAlign: "center",
    marginBottom: "1.5vh",
  },
  classLabel: {
    fontSize: "0.82rem",
    color: "rgba(255, 255, 255, 0.35)",
    marginBottom: 4,
  },
  className: {
    fontSize: "clamp(1.5rem, 2.5vw, 2rem)",
    fontWeight: 600,
    color: "#fff",
  },

  // ---- 最近消息 ----
  recentSection: {
    width: "min(60%, 500px)",
    marginBottom: "1.5vh",
  },
  recentTitle: {
    fontSize: "0.72rem",
    color: "rgba(255, 255, 255, 0.25)",
    marginBottom: 6,
    textAlign: "center" as const,
  },
  recentItem: {
    padding: "7px 14px",
    background: "rgba(255, 255, 255, 0.03)",
    borderRadius: 8,
    marginBottom: 5,
    border: "1px solid rgba(255, 255, 255, 0.05)",
  },
  recentContent: {
    display: "block",
    fontSize: "0.82rem",
    color: "rgba(255, 255, 255, 0.65)",
    textAlign: "center" as const,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  recentMeta: {
    display: "block",
    fontSize: "0.68rem",
    color: "rgba(255, 255, 255, 0.3)",
    textAlign: "center" as const,
    marginTop: 2,
  },

  // ---- 配对码 ----
  pairingBox: {
    padding: "14px 36px",
    background: "rgba(255, 255, 255, 0.04)",
    borderRadius: 14,
    textAlign: "center",
    border: "1px solid rgba(255, 255, 255, 0.07)",
    marginBottom: "1.5vh",
  },
  pairingLabel: {
    fontSize: "0.75rem",
    color: "rgba(255, 255, 255, 0.3)",
    marginBottom: 4,
  },
  pairingCode: {
    fontSize: "clamp(1.6rem, 2.5vw, 2.2rem)",
    fontWeight: 700,
    fontFamily: '"Courier New", monospace',
    letterSpacing: "0.3em",
    color: "#667eea",
  },

  // ---- 底部状态点 ----
  statusDot: {
    width: 7,
    height: 7,
    borderRadius: "50%",
  },

  // ---- 服务器地址编辑器 ----
  serverLink: {
    padding: "4px 8px",
    fontSize: "0.72rem",
    color: "rgba(255, 255, 255, 0.3)",
    background: "transparent",
    border: "1px solid rgba(255, 255, 255, 0.06)",
    borderRadius: 6,
    cursor: "pointer",
    whiteSpace: "nowrap" as const,
    overflow: "hidden",
    textOverflow: "ellipsis",
    maxWidth: 220,
    display: "block",
  },
  serverEditor: {
    display: "flex",
    gap: 6,
    alignItems: "center",
  },
  serverInput: {
    width: 180,
    padding: "5px 8px",
    fontSize: "0.72rem",
    border: "1px solid rgba(255, 255, 255, 0.12)",
    borderRadius: 6,
    outline: "none",
    background: "rgba(255, 255, 255, 0.06)",
    color: "#fff",
    boxSizing: "border-box" as const,
  },
  serverSaveBtn: {
    padding: "5px 10px",
    fontSize: "0.72rem",
    fontWeight: 600,
    color: "#fff",
    background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    border: "none",
    borderRadius: 6,
    cursor: "pointer",
    whiteSpace: "nowrap" as const,
    flexShrink: 0,
  },
  serverCancelBtn: {
    padding: "5px 8px",
    fontSize: "0.72rem",
    color: "rgba(255, 255, 255, 0.4)",
    background: "rgba(255, 255, 255, 0.04)",
    border: "1px solid rgba(255, 255, 255, 0.08)",
    borderRadius: 6,
    cursor: "pointer",
    flexShrink: 0,
  },

  // ---- 底部操作栏 ----
  footer: {
    position: "absolute" as const,
    bottom: 20,
    left: 0,
    right: 0,
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 24px",
  },
  footerLeft: {
    display: "flex",
    alignItems: "center",
    gap: 16,
  },
  statusInline: {
    display: "flex",
    alignItems: "center",
    gap: 6,
  },
  footerRight: {
    display: "flex",
    alignItems: "center",
    gap: 12,
  },
  footerText: {
    fontSize: "0.7rem",
    color: "rgba(255, 255, 255, 0.12)",
  },
  resetButton: {
    fontSize: "0.7rem",
    color: "rgba(255, 255, 255, 0.25)",
    background: "rgba(255, 255, 255, 0.03)",
    border: "1px solid rgba(255, 255, 255, 0.08)",
    borderRadius: 4,
    padding: "3px 10px",
    cursor: "pointer",
    transition: "all 0.2s",
  },
};
