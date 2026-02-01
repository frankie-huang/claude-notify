# 规范: 飞书卡片回传交互处理

## 概述

本规范定义飞书卡片按钮回传交互（`card.action.trigger` 事件）的处理机制。

## ADDED Requirements

### Requirement: 卡片回调事件处理

回调服务器 MUST 能够处理飞书 `card.action.trigger` 事件，根据按钮动作类型执行相应的权限决策。

#### Scenario: 处理批准运行回调
- **Given** 用户点击飞书卡片中的"批准运行"按钮
- **When** 服务器收到 `card.action.trigger` 事件，`action.value.action` 为 `allow`
- **Then** 服务器通过 Socket 发送 `allow` 决策给对应的 permission-notify 进程
- **And** 返回 `{"toast": {"type": "success", "content": "已批准运行"}}` 响应

#### Scenario: 处理始终允许回调
- **Given** 用户点击飞书卡片中的"始终允许"按钮
- **When** 服务器收到 `card.action.trigger` 事件，`action.value.action` 为 `always`
- **Then** 服务器通过 Socket 发送 `allow` 决策
- **And** 将权限规则写入项目的 `.claude/settings.local.json`
- **And** 返回 `{"toast": {"type": "success", "content": "已始终允许，后续相同操作将自动批准"}}` 响应

#### Scenario: 处理拒绝运行回调
- **Given** 用户点击飞书卡片中的"拒绝运行"按钮
- **When** 服务器收到 `card.action.trigger` 事件，`action.value.action` 为 `deny`
- **Then** 服务器通过 Socket 发送 `deny` 决策
- **And** 返回 `{"toast": {"type": "success", "content": "已拒绝运行"}}` 响应

#### Scenario: 处理拒绝并中断回调
- **Given** 用户点击飞书卡片中的"拒绝并中断"按钮
- **When** 服务器收到 `card.action.trigger` 事件，`action.value.action` 为 `interrupt`
- **Then** 服务器通过 Socket 发送 `deny` 决策（带 `interrupt: true`）
- **And** 返回 `{"toast": {"type": "success", "content": "已拒绝并中断"}}` 响应

### Requirement: 卡片回调错误处理

回调服务器 MUST 正确处理各种错误场景并返回适当的 toast 响应。

#### Scenario: 请求不存在
- **Given** 回调事件中的 `request_id` 在服务器中不存在
- **When** 服务器尝试处理该回调
- **Then** 返回 `{"toast": {"type": "error", "content": "请求不存在或已过期"}}` 响应

#### Scenario: 请求已处理
- **Given** 回调事件中的 `request_id` 对应的请求已被处理
- **When** 服务器尝试再次处理该回调
- **Then** 返回 `{"toast": {"type": "warning", "content": "该请求已被处理，请勿重复操作"}}` 响应

#### Scenario: Hook 进程已退出
- **Given** 回调事件中的 `request_id` 对应的 hook 进程已退出
- **When** 服务器尝试处理该回调
- **Then** 返回 `{"toast": {"type": "error", "content": "请求已失效，请返回终端查看状态"}}` 响应

#### Scenario: 缺少必要参数
- **Given** 回调事件中缺少 `action` 或 `request_id`
- **When** 服务器尝试处理该回调
- **Then** 返回 `{"toast": {"type": "error", "content": "无效的回调请求"}}` 响应

### Requirement: 卡片按钮回调格式

飞书卡片按钮 MUST 使用 `callback` 行为类型，以支持在飞书内直接响应用户操作。

#### Scenario: 按钮使用回调行为
- **Given** 发送权限请求卡片（OpenAPI 模式）
- **When** 卡片被渲染
- **Then** 四个按钮的 `behaviors` 都使用 `type: callback`
- **And** 每个按钮的 `value` 包含 `action` 和 `request_id` 字段

## 关联规范

- `permission-notify`: 权限通知主规范
- `feishu-card-format`: 飞书卡片格式规范
