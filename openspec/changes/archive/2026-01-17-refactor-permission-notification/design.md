## Context

当前 claude-notify 项目的权限请求通知功能实现在以下文件中：
- `permission-notify.sh` (684 行) - Shell 脚本，包含大量重复代码
- `callback-server/server.py` (727 行) - Python 服务，职责过多
- `callback-server/socket-client.py` (199 行) - Socket 客户端
- `callback-server/config.py` (40 行) - 超时配置

### 现有代码问题分析

#### permission-notify.sh 重复代码分析

1. **JSON 解析重复** - 相同的 jq/python3/grep-sed 三重判断出现在：
   - 第 78-113 行：解析顶级字段 (tool_name, tool_input, cwd)
   - 第 179-238 行：send_interactive_card 内提取 command/file_path/description
   - 第 489-538 行：run_fallback_mode 内提取 command/file_path

2. **飞书卡片构建重复** - 两处几乎相同的卡片构建：
   - 第 248-311 行：send_interactive_card（带按钮）
   - 第 542-576 行：run_fallback_mode（不带按钮）

3. **工具详情提取重复** - case 语句在两处出现：
   - 第 176-227 行
   - 第 487-538 行

#### server.py 职责过多

1. `RequestManager` 类承担了请求管理、连接检测、超时处理
2. `CallbackHandler` 类承担了路由、决策处理、HTML 渲染
3. `write_always_allow_rule` 函数与请求处理耦合

## Goals / Non-Goals

### Goals
- 消除重复代码，提高代码复用率
- 模块化设计，明确职责边界
- 提高可维护性和可测试性
- 保持现有功能完全不变

### Non-Goals
- 不改变对外接口（Hook 规范、HTTP API）
- 不引入新的外部依赖
- 不改变部署方式

## Decisions

### 1. Shell 脚本模块化方案

**Decision**: 创建 `lib/` 目录存放共享函数库，使用 `source` 引入

**结构**:
```
lib/
├── json.sh           # JSON 解析函数
├── feishu.sh         # 飞书卡片构建函数
├── tool.sh           # 工具详情格式化
├── socket.sh         # Socket 通信封装
└── log.sh            # 日志函数
```

**Alternatives considered**:
- 将所有逻辑保留在单一脚本中 - 拒绝，因为重复代码问题严重
- 使用 Python 重写整个脚本 - 拒绝，因为 Shell 脚本启动更快，适合 Hook 场景

### 2. JSON 解析统一方案

**Decision**: 封装统一的 JSON 解析函数，内部处理 jq/python3/grep-sed 三种方式

```bash
# lib/json.sh

# 初始化 JSON 解析器（检测可用工具）
json_init() { ... }

# 解析 JSON 字段
# 用法: json_get "$json" "field.nested.path"
json_get() { ... }

# 解析 JSON 对象
# 用法: json_get_object "$json" "tool_input"
json_get_object() { ... }
```

**Rationale**: 统一接口，调用处无需关心具体解析工具

### 3. 飞书卡片模板化方案

**Decision**: 将卡片结构抽象为可配置的模板函数

```bash
# lib/feishu.sh

# 构建权限请求卡片
# 参数: tool_name, project_name, timestamp, detail_content, template_color, [buttons_json]
build_permission_card() { ... }

# 发送飞书卡片
# 参数: webhook_url, card_json
send_feishu_card() { ... }
```

**Rationale**: 交互式和降级模式共用同一模板，仅按钮部分不同

### 4. 工具详情提取方案

**Decision**: 使用关联数组统一管理工具类型配置

```bash
# lib/tool.sh

# 工具类型 -> 卡片颜色映射
declare -A TOOL_COLORS=(
    ["Bash"]="orange"
    ["Edit"]="yellow"
    ["Write"]="yellow"
    ["Read"]="blue"
)

# 工具类型 -> 提取字段映射
declare -A TOOL_FIELDS=(
    ["Bash"]="command"
    ["Edit"]="file_path"
    ["Write"]="file_path"
    ["Read"]="file_path"
)

# 提取工具详情
# 参数: tool_name, tool_input_json
# 输出: detail_content (设置全局变量)
extract_tool_detail() { ... }
```

**Rationale**: 新增工具类型只需修改配置数组，无需改动逻辑

### 5. Python 服务模块化方案

**Decision**: 将 server.py 拆分为多个模块

```
callback-server/
├── server.py              # 主入口，启动服务
├── config.py              # 配置（保持不变）
├── handlers/
│   ├── __init__.py
│   └── callback.py        # HTTP 请求处理器
├── services/
│   ├── __init__.py
│   ├── request_manager.py # 请求管理
│   └── rule_writer.py     # 规则写入
├── models/
│   ├── __init__.py
│   └── decision.py        # Decision 类
└── templates/
    └── response.html      # HTML 响应模板
```

**Rationale**: 职责单一，便于测试和维护

## Risks / Trade-offs

### Risk 1: Shell 脚本 source 性能
- **影响**: 多次 source 可能增加启动时间
- **缓解**: 仅 source 必要的库，保持库函数精简

### Risk 2: 模块化增加复杂度
- **影响**: 文件数量增加，需要理解模块间关系
- **缓解**: 保持清晰的模块边界和命名约定

### Risk 3: 兼容性风险
- **影响**: 重构可能引入潜在 bug
- **缓解**: 保留现有测试用例，增加单元测试

## Migration Plan

1. **阶段 1**: 创建 Shell 函数库，permission-notify.sh 逐步迁移
2. **阶段 2**: 重构 Python 服务模块化
3. **阶段 3**: 集成测试，验证功能完整性
4. **阶段 4**: 清理旧代码，更新文档

## Open Questions

1. 是否需要为 webhook-notify.sh 也进行类似重构？（建议：是，可复用 lib/feishu.sh）
2. 是否需要添加单元测试？（建议：是，至少覆盖核心函数）
