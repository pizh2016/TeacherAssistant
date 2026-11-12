# 📣 喊话小喇叭 (Classroom Horn)

> **不依赖公网 IP、不需要域名备案、不使用云服务——一台办公室电脑就能跑起来的校园喊话系统。**

老师在办公室（或任何角落）用手机发一条文字，教室大屏** 2 秒内**弹窗/滚动显示并语音播报。数据全程不出校园，零外部依赖、零运维成本。

市面上的通知工具清一色云端方案：绑定硬件生态、数据上云、按年付费。校园内网场景下的**完全私有化实时喊话**没有现成解——这就是本项目存在的理由。

## ✨ 核心功能

| | |
|---|---|
| ⚡ **实时喊话** | WebSocket 按班级频道路由推送，端到端延迟 < 2 秒 |
| 🔊 **离线语音播报** | Web Speech API + pyttsx3 双方案，完全不联外网 |
| 📱 **零安装教师端** | 纯 H5 由后端静态托管，浏览器打开即用，配对码登录 |
| 📌 **强制置顶大屏** | Electron 覆盖全屏 PPT，开机自启、防屏保、断线补发 |
| 🏫 **多班级 + 批量广播** | 一位教师管理多个班级，一次发送多班到达 |
| ⏰ **定时 / 周期播报**、↩️ **60s 撤回**、🖼️ **图片投屏**、📋 **常用语模板**、🗂️ **历史审计导出** | Phase 2 全量落地 |

## 🧱 架构与技术选型

```
┌────────────────┐    WebSocket /     ┌────────────────┐     WebSocket      ┌────────────────┐
│  教师端 H5      │ ──── REST ───────► │  后端 FastAPI   │ ──/ws/class/{id}─► │  大屏端         │
│ Vue 3，零安装   │ ◄────────────────  │ Python 3.10     │ ◄───────────────── │ Electron + React│
└────────────────┘   同宿主静态托管     │ SQLite + JWT    │                    │ 全屏置顶 + TTS  │
                                      └────────────────┘                    └────────────────┘
```

选型不是罗列，每一条都对应场景约束：

- **FastAPI**——项目核心是 I/O 密集（WebSocket 广播 + SQLite 读写）而非计算密集，asyncio 够用，且原生 WebSocket 一个装饰器搞定。
- **WebSocket（而非 SSE / 长轮询）**——需要双向通道：推送之外还要预留大屏"已显示确认"、设备在线状态上报；一次握手延迟 <100ms。
- **SQLite（而非 MySQL / PG）**——100 班 × 50 条/天 × 30 天 ≈ 15 万行，绰绰有余；**私有化部署客户不用安装任何数据库**，零运维。SQLAlchemy 保证将来可无缝换 PG。
- **Vue 3 H5 教师端**——老师办公室电脑、路上手机混用，零安装第一优先级，更新即时生效。
- **Electron 大屏端**——唯一需要系统级能力的端：`setAlwaysOnTop('screen-saver')` 强制盖住全屏 PPT，浏览器 Fullscreen API 做不到；附带开机自启、隐藏任务栏、powerSaveBlocker。
- **pythonenv 便携运行时（而非 PyInstaller）**——ZIP 解压即用、不装 Python；保留源码级可调试性，避开 PyInstaller 漏打包动态 import / C 扩展的坑。

## 📦 部署：办公室 ↔ 教室

教室装一台大屏电脑（Electron），办公室装一台跑后端的电脑，同一内网即可，**没有第三步**：

- 老师浏览器访问 `http://<办公室电脑IP>:18800/static/teacher/` 直接喊话；
- 后端打成 **一个 40MB ZIP**（pythonenv + .pyc + H5 静态页 + `start-backend.bat`），双击启动；
- 大屏端拿到 ZIP 解压、输入班级配对码即自动接入对应班级频道。

## 🚀 快速开始

```powershell
# 1. 初始化后端环境（从本地 Python ZIP 解压出便携 .venv 并装依赖）
cd backend
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1

# 2. 启动后端（自动建表 + 播种默认班级：一年级A班 / 配对码 123456）
.venv\python.exe -m horn --dev

# 3. 打开教师端 H5：http://localhost:18800/static/teacher/index.html
#    API 文档：http://localhost:18800/docs
#    跑测试：.venv\python.exe -m pytest（REST + WebSocket 全绿）

# 4. 大屏端 / 教师端独立开发（可选）
cd display-app ; npm install ; npm run dev
cd teacher-app ; npm install ; npm run dev

# 5. 产品打包：便携 ZIP（pythonenv + .pyc + electron-builder 离线包）
.venv\python.exe scripts/build_runtime.py --package --force
```

## 📚 文档导航

| 文档 | 内容 |
|------|------|
| [QUICKSTART.md](QUICKSTART.md) | 开发日常：启动、迁移、调试、常用命令 |
| [00-总体技术方案设计](docs/00-总体技术方案设计.md) | 800+ 行方案总纲：背景、竞品、架构选型对比、数据模型 |
| [01-项目初始开发方案](docs/01-项目初始开发方案.md) | 目录结构、环境配置、版本控制、打包发布规划 |
| [02-后端API设计与实现](docs/02-后端API设计与实现.md) | **接口契约唯一事实源**：REST / WebSocket 协议 / 数据模型 |
| [04-操作手册](docs/04-操作手册.md) | 环境初始化 → 开发 → 构建 → 部署全流程 |
| [05-产品使用手册](docs/05-产品使用手册.md) | 面向教师 / 管理员的使用说明 |
| [公众号技术长文](https://mp.weixin.qq.com/s/9B3GFSN7P6Tbi_Kw7_knIA) | 完整开发复盘：选型论证、踩坑记录、AI 辅助开发实践 |

## ⚙️ 开发提示

- **`.venv` 无需激活**：`backend/.venv` 是解压版完整 Python（非标准 venv），直接调用 `.venv\python.exe`。
- **文档先行，契约驱动**：接口变更先改 [docs/02](docs/02-后端API设计与实现.md)，代码与文档对齐——这也是本项目的 AI 辅助开发方法论（详见公众号文章：文档先行 → 提示词精准 → MVP 避免过度设计）。
- **运行期目录不入库**：`backend/data|logs|static|runtime|generated/` 均已 gitignore。
- **依赖双轨同步**：`pyproject.toml` 为事实源，分层 `requirements-core/db/auth/tts/dev/build.txt` 需同步更新。
- **安全基线**：生产（`DEBUG=False`）必须经环境变量设置非默认 `JWT_SECRET_KEY`，否则启动即失败（fail-fast）。

---

> 有时候，最好的架构不是最复杂的架构，而是最适合场景的架构。
> 没有微服务、没有消息队列、没有 K8s——一个 Python 后端、一个 Vue 前端、一个 Electron 壳，就够了。

**后端** v0.2.0 · **大屏端 / 教师端** 见各 `package.json`
