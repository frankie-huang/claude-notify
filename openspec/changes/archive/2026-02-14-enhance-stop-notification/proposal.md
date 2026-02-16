# 提案：优化 Stop 事件通知内容

## 提案 ID
`enhance-stop-notification`

## 创建时间
2026-02-12

## 状态
Draft

## 概述

优化 Stop 事件完成通知的内容完整性和信息丰富度，包含两项改进：
1. **响应内容完整化**：提取最近一条用户消息之后的所有 assistant 文本（而非仅最后一条 assistant 消息）
2. **思考过程展示**：在通知中包含 Claude 的 thinking 内容，使用折叠面板展示

## 动机

### 当前问题
1. Stop 通知只取 JSONL transcript 中最后一条 `type=="assistant"` 消息的 text 内容。当用户提出多个子问题时，Claude 会产生多轮回复（中间穿插 tool_use 和 tool_result），导致通知中丢失前面的关键回复内容。
2. 通知中不包含 Claude 的思考过程（thinking），用户无法了解 Claude 的推理链路。

### 期望效果
1. 通知展示从最近一条用户文本消息开始的所有 assistant text 内容，完整呈现本轮对话的回复
2. 通知中包含思考过程，使用飞书折叠面板（collapsible_panel）展示，默认折叠不影响阅读

## 涉及能力

1. **permission-notify**（修改）：Stop 事件通知的内容提取逻辑和卡片格式

## 架构影响

### JSONL 解析逻辑变更

当前：`find_last_assistant_in_file()` → 找最后一条 assistant 消息 → 提取 text

变更后：`extract_response_from_file()` → 找最近一条用户文本消息 → 收集其后所有 assistant 消息 → 分别提取 text 和 thinking

### 卡片模板变更

Stop 卡片新增思考过程折叠面板区域（条件展示，无 thinking 时不显示）

## 实现范围

### 文件变更
- `src/hooks/stop.sh` - 核心逻辑：替换单消息提取为多消息提取 + thinking 支持
- `src/lib/feishu.sh` - 卡片构建：更新 `build_stop_card` 支持 thinking 参数
- `src/templates/feishu/stop-card.json` - 卡片模板：添加 thinking_element 占位符
- `src/templates/feishu/thinking-element.json` - 新增：thinking 折叠面板子模板
- `.env.example` / `install.sh` - 新增 `STOP_THINKING_MAX_LENGTH` 配置项

## 配置变更

新增配置项：
```bash
# Stop 事件思考过程最大长度，字符数 (可选，默认 5000)
# 设为 0 则不显示思考过程
STOP_THINKING_MAX_LENGTH=5000
```

## 依赖关系

- 依赖 `permission-notify` 规范中的 Stop 事件处理
- 依赖 `feishu-card-format` 规范中的卡片格式（新增使用 collapsible_panel 组件）

## 风险与限制

| 风险 | 缓解措施 |
|------|----------|
| collapsible_panel 兼容性 | 已验证 Card 2.0 支持；如不兼容可降级为灰色背景区块 |
| 多轮回复内容过长 | 保持现有 STOP_MESSAGE_MAX_LENGTH 截断 |
| thinking 内容过长 | 独立的 STOP_THINKING_MAX_LENGTH 截断 |
| JSONL 文件较大时性能 | jq -s slurp 模式对常规大小文件性能足够；已在后台异步执行 |

## 向后兼容性

- 不影响现有功能
- 无 thinking 时卡片与当前完全一致
- 新配置项均有默认值，无需手动配置
