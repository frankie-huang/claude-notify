## 1. 配置层

- [x] 1.1 更新 `.env.example` 中 `CLAUDE_COMMAND` 的注释和示例，说明支持列表格式（无引号和 JSON 两种）
- [x] 1.2 同步更新 `install.sh` 中的 `generate_env_template()` 配置模板
- [x] 1.3 在 `src/server/config.py` 中新增 `get_claude_commands()` 函数，解析 CLAUDE_COMMAND 为列表（支持无引号列表和 JSON 数组两种格式）
- [x] 1.4 在 `src/server/config.py` 中新增 `resolve_claude_command(cmd_arg)` 函数，根据索引或名称匹配返回具体命令

## 2. Claude 执行层

- [x] 2.1 修改 `src/server/handlers/claude.py` 中 `_get_claude_command()` 改为接受可选参数 `claude_command`，支持传入指定命令
- [x] 2.2 修改 `handle_new_session()` 接受 `claude_command` 参数，传递给 `_execute_and_check()`
- [x] 2.3 修改 `handle_continue_session()` 接受 `claude_command` 参数，传递给 `_execute_and_check()`
- [x] 2.4 修改 `_execute_and_check()` 接受 `claude_command` 参数，优先使用传入的命令

## 3. 存储层（Callback 后端）

- [x] 3.1 修改 `ChatIdStore.save()` 支持保存 `claude_command` 字段（可选参数，向后兼容）
- [x] 3.2 新增 `ChatIdStore.get_command()` 方法，查询 session 最近使用的 claude_command
- [x] 3.3 修改 `claude.py` 中调用 `ChatIdStore.save()` 的位置，传递 `claude_command`

## 4. /new 指令增强

- [x] 4.1 新增 `_parse_command_args()` 通用解析函数支持 `--dir=` 和 `--cmd=` 参数（`_parse_new_command()` 保留为向后兼容包装）
- [x] 4.2 修改 `_handle_new_command()` 传递 `claude_command` 到转发请求
- [x] 4.3 修改 `_forward_new_request()` 传递 `claude_command` 参数到 Callback 后端
- [x] 4.4 Callback 端 `/claude/new` 自动传递 data 字典（含 claude_command），`handle_new_session()` 已支持
- [x] 4.5 修改 `_send_new_session_card()` 在多 Command 配置时新增 Command 选择下拉框
- [x] 4.6 修改 `_handle_new_session_form()` 提取 `claude_command` 表单值并传递给 `_async_create_session()`

## 5. /reply 指令

- [x] 5.1 复用 `_parse_command_args()` 解析 `/reply` 指令参数（支持 `--cmd=`）
- [x] 5.2 新增 `_handle_reply_command()` 函数处理 `/reply` 指令
- [x] 5.3 在 `_COMMANDS` 中注册 `/reply` 命令
- [x] 5.4 Command 选择优先级在 Callback 后端 `handle_continue_session()` 中实现：请求指定 > ChatIdStore 记录 > 默认

## 6. 回复消息增强

- [x] 6.1 修改 `_forward_continue_request()` 传递 `claude_command` 参数（如有）
- [x] 6.2 Callback 端 `handle_continue_session()` 已支持接收可选 `claude_command`，未指定时从 ChatIdStore 查询
- [x] 6.3 `handle_continue_session()` 在 processing 状态时保存实际使用的 `claude_command` 到 ChatIdStore

## 7. 文档与验证

- [x] 7.1 更新 README 中相关配置说明
- [ ] 7.2 手动验证：单命令配置向后兼容
- [ ] 7.3 手动验证：多命令配置 + `--cmd` 索引选择
- [ ] 7.4 手动验证：多命令配置 + `--cmd` 名称匹配
- [ ] 7.5 手动验证：新建会话卡片 Command 选择器
- [ ] 7.6 手动验证：session Command 记忆与自动复用
- [ ] 7.7 手动验证：`/reply` 指令基本功能
