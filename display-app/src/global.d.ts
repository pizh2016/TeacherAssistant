/**
 * 全局类型声明 — 大屏端
 */

// Vite define 注入的后端 URL
declare const __BACKEND_URL__: string;

// Electron preload 暴露的 API
interface ElectronAPI {
  getVersion: () => Promise<string>;
  getPlatform: () => string;
  toggleFullscreen: () => void;
  minimize: () => void;
  // 双模式窗口策略：enterStandby=展示态全屏置顶，exitFullscreen=普通窗口
  enterStandby: () => void;
  exitFullscreen: () => void;
  // 系统托盘提示文本
  setTrayTooltip: (text: string) => void;
}

interface Window {
  electronAPI?: ElectronAPI;
  /** Electron 环境标记（preload 同步设置，用于判断窗口管理功能可用性） */
  __ELECTRON__?: boolean;
}
