## 1. Shell 函数库创建

- [x] 1.1 创建 `lib/` 目录结构
- [x] 1.2 实现 `lib/log.sh` 日志函数库
  - `log_init()` 初始化日志文件
  - `log()` 通用日志函数
  - `log_input()` 记录输入数据
- [x] 1.3 实现 `lib/json.sh` JSON 解析函数库
  - `json_init()` 检测可用解析工具
  - `json_get()` 获取 JSON 字段值
  - `json_get_object()` 获取 JSON 对象
  - 支持 jq/python3/grep-sed 三种方式
- [x] 1.4 实现 `lib/tool.sh` 工具详情函数库
  - 定义 `TOOL_COLORS` 颜色映射数组
  - 定义 `TOOL_FIELDS` 字段映射数组
  - `extract_tool_detail()` 提取工具详情
  - `get_tool_color()` 获取卡片颜色
- [x] 1.5 实现 `lib/feishu.sh` 飞书卡片函数库
  - `build_card_header()` 构建卡片头部
  - `build_card_content()` 构建卡片内容
  - `build_card_buttons()` 构建交互按钮
  - `build_permission_card()` 组装完整卡片
  - `send_feishu_card()` 发送卡片
- [x] 1.6 实现 `lib/socket.sh` Socket 通信函数库
  - `check_socket_tools()` 检测通信工具
  - `socket_send_request()` 发送请求到回调服务
  - `parse_socket_response()` 解析服务响应

## 2. permission-notify.sh 重构

- [x] 2.1 引入函数库
  - 添加 source 语句引入所有 lib/*.sh
  - 移除原有的重复函数定义
- [x] 2.2 重构 JSON 解析逻辑
  - 使用 `json_init()` 初始化
  - 使用 `json_get()` 替换所有 jq/python3/grep 调用
- [x] 2.3 重构飞书卡片发送
  - 使用 `extract_tool_detail()` 获取工具详情
  - 使用 `build_permission_card()` 构建卡片
  - 使用 `send_feishu_card()` 发送卡片
  - 合并 `send_interactive_card()` 和 `run_fallback_mode()` 中的卡片构建逻辑
- [x] 2.4 重构 Socket 通信
  - 使用 `socket_send_request()` 替换原有通信逻辑
  - 使用 `parse_socket_response()` 解析响应
- [x] 2.5 简化主流程
  - 使用函数库后主流程应更加清晰
  - 确保退出码和决策输出正确

## 3. Python 服务模块化

- [x] 3.1 创建目录结构
  - `callback-server/handlers/`
  - `callback-server/services/`
  - `callback-server/models/`
  - `callback-server/templates/`
- [x] 3.2 抽离 Decision 模型
  - 创建 `models/decision.py`
  - 移动 Decision 类和相关常量
- [x] 3.3 抽离规则写入服务
  - 创建 `services/rule_writer.py`
  - 移动 `write_always_allow_rule()` 函数
  - 移动 `RULE_FORMATTERS` 配置
- [x] 3.4 抽离请求管理服务
  - 创建 `services/request_manager.py`
  - 移动 `RequestManager` 类
- [x] 3.5 抽离 HTTP 处理器
  - 创建 `handlers/callback.py`
  - 移动 `CallbackHandler` 类
  - 移动 HTML 响应模板到 `templates/`
- [x] 3.6 重构 server.py
  - 保留服务启动逻辑
  - 导入并使用各模块
  - Socket 服务处理逻辑保留在 server.py

## 4. 测试验证

- [x] 4.1 Shell 函数库单元测试
  - 测试 `json_get()` 各种场景
  - 测试 `extract_tool_detail()` 各工具类型
  - 测试 `build_permission_card()` 输出格式
- [x] 4.2 集成测试
  - 验证交互模式完整流程
  - 验证降级模式完整流程
  - 验证各决策类型（allow/always/deny/interrupt）
- [x] 4.3 兼容性测试
  - 测试无 jq 环境
  - 测试无 python3 环境（仅 grep/sed）
  - 测试回调服务不可用场景

## 5. 文档更新

- [x] 5.1 更新 README.md
  - 添加模块结构说明
  - 更新依赖说明
- [x] 5.2 添加函数库文档
  - 每个 lib/*.sh 添加使用说明注释
  - 添加示例代码

## 依赖关系

- 任务 2 依赖任务 1 完成
- 任务 3 可与任务 1、2 并行
- 任务 4 依赖任务 2、3 完成
- 任务 5 在最后进行
