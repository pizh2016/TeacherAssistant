/**
 * 大屏端配置 — 后端 URL 管理 + 持久化存储
 *
 * 后端 URL 获取优先级（从高到低）：
 * 1. 用户配置（localStorage）— 管理员通过"服务器设置"手动指定
 * 2. Vite 开发模式 — 通过 define 注入 __BACKEND_URL__
 * 3. 回退 — 同源请求（window.location.origin），兼容 Nginx 反向代理
 *
 * 大屏端作为纯客户端，后端独立部署在远程服务器。
 */

const STORAGE_KEY = "horn_display_config";
const BACKEND_URL_KEY = "horn_backend_url";

/** 获取用户持久化的后端 URL（可能为 null） */
export function getStoredBackendUrl(): string | null {
  try {
    return localStorage.getItem(BACKEND_URL_KEY);
  } catch {
    return null;
  }
}

/** 设置并持久化后端 URL */
export function setBackendUrl(url: string): void {
  localStorage.setItem(BACKEND_URL_KEY, url);
}

/** 清除用户自定义的后端 URL（回退到默认值） */
export function clearBackendUrl(): void {
  localStorage.removeItem(BACKEND_URL_KEY);
}

/** 获取后端基础 URL */
export function getBackendUrl(): string {
  // 1. 用户手动配置的后端地址
  const stored = getStoredBackendUrl();
  if (stored) return stored;

  // 2. Vite 开发模式 — 通过 define 注入
  if (typeof __BACKEND_URL__ !== "undefined") {
    return __BACKEND_URL__;
  }

  // 3. 回退：同源请求（兼容纯 Web 部署 / Nginx 反向代理）
  return window.location.origin;
}

/** 持久化配置接口 */
export interface DisplayConfig {
  classId: number;
  className: string;
  token: string;
  pairingCode: string;
}

/** 读取持久化配置 */
export function loadConfig(): DisplayConfig | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as DisplayConfig;
  } catch {
    return null;
  }
}

/** 保存持久化配置 */
export function saveConfig(config: DisplayConfig): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
}

/** 清除持久化配置 */
export function clearConfig(): void {
  localStorage.removeItem(STORAGE_KEY);
}
