# feishu-command Spec Delta

## MODIFIED Requirements

### Requirement: /new 指令缺少目录时发送选择卡片

当用户执行 `/new` 指令但未指定工作目录时，系统 SHALL 发送飞书交互式卡片，卡片包含常用目录下拉菜单和自定义路径输入框。

#### Scenario: 卡片包含自定义路径输入框

- **GIVEN** 飞书网关收到 `/new` 指令
- **AND** 指令不包含 `--dir=` 参数
- **WHEN** 构建目录选择卡片
- **THEN** 卡片包含 `select_static` 下拉菜单（常用目录）
- **AND** 卡片包含 `input` 输入框（name 为 `custom_dir`）
- **AND** input 输入框 label 为"自定义路径"
- **AND** input 输入框 placeholder 为"输入完整路径，如 /home/user/project"
- **AND** input 输入框使用 `column_set` 容器与浏览按钮并排显示
- **AND** 卡片包含提示文本说明优先级："自定义路径优先；留空则使用上方选择的常用目录"

#### Scenario: 输入框与浏览按钮并排布局

- **GIVEN** 构建目录选择卡片
- **WHEN** 渲染自定义路径输入框和浏览按钮
- **THEN** 使用 `column_set` 容器包含两列
- **AND** 第一列为 `input` 组件（name=`custom_dir`），width 为 `weighted`
- **AND** 第二列为 `button` 组件（name=`browse_btn`，text="浏览"），width 为 `auto`
- **AND** 两列在同一行水平排列，输入框占据主要空间
- **AND** 创建会话按钮独占一行（全宽主按钮）不参与 column_set

#### Scenario: 无历史目录时卡片仍可用

- **GIVEN** 用户无历史使用记录
- **AND** 常用目录列表为空
- **WHEN** 构建目录选择卡片
- **THEN** 下拉菜单不显示或显示为空
- **AND** 自定义路径输入框正常可用
- **AND** 浏览目录按钮正常可用
- **AND** 用户可以通过输入框或浏览来选择目录

### Requirement: 目录选择卡片回调处理

系统 SHALL 处理用户在目录选择卡片中提交的操作，包括创建会话和浏览目录。

#### Scenario: 自定义路径优先于下拉选择

- **GIVEN** 用户在自定义路径输入框中填写了 "/home/user/new-project"
- **AND** 用户同时在下拉菜单选择了 "/home/user/old-project"
- **AND** 用户点击"创建会话"按钮
- **WHEN** 处理表单提交
- **THEN** 使用 custom_dir 值 "/home/user/new-project" 作为工作目录
- **AND** 忽略 directory 下拉菜单的值

#### Scenario: 下拉选择作为回退

- **GIVEN** 用户未在自定义路径输入框填写内容（custom_dir 为空字符串）
- **AND** 用户在下拉菜单选择了 "/home/user/project"
- **AND** 用户点击"创建会话"按钮
- **WHEN** 处理表单提交
- **THEN** 使用 directory 下拉菜单的值 "/home/user/project" 作为工作目录

#### Scenario: 两者都为空时报错

- **GIVEN** 用户未填写自定义路径
- **AND** 用户未选择下拉菜单中的目录
- **AND** 用户点击"创建会话"按钮
- **WHEN** 处理表单提交
- **THEN** 返回 toast 错误提示"请选择或输入一个工作目录"

## ADDED Requirements

### Requirement: 路径浏览接口

Callback 后端 SHALL 提供 `/claude/browse-dirs` 端点，列出指定路径下的子目录。

#### Scenario: 列出子目录

- **GIVEN** Callback 后端正在运行
- **WHEN** 收到 POST `/claude/browse-dirs` 请求
- **AND** 请求包含 `{"path": "/home/user", "limit": 20}`
- **THEN** 列出 `/home/user` 下的所有子目录（不含文件）
- **AND** 过滤以 `.` 开头的隐藏目录
- **AND** 按目录名字母排序
- **AND** 返回 `{"dirs": ["/home/user/project1", ...], "parent": "/home", "current": "/home/user"}`
- **AND** dirs 数量不超过 limit

#### Scenario: 路径验证

- **GIVEN** 收到 `/claude/browse-dirs` 请求
- **WHEN** path 不是绝对路径
- **THEN** 返回 `400` 状态码
- **AND** 返回 `{"error": "path must be absolute"}`

#### Scenario: 路径不存在

- **GIVEN** 收到 `/claude/browse-dirs` 请求
- **WHEN** path 不存在或无法访问
- **THEN** 返回 `400` 状态码
- **AND** 返回 `{"error": "path not found or not accessible"}`

#### Scenario: 默认起始路径

- **GIVEN** 收到 `/claude/browse-dirs` 请求
- **WHEN** 请求未包含 path 字段或 path 为空
- **THEN** 默认使用 `/` 作为浏览起始路径

#### Scenario: 认证保护

- **GIVEN** 收到 `/claude/browse-dirs` 请求
- **WHEN** 请求缺少有效的 `X-Auth-Token`
- **THEN** 返回 `401` 状态码
- **AND** 拒绝请求

### Requirement: 浏览目录卡片回调

飞书网关 SHALL 处理目录选择卡片中"浏览目录"按钮的回调，更新卡片显示子目录列表。

#### Scenario: 处理浏览按钮点击

- **GIVEN** 用户点击目录选择卡片中的"浏览"按钮（与 custom_dir 输入框并排）
- **AND** custom_dir 输入框值为 "/home/user"
- **WHEN** 网关收到 form 提交回调
- **AND** 触发按钮 name 为 `browse_btn`
- **THEN** 调用 Callback 后端 `/claude/browse-dirs` 接口
- **AND** 返回更新后的卡片，custom_dir 输入框回填为当前浏览路径
- **AND** 在输入框下方新增子目录列表（`select_static`，name 为 `browse_result`）
- **AND** 保持 prompt 输入框的原值（通过 default_value 回填）
- **AND** 保持 column_set 布局（输入框与浏览按钮并排）

#### Scenario: 浏览结果展示

- **GIVEN** browse-dirs 返回子目录列表
- **AND** 子目录为 ["/home/user/project1", "/home/user/project2"]
- **WHEN** 构建更新后的卡片
- **THEN** 卡片新增一个 `select_static` 组件（name 为 `browse_result`）
- **AND** 选项列表包含返回的子目录
- **AND** label 显示"浏览结果 (/home/user)"
- **AND** 用户选择浏览结果中的目录后，该值自动填入（通过下次提交的 form_values 传递）

#### Scenario: 浏览结果为空

- **GIVEN** browse-dirs 返回空列表（当前目录无子目录）
- **WHEN** 构建更新后的卡片
- **THEN** 卡片显示提示文本"该目录下没有子目录"
- **AND** 保持其他表单元素不变

#### Scenario: 浏览起始路径为空时的默认行为

- **GIVEN** 用户点击"浏览"按钮
- **AND** custom_dir 输入框为空
- **WHEN** 网关处理浏览请求
- **THEN** 使用 `/` 作为浏览起始路径
- **AND** 列出根目录下的子目录
- **AND** 返回卡片时 custom_dir 输入框回填为 `/`

#### Scenario: 选择浏览结果后创建会话

- **GIVEN** 用户在浏览结果中选择了 "/home/user/project1"
- **AND** custom_dir 输入框为空
- **AND** 用户点击"创建会话"按钮
- **WHEN** 处理表单提交
- **THEN** 使用 browse_result 的值 "/home/user/project1" 作为工作目录
