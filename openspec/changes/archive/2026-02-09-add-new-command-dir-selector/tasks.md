## 1. 基础设施准备

- [x] 1.1 在 SessionStore 中新增目录历史记录功能
  - 新增 `record_dir_usage(sender_id, project_dir)` 方法记录目录使用
  - 新增 `get_common_dirs(sender_id, limit=5)` 方法获取常用目录
  - 目录历史存储在独立文件中（如 `dir_history.json`）

## 2. 卡片发送逻辑

- [x] 2.1 修改 `_handle_new_command` 函数
  - 当缺少 project_dir 时，调用卡片发送函数而非返回错误文本
  - 传递 sender_id、chat_id、message_id、prompt 等参数

- [x] 2.2 实现 `_send_dir_selector_card` 函数
  - 查询用户常用目录列表
  - 构建飞书交互式卡片（包含下拉菜单和提交按钮）
  - 卡片 value 中包含 action="select_dir"、prompt、chat_id 等信息

## 3. 卡片回调处理（异步模式）

- [x] 3.1 在 `_handle_card_action` 中新增 `select_dir` 动作处理
  - 解析用户选择的目录（从 input_select 组件获取）
  - **立即返回** toast + "处理中"卡片响应（<500ms）
  - 启动后台线程执行实际的会话创建

- [x] 3.2 实现 `_handle_dir_selected_async` 函数
  - 立即构建并返回"处理中"响应
  - 在后台线程中：验证目录、调用 `/claude/new`、发送结果通知

- [x] 3.3 实现后台会话创建函数
  - 验证 auth_token
  - 转发到 `/claude/new` 接口
  - 根据结果发送新的飞书消息通知
  - 成功：发送"会话已创建"消息（包含 session_id）
  - 失败：发送错误消息

## 4. 卡片响应格式

- [x] 4.1 实现"处理中"卡片响应
  - 显示"⏳ 正在创建会话"标题
  - 显示"请稍候，正在启动 Claude..."提示
  - 移除所有交互组件

- [x] 4.2 实现完成通知消息格式
  - 复用现有的 `_send_new_result_notification` 逻辑
  - 或发送独立的文本消息通知

## 5. 测试验证

- [x] 5.1 测试常用目录收集功能
  - 多次使用不同目录创建会话
  - 验证历史记录正确保存
  - 验证高频目录正确排序

- [ ] 5.2 测试目录选择卡片流程
  - 发送无参数 `/new` 指令
  - 验证卡片正确发送
  - 选择目录并提交
  - 验证会话成功创建
  - 验证卡片正确更新

- [ ] 5.3 测试边界场景
  - 目录不存在时的处理
  - 手动输入非历史目录
  - 重复提交的处理
