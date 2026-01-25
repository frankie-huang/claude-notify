<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

## 开发注意事项

### 配置文件同步

修改 `.env.example` 时，需要同步更新 `install.sh` 中的 `generate_env_template()` 函数，确保两处配置保持一致。

涉及文件：
- `.env.example` - 环境变量配置模板
- `install.sh` - 安装脚本中的 heredoc（第 271-352 行附近）

### 环境变量读取方式

**Bash 脚本中读取配置：**

使用 `shell-lib/env.sh` 提供的 `get_config` 函数：

```bash
# 引入 env.sh（如果尚未引入）
if ! type get_config &> /dev/null; then
    source "${BASH_SOURCE[0]%/*}/env.sh"
fi

# 读取配置，第二个参数为默认值
WEBHOOK_URL=$(get_config "FEISHU_WEBHOOK_URL" "")
PORT=$(get_config "CALLBACK_SERVER_PORT" "8080")
```

优先级：`.env` 文件 > 环境变量 > 默认值

**禁止直接使用 `${VAR:-default}` 方式读取**，因为这种方式无法从 `.env` 文件读取。

**Python 中读取配置：**

使用 `server/config.py` 提供的 `get_config` 和 `get_config_int` 函数：

```python
from config import get_config, get_config_int

WEBHOOK_URL = get_config('FEISHU_WEBHOOK_URL', '')
PORT = get_config_int('CALLBACK_SERVER_PORT', 8080)
```