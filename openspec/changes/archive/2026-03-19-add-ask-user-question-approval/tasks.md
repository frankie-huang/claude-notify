## 1. Hook 脚本层

- [x] 1.1 permission.sh: 移除 AskUserQuestion 的 fallback 逻辑（L379-386）
- [x] 1.2 permission.sh: 新增 AskUserQuestion 分支，构建表单卡片 + socket 等待回调
- [x] 1.3 permission.sh: 扩展 `output_decision` 函数，新增 `output_decision_with_updated_input` 支持 `updatedInput` 参数输出
- [x] 1.4 socket.sh: 扩展 `parse_socket_response` 解析响应中的 `updated_input` 数据

## 2. 飞书卡片层

- [x] 2.1 feishu.sh: 新增 `build_ask_question_card()` 函数，根据 questions 数组动态构建 form 表单
- [x] 2.2 feishu.sh: 每个 question 渲染为 header(markdown) + select_static/multi_select_static + input 组合
- [x] 2.3 feishu.sh: 每个问题额外渲染独立 input 文本框，单选时自定义输入优先覆盖选项，多选时追加
- [x] 2.4 feishu.sh: 表单底部添加"提交回答"、"拒绝回答"和"拒绝并中断"三个按钮
- [x] 2.5 新增卡片模板文件 `src/templates/feishu/ask-question-card.json`（外层框架模板）

## 3. 回调服务器层

- [x] 3.1 feishu.py: 新增 `_handle_ask_question_answer()` 表单回调处理函数
- [x] 3.2 feishu.py: 从 form_value 中提取各问题的选择/输入，构造 `answers` dict（自定义输入优先/追加）
- [x] 3.3 callback.py: 扩展 `handle_callback_decision` 接口，支持 `action=answer` + `answers` + `questions` 参数
- [x] 3.4 decision.py: Decision 模型扩展，新增 `allow_with_updated_input()` 工厂方法
- [x] 3.5 decision_handler.py: 扩展 `handle_decision` 支持 `answers` 和 `questions` 参数，socket 响应中携带 `updated_input` 数据

## 4. 集成与测试

- [ ] 4.1 端到端测试：交互模式下 AskUserQuestion 触发飞书表单卡片
- [ ] 4.2 端到端测试：用户选择预设选项 → 提交 → Claude Code 收到正确答案
- [ ] 4.3 端到端测试：用户选择自定义输入 → 填写文本 → 提交 → Claude Code 收到正确答案
- [ ] 4.4 端到端测试：用户点击"拒绝回答" → Claude Code 收到 deny 决策
- [ ] 4.5 端到端测试：MCP 模式下的 AskUserQuestion 表单审批
- [ ] 4.6 回归测试：普通权限审批流程不受影响
