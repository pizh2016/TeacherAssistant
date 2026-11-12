/**
 * 大屏端配对页面 — 配置后端地址 + 输入配对码连接
 *
 * 流程：
 * 1. （可选）配置后端服务器 URL
 * 2. 输入 6 位配对码
 * 3. POST /api/auth/pairing-login (role=display) 获取 JWT
 * 4. 成功后回调 onPaired()
 */

import { useState } from "react";
import { getBackendUrl, getStoredBackendUrl, setBackendUrl } from "../config";

interface PairingViewProps {
  onPaired: (config: {
    classId: number;
    className: string;
    token: string;
    pairingCode: string;
  }) => void;
}

export default function PairingView({ onPaired }: PairingViewProps) {
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // 后端地址配置
  const storedUrl = getStoredBackendUrl();
  const currentUrl = getBackendUrl();
  const [showServerSettings, setShowServerSettings] = useState(false);
  const [serverUrlInput, setServerUrlInput] = useState(storedUrl || "");
  const [serverUrlSaved, setServerUrlSaved] = useState(false);

  function handleInput(value: string) {
    const cleaned = value.replace(/\D/g, "").slice(0, 6);
    setCode(cleaned);
    setError("");
  }

  function handleServerUrlSave() {
    const url = serverUrlInput.trim().replace(/\/+$/, "");
    if (!url) return;
    setBackendUrl(url);
    setServerUrlSaved(true);
    setTimeout(() => setServerUrlSaved(false), 2000);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (code.length !== 6 || loading) return;

    setLoading(true);
    setError("");

    try {
      const res = await fetch(`${getBackendUrl()}/api/auth/pairing-login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pairing_code: code, role: "display" }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => null);
        if (res.status === 401) {
          setError("配对码无效，请检查后重试");
        } else {
          setError(err?.error?.message ?? `连接失败 (${res.status})`);
        }
        return;
      }

      const data = await res.json();
      const cls = data.classes?.[0];
      if (!cls) {
        setError("该配对码未绑定班级");
        return;
      }

      onPaired({
        classId: cls.id,
        className: cls.name,
        token: data.token,
        pairingCode: code,
      });
    } catch {
      setError("无法连接后端，请检查网络");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        {/* 标题区 */}
        <h1 style={styles.title}>喊话小喇叭</h1>
        <p style={styles.subtitle}>大屏端配置</p>

        {/* 服务器地址配置（低调折叠区） */}
        <div style={styles.serverSection}>
          <button
            type="button"
            onClick={() => setShowServerSettings(!showServerSettings)}
            style={styles.serverToggle}
          >
            <span>🌐 服务器地址</span>
            <span style={styles.serverToggleRight}>
              <span style={styles.serverUrlDisplay}>{currentUrl}</span>
              <span style={styles.caret}>{showServerSettings ? "▲" : "▼"}</span>
            </span>
          </button>

          {showServerSettings && (
            <div style={styles.serverForm}>
              <input
                type="text"
                value={serverUrlInput}
                onChange={(e) => setServerUrlInput(e.target.value)}
                placeholder="http://192.168.1.100:18800"
                style={styles.serverInput}
              />
              <button
                type="button"
                onClick={handleServerUrlSave}
                disabled={!serverUrlInput.trim()}
                style={{
                  ...styles.serverSaveBtn,
                  opacity: !serverUrlInput.trim() ? 0.4 : 1,
                }}
              >
                {serverUrlSaved ? "✓ 已保存" : "保存"}
              </button>
            </div>
          )}
        </div>

        {/* 分隔线 */}
        <div style={styles.divider} />

        {/* 配对码输入区 */}
        <form onSubmit={handleSubmit} style={styles.form}>
          <label style={styles.label}>班级配对码</label>
          <input
            type="text"
            inputMode="numeric"
            maxLength={6}
            value={code}
            onChange={(e) => handleInput(e.target.value)}
            placeholder="请输入 6 位数字配对码"
            disabled={loading}
            style={styles.input}
            autoFocus
          />

          {error && <p style={styles.error}>{error}</p>}

          <button
            type="submit"
            disabled={code.length !== 6 || loading}
            style={{
              ...styles.button,
              opacity: code.length !== 6 || loading ? 0.4 : 1,
            }}
          >
            {loading ? "连接中..." : "连 接"}
          </button>
        </form>

        <p style={styles.hint}>
          配对码由管理员在后端系统中创建班级时生成
        </p>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    width: "100vw",
    height: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%)",
    fontFamily: "system-ui, -apple-system, sans-serif",
    padding: 24,
    boxSizing: "border-box",
  },
  card: {
    background: "rgba(255, 255, 255, 0.05)",
    backdropFilter: "blur(20px)",
    borderRadius: 24,
    padding: "40px 36px 32px",
    width: "100%",
    maxWidth: 440,
    textAlign: "center",
    border: "1px solid rgba(255, 255, 255, 0.1)",
    boxSizing: "border-box",
  },
  title: {
    fontSize: "2rem",
    fontWeight: 700,
    color: "#fff",
    margin: 0,
  },
  subtitle: {
    fontSize: "0.9rem",
    color: "rgba(255, 255, 255, 0.45)",
    margin: "6px 0 0",
  },

  // ---- 服务器地址区 ----
  serverSection: {
    marginTop: 28,
    textAlign: "left" as const,
  },
  serverToggle: {
    width: "100%",
    padding: "10px 14px",
    fontSize: "0.8rem",
    color: "rgba(255, 255, 255, 0.5)",
    background: "transparent",
    border: "1px solid rgba(255, 255, 255, 0.08)",
    borderRadius: 10,
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    transition: "background 0.2s",
  },
  serverToggleRight: {
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  serverUrlDisplay: {
    fontSize: "0.72rem",
    color: "rgba(255, 255, 255, 0.3)",
    maxWidth: 200,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  caret: {
    fontSize: "0.6rem",
    color: "rgba(255, 255, 255, 0.25)",
  },
  serverForm: {
    display: "flex",
    gap: 8,
    marginTop: 10,
  },
  serverInput: {
    flex: 1,
    padding: "10px 14px",
    fontSize: "0.82rem",
    border: "1px solid rgba(255, 255, 255, 0.12)",
    borderRadius: 8,
    outline: "none",
    background: "rgba(255, 255, 255, 0.06)",
    color: "#fff",
    boxSizing: "border-box" as const,
  },
  serverSaveBtn: {
    padding: "10px 16px",
    fontSize: "0.8rem",
    fontWeight: 600,
    color: "#fff",
    background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    border: "none",
    borderRadius: 8,
    cursor: "pointer",
    whiteSpace: "nowrap" as const,
    flexShrink: 0,
  },

  // ---- 分隔线 ----
  divider: {
    height: 1,
    background: "rgba(255, 255, 255, 0.06)",
    margin: "24px 0",
  },

  // ---- 配对码输入区 ----
  form: {
    display: "flex",
    flexDirection: "column",
    gap: 14,
  },
  label: {
    fontSize: "0.85rem",
    fontWeight: 600,
    color: "rgba(255, 255, 255, 0.65)",
    textAlign: "left",
  },
  input: {
    width: "100%",
    padding: "16px 20px",
    fontSize: "1.8rem",
    fontFamily: '"Courier New", monospace',
    letterSpacing: "0.3em",
    textAlign: "center",
    border: "2px solid rgba(255, 255, 255, 0.15)",
    borderRadius: 12,
    outline: "none",
    background: "rgba(255, 255, 255, 0.06)",
    color: "#fff",
    boxSizing: "border-box",
    transition: "border-color 0.2s",
  },
  error: {
    color: "#ff6b6b",
    fontSize: "0.85rem",
    margin: 0,
    textAlign: "left",
  },
  button: {
    marginTop: 8,
    padding: 16,
    fontSize: "1.1rem",
    fontWeight: 700,
    color: "#fff",
    background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    border: "none",
    borderRadius: 12,
    cursor: "pointer",
    transition: "opacity 0.2s",
  },
  hint: {
    marginTop: 24,
    fontSize: "0.75rem",
    color: "rgba(255, 255, 255, 0.25)",
    margin: "24px 0 0",
  },
};
