# 喊话小喇叭 - 后端 API 设计与实现

> **文档定位**：后端 REST / WebSocket 接口契约（**唯一事实源**）。前端 H5、大屏端 Electron、后端实现均以本文档为准。
> **关联文档**：[总体技术方案设计](00-总体技术方案设计.md) | [项目初始开发方案](01-项目初始开发方案.md) | [系统架构图](architecture.png)
> **契约版本**：v2.0（Phase 2 更新）

---

## 目录
- [一、总体约定](#一总体约定)
- [二、数据模型](#二数据模型)
- [三、认证与鉴权](#三认证与鉴权)
- [四、REST API 契约](#四rest-api-契约)
- [五、WebSocket 契约](#五websocket-契约)
- [六、错误码规范](#六错误码规范)

---

## 一、总体约定

| 约定项 | 规范 |
|--------|------|
| **基础路径** | REST 统一前缀 `/api`；WebSocket 前缀 `/ws` |
| **数据格式** | 请求/响应均为 `application/json; charset=utf-8` |
| **时间格式** | ISO 8601 字符串（UTC），如 `2026-10-16T08:30:00+00:00`；毫秒时间戳字段以 `_ms` 结尾（整数） |
| **主键类型** | `class_id`、`teacher_id`、`message_id` 均为**整数**（SQLite AUTOINCREMENT） |
| **配对码** | `pairing_code` 为 **6 位数字字符串**（`"000000"~"999999"`），全局唯一 |
| **命名风格** | JSON 字段统一 `snake_case` |
| **版本** | 后端版本见 `backend/VERSION_BACKEND`；接口重大变更需升 `MAJOR`/`MINOR` |

> **重要**：`class_id` 采用整数主键，配对码 `pairing_code` 作为对外的易记标识。大屏端/老师端登录时提交 `pairing_code`，服务端解析为内部整数 `class_id`。

---

## 二、数据模型

对齐 [00-总体技术方案设计.md](00-总体技术方案设计.md) §5.5，共 6 张表：

### 2.1 classes（班级）
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INTEGER | PK, AUTOINCREMENT | 班级内部主键 |
| `name` | TEXT | NOT NULL | 班级名称 |
| `pairing_code` | TEXT | UNIQUE, NOT NULL | 6 位数字配对码 |
| `created_at` | DATETIME | DEFAULT now | 创建时间 |

### 2.2 teachers（教师）
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INTEGER | PK, AUTOINCREMENT | 教师主键 |
| `name` | TEXT | NOT NULL | 姓名（唯一标识） |
| `phone` | TEXT | UNIQUE, NULL | 手机号 |
| `wechat_openid` | TEXT | UNIQUE, NULL | 微信 OpenID |
| `last_login_at` | DATETIME | NULL | 最后登录时间 |
| `created_at` | DATETIME | DEFAULT now | 创建时间 |

### 2.3 teacher_classes（教师-班级绑定）
| 字段 | 类型 | 约束 |
|------|------|------|
| `teacher_id` | INTEGER | PK 之一, FK→teachers.id |
| `class_id` | INTEGER | PK 之一, FK→classes.id |

### 2.4 messages（消息）
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INTEGER | PK, AUTOINCREMENT | 消息主键 |
| `teacher_id` | INTEGER | NOT NULL, FK→teachers.id | 发送者 |
| `class_id` | INTEGER | NOT NULL, FK→classes.id | 目标班级 |
| `content` | TEXT | NOT NULL | 消息内容（≤500 字） |
| `display_mode` | TEXT | NOT NULL, DEFAULT `popup` | 展示样式：`popup`/`marquee` |
| `reminder_level` | TEXT | NOT NULL, DEFAULT `normal` | 提醒强度：`normal`/`strong` |
| `duration` | INTEGER | NOT NULL, DEFAULT 120 | 显示时长（秒，30~300） |
| `tts_enabled` | INTEGER(bool) | NOT NULL, DEFAULT 1 | 是否语音播报 |
| `audio_path` | TEXT | NULL | pyttsx3 生成的音频路径（可选） |
| `image_path` | TEXT | NULL | 图片附件路径（可选，≤5MB） |
| `sent_at` | DATETIME | DEFAULT now | 发送时间 |

### 2.5 scheduled_messages（定时任务）
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INTEGER | PK, AUTOINCREMENT | 定时任务主键 |
| `teacher_id` | INTEGER | NOT NULL, FK→teachers.id | 创建者 |
| `class_id` | INTEGER | NOT NULL, FK→classes.id | 目标班级 |
| `content` | TEXT | NOT NULL | 消息内容 |
| `display_mode` | TEXT | NOT NULL, DEFAULT `popup` | 展示样式 |
| `reminder_level` | TEXT | NOT NULL, DEFAULT `normal` | 提醒强度 |
| `duration` | INTEGER | NOT NULL, DEFAULT 120 | 显示时长 |
| `tts_enabled` | INTEGER(bool) | NOT NULL, DEFAULT 1 | 是否语音播报 |
| `image_path` | TEXT | NULL | 图片附件路径 |
| `schedule_type` | TEXT | NOT NULL, DEFAULT `once` | 类型：`once`/`daily`/`weekly`/`cron` |
| `schedule_at` | DATETIME | NULL | 单次定时执行时间 |
| `cron_expression` | TEXT | NULL | Cron 表达式（5段） |
| `is_active` | INTEGER(bool) | NOT NULL, DEFAULT 1, INDEX | 是否启用 |
| `created_at` | DATETIME | DEFAULT now | 创建时间 |

### 2.6 teacher_templates（教师自定义模板）
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INTEGER | PK, AUTOINCREMENT | 模板主键 |
| `teacher_id` | INTEGER | NOT NULL, FK→teachers.id | 所属教师 |
| `content` | TEXT(500) | NOT NULL | 模板内容 |
| `sort_order` | INTEGER | NOT NULL, DEFAULT 0 | 排序序号 |
| `created_at` | DATETIME | DEFAULT now | 创建时间 |

索引：`idx_template_teacher(teacher_id, sort_order)`

### 2.7 索引
```sql
CREATE INDEX idx_messages_class_sent ON messages(class_id, sent_at DESC);
CREATE INDEX idx_messages_teacher ON messages(teacher_id, sent_at DESC);
CREATE INDEX idx_scheduled_active ON scheduled_messages(is_active);
```

---

## 三、认证与鉴权

| 机制 | 说明 |
|------|------|
| **登录方式** | Phase 2: 教师使用**姓名登录**（`POST /api/auth/teacher-login`，首次自动注册）；配对码登录（`POST /api/auth/pairing-login`）**仅限大屏端**（role=display） |
| **令牌** | JWT（HS256），载荷含 `sub`（角色标识）、`role`（`teacher`/`display`）、`class_ids`（教师）或 `class_id`（大屏）、`exp` |
| **有效期** | `auth.access_token_expire_minutes`（默认 30 分钟，见 `defaults/settings.json`） |
| **REST 鉴权** | 除 `/health`、`/`、登录接口外，均需 `Authorization: Bearer <token>` |
| **WS 鉴权** | 浏览器 WebSocket 无法自定义 header，故 **token 走连接后首帧 `join_class` 消息**（见 §5.2）；未在 10 秒内完成 `join_class` 的连接将被服务端关闭 |
| **密钥** | `auth.jwt_secret_key`（见 `defaults/settings.json`）必须替换默认占位值；非 DEBUG 环境使用默认值时**启动即失败**（fail-fast） |

### 3.1 JWT 载荷示例
```json
{
  "sub": "teacher-1",
  "role": "teacher",
  "class_ids": [1, 2],
  "exp": 1760000000
}
```

---

## 四、REST API 契约

### 4.1 端点总览

| 方法 | 路径 | 鉴权 | 描述 |
|------|------|------|------|
| GET | `/health` | 否 | 健康检查 |
| GET | `/` | 否 | 服务信息 |
| POST | `/api/auth/pairing-login` | 否 | 配对码登录（**仅 display**） |
| POST | `/api/auth/teacher-login` | 否 | 教师姓名登录（自动注册） |
| GET | `/api/classes` | 是 | 获取班级列表 |
| POST | `/api/classes` | 是（teacher） | 创建班级（自动生成配对码） |
| PUT | `/api/classes/{id}` | 是（teacher） | 重命名班级 |
| DELETE | `/api/classes/{id}` | 是（teacher） | 删除班级 |
| POST | `/api/classes/{id}/regenerate-code` | 是（teacher） | 重新生成配对码 |
| POST | `/api/messages` | 是（teacher） | 发送消息（写库 + WS 广播） |
| POST | `/api/messages/batch` | 是（teacher） | 批量发送（≤6 班） |
| POST | `/api/messages/{id}/recall` | 是（teacher） | 撤回消息（60秒内） |
| POST | `/api/messages/upload` | 是（teacher） | 上传图片（≤5MB） |
| GET | `/api/messages/history` | 是 | 分页查询发送历史 |
| GET | `/api/messages/latest` | 是 | 断线重连补发 |
| POST | `/api/messages/scheduled` | 是（teacher） | 创建定时任务 |
| GET | `/api/messages/scheduled` | 是（teacher） | 查询定时任务列表 |
| DELETE | `/api/messages/scheduled/{id}` | 是（teacher） | 删除定时任务 |
| PUT | `/api/messages/scheduled/{id}/toggle` | 是（teacher） | 启用/停用定时任务 |
| GET | `/api/messages/audit` | 是 | 审计查询（带筛选） |
| GET | `/api/messages/export` | 是 | 导出 CSV |
| GET | `/api/templates` | 是（teacher） | 查询自定义模板 |
| POST | `/api/templates` | 是（teacher） | 创建模板 |
| PUT | `/api/templates/{id}` | 是（teacher） | 更新模板 |
| DELETE | `/api/templates/{id}` | 是（teacher） | 删除模板 |

### 4.2 GET /health
**响应 200**
```json
{ "status": "healthy", "timestamp": "2026-10-16T08:30:00+00:00", "version": "0.1.0" }
```

### 4.3 POST /api/auth/pairing-login
**Phase 2 更新**：配对码登录**仅限大屏端**（role=display），教师请使用 §4.4 的姓名登录。

**请求**
```json
{ "pairing_code": "123456", "role": "display" }
```
- `role` 必须为 `display`，传入 `teacher` 将返回 `403` 错误。

**响应 200**
```json
{
  "token": "<jwt>",
  "role": "display",
  "teacher_id": null,
  "teacher_name": "",
  "classes": [ { "id": 1, "name": "一年级A班", "pairing_code": "123456" } ]
}
```
**错误**：`401` 配对码无效；`403` 教师请使用姓名登录。

### 4.4 POST /api/auth/teacher-login
教师姓名登录，首次使用自动注册。姓名即账号，同名教师始终复用同一记录。

**请求**
```json
{ "name": "张老师" }
```
- `name` 长度 1~64 字符。

**响应 200**
```json
{
  "token": "<jwt>",
  "role": "teacher",
  "teacher_id": 1,
  "teacher_name": "张老师",
  "classes": [ { "id": 1, "name": "一年级A班", "pairing_code": "123456" } ]
}
```
- 首次登录无班级时，`classes` 为空数组，前端引导创建班级。

### 4.5 GET /api/classes
**响应 200**
```json
[ { "id": 1, "name": "一年级A班", "pairing_code": "123456" } ]
```
仅返回当前 token 对应教师绑定的班级。教师角色从 DB 查询实际绑定关系（JWT 中的 class_ids 可能过期）。

### 4.6 POST /api/classes
创建新班级，自动生成 6 位数字配对码，并绑定到当前教师。

**请求**
```json
{ "name": "二年级A班" }
```
- `name` 长度 1~64，同一教师下不可重名。

**响应 201**
```json
{
  "id": 2,
  "name": "二年级A班",
  "pairing_code": "654321",
  "message": "班级创建成功"
}
```

### 4.7 PUT /api/classes/{class_id}
重命名班级。仅绑定该班级的教师可操作。

**请求**
```json
{ "name": "二年级B班" }
```
**响应 200**：返回更新后的 `ClassOut`。

### 4.8 DELETE /api/classes/{class_id}
删除班级及其关联数据（消息、绑定关系）。仅绑定该班级的教师可操作。

**响应 204**：无内容。

### 4.9 POST /api/classes/{class_id}/regenerate-code
重新生成配对码，旧配对码立即失效。大屏端需使用新配对码重新登录。

**响应 200**：返回更新后的 `ClassOut`。

### 4.10 POST /api/messages
**请求**
```json
{
  "class_id": 1,
  "content": "请同学们到操场集合",
  "display_mode": "popup",
  "reminder_level": "normal",
  "duration": 120,
  "tts_enabled": true
}
```
- `content` 长度 1~500；`duration` 30~300；`display_mode ∈ {popup, marquee}`；`reminder_level ∈ {normal, strong}`。
- 服务端校验 token 中的教师是否绑定 `class_id`，否则 `403`。

**响应 200**
```json
{ "id": 1001, "status": "sent", "sent_at": "2026-10-16T08:30:00+00:00" }
```
**副作用**：写入 `messages` 表，并向 `/ws/class/{class_id}` 频道广播 `new_message`（见 §5.3）。

### 4.11 GET /api/messages/history
**查询参数**：`class_id`（可选）、`page`（默认 1）、`limit`（默认 20，最大 100）。
**响应 200**
```json
{
  "total": 135,
  "page": 1,
  "limit": 20,
  "items": [
    {
      "id": 1001, "class_id": 1, "content": "...",
      "display_mode": "popup", "reminder_level": "normal",
      "duration": 120, "tts_enabled": true,
      "sent_at": "2026-10-16T08:30:00+00:00"
    }
  ]
}
```

### 4.12 GET /api/messages/latest
**查询参数**：`class_id`（必填）、`since`（可选，消息 id 游标，返回 id > since 的消息）。
**响应 200**：返回该班级 `since` 之后的消息数组（结构同 history 的 `items`），用于大屏端断线重连补发。

---

## 五、WebSocket 契约

### 5.1 路由
```
WS /ws/class/{class_id}
```
- `class_id` 为整数。连接建立后需在 10 秒内发送 `join_class` 完成鉴权，否则服务端以 `4401` 关闭。

### 5.2 客户端 → 服务端事件

| 事件 `type` | 载荷 | 描述 |
|------|------|------|
| `join_class` | `{ "type": "join_class", "class_id": 1, "token": "<jwt>" }` | 加入班级频道并鉴权 |
| `heartbeat` | `{ "type": "heartbeat", "timestamp_ms": 1760000000000 }` | 心跳保活（建议每 30 秒） |
| `ack_message` | `{ "type": "ack_message", "message_id": 1001 }` | 确认已展示（可选，用于审计） |

### 5.3 服务端 → 客户端事件

| 事件 `type` | 载荷 | 描述 |
|------|------|------|
| `connection_ack` | `{ "type": "connection_ack", "status": "ok", "class_id": 1, "class_name": "一年级A班" }` | 鉴权成功确认 |
| `new_message` | 见下 | 新消息推送 |
| `pong` | `{ "type": "pong", "timestamp_ms": 1760000000000 }` | 心跳响应 |
| `reconnect_hint` | `{ "type": "reconnect_hint", "last_message_id": 1001 }` | 重连后提示从何处补发 |

**`new_message` 载荷**
```json
{
  "type": "new_message",
  "id": 1001,
  "class_id": 1,
  "content": "请同学们到操场集合",
  "display_mode": "popup",
  "reminder_level": "normal",
  "duration": 120,
  "tts_enabled": true,
  "audio_path": null,
  "image_path": null,
  "sent_at": "2026-10-16T08:30:00+00:00"
}
```

**`recall_message` 载荷**（Phase 2 新增）
```json
{
  "type": "recall_message",
  "message_id": 10,
  "class_id": 1
}
```
大屏端收到此事件应立即移除对应消息的展示。

### 5.4 关闭码
| code | 含义 |
|------|------|
| `4401` | 未鉴权 / token 无效 |
| `4403` | token 与所连接 `class_id` 不匹配 |
| `4408` | join 超时（未在 10 秒内发送 `join_class`） |

---

## 六、错误码规范

统一错误响应体：
```json
{ "error": { "code": "PAIRING_CODE_INVALID", "message": "配对码无效", "status": 401 } }
```

| HTTP | code | 含义 |
|------|------|------|
| 400 | `VALIDATION_ERROR` | 请求体校验失败（字段/长度/枚举） |
| 401 | `PAIRING_CODE_INVALID` | 配对码不存在或不匹配 |
| 401 | `TOKEN_INVALID` | JWT 无效/过期 |
| 401 | `TOKEN_MISSING` | 缺少 Authorization 头 |
| 403 | `CLASS_FORBIDDEN` | 教师未绑定该班级 |
| 404 | `NOT_FOUND` | 资源不存在 |
| 500 | `INTERNAL_ERROR` | 服务端异常（不泄露堆栈） |
| 400 | `MESSAGE_RECALL_EXPIRED` | 消息撤回超过 60 秒时限 |
| 404 | `MESSAGE_RECALL_NOT_FOUND` | 要撤回的消息不存在 |
| 400 | `IMAGE_TOO_LARGE` | 图片超过 5MB 限制 |
| 400 | `IMAGE_FORMAT_INVALID` | 不支持的图片格式 |
| 400 | `SCHEDULE_INVALID` | 定时任务参数无效 |
| 400 | `BATCH_LIMIT_EXCEEDED` | 批量发送超过 6 班限制 |

---

## 附录：Phase 2 新增接口 (v2.0)

### A.1 教师姓名登录

```
POST /api/auth/teacher-login
Body: { "name": "张老师" }
Response: { "token": "...", "role": "teacher", "teacher_id": 1, "classes": [...] }
```

首次登录自动注册到 `teachers` 表。**同名去重逻辑**：姓名即账号，同名教师无论是否已绑定班级，始终复用同一 `teachers` 记录（不追加数字后缀）。配对码登录 (`pairing-login`) 仅限 `role=display`。

### A.2 批量广播

```
POST /api/messages/batch
Body: { "class_ids": [1,2,3], "content": "...", ... }
Response: { "ids": [10,11,12], "status": "sent", "sent_at": "...", "class_count": 3 }
```

`class_ids` 最多 6 个。服务端对每个班级分别 INSERT + WS 广播。

### A.3 消息撤回

```
POST /api/messages/{message_id}/recall
Response: { "status": "recalled", "message_id": 10 }
```

60 秒内可撤回。WS 广播 `recall_message` 事件，大屏端立即移除展示。

### A.4 图片上传

```
POST /api/messages/upload
Content-Type: multipart/form-data
Field: file (image/*, ≤5MB)
Response: { "image_path": "/static/uploads/xxx.png", "url": "/static/uploads/xxx.png" }
```

### A.5 定时播报

```
POST /api/messages/scheduled
Body: { "class_id": 1, "content": "...", "schedule_type": "once|daily|weekly", "schedule_at": "...", "cron_expression": "..." }
GET /api/messages/scheduled
DELETE /api/messages/scheduled/{id}
PUT /api/messages/scheduled/{id}/toggle
```

后端集成 APScheduler，支持单次定时、每日、每周周期任务。

### A.6 自定义模板

```
GET /api/templates
POST /api/templates          Body: { "content": "..." }
PUT /api/templates/{id}      Body: { "content": "..." }
DELETE /api/templates/{id}
```

### A.7 消息审计与导出

```
GET /api/messages/audit?class_id=&teacher_id=&start_time=&end_time=&page=&limit=
GET /api/messages/export?class_id=&teacher_id=&start_time=&end_time=
```

导出为 CSV（UTF-8 BOM），可直接用 Excel 打开。

### A.8 WebSocket 新增事件

| 事件类型 | 方向 | 说明 |
|---------|------|------|
| `recall_message` | Server→Client | `{ "type": "recall_message", "message_id": 10, "class_id": 1 }` 大屏立即移除该消息 |
| `new_message` 新增字段 | Server→Client | `image_path: string | null` 图片附件路径 |

---

## 七、日志体系

### 7.1 结构化日志格式

后端控制台采用结构化日志，格式为：

```
时间戳 | 级别 | 操作类型 | 用户上下文 | IP | 描述
```

示例：
```
2026-10-20 13:18:20 | INFO | TEACHER_LOGIN | teacher_id=5, name=张老师 | IP=127.0.0.1:9407 | 登录成功
```

### 7.2 日志过滤规则

| 过滤项 | 说明 |
|--------|------|
| `/health` 请求 | 中间件 + PathFilter 双重过滤，不输出访问日志 |
| `/static/*` 请求 | 静态资源请求不输出访问日志 |
| `/` 根路径 | 不输出访问日志 |
| uvicorn.access | 设为 WARNING 级别，抑制默认访问日志 |

### 7.3 关键操作日志

| 操作类型 | 级别 | 用户上下文 | 说明 |
|----------|------|-----------|------|
| `TEACHER_LOGIN` | INFO | teacher_id, name, IP | 教师登录成功 |
| `DISPLAY_LOGIN` | INFO | class_id, IP | 大屏端配对登录 |
| `CLASS_CREATE/UPDATE/DELETE` | INFO | teacher_id, IP, class_id | 班级数据变更 |
| `MSG_CREATE/BATCH/RECALL` | INFO | teacher_id, IP, msg_id | 消息操作 |
| `SCHEDULE_CREATE` | INFO | teacher_id, IP, id | 定时任务创建 |
| `TPL_CREATE/UPDATE/DELETE` | INFO | teacher_id, IP, tpl_id | 模板操作 |
| `WS_JOIN/LEAVE` | INFO | user_id, role, IP, class_id | WebSocket 连接/断开 |
| `API_ERROR` | WARNING | method, path, status_code | API 错误 |
| `UNHANDLED_ERROR` | ERROR | 完整堆栈 | 未捕获异常 |

---

*文档版本：v2.1*
*最后更新：2026-10-20*
*作者：全栈架构师*
