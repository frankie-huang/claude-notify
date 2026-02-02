## Context

当前系统在多处硬编码使用 `claude` 命令。用户希望能够：
1. 使用其他 Claude 变体命令（如 `claude-glm`）
2. 传递额外参数（如 `--setting opus`、`--model sonnet`）

此配置将用于：
- 继续会话功能（已实现）
- 新建会话功能（计划中）

## Goals / Non-Goals

**Goals:**
- 支持通过环境变量配置 Claude 命令
- 支持带参数的命令（如 `claude --setting opus`）
- 保持向后兼容（默认使用 `claude`）
- 配置统一服务于继续会话和新建会话场景

**Non-Goals:**
- 不支持运行时动态参数（所有参数通过环境变量预设）
- 不支持命令白名单/安全校验（用户自己负责配置安全）
- 不支持不同会话使用不同命令

## Decisions

### 1. 环境变量命名

- **变量名**: `CLAUDE_COMMAND`
- **默认值**: `claude`
- **格式**: 命令字符串，可包含空格和参数

### 2. 配置示例

```bash
# 默认（使用 claude）
CLAUDE_COMMAND=claude

# 使用 glm 模型
CLAUDE_COMMAND=claude-glm

# 带参数的命令
CLAUDE_COMMAND="claude --setting opus"

# 复杂场景（自定义脚本）
CLAUDE_COMMAND="/path/to/custom-claude.sh"
```

### 3. 命令构建实现

通过登录 shell 执行命令，自动加载 shell 配置文件，支持别名：

```python
import os
import shlex
import subprocess

shell = os.environ.get('SHELL', '/bin/bash')
claude_cmd = get_config('CLAUDE_COMMAND', 'claude')
safe_prompt = shlex.quote(prompt)
safe_session = shlex.quote(session_id)
cmd_str = f'{claude_cmd} -p {safe_prompt} --resume {safe_session}'

# 通过登录 shell 执行，加载 ~/.bashrc 等配置文件
proc = subprocess.Popen([shell, '-lc', cmd_str], cwd=project_dir, ...)
```

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 命令注入 | 使用列表形式传参，不用 shell=True |
| 配置错误导致无法执行 | 启动时验证命令存在性，记录警告 |
| 不同用户的命令不一致 | 每个环境独立配置，符合预期 |

## Migration Plan

1. 添加环境变量，默认值为 `claude`
2. 修改代码读取环境变量
3. 更新 `.env.example` 和 `install.sh`
4. 用户无需迁移（默认行为不变）

## Open Questions

无
