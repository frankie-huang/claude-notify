## ADDED Requirements

### Requirement: Shell Script Modular Architecture

系统 SHALL 采用模块化架构组织 Shell 脚本代码，将复用逻辑抽离为独立的函数库。

#### Scenario: JSON 解析函数库

- **GIVEN** 系统需要解析 JSON 数据
- **WHEN** 任何 Shell 脚本需要读取 JSON 字段
- **THEN** 脚本引用 `lib/json.sh` 函数库
- **AND** 使用统一的 `json_get()` 函数获取字段值
- **AND** 函数内部自动选择可用的解析工具（jq > python3 > grep/sed）
- **AND** 调用方无需关心具体解析实现

#### Scenario: 飞书卡片函数库

- **GIVEN** 系统需要发送飞书通知
- **WHEN** 需要构建飞书卡片消息
- **THEN** 脚本引用 `lib/feishu.sh` 函数库
- **AND** 使用 `build_permission_card()` 构建权限请求卡片
- **AND** 使用 `send_feishu_card()` 发送卡片
- **AND** 交互式和降级模式复用相同的卡片模板

#### Scenario: 工具详情函数库

- **GIVEN** 系统需要格式化不同工具类型的请求详情
- **WHEN** 需要提取 Bash/Edit/Write/Read 等工具的参数
- **THEN** 脚本引用 `lib/tool.sh` 函数库
- **AND** 使用 `extract_tool_detail()` 获取格式化的详情内容
- **AND** 新增工具类型仅需修改配置数组，无需改动提取逻辑

#### Scenario: 日志函数库

- **GIVEN** 系统需要记录日志
- **WHEN** 任何脚本需要输出日志
- **THEN** 脚本引用 `lib/log.sh` 函数库
- **AND** 使用统一的 `log()` 函数记录日志
- **AND** 日志自动包含时间戳和调用位置

### Requirement: Python Service Modular Architecture

系统 SHALL 采用模块化架构组织 Python 服务代码，实现关注点分离。

#### Scenario: HTTP 处理器模块分离

- **GIVEN** 回调服务需要处理 HTTP 请求
- **WHEN** 用户点击飞书卡片按钮
- **THEN** 请求由 `handlers/callback.py` 模块处理
- **AND** 处理器仅负责路由和参数解析
- **AND** 业务逻辑委托给 services 层

#### Scenario: 请求管理服务模块

- **GIVEN** 系统需要管理待处理的权限请求
- **WHEN** permission-notify.sh 发起请求
- **THEN** 请求由 `services/request_manager.py` 管理
- **AND** 模块负责请求注册、状态跟踪、连接管理
- **AND** 与 HTTP 处理器解耦

#### Scenario: 规则写入服务模块

- **GIVEN** 用户点击"始终允许"按钮
- **WHEN** 系统需要写入权限规则
- **THEN** 规则由 `services/rule_writer.py` 模块处理
- **AND** 模块负责规则格式化和文件写入
- **AND** 与请求管理模块解耦

#### Scenario: 决策模型独立

- **GIVEN** 系统需要构造决策响应
- **WHEN** 需要返回 allow/deny 决策
- **THEN** 使用 `models/decision.py` 中的 Decision 类
- **AND** 类提供 `allow()` 和 `deny()` 工厂方法
- **AND** 决策格式符合 Claude Code Hook 规范

### Requirement: Tool Type Configuration

系统 SHALL 使用配置驱动的方式管理工具类型，支持灵活扩展。

#### Scenario: 工具类型配置集中管理

- **GIVEN** 系统支持多种工具类型（Bash, Edit, Write, Read, Glob, Grep 等）
- **WHEN** 需要处理特定工具的权限请求
- **THEN** 工具类型的颜色、字段映射、规则格式集中配置
- **AND** 新增工具类型仅需添加配置项
- **AND** 无需修改核心处理逻辑

#### Scenario: Shell 脚本工具配置

- **GIVEN** permission-notify.sh 需要处理工具详情
- **WHEN** 提取工具参数用于显示
- **THEN** 使用 `lib/tool.sh` 中的配置数组
- **AND** `TOOL_COLORS` 映射工具类型到卡片颜色
- **AND** `TOOL_FIELDS` 映射工具类型到参数字段名

#### Scenario: Python 服务工具配置

- **GIVEN** 回调服务需要生成权限规则
- **WHEN** 用户点击"始终允许"
- **THEN** 使用 `RULE_FORMATTERS` 字典生成规则字符串
- **AND** 新增工具类型仅需添加格式化函数

## MODIFIED Requirements

### Requirement: Error Handling

脚本 SHALL 具备容错能力，确保不会阻塞 Claude Code 正常运行。脚本 SHALL 在无 jq 环境下使用原生 Linux 命令（grep、sed、awk）解析 JSON，功能与 jq 解析一致。**脚本 SHALL 通过统一的函数库实现 JSON 解析，避免重复代码。**

#### Scenario: 无 jq 环境下使用原生命令解析

- **GIVEN** 系统未安装 jq
- **WHEN** 脚本接收到 PermissionRequest hook 的 JSON 数据
- **THEN** `lib/json.sh` 中的 `json_get()` 函数自动使用 grep、sed 等原生命令解析 JSON
- **AND** 正确提取 `tool_name` 字段
- **AND** 正确提取 `tool_input` 中的嵌套字段（command、file_path、pattern 等）
- **AND** 通知内容与使用 jq 解析时完全一致

#### Scenario: jq 可用时优先使用

- **GIVEN** 系统已安装 jq
- **WHEN** 脚本接收到 JSON 数据
- **THEN** `lib/json.sh` 中的 `json_init()` 检测到 jq 可用
- **AND** `json_get()` 函数优先使用 jq 解析（更可靠）
- **AND** 不使用原生命令解析

#### Scenario: JSON 解析失败降级处理

- **GIVEN** stdin 输入的 JSON 格式无效或缺少必要字段
- **WHEN** 脚本尝试解析 JSON（无论使用 jq 还是原生命令）
- **THEN** 脚本发送降级通知消息，说明有权限请求但无法解析详情
- **AND** 脚本以退出码 0 结束，不阻塞 Claude Code

#### Scenario: Webhook 请求失败静默处理

- **GIVEN** 飞书 Webhook URL 不可达或返回错误
- **WHEN** `lib/feishu.sh` 中的 `send_feishu_card()` 尝试发送通知
- **THEN** 函数记录错误日志
- **AND** 脚本以退出码 0 结束
- **AND** 不影响 Claude Code 继续运行
