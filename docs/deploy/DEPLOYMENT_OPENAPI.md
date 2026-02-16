# OpenAPI 模式部署文档

本文档详细说明 OpenAPI 模式的架构设计和部署步骤，包括单机部署和分离部署两种方式。

## 目录

- [模式简介](#模式简介)
- [架构概览](#架构概览)
- [组件列表](#组件列表)
- [配置说明](#配置说明)
- [飞书应用配置](#飞书应用配置)
- [部署步骤](#部署步骤)
- [网关注册与双向认证](#网关注册与双向认证)
- [群聊功能](#群聊功能)
- [安全配置](#安全配置)
- [常见问题](#常见问题)

---

## 模式简介

OpenAPI 模式使用飞书开放平台 API 发送消息，支持飞书内直接响应、多实例部署和消息回复继续会话等高级功能。

### 特点

| 特性 | 说明 |
|------|------|
| **飞书应用** | 需要创建飞书开放平台应用 |
| **交互方式** | 按钮直接在飞书内响应 |
| **配置复杂度** | 较复杂（需配置应用凭证） |
| **部署方式** | 单机部署 / 分离部署 |
| **推荐场景** | 团队协作、多机器部署 |

### 支持功能

- ✅ 飞书内直接响应（无需浏览器）
- ✅ 多实例部署
- ✅ 消息回复继续会话
- ✅ 群聊支持
- ✅ 自动注册与双向认证
- ✅ 用户授权控制

### 适用场景

**单机部署**：
- 团队协作使用
- 需要飞书内直接响应
- 需要回复继续会话功能

**分离部署**：
- 多机器/多实例部署
- 共享飞书应用
- 分布式架构

---

## 架构概览

### 单机部署架构

所有服务运行在同一台机器上。

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│  Claude Code    │────────▶│ src/hook-router  │────────▶│  飞书 OpenAPI   │
│                 │  Hook   │  → permission.sh │  Card   │  (access_token) │
└─────────────────┘         └────────┬─────────┘         └─────────────────┘
                                     │
                                     │ Unix Socket
                                     │ (注册请求)
                                     ▼
                            ┌──────────────────┐
                            │   src/server/    │
                            │   HTTP Server    │
                            └────────┬─────────┘
                                     │
                                     │ Feishu Event
                                     │ (card.action.trigger)
                                     ▼
                            ┌──────────────────┐         ┌─────────────────┐
                            │   src/server/    │────────▶│ src/hooks/      │
                            │   (resolve)      │  Socket │  permission.sh  │
                            └──────────────────┘         └────────┬─────────┘
                                                                 │
                                                                 │ Decision JSON
                                                                 ▼
                                                            ┌─────────────────┐
                                                            │  Claude Code    │
                                                            │  (继续/拒绝)     │
                                                            └─────────────────┘
```

### 分离部署架构

飞书网关与 Callback 服务分离，支持多实例。

```
                                                    ┌─────────────────────┐
                                                    │   Feishu Gateway    │
                                                    │  (飞书应用凭证)      │
                                                    │  FEISHU_APP_ID      │
                                                    │  FEISHU_APP_SECRET  │
                                                    └──────────┬──────────┘
                                                               │
                              ┌─────────────────┬──────────────┼──────────────┐
                              │                 │              │              │
                              ▼                 ▼              ▼              ▼
┌──────────────┐      ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ Claude Code  │─────▶│ Callback A  │   │ Callback B  │   │ Callback C  │
│   实例 A     │      │ :8081       │   │ :8082       │   │ :8083       │
└──────────────┘      └─────────────┘   └─────────────┘   └─────────────┘
       │                     │                 │              │
       │                     └─────────────────┴──────────────┘
       │                               按钮 value 携带 callback_url
       │                               网关自动路由到对应服务
       ▼
 (独立 FEISHU_OWNER_ID)
```

### 数据流向

#### 发送消息流程

```
1. Claude Code 触发权限请求
       ↓
2. hook-router.sh 接收 Hook 事件
       ↓
3. permission.sh 构建飞书卡片
       ↓
4. 通过 Unix Socket 注册请求到回调服务
       ↓
5. 调用飞书 OpenAPI 发送卡片
   - 单机：直接调用 message/send
   - 分离：通过网关调用 /feishu/send
       ↓
6. 飞书群聊显示交互卡片
```

#### 用户操作流程（飞书内响应）

```
1. 用户点击飞书卡片按钮
       ↓
2. 飞书发送 card.action.trigger 事件
   - 单机：直接发送到本机服务
   - 分离：发送到网关
       ↓
3. 事件处理器解析操作
       ↓
4. 通过 Unix Socket 返回决策
       ↓
5. permission.sh 接收决策
       ↓
6. Claude Code 继续或拒绝执行
       ↓
7. 飞书显示操作结果 Toast
```

---

## 组件列表

| 组件 | 路径 | 说明 |
|------|------|------|
| Hook 路由 | `src/hook-router.sh` | Claude Code Hook 统一入口 |
| 权限处理 | `src/hooks/permission.sh` | 构建并发送飞书卡片 |
| 卡片模板 | `src/templates/feishu/buttons-openapi.json` | OpenAPI 模式卡片模板 |
| 回调服务 | `src/server/main.py` | ThreadedHTTPServer，处理飞书事件回调 |
| 飞书事件处理器 | `src/server/handlers/feishu.py` | 处理飞书事件（网关功能） |
| 会话继续 | `src/server/handlers/claude.py` | 处理回复继续会话 |
| Message-Session Store | `src/server/services/message_session_store.py` | 消息 ID 与会话映射 |
| Session-Chat Store | `src/server/services/session_chat_store.py` | 会话 ID 与群聊映射 |
| Auth Token Store | `src/server/services/auth_token_store.py` | 网关注册令牌存储 |
| Binding Store | `src/server/services/binding_store.py` | 网关注册绑定存储（owner_id → callback_url） |
| Dir History Store | `src/server/services/dir_history_store.py` | 目录使用历史 |
| 飞书 API 服务 | `src/server/services/feishu_api.py` | 飞书 OpenAPI 封装 |
| 自动注册 | `src/server/services/auto_register.py` | Callback 向网关注册 |
| 认证令牌 | `src/server/services/auth_token.py` | 双向认证令牌管理 |

---

## 配置说明

### 单机部署配置

```bash
# .env 文件
FEISHU_SEND_MODE=openapi

# 必需配置
FEISHU_APP_ID=cli_xxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxx
FEISHU_VERIFICATION_TOKEN=your_verification_token
FEISHU_OWNER_ID=ou_xxx  # 默认消息接收者（必需）

# 可选配置
CALLBACK_SERVER_URL=http://localhost:8080
CALLBACK_SERVER_PORT=8080
```

### 分离部署配置

#### 网关服务配置

```bash
# 网关 .env
FEISHU_SEND_MODE=openapi
FEISHU_APP_ID=cli_xxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxx
FEISHU_VERIFICATION_TOKEN=your_verification_token
FEISHU_OWNER_ID=ou_admin_user  # 默认接收者
CALLBACK_SERVER_PORT=8080
```

#### Callback 服务配置

每个 Callback 实例配置如下：

```bash
# Callback 实例 .env
FEISHU_SEND_MODE=openapi
FEISHU_GATEWAY_URL=http://gateway-server:8080  # 网关地址
CALLBACK_SERVER_URL=http://instance-a:8081     # 本机外部访问地址
CALLBACK_SERVER_PORT=8081
FEISHU_OWNER_ID=ou_user_a  # 此实例的消息接收者
```

> **注意**：Callback 服务不需要 `FEISHU_VERIFICATION_TOKEN`，网关请求通过注册时下发的 `auth_token` 验证。

### 配置清单

| 变量 | 必需 | 默认值 | 说明 |
|------|:----:|:------:|------|
| `FEISHU_SEND_MODE` | 否 | `webhook` | 发送模式（设为 `openapi`） |
| `FEISHU_APP_ID` | **网关** | - | 飞书应用 App ID（单机/网关必需，Callback 不需要） |
| `FEISHU_APP_SECRET` | **网关** | - | 飞书应用 App Secret（单机/网关必需，Callback 不需要） |
| `FEISHU_VERIFICATION_TOKEN` | **网关** | - | 飞书验证 Token（单机/网关必需，Callback 不需要） |
| `FEISHU_OWNER_ID` | **是** | - | 默认消息接收者（OpenAPI 模式必需） |
| `FEISHU_CHAT_ID` | 否 | - | 默认群聊 ID |
| `FEISHU_GATEWAY_URL` | **Callback** | - | 网关地址（分离部署时 Callback 必需） |
| `CALLBACK_SERVER_URL` | **是** | `http://localhost:8080` | 回调服务外部访问地址 |
| `CALLBACK_SERVER_PORT` | 否 | `8080` | 回调服务监听端口 |

---

## 飞书应用配置

### 1. 创建应用

1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 点击「创建企业自建应用」
3. 填写应用名称和描述
4. 记录 `App ID` 和 `App Secret`

### 2. 配置权限

在「权限管理」中开通以下权限：

| 权限名称 | 权限代码 | 说明 | 必需 |
|----------|----------|------|:----:|
| 获取用户基本信息 | `contact:user.base:readonly` | 获取用户信息 | ✓ |
| 获取用户统一 ID | `contact:user.union_id:readonly` | 获取用户 union_id | |
| 发送消息 | `im:message` | 发送飞书消息 | ✓ |
| 接收消息 | `im:message:receive_as_bot` | 接收飞书事件 | ✓ |

### 3. 配置事件订阅

在「事件订阅」中配置：

**请求地址**：
- 单机部署：`http://your-server:8080/feishu/event`
- 分离部署：`http://gateway-server:8080/feishu/event`

**订阅事件**：

| 事件类型 | 说明 | 必需 |
|----------|------|:----:|
| `card.action.trigger` | 卡片按钮点击事件 | ✓ |
| `im.message.receive_v1` | 接收消息事件（回复继续会话） | ✓ |

### 4. 配置加密与签名

在「加密与签名」中：
1. 启用「事件订阅验证」
2. 记录「验证 Token」（用于 `FEISHU_VERIFICATION_TOKEN`）
3. 可选：配置「加密 Key」

### 5. 发布版本

1. 配置完成后点击「创建版本」
2. 申请发布到生产环境
3. 等待管理员审批

### 6. 配置可用范围

在「应用发布」→「可用范围」中：
- **全员可访问**：所有企业成员可见
- **指定部门/成员**：仅指定人员可见（推荐生产环境）

---

## 部署步骤

### 单机部署

```bash
# 1. 在飞书开放平台创建应用，获取凭证
# 记录 APP_ID、APP_SECRET、VERIFICATION_TOKEN

# 2. 运行安装脚本
./install.sh

# 3. 配置环境变量
cp .env.example .env
vim .env
```

**配置示例**：
```bash
FEISHU_SEND_MODE=openapi
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_VERIFICATION_TOKEN=xxx
FEISHU_OWNER_ID=ou_xxx  # 默认接收者
CALLBACK_SERVER_URL=http://your-server:8080
```

```bash
# 4. 配置飞书应用事件订阅
# 请求地址：http://your-server:8080/feishu/event

# 5. 启动服务
./src/start-server.sh

# 6. 启动 Claude Code
claude
```

### 分离部署

#### 网关服务部署

```bash
# 在网关服务器上
git clone ... && cd claude-notify
./install.sh

# 配置
cat > .env << EOF
FEISHU_SEND_MODE=openapi
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_VERIFICATION_TOKEN=xxx
FEISHU_OWNER_ID=ou_admin
CALLBACK_SERVER_PORT=8080
EOF

# 启动网关
./src/start-server.sh
```

#### Callback 服务部署

在每个需要运行 Claude Code 的机器上：

```bash
# 在实例机器上
git clone ... && cd claude-notify
./install.sh

# 配置
cat > .env << EOF
FEISHU_SEND_MODE=openapi
FEISHU_GATEWAY_URL=http://gateway-server:8080
FEISHU_OWNER_ID=ou_user_a
CALLBACK_SERVER_URL=http://this-machine:8081
CALLBACK_SERVER_PORT=8081
EOF

# 启动服务
./src/start-server.sh
```

---

## 网关注册与双向认证

### 功能说明

分离部署模式下，Callback 服务启动时自动向飞书网关注册，获取 `auth_token` 用于后续通信认证。

### 工作流程

```
┌─────────────────┐      注册请求      ┌─────────────────┐
│ Callback 服务   │───────────────────▶│  飞书网关       │
│ (启动时)        │  /register          │                 │
└─────────────────┘                     └────────┬────────┘
                                                │
                                        验证 VERIFICATION_TOKEN
                                                │
                                        生成 auth_token
                                                │
┌─────────────────┘                     ┌────────▼────────┐
│                 │◀────────────────────│  返回 Token     │
│ 存储 auth_token │                     └─────────────────┘
└─────────────────┘
```

### 注册配置

| 变量 | 必需 | 说明 |
|------|:----:|------|
| `CALLBACK_SERVER_URL` | **是** | Callback 服务外部访问地址 |
| `FEISHU_OWNER_ID` | **是** | 默认消息接收者 |
| `FEISHU_GATEWAY_URL` | **是** | 飞书网关地址 |

> **注意**：Callback 服务不需要 `FEISHU_VERIFICATION_TOKEN`，网关通过注册时生成的 `auth_token` 验证请求。

### 用户授权控制

新设备首次注册时需要用户确认：

1. 首次注册时，网关发送确认消息到 `FEISHU_OWNER_ID`
2. 用户在飞书中点击「确认授权」按钮
3. 网关记录授权状态，后续请求直接通过

> 详细机制请参考 [飞书网关认证与注册机制](GATEWAY_AUTH.md)

---

## 群聊功能

### 功能说明

OpenAPI 模式支持将消息发送到飞书群聊，而非仅限私聊。

### 消息发送目标

消息发送目标的优先级：

```
chat_id 参数 > owner_id
```

- `chat_id 参数`：客户端调用时传入的群聊 ID
- `owner_id`：默认消息接收者

### 配置方式

通过环境变量配置默认群聊：

```bash
# .env 文件
FEISHU_CHAT_ID=oc_xxxxxxxxx  # 群聊 ID

# FEISHU_OWNER_ID 仍需配置（用于网关注册和认证）
FEISHU_OWNER_ID=ou_xxx
```

> **说明**：`FEISHU_CHAT_ID` 由客户端 Shell 脚本读取，调用网关时会作为 `chat_id` 参数传递。

### Session 与群聊映射

当用户在群聊中回复消息继续会话时，系统会自动记录 `session_id -> chat_id` 映射：

```
┌─────────────┐    回复消息     ┌─────────────┐
│ 群聊        │───────────────▶│  网关接收    │
│ (chat_id)   │                │  (session)  │
└─────────────┘                └──────┬──────┘
                                      │
                               保存映射关系
                               session_id → chat_id
                                      │
                               ┌──────▼──────┐
                               │  后续消息    │
                               │  发往该群聊  │
                               └─────────────┘
```

这样，后续该 session 的通知消息会自动发送到对应的群聊。

### 多实例配置

每个 Callback 实例可以配置不同的群聊：

| 实例 | FEISHU_OWNER_ID | FEISHU_CHAT_ID | 效果 |
|------|-----------------|----------------|------|
| 实例 A | `ou_user_a` | `oc_group_a` | 消息发往群聊 A |
| 实例 B | `ou_user_b` | `oc_group_b` | 消息发往群聊 B |

---

## 安全配置

### 必需安全措施

| 措施 | 优先级 | 说明 |
|------|:------:|------|
| **Verification Token** | 严重 | ✅ 必须配置 `FEISHU_VERIFICATION_TOKEN` |
| **HTTPS** | 高 | 生产环境使用 HTTPS |
| **Callback 白名单** | 高 | 分离部署时必须配置 |

### 推荐 .env 配置

```bash
# 单机部署
FEISHU_VERIFICATION_TOKEN=your_verification_token  # 必须配置！

# 分离部署 - 网关
FEISHU_VERIFICATION_TOKEN=your_verification_token

# 分离部署 - Callback（不需要 VERIFICATION_TOKEN）
FEISHU_GATEWAY_URL=http://gateway-server:8080
```

### 安全检查清单

- [ ] OpenAPI 模式是否配置了 `FEISHU_VERIFICATION_TOKEN`
- [ ] 分离部署是否配置了 Callback 白名单
- [ ] `FEISHU_APP_SECRET` 是否妥善保管
- [ ] 生产环境是否使用 HTTPS
- [ ] 服务是否运行在内网/防火墙后

> 完整的安全分析请参考 [通信鉴权与安全分析](SECURITY_ANALYSIS.md)

---

## 常见问题

### Q: 事件订阅 URL 验证失败？

**A:** 检查以下几点：
1. 服务是否已启动
2. URL 是否正确（`/feishu/event`）
3. `FEISHU_VERIFICATION_TOKEN` 是否正确
4. 网络是否能从公网访问

### Q: 点击按钮后没有反应？

**A:** 检查以下几点：
1. 飞书开放平台是否订阅了 `card.action.trigger` 事件
2. 服务日志中是否有错误信息
3. `FEISHU_VERIFICATION_TOKEN` 是否正确

### Q: 如何获取 FEISHU_OWNER_ID？

**A:** 有以下几种方式：
1. 在飞书开放平台「用户管理」中查看
2. 发送一条消息到你的飞书机器人，在日志中查看 `open_id`
3. 使用飞书 API `GET /contact/v3/users/:user_id`

### Q: 分离部署时 Callback 注册失败？

**A:** 检查以下几点：
1. `FEISHU_GATEWAY_URL` 是否正确
2. `CALLBACK_SERVER_URL` 是否可以从网关访问
3. 网关服务是否正常运行
4. 检查网关日志中是否有注册请求记录

### Q: 如何配置多个 Claude 命令？

**A:** 在 `.env` 中配置：
```bash
CLAUDE_COMMAND=[claude, claude --setting opus]
```

然后在飞书中：
- `/new --cmd=0 --dir=/path prompt` — 使用第一个命令 `claude`
- `/new --cmd=1 --dir=/path prompt` — 使用第二个命令 `claude --setting opus`
- `/new --cmd=opus --dir=/path prompt` — 子串匹配，命中 `claude --setting opus`

> **说明**：`--cmd` 支持两种匹配方式：
> - **索引**：从 0 开始，`--cmd=0` 表示第一个命令
> - **子串**：大小写敏感，查找命令字符串中是否包含指定子串

### Q: 回复消息继续会话不生效？

**A:** 检查以下几点：
1. 飞书应用是否订阅了 `im.message.receive_v1` 事件
2. 消息是否是「回复」形式（不是新消息）
3. 原消息是否包含 `session_id`

---

## 相关文档

- [Webhook 模式部署文档](DEPLOYMENT_WEBHOOK.md) - Webhook 模式详细说明
- [模式选择指南](DEPLOYMENT_MODES.md) - 两种模式对比与选择
- [飞书消息回复继续会话方案](FEISHU_SESSION_CONTINUE.md) - 回复继续功能详细设计
- [飞书网关认证与注册机制](GATEWAY_AUTH.md) - 网关注册与双向认证详细说明
- [通信鉴权与安全分析](SECURITY_ANALYSIS.md) - 安全风险评估与加固建议
- [Socket 通信协议](../src/shared/protocol.md) - Unix Socket 通信规范
