/**
 * 大屏端消息展示组件
 *
 * 两种模式：
 * - popup：全屏居中弹窗，倒计时自动关闭
 * - marquee：跑马灯平滑滚动文本
 *
 * 强提醒 (reminder_level=strong) 时增加闪烁边框效果。
 */

import { useEffect, useRef, useState } from "react";
import type { DisplayMessage } from "../types/ws";
import { getBackendUrl } from "../config";

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

interface MessageDisplayProps {
  message: DisplayMessage;
  queueCount: number;
  onDismiss: () => void;
  ttsRepeatCurrent?: number;
  ttsRepeatTotal?: number;
}

export default function MessageDisplay({
  message,
  queueCount,
  onDismiss,
  ttsRepeatCurrent = 0,
  ttsRepeatTotal = 0,
}: MessageDisplayProps) {
  console.log("[MessageDisplay] message:", { id: message.id, teacher_name: message.teacher_name, sent_at: message.sent_at, tts_repeat: message.tts_repeat });
  const [remaining, setRemaining] = useState(message.duration);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 倒计时
  useEffect(() => {
    setRemaining(message.duration);
    timerRef.current = setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          if (timerRef.current) clearInterval(timerRef.current);
          onDismiss();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [message.duration, onDismiss]);

  // TTS 播报进度信息
  const showTtsProgress = message.tts_enabled && ttsRepeatTotal > 1 && ttsRepeatCurrent > 0;

  if (message.display_mode === "marquee") {
    return <MarqueeDisplay message={message} queueCount={queueCount} remaining={remaining} showTtsProgress={showTtsProgress} ttsRepeatCurrent={ttsRepeatCurrent} ttsRepeatTotal={ttsRepeatTotal} />;
  }

  return <PopupDisplay message={message} queueCount={queueCount} remaining={remaining} showTtsProgress={showTtsProgress} ttsRepeatCurrent={ttsRepeatCurrent} ttsRepeatTotal={ttsRepeatTotal} />;
}

// ============================================================================
// 弹窗模式
// ============================================================================

function PopupDisplay({
  message,
  queueCount,
  remaining,
  showTtsProgress,
  ttsRepeatCurrent,
  ttsRepeatTotal,
}: {
  message: DisplayMessage;
  queueCount: number;
  remaining: number;
  showTtsProgress: boolean;
  ttsRepeatCurrent: number;
  ttsRepeatTotal: number;
}) {
  const isStrong = message.reminder_level === "strong";

  return (
    <div
      style={{
        ...styles.overlay,
        animation: isStrong ? "strongPulse 0.5s ease-in-out 3" : undefined,
      }}
    >
      <div style={styles.popup}>
        {/* 倒计时进度条 */}
        <div style={styles.progressTrack}>
          <div
            style={{
              ...styles.progressBar,
              width: `${(remaining / message.duration) * 100}%`,
              background: isStrong ? "#ef4444" : "#667eea",
            }}
          />
        </div>

        {/* 排队指示器 */}
        {queueCount > 0 && (
          <div style={styles.queueBadge}>排队中 {queueCount} 条</div>
        )}

        {/* 提醒标签 */}
        {isStrong && (
          <div style={styles.strongBadge}>⚠️ 强提醒</div>
        )}

        {/* TTS 播报进度标签 */}
        {showTtsProgress && (
          <div style={styles.ttsBadge}>🔊 播报 {ttsRepeatCurrent}/{ttsRepeatTotal} 次</div>
        )}

        {/* 消息内容 */}
        <div style={styles.messageContent}>{message.content}</div>

        {/* 图片附件 */}
        {message.image_path && (
          <div style={styles.imageContainer}>
            <img
              src={`${getBackendUrl()}${message.image_path}`}
              alt="附件图片"
              style={styles.messageImage}
            />
          </div>
        )}

        {/* 倒计时 */}
        <div style={styles.countdown}>{remaining}s</div>

        {/* 发送者和时间 */}
        {(message.teacher_name || message.sent_at) && (
          <div style={styles.messageMeta}>
            {message.teacher_name && <span>{message.teacher_name}</span>}
            {message.teacher_name && message.sent_at && <span style={styles.metaDot}>·</span>}
            {message.sent_at && <span>{formatTime(message.sent_at)}</span>}
          </div>
        )}
      </div>

      <style>{`
        @keyframes strongPulse {
          0%, 100% { box-shadow: inset 0 0 0 0 rgba(239, 68, 68, 0); }
          50% { box-shadow: inset 0 0 80px 20px rgba(239, 68, 68, 0.3); }
        }
      `}</style>
    </div>
  );
}

// ============================================================================
// 跑马灯模式
// ============================================================================

function MarqueeDisplay({
  message,
  queueCount,
  remaining,
  showTtsProgress,
  ttsRepeatCurrent,
  ttsRepeatTotal,
}: {
  message: DisplayMessage;
  queueCount: number;
  remaining: number;
  showTtsProgress: boolean;
  ttsRepeatCurrent: number;
  ttsRepeatTotal: number;
}) {
  const isStrong = message.reminder_level === "strong";

  return (
    <div
      style={{
        ...styles.marqueeContainer,
        border: isStrong ? "3px solid #ef4444" : "2px solid #667eea",
      }}
    >
      {/* 标签 */}
      <div style={styles.marqueeLabel}>
        {isStrong ? "⚠️ 强提醒" : "📢 通知"}
        {message.teacher_name && (
          <span style={styles.marqueeSender}> · {message.teacher_name}</span>
        )}
        {showTtsProgress && (
          <span style={styles.marqueeTts}> 🔊 {ttsRepeatCurrent}/{ttsRepeatTotal}</span>
        )}
      </div>

      {/* 排队指示器 */}
      {queueCount > 0 && (
        <div style={styles.marqueeQueue}>排队中 {queueCount} 条</div>
      )}

      {/* 滚动文本 */}
      <div style={styles.marqueeTrack}>
        <div
          style={{
            ...styles.marqueeText,
            animation: `marqueeScroll ${Math.max(message.content.length * 0.15, 8)}s linear infinite`,
          }}
        >
          {message.content}
          <span style={{ margin: "0 4em" }} />
          {message.content}
        </div>
      </div>

      {/* 倒计时 */}
      <div style={styles.marqueeCountdown}>{remaining}s</div>

      <style>{`
        @keyframes marqueeScroll {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
      `}</style>
    </div>
  );
}

// ============================================================================
// 共享样式
// ============================================================================

const styles: Record<string, React.CSSProperties> = {
  // 弹窗覆盖层
  overlay: {
    position: "fixed",
    inset: 0,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "rgba(0, 0, 0, 0.92)",
    zIndex: 9999,
    cursor: "pointer",
    fontFamily: "system-ui, -apple-system, sans-serif",
  },
  popup: {
    position: "relative",
    width: "85%",
    maxWidth: 1400,
    background: "linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)",
    borderRadius: 28,
    padding: "64px 60px 48px",
    overflow: "hidden",
    border: "2px solid rgba(102, 126, 234, 0.3)",
  },
  progressTrack: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: 4,
    background: "rgba(255, 255, 255, 0.1)",
  },
  progressBar: {
    height: "100%",
    transition: "width 1s linear",
    borderRadius: "0 2px 2px 0",
  },
  queueBadge: {
    position: "absolute",
    top: 16,
    right: 20,
    padding: "6px 14px",
    background: "rgba(102, 126, 234, 0.2)",
    color: "#667eea",
    borderRadius: 14,
    fontSize: "0.9rem",
    fontWeight: 500,
  },
  strongBadge: {
    display: "inline-block",
    padding: "6px 18px",
    background: "rgba(239, 68, 68, 0.2)",
    color: "#ef4444",
    borderRadius: 24,
    fontSize: "1.1rem",
    fontWeight: 600,
    marginBottom: 20,
  },
  ttsBadge: {
    display: "inline-block",
    padding: "6px 18px",
    background: "rgba(34, 197, 94, 0.2)",
    color: "#22c55e",
    borderRadius: 24,
    fontSize: "1.1rem",
    fontWeight: 600,
    marginBottom: 16,
  },
  messageContent: {
    fontSize: "4rem",
    fontWeight: 600,
    color: "#fff",
    lineHeight: 1.4,
    textAlign: "center",
    wordBreak: "break-word",
    padding: "24px 0",
  },
  imageContainer: {
    marginTop: 24,
    textAlign: "center" as const,
  },
  messageImage: {
    maxWidth: "100%",
    maxHeight: 500,
    borderRadius: 16,
    objectFit: "contain" as const,
  },
  countdown: {
    textAlign: "right",
    fontSize: "1.1rem",
    color: "rgba(255, 255, 255, 0.4)",
    marginTop: 16,
  },
  messageMeta: {
    display: "flex",
    justifyContent: "flex-end",
    alignItems: "center",
    gap: 6,
    fontSize: "1rem",
    color: "rgba(255, 255, 255, 0.5)",
    marginTop: 10,
  },
  metaDot: {
    margin: "0 2px",
  },

  // 跑马灯
  marqueeContainer: {
    position: "fixed",
    top: 0,
    left: 0,
    right: 0,
    height: 120,
    background: "linear-gradient(180deg, rgba(15, 12, 41, 0.95) 0%, rgba(26, 26, 46, 0.95) 100%)",
    zIndex: 9999,
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    cursor: "pointer",
    fontFamily: "system-ui, -apple-system, sans-serif",
    overflow: "hidden",
  },
  marqueeLabel: {
    position: "absolute",
    top: 8,
    left: 16,
    fontSize: "0.75rem",
    color: "rgba(255, 255, 255, 0.5)",
  },
  marqueeSender: {
    fontWeight: 500,
    color: "rgba(255, 255, 255, 0.7)",
  },
  marqueeTts: {
    color: "#22c55e",
    fontWeight: 500,
  },
  marqueeQueue: {
    position: "absolute",
    top: 8,
    right: 16,
    padding: "2px 8px",
    background: "rgba(102, 126, 234, 0.3)",
    color: "#a5b4fc",
    borderRadius: 10,
    fontSize: "0.7rem",
    fontWeight: 500,
  },
  marqueeTrack: {
    overflow: "hidden",
    whiteSpace: "nowrap",
    padding: "0 20px",
  },
  marqueeText: {
    display: "inline-block",
    fontSize: "2.2rem",
    fontWeight: 600,
    color: "#fff",
  },
  marqueeCountdown: {
    position: "absolute",
    bottom: 8,
    right: 16,
    fontSize: "0.75rem",
    color: "rgba(255, 255, 255, 0.4)",
  },
};
