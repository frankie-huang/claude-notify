# Change: 适配 AskUserQuestion 卡片审批场景

## Why

当前 AskUserQuestion 权限请求直接回退到终端交互（`exit $EXIT_FALLBACK`），在 `claude -p` 非交互模式下无法使用。需要支持通过飞书卡片表单让用户选择/输入答案，实现远程回答 AskUserQuestion。

## What Changes

- permission.sh 移除 AskUserQuestion 的 fallback 逻辑，改为构建带表单的飞书卡片并等待回调
- 新增 AskUserQuestion 专用卡片模板（form 表单：下拉选择 + 自定义输入）
- feishu.sh 新增 `build_ask_question_card()` 卡片构建函数（内嵌 Python 动态构建表单元素）
- permission.sh 新增 `output_decision_with_updated_input()` 函数输出带 updatedInput 的决策
- questions 数据通过 base64 编码在 socket 请求中传递，server 端解码还原
- 回调服务器新增 `_handle_ask_question_answer()` 表单提交处理，拒绝/中断走通用权限决策路径
- Decision 模型新增 `allow_with_updated_input()` 工厂方法
- Socket 通信扩展，支持解析响应中的 `updated_input` 数据

## Impact

- Affected specs: `permission-notify`, `card-callback`
- Affected code:
  - `src/hooks/permission.sh` — 移除 fallback，新增表单卡片流程 + `output_decision_with_updated_input()`
  - `src/lib/feishu.sh` — 新增 `build_ask_question_card()` 卡片构建函数
  - `src/templates/feishu/` — 新增 `ask-question-card.json` 卡片模板
  - `src/server/handlers/feishu.py` — 新增 `_handle_ask_question_answer()` 表单回调处理
  - `src/server/handlers/callback.py` — 扩展 `/cb/decision` 支持 `action=answer`
  - `src/server/models/decision.py` — 新增 `allow_with_updated_input()` 工厂方法
  - `src/server/services/decision_handler.py` — 扩展 `handle_decision` 支持 answers/questions 参数
  - `src/lib/socket.sh` — 解析响应中的 `updated_input`
