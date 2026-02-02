# Change: 支持自定义 Claude 命令

## Why

当前系统硬编码使用 `claude` 命令，无法支持：
- 使用其他 Claude 变体命令（如 `claude-glm`）
- 添加额外参数（如 `--setting`、`--model` 等）
- 使用 shell 配置文件中定义的别名

用户希望可以配置 Claude 命令，用于：
1. 继续会话功能（已实现）
2. 新建会话功能（计划中）

## What Changes

- **新增环境变量** `CLAUDE_COMMAND`，配置 Claude 命令
- **修改** `claude.py` 的 `_execute_and_check` 函数：
  - 通过登录 shell（`bash -lc`）执行命令
  - 自动加载 shell 配置文件，支持别名
  - 使用 `shlex.quote()` 安全处理特殊字符
- **更新** `.env.example` 添加配置说明
- **更新** `install.sh` 的 `generate_env_template` 函数

默认值保持向后兼容：`CLAUDE_COMMAND="claude"`

## Impact

- Affected specs: `session-continue`
- Affected code:
  - `src/server/handlers/claude.py`
  - `.env.example`
  - `install.sh`
