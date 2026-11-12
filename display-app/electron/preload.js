/**
 * 喊话小喇叭 - Electron preload 脚本
 *
 * 在渲染进程中暴露安全的 API（contextBridge）。
 * 大屏端为纯客户端，后端独立部署，preload 仅负责窗口管理相关 API。
 */

const { contextBridge, ipcRenderer } = require('electron');

// 标记 Electron 环境（供渲染进程判断是否可用窗口管理功能）
contextBridge.exposeInMainWorld('__ELECTRON__', true);

contextBridge.exposeInMainWorld('electronAPI', {
  // 应用信息
  getVersion: () => ipcRenderer.invoke('app:get-version'),
  getPlatform: () => process.platform,

  // 窗口控制
  toggleFullscreen: () => ipcRenderer.send('window:toggle-fullscreen'),
  minimize: () => ipcRenderer.send('window:minimize'),

  // 双模式窗口策略
  // enterStandby: 模式二（displaying）→ 全屏 + 置顶 + 隐藏任务栏 + 防屏保
  // exitFullscreen: 模式一（pairing/standby）→ 普通窗口，不全屏、不置顶
  enterStandby: () => ipcRenderer.send('window:enter-standby'),
  exitFullscreen: () => ipcRenderer.send('window:exit-fullscreen'),

  // 系统托盘提示文本更新
  setTrayTooltip: (text) => ipcRenderer.send('tray:set-tooltip', text),
});
