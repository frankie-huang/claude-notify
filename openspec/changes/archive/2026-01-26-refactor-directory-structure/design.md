# Design: 目录重构技术设计

## Context

当前项目根目录有 15+ 个一级目录/文件，随着功能增加，结构变得分散。Shell 和 Python 代码混在不同顶级目录，路径引用方式不统一，导致：

1. 新用户难以快速理解项目结构
2. 路径硬编码分散，重构时需要大量更新
3. 入口文件不够突出

本设计定义重构的技术方案，重点解决路径自适应问题。

## Goals / Non-Goals

### Goals
- 根目录精简，源代码集中到 `src/`
- 入口脚本置于 `src/` 一级，便于快速定位
- 建立统一的路径解析机制，提高路径自适应能力
- 适度合并重复代码

### Non-Goals
- 不改变现有功能逻辑
- 不改变外部接口（飞书 Webhook 格式、Socket 协议等）
- 不改变 `.env` 配置项名称

## Decisions

### Decision 1: 项目路径解析机制

**选择**：使用 `readlink -f` + 相对路径向上查找

**实现**：
```bash
# src/lib/core.sh
get_project_root() {
    local real_path
    real_path="$(readlink -f "${BASH_SOURCE[0]}")"
    # 从 src/lib/core.sh 向上两级到项目根目录
    printf '%s' "$(cd "$(dirname "$real_path")/../.." && pwd)"
}

# 初始化路径变量
PROJECT_ROOT="$(get_project_root)"
SRC_DIR="$PROJECT_ROOT/src"
LIB_DIR="$SRC_DIR/lib"
CONFIG_DIR="$SRC_DIR/config"
TEMPLATES_DIR="$SRC_DIR/templates"
```

**优点**：
- 支持软链接调用（如 `/usr/local/bin/hook` -> 实际路径）
- 无论从哪个目录执行，都能正确解析
- 路径变量集中定义，便于维护

**备选方案**：
- 使用环境变量 `CLAUDE_NOTIFY_ROOT`：需要用户手动设置，增加配置复杂度
- 使用 `$0` 解析：不支持 source 场景

### Decision 2: Shell 库合并策略

**选择**：合并 `project.sh`、`env.sh`、`log.sh` 为 `core.sh`

**理由**：
- 这三个库几乎被所有脚本引用
- 合并后减少 source 语句数量
- 初始化逻辑可以统一（路径解析 → 环境加载 → 日志初始化）

**合并后结构**：
```bash
# src/lib/core.sh
# 包含：
# - 路径变量定义（PROJECT_ROOT, SRC_DIR, LIB_DIR 等）
# - get_config() 函数（从 .env 读取配置）
# - log() 函数及日志初始化
```

**保持独立的库**：
- `json.sh` - JSON 解析逻辑复杂，保持独立
- `feishu.sh` - 飞书卡片构建
- `socket.sh` - Socket 通信
- `tool.sh` - 工具详情提取
- `vscode-proxy.sh` - VSCode 代理客户端

### Decision 3: Hook 路由机制

**选择**：创建统一的 `hook-router.sh` 作为唯一入口

**关键问题：stdin 只能读取一次**

Claude Code 通过 stdin 传入 JSON 数据，路由脚本必须先读取并保存，再传递给子脚本：

```bash
# src/hook-router.sh - 统一 Hook 入口
#!/bin/bash

# 获取脚本所在目录（支持软链接）
SCRIPT_DIR="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"

# 初始化核心库（路径、环境、日志）
source "$SCRIPT_DIR/lib/core.sh"

# 初始化 JSON 解析器（自动选择 jq > python3 > grep/sed）
source "$LIB_DIR/json.sh"
json_init

# 读取 stdin 到变量（只能读取一次，子脚本共享此变量）
INPUT=$(cat)

# 使用 json_get 解析事件类型（自动降级，不强依赖 jq）
HOOK_EVENT=$(json_get "$INPUT" "event")
HOOK_EVENT="${HOOK_EVENT:-unknown}"

log "Hook event: $HOOK_EVENT"

# 根据事件类型分发到对应处理脚本
# 子脚本通过 $INPUT 变量获取输入数据（不再从 stdin 读取）
case "$HOOK_EVENT" in
    PermissionRequest)
        source "$SRC_DIR/hooks/permission.sh"
        ;;
    Notification|Stop)
        source "$SRC_DIR/hooks/webhook.sh"
        ;;
    *)
        log "Unknown hook event: $HOOK_EVENT"
        exit 1
        ;;
esac
```

**JSON 解析降级机制**（复用现有 `lib/json.sh`）：
- 优先使用 `jq`（最可靠）
- 降级到 `python3`（跨平台）
- 最后降级到 `grep/sed`（有限支持）

所有 JSON 解析统一使用 `json_get()` 函数，不直接调用 jq/python3。

**子脚本改造**：
```bash
# src/hooks/permission.sh
# 不再从 stdin 读取，直接使用 $INPUT 变量（由 hook-router.sh 设置）
# 不再调用 json_init（已由 hook-router.sh 初始化）

# INPUT=$(cat)      # 删除这行
# json_init         # 删除这行

# 直接使用 $INPUT 和 json_get（JSON 解析器已初始化）
TOOL_NAME=$(json_get "$INPUT" "tool_name")
SESSION_ID=$(json_get "$INPUT" "session_id")
# ... 其余逻辑不变
```

**优点**：
- 单一入口，Claude Code 只需配置一个 hook 路径
- 公共初始化逻辑（路径、环境、日志、JSON）只写一次
- 便于添加新的 Hook 类型
- 目录结构更清晰

**备选方案**：保持独立脚本方式
- 优点：故障隔离，调试简单
- 缺点：配置多个路径，初始化逻辑重复

**决定**：采用统一路由模式

目录结构：
- `src/hook-router.sh` - 唯一入口（配置到 Claude Code）
- `src/hooks/permission.sh` - 权限请求处理逻辑
- `src/hooks/webhook.sh` - 通用通知处理逻辑

### Decision 4: Python 路径解析

**选择**：保持 Python 使用相对导入 + `__file__` 解析

**实现**：
```python
# src/server/config.py
from pathlib import Path

# 获取项目根目录
_SERVER_DIR = Path(__file__).parent
_SRC_DIR = _SERVER_DIR.parent
PROJECT_ROOT = _SRC_DIR.parent

# 路径常量
LOG_DIR = PROJECT_ROOT / "log"
CONFIG_DIR = _SRC_DIR / "config"
```

**理由**：Python 的 `pathlib` 已经很好地处理了路径解析，无需额外机制。

### Decision 5: 文件重命名策略

| 原文件 | 新文件 | 说明 |
|--------|--------|------|
| `hooks/hook-router.sh` | `src/hook-router.sh` | 统一 Hook 入口（置顶） |
| `hooks/permission-notify.sh` | `src/hooks/permission.sh` | 权限请求处理 |
| `hooks/webhook-notify.sh` | `src/hooks/webhook.sh` | 通用通知处理 |
| `server/start.sh` | `src/start-server.sh` | 服务启动入口（置顶） |
| `server/*` | `src/server/*` | Python 服务目录 |
| `shell-lib/*` | `src/lib/*` | Shell 库目录 |
| `shared/*` | `src/shared/*` | 跨语言共享 |
| `config/*` | `src/config/*` | 配置文件 |
| `templates/*` | `src/templates/*` | 模板文件 |
| `local-proxy/*` | `src/proxy/*` | VSCode 代理 |

## Risks / Trade-offs

### Risk 1: 现有用户迁移
- **风险**：现有用户 hook 配置路径失效
- **缓解**：`install.sh` 会自动更新配置，用户只需重新运行安装脚本

### Risk 2: 路径引用遗漏
- **风险**：某些隐藏的路径引用未更新
- **缓解**：使用 grep 全面搜索路径引用，建立检查清单

### Trade-off: 目录深度增加
- **代价**：源代码多了一层 `src/` 目录
- **收益**：根目录更清晰，符合常见开源项目结构

## Migration Plan

### 阶段 1：创建新结构
1. 创建 `src/` 及其子目录
2. 合并 Shell 库为 `core.sh`
3. 复制文件到新位置（保留原文件）

### 阶段 2：更新路径引用
1. 更新所有 Shell 脚本的 source 路径
2. 更新 Python 的路径常量
3. 更新 `install.sh`
4. 更新文档

### 阶段 3：测试验证
1. 运行所有测试脚本
2. 手动测试完整流程
3. 验证日志输出正常

### 阶段 4：清理
1. 删除原目录
2. 更新 `.gitignore`
3. 提交变更

### 回滚方案
如遇问题：
1. Git revert 提交
2. 运行 `install.sh` 恢复配置

## Open Questions

1. **是否保留 `shell-lib/` 目录别名？**
   - 方案 A：完全删除，只用 `src/lib/`
   - 方案 B：保留软链接 `shell-lib -> src/lib` 过渡一段时间
   - **建议**：方案 A，直接切换，避免混淆

2. **`test/` 目录是否移入 `src/`？**
   - 方案 A：保持在根目录（`test/`）
   - 方案 B：移入 `src/test/`
   - **建议**：方案 A，测试代码通常不属于源代码，保持在根目录便于运行
