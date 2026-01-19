# permission-notify Specification - Delta

## ADDED Requirements

### Requirement: Feishu Card Template System

系统 SHALL 提供基于模板文件的飞书卡片构建机制,将卡片结构与渲染逻辑分离。

#### Scenario: 模板文件加载

- **GIVEN** 系统使用 `build_permission_card()` 构建权限请求卡片
- **WHEN** 函数被调用
- **THEN** 系统从 `templates/feishu/permission-card.json` 加载模板文件
- **AND** 模板路径可通过环境变量 `FEISHU_TEMPLATE_PATH` 自定义
- **AND** 如果模板文件不存在,记录错误日志并返回失败
- **AND** 调用方利用现有的 `send_feishu_text()` 发送降级文本通知

#### Scenario: 模板变量替换

- **GIVEN** 模板文件包含占位符 `{{variable_name}}`
- **WHEN** 调用 `render_card_template()` 函数并传入变量值
- **THEN** 系统将所有 `{{variable_name}}` 替换为实际值
- **AND** 特殊字符(如双引号、反斜杠)自动转义为 JSON 安全格式
- **AND** 返回完整的飞书卡片 JSON 字符串

#### Scenario: 模板验证

- **GIVEN** 模板文件被加载
- **WHEN** 系统检测到 `jq` 或 `python3` 可用
- **THEN** 系统验证模板文件的 JSON 格式正确性
- **AND** 如果 JSON 格式无效,记录错误日志并降级到原有逻辑
- **AND** 如果无验证工具可用,跳过验证步骤

#### Scenario: 模板文件组织结构

- **GIVEN** 系统需要管理多种类型的飞书卡片
- **WHEN** 查看模板目录 `templates/feishu/`
- **THEN** 目录包含 `permission-card.json` (交互模式权限请求卡片)
- **AND** 目录包含 `permission-card-static.json` (静态模式权限请求卡片)
- **AND** 目录包含 `notification-card.json` (通用通知卡片)
- **AND** 目录包含 `buttons.json` (交互按钮配置)
- **AND** 目录包含 `README.md` (模板使用说明和变量清单)

#### Scenario: 自定义模板支持

- **GIVEN** 用户希望自定义卡片样式
- **WHEN** 用户设置环境变量 `FEISHU_TEMPLATE_PATH=/custom/path`
- **AND** 在自定义路径创建模板文件
- **THEN** 系统使用自定义路径的模板
- **AND** 如果自定义模板不存在,记录错误并返回失败

#### Scenario: 模板渲染错误处理

- **GIVEN** 模板渲染过程中发生错误(如变量未定义)
- **WHEN** 捕获到渲染错误
- **THEN** 系统记录详细的错误日志(包含模板路径、变量名、错误原因)
- **AND** 系统返回失败状态码
- **AND** 调用方利用现有的 `send_feishu_text()` 发送降级文本通知

## MODIFIED Requirements

### Requirement: Feishu Card Message Format

通知消息 SHALL 使用飞书交互式卡片格式,包含以下信息。卡片结构通过模板文件定义,支持通过修改模板文件更新样式。

#### Scenario: 卡片消息内容完整

- **GIVEN** 权限请求事件发生
- **WHEN** 发送飞书通知
- **THEN** 卡片标题显示 "Claude Code 权限请求"
- **AND** 卡片包含项目名称(从 `CLAUDE_PROJECT_DIR` 或 `cwd` 获取)
- **AND** 卡片包含请求时间戳
- **AND** 卡片包含工具类型(Bash/Edit/Write 等)
- **AND** 卡片包含请求详情(命令内容或文件路径)
- **AND** 卡片包含请求 ID(用于关联回调)
- **AND** 卡片包含操作提示(如 "请尽快操作以避免 Claude 超时")
- **AND** 卡片包含 4 个操作按钮(批准/始终允许/拒绝/拒绝并中断)
- **AND** 卡片结构由 `templates/feishu/permission-card.json` 模板定义
- **AND** 可通过编辑模板文件修改卡片样式,无需改动代码
- **AND** 如果模板文件损坏或格式无效,系统记录错误并发送降级文本通知

#### Scenario: 卡片样式更新

- **GIVEN** 用户希望更新卡片样式
- **WHEN** 用户直接编辑 `templates/feishu/permission-card.json` 文件
- **AND** 修改模板的 JSON 结构(如调整布局、添加元素)
- **THEN** 下次发送权限请求时自动使用新样式
- **AND** 无需修改任何 Shell 脚本代码
- **AND** 如果新模板 JSON 格式无效,系统记录错误并发送降级文本通知

### Requirement: Shell Script Modular Architecture

系统 SHALL 采用模块化架构组织 Shell 脚本代码,将复用逻辑抽离为独立的函数库。卡片构建逻辑通过模板文件实现进一步解耦。

#### Scenario: 飞书卡片函数库

- **GIVEN** 系统需要发送飞书通知
- **WHEN** 需要构建飞书卡片消息
- **THEN** 脚本引用 `shell-lib/feishu.sh` 函数库
- **AND** 使用 `build_permission_card()` 构建权限请求卡片
- **AND** 使用 `send_feishu_card()` 发送卡片
- **AND** 交互式和降级模式复用相同的卡片模板
- **AND** 卡片结构由模板文件定义,与渲染逻辑分离
- **AND** `render_card_template()` 函数负责加载模板和变量替换
- **AND** 提供 `json_escape()` 函数处理变量转义
- **AND** 提供 `validate_template()` 函数验证模板格式

#### Scenario: 模板与业务逻辑分离

- **GIVEN** 系统需要维护多种类型的飞书卡片
- **WHEN** 开发者需要调整卡片样式
- **THEN** 直接编辑 `templates/feishu/` 目录下的 JSON 模板文件
- **AND** Shell 函数库仅需提供变量数据,不包含卡片结构
- **AND** 新增卡片类型仅需添加新模板文件,无需修改渲染逻辑
- **AND** 模板文件可独立版本控制(通过 Git 分支或文件命名)
