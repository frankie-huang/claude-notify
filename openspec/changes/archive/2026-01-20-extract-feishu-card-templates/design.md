# Design: 飞书卡片模板化方案

## Context

当前系统通过 `shell-lib/feishu.sh` 构建飞书卡片,卡片结构硬编码在函数中:

```bash
build_permission_card() {
    local card="{
      \"msg_type\": \"interactive\",
      \"card\": {
        \"header\": { ... },
        \"elements\": [
          ...
        ]
      }
    }"
}
```

这种方式存在以下问题:
- JSON 结构与业务逻辑混合
- 修改卡片样式需要理解复杂的字符串转义
- 多次修改后代码可读性下降
- 无法独立管理卡片版本

## Goals / Non-Goals

### Goals
- 将卡片 JSON 结构抽离为独立的模板文件
- 提供变量替换机制,支持动态内容注入
- 保持现有 Shell 函数接口不变(向后兼容)
- 支持模板继承和组合
- 提供模板验证机制

### Non-Goals
- 不引入复杂的模板引擎(如 Jinja2)
- 不改变现有的卡片结构和字段
- 不影响现有的权限请求流程

## Decisions

### Decision 1: 使用 JSON 模板文件

**选择**: 使用 `.json` 文件存储卡片模板,使用占位符标记动态内容

**理由**:
- 原生 JSON 格式,易于编辑和验证
- 无需额外依赖,Shell 可直接处理
- 与飞书官方文档结构一致

**占位符格式**:
- 使用 `{{variable_name}}` 标记变量
- 支持嵌套字段: `{{tool.name}}`

**示例**:
```json
{
  "msg_type": "interactive",
  "card": {
    "header": {
      "template": "{{template_color}}",
      "title": {"content": "{{title}}", "tag": "plain_text"}
    }
  }
}
```

### Decision 2: 模板变量替换机制

**实现方案**:
- Shell 函数 `render_template()` 负责变量替换
- 使用 `sed` 进行批量替换(性能足够)
- 支持从关联数组或键值对列表注入变量

**伪代码**:
```bash
render_template() {
    local template_file="$1"
    local template_content=$(cat "$template_file")

    # 遍历变量并替换
    for var in "${@:2}"; do
        local key="${var%%=*}"
        local value="${var#*=}"
        template_content=$(echo "$template_content" | sed "s|{{$key}}|$value|g")
    done

    echo "$template_content"
}
```

**调用方式**:
```bash
render_template "permission-card.json" \
    "title=Claude Code 权限请求" \
    "tool_name=Bash" \
    "template_color=orange"
```

### Decision 3: 模板文件组织结构

```
templates/feishu/
├── permission-card.json        # 权限请求卡片(交互模式)
├── permission-card-static.json # 权限请求卡片(静态模式)
├── notification-card.json      # 通用通知卡片
├── buttons.json                # 交互按钮配置
└── README.md                   # 模板使用说明
```

**设计考虑**:
- 交互模式和静态模式分离(避免模板过于复杂)
- 按钮配置独立,方便统一修改
- README 提供变量清单和示例

### Decision 4: 模板验证

**验证机制**:
- 加载模板时检查 JSON 语法(使用 `jq` 或 Python)
- 必要字段检查(如 `msg_type`, `card.header`)
- 提供调试模式输出渲染后的 JSON

**实现**:
```bash
validate_template() {
    local template_file="$1"
    if command -v jq &> /dev/null; then
        jq empty "$template_file" 2>&1
    elif command -v python3 &> /dev/null; then
        python3 -m json.tool "$template_file" > /dev/null 2>&1
    else
        return 0  # 无工具时跳过验证
    fi
}
```

### Decision 5: 向后兼容性

**兼容策略**:
- 保留原有的 `build_permission_card()` 函数签名
- 内部实现改为调用模板渲染
- 提供环境变量 `FEISHU_TEMPLATE_PATH` 支持自定义模板路径
- 如果模板文件不存在,降级到原有的硬编码逻辑

**错误处理**:
```bash
build_permission_card() {
    local template_file="${FEISHU_TEMPLATE_PATH:-templates/feishu/permission-card.json}"

    # 模板文件必须存在
    if [ ! -f "$template_file" ]; then
        log_error "Template not found: $template_file"
        return 1
    fi

    # 使用模板渲染
    render_template "$template_file" ...
}
```

## Risks / Trade-offs

### Risk 1: 模板文件路径问题

**风险**: Shell 脚本的当前工作目录不确定,相对路径可能失效

**缓解措施**:
- 使用绝对路径(基于 `SCRIPT_DIR`)
- 提供环境变量配置覆盖
- 启动时验证模板文件可访问性

### Risk 2: 性能影响

**风险**: 模板渲染比直接字符串拼接慢

**评估**:
- 权限请求频率低(每次操作最多一次)
- `sed` 替换性能足够(毫秒级)
- 可接受的范围

**优化**:
- 可选的模板缓存(内存中)
- 预编译模板(高级优化,非必需)

### Risk 3: 变量注入安全问题

**风险**: 模板变量可能包含特殊字符导致 JSON 格式错误

**缓解措施**:
- 变量注入前进行 JSON 转义
- 渲染后验证 JSON 格式
- 提供详细的错误日志

**转义函数**:
```bash
json_escape() {
    local text="$1"
    text=$(echo "$text" | sed 's/\\/\\\\/g; s/"/\\"/g')
    echo "$text"
}
```

## Migration Plan

### 阶段 1: 模板创建(不破坏现有功能)
1. 创建 `templates/feishu/` 目录
2. 从 `feishu.sh` 提取现有卡片结构,创建 JSON 模板
3. 添加模板验证工具
4. 编写模板使用文档

### 阶段 2: 渐进式迁移
1. 在 `feishu.sh` 中添加 `render_template()` 函数
2. 修改 `build_permission_card()` 使用模板渲染
3. 添加模板验证逻辑,确保模板文件必须存在
4. 添加日志输出,记录渲染状态

### 阶段 3: 测试和验证
1. 单元测试:模板渲染函数
2. 集成测试:权限请求流程
3. 验证向后兼容性
4. 性能基准测试

### 阶段 4: 代码清理
1. 移除硬编码的卡片构建逻辑
2. 统一使用模板渲染
3. 代码格式化和注释优化
4. 更新文档

**回滚计划**:
- Git 历史保留完整代码,可随时回退
- 模板文件损坏时,利用现有的 `send_feishu_text()` 发送降级通知

## Open Questions

1. **是否支持条件渲染**?
   - 当前设计:不支持(通过分离静态/交互模板解决)
   - 未来扩展:可引入简单的条件语法(如 `{{#if buttons}}...{{/if}}`)

2. **是否支持数组展开**?
   - 当前设计:按钮数组作为整体变量注入
   - 未来扩展:支持列表渲染(如 `{{#each items}}...{{/each}}`)

3. **模板版本管理策略**?
   - 选项 A:文件名包含版本号(如 `permission-card-v2.json`)
   - 选项 B:Git 分支管理
   - 建议:先使用 Git 分支,按需引入版本号

4. **是否支持多语言卡片**?
   - 当前设计:模板内容固定中文
   - 未来扩展:i18n 支持(如 `templates/feishu/en/`)

## Implementation Notes

### 模板变量清单

**permission-card.json** 变量:
- `{{title}}` - 卡片标题
- `{{template_color}}` - 模板颜色
- `{{tool_name}}` - 工具名称
- `{{project_name}}` - 项目名称
- `{{timestamp}}` - 时间戳
- `{{detail_content}}` - 详情内容(Markdown)
- `{{buttons_json}}` - 按钮数组(JSON 字符串)
- `{{note_content}}` - 提示文本

**buttons.json** 变量:
- `{{callback_url}}` - 回调服务器 URL
- `{{request_id}}` - 请求 ID

### 错误处理策略

1. 模板文件不存在 → 降级到原有逻辑 + 警告日志
2. JSON 格式错误 → 详细错误日志 + 降级
3. 变量替换失败 → 记录失败变量 + 使用占位符
4. 渲染后 JSON 无效 → 错误日志 + 降级

### 测试策略

**单元测试**:
```bash
test_render_template() {
    local result=$(render_template "test.json" "name=value")
    assert_contains "$result" '"name": "value"'
}
```

**集成测试**:
```bash
test_build_permission_card() {
    local card=$(build_permission_card "Bash" "testproj" "2024-01-01" "**cmd**" "orange" "")
    assert_valid_json "$card"
}
```
