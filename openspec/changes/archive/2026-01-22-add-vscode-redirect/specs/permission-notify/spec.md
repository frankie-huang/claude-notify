## ADDED Requirements

### Requirement: VSCode Auto Redirect Configuration

系统 SHALL 支持通过环境变量配置 VSCode 自动跳转功能。

#### Scenario: 配置 VSCode Remote 前缀

- **GIVEN** 用户在 `.env` 文件中配置 `VSCODE_REMOTE_PREFIX`
- **WHEN** 回调服务启动
- **THEN** 服务读取该配置
- **AND** 配置值为 VSCode URI 前缀（如 `vscode://vscode-remote/ssh-remote+server`）
- **AND** 不包含项目路径部分

#### Scenario: 未配置时禁用跳转

- **GIVEN** 用户未配置 `VSCODE_REMOTE_PREFIX` 环境变量
- **WHEN** 用户点击飞书卡片按钮并处理完成
- **THEN** 响应页面显示操作结果
- **AND** 不执行 VSCode 跳转
- **AND** 保持当前的自动关闭页面行为

### Requirement: Response Page VSCode Redirect

回调服务响应页面 SHALL 在配置启用时自动跳转到 VSCode。

#### Scenario: 操作成功后跳转 VSCode

- **GIVEN** 用户已配置 `VSCODE_REMOTE_PREFIX`
- **AND** 权限请求包含有效的项目路径（`project_dir`）
- **WHEN** 用户点击飞书卡片按钮（批准/拒绝/始终允许/拒绝并中断）
- **AND** 回调服务成功处理决策
- **THEN** 响应页面显示操作成功信息
- **AND** 页面在短暂延迟（约 500ms）后自动跳转到 VSCode
- **AND** VSCode URI 格式为 `{VSCODE_REMOTE_PREFIX}{project_dir}`

#### Scenario: 跳转后聚焦终端

- **GIVEN** VSCode 跳转成功执行
- **WHEN** VSCode 打开项目
- **THEN** 用户可以在 VSCode 中查看 Claude Code 终端的执行结果
- **AND** 终端保持之前的聚焦状态（依赖用户的 VSCode 布局设置）

#### Scenario: 操作失败时不跳转

- **GIVEN** 用户已配置 `VSCODE_REMOTE_PREFIX`
- **WHEN** 回调服务处理决策失败（请求无效、连接断开等）
- **THEN** 响应页面显示错误信息
- **AND** 不执行 VSCode 跳转

#### Scenario: 页面显示跳转提示

- **GIVEN** 用户已配置 `VSCODE_REMOTE_PREFIX`
- **AND** 决策处理成功
- **WHEN** 响应页面加载
- **THEN** 页面显示"正在跳转到 VSCode..."的提示信息
- **AND** 用户可以看到跳转即将发生

#### Scenario: 跳转失败时显示手动链接

- **GIVEN** 用户已配置 `VSCODE_REMOTE_PREFIX`
- **AND** 决策处理成功
- **AND** 页面尝试跳转到 VSCode
- **WHEN** 跳转超时（页面仍未离开，如 2 秒后）
- **THEN** 页面显示"跳转失败"的错误提示
- **AND** 页面显示可点击的 VSCode URI 链接
- **AND** 用户可以手动点击链接打开 VSCode
