# 部署模式架构文档

本文档详细说明项目支持的两种部署模式：Webhook 模式和 OpenAPI 模式。

## 目录

- [模式对比](#模式对比)
- [Webhook 模式](#webhook-模式)
- [OpenAPI 模式](#openapi-模式)
- [配置清单](#配置清单)
- [部署选择指南](#部署选择指南)
- [网关注册与认证](#网关注册与认证)
- [群聊绑定功能](#群聊绑定功能)

---

## 模式对比

| 特性 | Webhook 模式 | OpenAPI 模式 |
|------|-------------|-------------|
| **飞书应用** | 无需注册，使用机器人 Webhook | 需要创建飞书开放平台应用 |
| **交互方式** | 按钮跳转浏览器页面 | 按钮直接在飞书内响应 |
| **配置复杂度** | 简单（仅需 Webhook URL） | 较复杂（需配置应用凭证） |
| **多实例部署** | 不支持 | 支持分离部署 |
| **回复继续会话** | 不支持 | 支持 |
| **群聊绑定** | 不支持 | 支持 |
| **自动注册与双向认证** | 不支持 | 支持 |
| **推荐场景** | 个人使用、快速体验 | 团队协作、多机器部署 |

---

## Webhook 模式

### 架构概览

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│  Claude Code    │────────▶│ src/hook-router  │────────▶│  飞书 Webhook   │
│                 │  Hook   │  → permission.sh │  Card   │     URL         │
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
                                     │ HTTP Callback
                                     │ (浏览器访问)
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

### 数据流向

1. **发送通知**：Claude Code → Hook 路由 → 飞书 Webhook URL
2. **用户操作**：点击按钮 → 浏览器跳转到 Callback 服务
3. **决策返回**：Callback 服务 → Unix Socket → Hook 脚本 → Claude Code

### 组件列表

| 组件 | 路径 | 说明 |
|------|------|------|
| Hook 路由 | `src/hook-router.sh` | Claude Code Hook 统一入口 |
| 权限处理 | `src/hooks/permission.sh` | 构建并发送飞书卡片 |
| 卡片模板 | `src/templates/feishu/buttons.json` | Webhook 模式卡片模板 |
| 回调服务 | `src/server/main.py` | ThreadedHTTPServer，处理浏览器回调请求 |
| Socket 服务器 | `src/server/main.py:run_socket_server` | Unix Socket 服务器，接收 Hook 连接 |
| 请求管理器 | `src/server/services/request_manager.py` | 管理等待中的权限请求 |

### 配置要求

```bash
# .env 文件
FEISHU_SEND_MODE=webhook

# 必需配置
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx

# 可选配置
CALLBACK_SERVER_URL=http://localhost:8080
CALLBACK_SERVER_PORT=8080
PERMISSION_SOCKET_PATH=/tmp/claude-permission.sock
```

### 部署步骤

```bash
# 1. 获取飞书机器人 Webhook URL
# 在飞书群设置 → 群机器人 → 添加机器人 → 自定义机器人 → 获取 Webhook URL

# 2. 运行安装脚本
./install.sh

# 3. 配置环境变量
cp .env.example .env
vim .env  # 设置 FEISHU_WEBHOOK_URL

# 4. 启动回调服务
./src/start-server.sh

# 5. 启动 Claude Code
claude
```

### 限制

| 限制项 | 说明 |
|--------|------|
| **交互跳转** | 需要打开浏览器，无法在飞书内直接响应 |
| **多实例** | 不支持，每个实例需要独立的 Webhook |
| **回复继续** | 不支持消息回复继续会话 |

---

## OpenAPI 模式

### 架构概览

#### 单机部署

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

#### 分离部署（多实例）

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
 (独立 FEISHU_RECEIVE_ID)
```

### 数据流向

#### 发送消息流程

1. **获取 Token**：服务启动时用 `APP_ID/APP_SECRET` 获取 `access_token`
2. **构建卡片**：使用 `buttons-openapi.json` 模板
3. **发送卡片**：调用飞书 `message/send` API
4. **用户操作**：点击按钮触发 `card.action.trigger` 事件

#### 分离部署流程

1. **Callback 服务**：通过 `FEISHU_GATEWAY_URL` 发送卡片
2. **按钮携带**：`callback_url` 字段标识本机地址
3. **网关接收**：飞书事件发送到网关
4. **网关路由**：解析 `callback_url`，转发决策到对应实例

### 组件列表

| 组件 | 路径 | 说明 |
|------|------|------|
| Hook 路由 | `src/hook-router.sh` | Claude Code Hook 统一入口 |
| 权限处理 | `src/hooks/permission.sh` | 构建并发送飞书卡片 |
| 卡片模板 | `src/templates/feishu/buttons-openapi.json` | OpenAPI 模式卡片模板 |
| 回调服务 | `src/server/main.py` | ThreadedHTTPServer，处理飞书事件回调 |
| 飞书事件处理器 | `src/server/handlers/feishu.py` | 处理飞书事件（网关功能） |
| 会话继续 | `src/server/handlers/claude.py` | 处理回复继续会话 |
| Session Store | `src/server/services/session_store.py` | 消息 ID 与会话映射 |
| Binding Store | `src/server/services/binding_store.py` | 群聊绑定存储 |
| 飞书 API 服务 | `src/server/services/feishu_api.py` | 飞书 OpenAPI 封装 |
| 自动注册 | `src/server/services/auto_register.py` | Callback 向网关注册 |
| 认证令牌 | `src/server/services/auth_token.py` | 双向认证令牌管理 |

### 配置要求

#### 单机部署

```bash
# .env 文件
FEISHU_SEND_MODE=openapi

# 必需配置
FEISHU_APP_ID=cli_xxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxx
FEISHU_VERIFICATION_TOKEN=your_verification_token  # 从飞书开放平台获取

# 可选配置
FEISHU_OWNER_ID=ou_xxx  # 默认消息接收者
CALLBACK_SERVER_URL=http://localhost:8080
CALLBACK_SERVER_PORT=8080
```

#### 分离部署

**网关服务配置**：
```bash
FEISHU_SEND_MODE=openapi
FEISHU_APP_ID=cli_xxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxx
FEISHU_VERIFICATION_TOKEN=your_verification_token
FEISHU_OWNER_ID=ou_admin_user  # 默认接收者
CALLBACK_SERVER_PORT=8080
```

**Callback 服务配置**（实例 A）：
```bash
FEISHU_SEND_MODE=openapi
FEISHU_GATEWAY_URL=http://gateway-server:8080  # 网关地址
CALLBACK_SERVER_URL=http://instance-a:8081  # 本机外部访问地址
CALLBACK_SERVER_PORT=8081
FEISHU_VERIFICATION_TOKEN=your_verification_token  # 需与网关一致
FEISHU_OWNER_ID=ou_user_a  # 此实例的消息接收者
```

**Callback 服务配置**（实例 B）：
```bash
FEISHU_SEND_MODE=openapi
FEISHU_GATEWAY_URL=http://gateway-server:8080
CALLBACK_SERVER_URL=http://instance-b:8082
CALLBACK_SERVER_PORT=8082
FEISHU_VERIFICATION_TOKEN=your_verification_token  # 需与网关一致
FEISHU_OWNER_ID=ou_user_b  # 此实例的消息接收者
```

### 飞书应用配置

#### 1. 创建应用

1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 记录 `App ID` 和 `App Secret`
4. 在「凭证与基础信息」页面获取 `Verification Token`

#### 2. 配置权限

在应用权限管理中开通以下权限：

| 权限名称 | 权限代码 | 说明 |
|----------|----------|------|
| 获取用户基本信息 | `contact:user.base:readonly` | 获取用户信息（必需） |
| 获取用户统一 ID | `contact:user.union_id:readonly` | 获取用户 union_id（可选） |
| 发送消息 | `im:message` | 发送飞书消息（必需） |
| 接收消息 | `im:message` | 接收飞书事件（必需） |

#### 3. 配置事件订阅

在应用事件订阅中添加：

| 事件类型 | 说明 | 必需 |
|----------|------|:----:|
| `card.action.trigger` | 卡片按钮点击事件 | ✓ |
| `im.message.receive_v1` | 接收消息事件（用于回复继续会话） | ✓ |

**请求地址配置**：
- 单机部署：`http://your-server:8080/feishu/event`
- 分离部署：`http://gateway-server:8080/feishu/event`

**加密与签名**：
- 启用「事件订阅验证」
- 配置「加密 Key」（可选，用于消息加密）
- 记录「验证 Token」用于验证事件来源

#### 4. 发布版本

配置完成后，需要创建版本并发布到生产环境。

#### 5. 配置权限范围

根据需要配置应用的可访问范围：
- **全员可访问**：所有企业成员可见
- **指定部门/成员**：仅指定人员可见（推荐用于生产环境）

### 部署步骤

#### 单机部署

```bash
# 1. 在飞书开放平台创建应用，获取凭证
# 记录 APP_ID、APP_SECRET

# 2. 运行安装脚本
./install.sh

# 3. 配置环境变量
cp .env.example .env
vim .env
# FEISHU_SEND_MODE=openapi
# FEISHU_APP_ID=cli_xxx
# FEISHU_APP_SECRET=xxx
# FEISHU_OWNER_ID=ou_xxx  # 默认接收者（可选）

# 4. 配置飞书应用事件订阅
# 请求地址：http://your-server:8080/feishu/event

# 5. 启动服务
./src/start-server.sh

# 6. 启动 Claude Code
claude
```

#### 分离部署

**网关服务**：
```bash
# 网关服务器
git clone ... && cd claude-notify
./install.sh

# 配置
cat > .env << EOF
FEISHU_SEND_MODE=openapi
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
CALLBACK_SERVER_PORT=8080
EOF

# 启动网关
./src/start-server.sh
```

**Callback 服务**（每台机器）：
```bash
# 实例机器
git clone ... && cd claude-notify
./install.sh

# 配置
cat > .env << EOF
FEISHU_SEND_MODE=openapi
FEISHU_GATEWAY_URL=http://gateway-server:8080
CALLBACK_SERVER_PORT=8081
CALLBACK_SERVER_URL=http://this-machine:8081
EOF

# 启动服务
./src/start-server.sh
```

---

## 配置清单

### 发送模式

| 变量 | 必需 | 默认值 | 说明 |
|------|:----:|:------:|------|
| `FEISHU_SEND_MODE` | 否 | `webhook` | 发送模式：`webhook` 或 `openapi` |

### Webhook 模式配置

| 变量 | 必需 | 默认值 | 说明 |
|------|:----:|:------:|------|
| `FEISHU_WEBHOOK_URL` | 是 | - | 飞书机器人 Webhook URL |

### OpenAPI 模式配置

| 变量 | 必需 | 默认值 | 说明 |
|------|:----:|:------:|------|
| `FEISHU_APP_ID` | 是 | - | 飞书应用 App ID |
| `FEISHU_APP_SECRET` | 是 | - | 飞书应用 App Secret |
| `FEISHU_VERIFICATION_TOKEN` | 是 | - | 飞书验证 Token（用于验证事件来源） |
| `FEISHU_OWNER_ID` | 否 | - | 默认消息接收者 / @ 用户 |
| `FEISHU_CHAT_ID` | 否 | - | 默认群聊 ID（群聊绑定功能） |
| `FEISHU_GATEWAY_URL` | 否 | - | 网关地址（分离部署时） |

### 通用配置

| 变量 | 必需 | 默认值 | 说明 |
|------|:----:|:------:|------|
| `CALLBACK_SERVER_URL` | 否 | `http://localhost:8080` | 回调服务外部访问地址 |
| `CALLBACK_SERVER_PORT` | 否 | `8080` | 回调服务监听端口 |
| `PERMISSION_SOCKET_PATH` | 否 | `/tmp/claude-permission.sock` | Unix Socket 路径 |
| `PERMISSION_NOTIFY_DELAY` | 否 | `60` | 权限通知延迟（秒） |
| `REQUEST_TIMEOUT` | 否 | `300` | 请求超时时间（秒） |
| `CLOSE_PAGE_TIMEOUT` | 否 | `3` | 决策页面自动关闭延迟（秒） |
| `ACTIVATE_VSCODE_ON_CALLBACK` | 否 | `false` | 回调时激活 VSCode |
| `VSCODE_URI_PREFIX` | 否 | - | VSCode URI 前缀 |
| `VSCODE_SSH_PROXY_PORT` | 否 | - | VSCode SSH 代理端口 |
| `FEISHU_OWNER_ID` | 否 | - | 默认接收者 / 通知 @ 用户 |
| `FEISHU_AT_USER` | 否 | 空(@ owner) | 通知 @ 配置：空=@ owner，`all`=@ 所有人，`off`=禁用 |
| `CLAUDE_COMMAND` | 否 | `claude` | Claude 命令路径 |
| `STOP_MESSAGE_MAX_LENGTH` | 否 | `5000` | 任务完成通知最大长度 |

---

## 部署选择指南

### 选择 Webhook 模式

**适用场景**：
- 个人使用
- 快速体验功能
- 无需飞书应用权限
- 单机器部署

**优点**：
- 配置简单，2 分钟完成
- 无需飞书应用审核
- 无需配置事件订阅

**缺点**：
- 需要打开浏览器操作
- 不支持多实例部署
- 不支持回复继续会话

### 选择 OpenAPI 模式

**适用场景**：
- 团队协作使用
- 多机器/多实例部署
- 需要飞书内直接响应
- 需要回复继续会话功能

**优点**：
- 飞书内直接操作，无需跳转
- 支持分离部署，多实例共享应用
- 支持消息回复继续会话
- 用户体验更好

**缺点**：
- 配置复杂，需要飞书应用
- 需要配置事件订阅和权限

### 决策流程图

```
是否需要多实例部署？
    │
    ├─ 是 → OpenAPI 模式 + 分离部署
    │
    └─ 否 → 是否需要飞书内直接响应？
              │
              ├─ 是 → OpenAPI 模式 + 单机部署
              │
              └─ 否 → Webhook 模式（快速开始）
```

---

## 安全配置

> **重要**: 当前版本存在多个安全风险，详见 [通信鉴权与安全分析](SECURITY_ANALYSIS.md)

### 已实现的安全措施 ✅

| 措施 | 说明 |
|------|------|
| **Verification Token** | 飞书事件回调验证（需配置 `FEISHU_VERIFICATION_TOKEN`） |

### 剩余安全风险

| 风险 | 等级 | 影响范围 |
|------|:----:|----------|
| 无鉴权的权限决策接口 | **中** | 所有模式 |
| Callback URL 无白名单 | **高** | 分离部署 |
| 飞书发送接口无保护 | **高** | OpenAPI 模式 |
| 会话继续接口无验证 | **高** | OpenAPI 模式 |
| Socket 权限过宽 | **中** | 所有模式 |

> **注**：权限决策接口风险因 request_id 已优化为 32 位随机字符，从「严重」降为「中」。内网部署时风险可忽略，公网部署建议配合速率限制。

### 安全配置项

| 变量 | 必需 | 默认值 | 说明 |
|------|:----:|:------:|------|
| `FEISHU_VERIFICATION_TOKEN` | 是* | - | 飞书验证 Token（*OpenAPI 模式必须） |
| `ALLOWED_CALLBACK_DOMAINS` | 是* | - | 允许的 Callback 域名白名单（*分离部署必须） |

### 安全加固建议

#### Webhook 模式

| 建议 | 优先级 | 说明 |
|------|:------:|------|
| **内网部署** | 高 | 服务仅监听 127.0.0.1 |
| **防火墙** | 高 | 限制端口仅本地访问 |
| **速率限制** | 中 | 公网部署时建议添加 Nginx rate limiting |

```bash
# 推荐 .env 配置
CALLBACK_SERVER_URL=http://127.0.0.1:8080
```

#### OpenAPI 模式

| 建议 | 优先级 | 说明 |
|------|:------:|------|
| **Verification Token** | 严重 | ✅ 必须配置 FEISHU_VERIFICATION_TOKEN |
| **Callback 白名单** | 高 | 分离部署时必须配置 |
| **HTTPS** | 中 | 生产环境使用 HTTPS |
| **IP 白名单** | 中 | 仅允许飞书服务器 IP |

```bash
# 推荐 .env 配置
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_VERIFICATION_TOKEN=your_verification_token  # 必须配置！
ALLOWED_CALLBACK_DOMAINS=localhost,127.0.0.1
```

#### 分离部署

| 建议 | 优先级 | 说明 |
|------|:------:|------|
| **内网通信** | 高 | 网关与 Callback 使用内网地址 |
| **Callback 白名单** | 严重 | 必须配置 ALLOWED_CALLBACK_DOMAINS |
| **共享密钥** | 高 | Gateway 与 Callback 间使用共享密钥 |

```bash
# 网关 .env
FEISHU_VERIFICATION_TOKEN=your_verification_token
ALLOWED_CALLBACK_DOMAINS=gateway-server,instance-a.internal,instance-b.internal

# Callback .env
FEISHU_GATEWAY_URL=http://gateway-server.internal:8080
ALLOWED_CALLBACK_DOMAINS=gateway-server.internal
```

### 部署前安全检查

- [ ] 服务是否运行在内网/防火墙后
- [ ] CALLBACK_SERVER_URL 是否使用内网地址
- [ ] OpenAPI 模式是否配置了 FEISHU_VERIFICATION_TOKEN
- [ ] 分离部署是否配置了 ALLOWED_CALLBACK_DOMAINS
- [ ] FEISHU_APP_SECRET 是否妥善保管
- [ ] Socket 文件权限是否为 0666

> 完整的安全分析、攻击场景和修复代码请参考 [通信鉴权与安全分析](SECURITY_ANALYSIS.md)

---

## 网关注册与双向认证

### 功能说明

在 OpenAPI 分离部署模式下，Callback 服务启动时会自动向飞书网关注册，实现双向认证机制。

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

### 自动注册配置

| 变量 | 必需 | 说明 |
|------|:----:|------|
| `CALLBACK_SERVER_URL` | 是 | Callback 服务外部访问地址 |
| `FEISHU_OWNER_ID` | 是 | 默认消息接收者 |
| `FEISHU_GATEWAY_URL` | 是 | 飞书网关地址 |
| `FEISHU_VERIFICATION_TOKEN` | 是 | 验证 Token（需与网关一致） |

### 注册成功后的行为

1. Callback 服务将 `auth_token` 存储到 `runtime/auth_token.json`
2. 后续所有飞书请求携带 `auth_token` 进行认证
3. 网关验证 Token 后才处理请求

### 用户授权控制

新设备注册时需要用户在飞书中确认：

1. 首次注册时，网关发送确认消息到 `FEISHU_OWNER_ID`
2. 用户在飞书中点击「确认授权」按钮
3. 网关记录授权状态，后续请求直接通过

> 详细机制请参考 [飞书网关认证与注册机制](GATEWAY_AUTH.md)

---

## 群聊绑定功能

### 功能说明

OpenAPI 模式支持将飞书群聊与用户绑定，实现多群聊消息路由。

### 消息路由优先级

```
client 参数 chat_id > FEISHU_CHAT_ID 配置 > owner_id
```

### 绑定流程

```
┌─────────────┐    发送消息    ┌─────────────┐
│ 用户        │───────────────▶│  飞书群聊   │
│ (owner_id)  │                │             │
└─────────────┘                └──────┬──────┘
                                      │
                               ┌──────▼──────┐
                               │  网关接收    │
                               │  (chat_id)  │
                               └──────┬──────┘
                                      │
                               记录绑定关系
                               chat_id ↔ owner_id
                                      │
                               ┌──────▼──────┐
                               │  后续消息    │
                               │  自动路由    │
                               └─────────────┘
```

### 配置方式

#### 方式一：通过环境变量

```bash
# .env 文件
FEISHU_CHAT_ID=oc_xxxxxxxxx  # 群聊 ID
```

#### 方式二：通过首次回复

1. 用户在群聊中发送任意消息
2. 网关自动记录 `chat_id` 与 `owner_id` 的绑定关系
3. 后续消息自动发送到该群聊

### 多群聊支持

每个 Callback 实例可以绑定到不同的群聊：

| 实例 | FEISHU_OWNER_ID | FEISHU_CHAT_ID | 效果 |
|------|-----------------|----------------|------|
| 实例 A | `ou_user_a` | `oc_group_a` | 消息发往群聊 A |
| 实例 B | `ou_user_b` | `oc_group_b` | 消息发往群聊 B |

### 查看绑定状态

绑定关系存储在 `runtime/binding_store.json`：

```json
{
  "oc_group_a": "ou_user_a",
  "oc_group_b": "ou_user_b"
}
```

---

## 相关文档

- [Socket 通信协议](../src/shared/protocol.md) - Unix Socket 通信规范
- [飞书卡片模板说明](../src/templates/feishu/README.md) - 卡片模板使用指南
- [飞书回复继续会话方案](FEISHU_SESSION_CONTINUE.md) - 回复继续功能详细设计
- [飞书网关认证与注册机制](GATEWAY_AUTH.md) - 网关注册与双向认证详细说明
- [通信鉴权与安全分析](SECURITY_ANALYSIS.md) - 安全风险评估与加固建议
