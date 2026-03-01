## Context

当前普通消息（非指令、非回复）的处理逻辑固定返回使用提示，`/new prompt`（无 `--dir`）会发送目录选择卡片。需要在配置了默认目录时改变这两处行为，支持自动会话管理。

`DEFAULT_CHAT_DIR` 是用户级别配置（每个 Callback 后端独立配置），在分离部署场景下不同用户有不同的默认目录。

## Goals / Non-Goals

- Goals:
  - 普通消息自动继续/创建默认目录下的 Claude 会话
  - `/new prompt`（无 `--dir`）在默认目录直接创建新会话
  - 服务启动时自动创建不存在的默认目录
  - 新建的默认会话自动成为活跃默认会话
  - 分离部署时每个用户独立的默认目录
- Non-Goals:
  - 不改变 `/new --dir=...`、`/reply`、回复消息等现有行为
  - 不支持多个默认目录
  - 不支持 webhook 模式（无消息交互能力）

## Decisions

- **配置位置**: Callback 后端的 `.env` 文件中配置 `DEFAULT_CHAT_DIR`
- **传播路径**: Callback 注册时将 `default_chat_dir` 随 `claude_commands`、`reply_in_thread` 等字段一起传给网关，存入 `BindingStore` 中的 binding 数据
- **读取方式**: 消息处理时从用户的 `binding` 中读取 `default_chat_dir`，而非从本地 config 读取（确保分离部署时正确）
- **默认会话存储**: 持久化到 `BindingStore`，通过 `default_chat_session_id` 字段记录活跃会话 ID。网关重启后不丢失
- **普通消息触发条件**: 非指令 + 非回复 + 消息内容非空 + binding 中有 `default_chat_dir`
- **继续会话逻辑**: 检查 binding 中 `default_chat_session_id` 是否存在 → 存在则 continue → 不存在则 new 并写入
- **`/new prompt` 逻辑**: binding 中有 `default_chat_dir` 且无 `--dir` 且有 prompt → 直接 `_forward_new_request`，更新 binding 中的 `default_chat_session_id`
- **目录创建时机**: Callback 后端启动时（`main.py`），使用 `os.makedirs(dir, exist_ok=True)`
- **会话失效**: 不主动检测 Claude 进程状态；continue 失败时下游返回错误，用户再发消息或 `/new prompt` 即可重建

## Data Flow

```
Callback 后端 (.env: DEFAULT_CHAT_DIR=/path)
    ↓ auto_register
网关 BindingStore: binding[owner_id].default_chat_dir = "/path"
    ↓ 消息处理时
feishu.py: binding.get('default_chat_dir') → 路由决策
```

## Risks / Trade-offs

- 用户误发消息会自动继续 Claude 会话 → 可接受，用户可选择不配置此项
- 服务重启后活跃会话不丢失（已持久化到 BindingStore）
- continue 失败时需要用户手动 `/new` 重建 → 简单明确，不做过度自动化
- 注册数据中增加字段 → 向后兼容（新字段缺失时默认空字符串）
