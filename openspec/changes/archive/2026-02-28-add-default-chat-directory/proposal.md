# Change: 支持默认聊天目录

## Why

当用户直接发送消息（无 `/new`、`/reply` 等指令，也非回复消息）时，系统仅返回使用提示。对于只在固定项目目录下使用 Claude 的用户来说，每次都需要输入 `/new --dir=...` 或通过卡片选择目录，操作繁琐。

支持配置一个默认聊天目录后，用户发送的普通消息会自动继续（或创建）会话，`/new prompt` 也会直接使用默认目录，大幅简化交互流程。

## What Changes

- 新增配置项 `DEFAULT_CHAT_DIR`，指定默认的 Claude 工作目录
- 服务启动时检测该目录是否存在，不存在则自动创建
- 普通消息处理逻辑变更：配置了默认目录时，自动继续活跃的默认会话（无活跃会话则新建）
- `/new prompt`（无 `--dir`）处理逻辑变更：配置了默认目录时，直接在默认目录创建新会话（跳过目录选择卡片），并替换为当前活跃的默认会话
- 新增"当前默认会话"存储，记录活跃的默认会话 ID
- 未配置时所有现有行为不变

### 行为矩阵

| 用户操作 | 有 `DEFAULT_CHAT_DIR` | 无 `DEFAULT_CHAT_DIR` |
|---|---|---|
| 普通消息 | 继续默认会话（无则新建） | 发送使用提示（现有行为） |
| `/new prompt` | 在默认目录新建会话，成为新的活跃默认会话 | 发送目录选择卡片（现有行为） |
| `/new --dir=/x prompt` | 在指定目录新建会话（不变） | 在指定目录新建会话（不变） |
| `/new`（无参数） | 发送目录选择卡片（不变） | 发送目录选择卡片（不变） |

## Impact

- Affected specs: `feishu-command`
- Affected code:
  - `src/server/handlers/feishu.py` — 普通消息分支 + `/new` 命令逻辑
  - `src/server/config.py` — 新增配置项
  - `src/server/main.py` — 启动时检测/创建目录
  - `src/server/services/` — 新增默认会话存储
  - `.env.example` — 新增配置说明
