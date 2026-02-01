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

### Python 版本要求

本项目 Python 代码需兼容 **Python 3.6+**，编写代码时注意：

| 特性 | Python 3.6+ 兼容写法 | 不要使用 |
|------|---------------------|----------|
| 类型注解 | `from typing import Dict, List, Tuple`<br>`Dict[str, Any]`<br>`Tuple[bool, dict]` | 小写内置泛型 `dict[str, Any]` (3.9+) |
| 空泛型 | `Optional[Dict[str, Any]]` | `Optional[Dict]` (需要完整参数) |
| 联合类型 | `Optional[int]`<br>`Union[int, None]`<br>`Union[str, int]` | `int \| None` (3.10+) |
| subprocess | `stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True` | `capture_output=True, text=True` (3.7+) |
| 运算符 | 普通赋值 `x = foo()` | `:=` walrus (3.8+) |

**常见错误示例：**

```python
# ❌ 错误 - Python 3.6 不支持
def foo() -> Optional[Dict]:  # 空泛型
    pass
result = subprocess.run(cmd, capture_output=True, text=True)
if (n := len(data)) > 0:  # walrus
    pass
x: int | None = None  # 联合类型语法

# ✅ 正确 - Python 3.6 兼容
from typing import Optional, Dict, Any, Union
def foo() -> Optional[Dict[str, Any]]:
    pass
result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
n = len(data)
if n > 0:
    pass
x: Optional[int] = None  # 或 Union[int, None]
```

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