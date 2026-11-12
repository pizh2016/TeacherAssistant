/**
 * 喊话小喇叭 - 大屏端 Electron 主进程
 *
 * 职责：
 * - 创建和管理窗口（分阶段全屏策略）
 * - IPC 通信（窗口控制、应用信息）
 * - 管理应用生命周期
 *
 * 架构定位：
 * - 大屏端为纯客户端应用，后端独立部署在远程服务器
 * - 后端 URL 由渲染进程通过 localStorage 用户配置获取
 * - 主进程仅负责窗口管理和系统级操作
 *
 * 环境判断：
 * - 开发模式：app.isPackaged === false → 加载 Vite dev server (localhost:5174)
 * - 生产模式：app.isPackaged === true → 加载 dist/index.html
 */

const { app, BrowserWindow, ipcMain, shell, globalShortcut, powerSaveBlocker, Tray, Menu, nativeImage } = require('electron');
const path = require('path');

// --- 环境判断 ---
const IS_DEV = !app.isPackaged;

let mainWindow = null;

/** powerSaveBlocker ID（展示态防屏保） */
let powerSaveBlockerId = null;

/** 是否处于展示模式（displaying 态），用于 F11/toggle-fullscreen 状态同步 */
let isDisplayMode = false;

/** 系统托盘 */
let tray = null;

/** 托盘提示文本（根据连接状态动态更新） */
let trayTooltip = '喊话小喇叭 - 大屏端';

// ==============================================================================
// 路径工具
// ==============================================================================

/** 获取 preload 脚本路径 */
function getPreloadPath() {
  return path.join(__dirname, 'preload.js');
}

/** 获取窗口图标路径（开发模式和生产模式兼容） */
function getIconPath() {
  // 开发模式：从 assets/icons 读取
  const devIcon = path.join(__dirname, '..', 'assets', 'icons', 'app.png');
  // 生产模式：从 asar 外或 dist 目录读取
  const prodIcon = path.join(__dirname, '..', 'dist', 'icons', 'app.png');
  const fs = require('fs');
  if (fs.existsSync(devIcon)) return devIcon;
  if (fs.existsSync(prodIcon)) return prodIcon;
  return undefined;
}

// ==============================================================================
// 窗口管理
// ==============================================================================

/**
 * 创建主窗口
 *
 * 双模式窗口策略：
 * - 模式一（pairing / standby）：普通窗口 1280×720，不全屏、不置顶，任务栏可见
 * - 模式二（displaying）：全屏 + screen-saver 级置顶，任务栏隐藏，防屏保
 * - 开发模式下窗口行为与生产模式一致（全屏/置顶均生效）
 */
function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 720,
    fullscreen: false,
    alwaysOnTop: false,
    skipTaskbar: false,
    autoHideMenuBar: true,
    icon: getIconPath(),
    webPreferences: {
      preload: getPreloadPath(),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // 开发模式：普通窗口 + DevTools
  if (IS_DEV) {
    mainWindow.loadURL('http://localhost:5174');
    mainWindow.webContents.openDevTools();
  } else {
    // 生产模式：加载构建产物
    const indexPath = path.join(__dirname, '..', 'dist', 'index.html');
    mainWindow.loadFile(indexPath);
  }

  // 外部链接用默认浏览器打开
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// =============================================================================
// IPC 通信
// =============================================================================

/**
 * 注册 IPC 处理器
 */
function registerIpcHandlers() {
  // 应用信息
  ipcMain.handle('app:get-version', () => app.getVersion());

  // 简单全屏切换（已被 enterStandby/exitFullscreen 取代，保留兼容）
  ipcMain.on('window:toggle-fullscreen', () => {
    if (!mainWindow) return;
    const willFullscreen = !mainWindow.isFullScreen();
    if (willFullscreen) {
      // 进入全屏时同步展示模式状态
      isDisplayMode = true;
      if (powerSaveBlockerId === null) {
        powerSaveBlocker.start('prevent-display-sleep');
      }
      mainWindow.show();
      mainWindow.setAlwaysOnTop(true, 'screen-saver');
      // 异步等待全屏完成后再 setSkipTaskbar（避免 Windows 上窗口消失）
      const onFs = () => {
        mainWindow.removeListener('enter-full-screen', onFs);
        try { mainWindow.setSkipTaskbar(true); mainWindow.moveTop(); mainWindow.focus(); } catch {}
      };
      mainWindow.once('enter-full-screen', onFs);
      mainWindow.setFullScreen(true);
    } else {
      // 退出全屏时恢复普通窗口
      isDisplayMode = false;
      mainWindow.setAlwaysOnTop(false);
      mainWindow.setFullScreen(false);
      mainWindow.setSkipTaskbar(false);
      if (powerSaveBlockerId !== null) {
        powerSaveBlocker.stop(powerSaveBlockerId);
        powerSaveBlockerId = null;
      }
    }
  });

  ipcMain.on('window:minimize', () => {
    mainWindow?.minimize();
  });

  // ---- 模式二：消息展示态 → 全屏 + 置顶 + 隐藏任务栏 + 防屏保 ----
  ipcMain.on('window:enter-standby', () => {
    console.log('[Main] === enter-standby IPC received === (isDisplayMode=' + isDisplayMode + ')');
    if (!mainWindow) {
      console.error('[Main] enter-standby: mainWindow is null! Cannot enter display mode.');
      return;
    }
    isDisplayMode = true;
    try {
      // 1. 防屏保（阻止显示器休眠）
      if (powerSaveBlockerId === null) {
        powerSaveBlockerId = powerSaveBlocker.start('prevent-display-sleep');
        console.log('[Main] powerSaveBlocker started');
      }

      // 2. 确保窗口可见（可能被最小化）
      if (mainWindow.isMinimized()) {
        mainWindow.restore();
      }
      mainWindow.show();
      mainWindow.focus();
      console.log('[Main] window show + focus done');

      // 3. 先设置置顶（在全屏之前，确保窗口已经在顶层）
      mainWindow.setAlwaysOnTop(true, 'screen-saver');
      console.log('[Main] setAlwaysOnTop(true, screen-saver) done');

      // 4. 注册全屏完成事件监听（必须在 setFullScreen 之前）
      const onEnterFullScreen = () => {
        mainWindow.removeListener('enter-full-screen', onEnterFullScreen);
        try {
          // 全屏完成后再隐藏任务栏图标
          mainWindow.setSkipTaskbar(true);
          // 强制拉到最前面 + 获取焦点
          mainWindow.moveTop();
          mainWindow.focus();
          console.log('[Main] === enter-full-screen event: skipTaskbar + moveTop + focus done ===');
        } catch (err) {
          console.error('[Main] enter-full-screen callback failed:', err);
        }
      };
      mainWindow.once('enter-full-screen', onEnterFullScreen);

      // 5. 进入全屏（异步操作，完成后触发上面的回调）
      mainWindow.setFullScreen(true);
      console.log('[Main] setFullScreen(true) called, waiting for enter-full-screen event...');
    } catch (err) {
      console.error('[Main] enter-standby failed, fallback to maximize:', err);
      mainWindow.maximize();
      mainWindow.setAlwaysOnTop(true, 'screen-saver');
      mainWindow.setSkipTaskbar(true);
      mainWindow.moveTop();
      mainWindow.focus();
    }
  });

  // ---- 模式一：配对/待机态 → 普通窗口，不全屏、不置顶 ----
  ipcMain.on('window:exit-fullscreen', () => {
    if (!mainWindow) return;
    isDisplayMode = false;
    try {
      // 1. 解除防屏保
      if (powerSaveBlockerId !== null) {
        powerSaveBlocker.stop(powerSaveBlockerId);
        powerSaveBlockerId = null;
      }
      // 2. 取消置顶
      mainWindow.setAlwaysOnTop(false);
      // 3. 退出全屏
      mainWindow.setFullScreen(false);
      // 4. 恢复任务栏
      mainWindow.setSkipTaskbar(false);
      console.log('[Main] exit-fullscreen: normal window restored');
    } catch (err) {
      console.error('[Main] exit-fullscreen failed:', err);
    }
  });

  // 全局快捷键：Ctrl+Q 退出应用
  globalShortcut.register('Ctrl+Q', () => {
    console.log('[Main] Ctrl+Q pressed, quitting...');
    app.quit();
  });

  // ---- 渲染进程 → 主进程：更新托盘提示文本 ----
  ipcMain.on('tray:set-tooltip', (_event, text) => {
    trayTooltip = text;
    if (tray) tray.setToolTip(text);
  });

  // 全局快捷键：F11 手动切换全屏（调试/应急用）
  // 与展示模式状态同步：展示态下禁止退出全屏，非展示态下可进入/退出
  globalShortcut.register('F11', () => {
    if (!mainWindow) return;
    const isFs = mainWindow.isFullScreen();

    if (isFs && isDisplayMode) {
      // 展示态下按 F11：忽略（避免破坏展示态窗口状态）
      console.log('[Main] F11: ignored in display mode (use Esc in standby to exit)');
      return;
    }

    if (isFs) {
      // 非展示态退出全屏 → 恢复普通窗口
      mainWindow.setFullScreen(false);
      mainWindow.setAlwaysOnTop(false);
      mainWindow.setSkipTaskbar(false);
      if (powerSaveBlockerId !== null) {
        powerSaveBlocker.stop(powerSaveBlockerId);
        powerSaveBlockerId = null;
      }
      console.log('[Main] F11: exited fullscreen → normal window');
    } else {
      // 进入全屏 → 同步进入展示模式（使用异步安全模式）
      try {
        if (powerSaveBlockerId === null) {
          powerSaveBlockerId = powerSaveBlocker.start('prevent-display-sleep');
        }
        mainWindow.show();
        mainWindow.setAlwaysOnTop(true, 'screen-saver');
        // 异步等待全屏完成后再 setSkipTaskbar（避免 Windows 上窗口消失）
        const onFs = () => {
          mainWindow.removeListener('enter-full-screen', onFs);
          try { mainWindow.setSkipTaskbar(true); mainWindow.moveTop(); mainWindow.focus(); } catch {}
        };
        mainWindow.once('enter-full-screen', onFs);
        mainWindow.setFullScreen(true);
        isDisplayMode = true;
        console.log('[Main] F11: entered fullscreen (display mode)');
      } catch (err) {
        console.error('[Main] F11 fullscreen failed, fallback to maximize:', err);
        mainWindow.maximize();
        mainWindow.setAlwaysOnTop(true, 'screen-saver');
        mainWindow.setSkipTaskbar(true);
        mainWindow.moveTop();
        mainWindow.focus();
        isDisplayMode = true;
      }
    }
  });
}

// =============================================================================
// 应用生命周期
// =============================================================================

// =============================================================================
// 系统托盘
// =============================================================================

/** 获取托盘图标路径（优先使用 assets/icons/app.png，回退到默认图标） */
function getTrayIconPath() {
  // 开发模式：从 assets/icons 读取
  const devIcon = path.join(__dirname, '..', 'assets', 'icons', 'app.png');
  // 生产模式：从 asar 外或 dist 目录读取
  const prodIcon = path.join(__dirname, '..', 'dist', 'icons', 'app.png');
  const fs = require('fs');
  if (fs.existsSync(devIcon)) return devIcon;
  if (fs.existsSync(prodIcon)) return prodIcon;
  return null;
}

/** 创建系统托盘 */
function createTray() {
  const iconPath = getTrayIconPath();
  let trayIcon;
  if (iconPath) {
    trayIcon = nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 });
  }
  // 如果图标加载失败，使用空图标（Electron 会显示默认图标）
  tray = new Tray(trayIcon || nativeImage.createEmpty());
  tray.setToolTip(trayTooltip);

  const contextMenu = Menu.buildFromTemplate([
    {
      label: '显示窗口',
      click: () => {
        if (!mainWindow) return;
        if (mainWindow.isMinimized()) mainWindow.restore();
        mainWindow.show();
        mainWindow.focus();
      },
    },
    { type: 'separator' },
    {
      label: '退出',
      click: () => {
        console.log('[Main] Tray: quit requested');
        app.quit();
      },
    },
  ]);

  tray.setContextMenu(contextMenu);

  // 双击托盘图标 → 显示窗口
  tray.on('double-click', () => {
    if (!mainWindow) return;
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
    console.log('[Main] Tray: double-click → show window');
  });

  console.log('[Main] Tray created');
}

// =============================================================================
// 应用生命周期
// =============================================================================

app.whenReady().then(() => {
  // 注册 IPC 处理器
  registerIpcHandlers();

  // 创建窗口
  createMainWindow();

  // 创建系统托盘
  createTray();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createMainWindow();
    }
  });
});

// 所有窗口关闭时退出应用
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// 应用退出前清理资源（powerSaveBlocker + 托盘）
app.on('before-quit', () => {
  if (powerSaveBlockerId !== null) {
    try {
      powerSaveBlocker.stop(powerSaveBlockerId);
      powerSaveBlockerId = null;
      console.log('[Main] before-quit: powerSaveBlocker stopped');
    } catch (err) {
      console.error('[Main] before-quit: failed to stop powerSaveBlocker:', err);
    }
  }
  if (tray) {
    tray.destroy();
    tray = null;
    console.log('[Main] before-quit: tray destroyed');
  }
});

// 未捕获异常处理
process.on('uncaughtException', (err) => {
  console.error('[Main] Uncaught exception:', err);
});

process.on('unhandledRejection', (reason) => {
  console.error('[Main] Unhandled rejection:', reason);
});
