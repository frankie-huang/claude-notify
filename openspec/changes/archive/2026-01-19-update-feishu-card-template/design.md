# Design Document

## 飞书卡片 2.0 格式设计

### 架构对比

#### 1.0 格式结构（当前）

```json
{
  "msg_type": "interactive",
  "card": {
    "header": { ... },
    "elements": [
      { "tag": "div", ... },
      { "tag": "hr" },
      { "tag": "div", "fields": [...] },
      { "tag": "action", "actions": [...] },
      { "tag": "note", ... }
    ]
  }
}
```

#### 2.0 格式结构（目标）

```json
{
  "msg_type": "interactive",
  "card": {
    "schema": "2.0",
    "config": {
      "update_multi": true,
      "style": {
        "text_size": {
          "normal_v2": {
            "default": "normal",
            "pc": "normal",
            "mobile": "heading"
          }
        }
      }
    },
    "header": { ... },
    "body": {
      "direction": "vertical",
      "elements": [
        { "tag": "markdown", ... },
        { "tag": "hr" },
        { "tag": "column_set", "columns": [...] },
        { "tag": "column_set", "columns": [...] },
        { "tag": "div", ... }
      ]
    }
  }
}
```

### 关键设计决策

#### 1. 文本大小配置

```json
"config": {
  "style": {
    "text_size": {
      "normal_v2": {
        "default": "normal",
        "pc": "normal",
        "mobile": "heading"
      }
    }
  }
}
```

**决策理由：** 移动端屏幕较小，使用 `heading` 级别文本可提高可读性，PC 端保持 `normal` 避免内容过于突兀。

#### 2. 信息并排布局

使用 `column_set` 实现项目名称和时间的并排显示：

```json
{
  "tag": "column_set",
  "columns": [
    {
      "tag": "column",
      "width": "weighted",
      "weight": 1,
      "elements": [
        {
          "tag": "markdown",
          "content": "**项目：**\n{{project_name}}"
        }
      ]
    },
    {
      "tag": "column",
      "width": "weighted",
      "weight": 1,
      "elements": [
        {
          "tag": "markdown",
          "content": "**时间：**\n{{timestamp}}"
        }
      ]
    }
  ]
}
```

**决策理由：** 使用 `width: "weighted"` + `weight: 1` 实现均分宽度，确保两列对齐美观。

#### 3. 按钮横向排列

```json
{
  "tag": "column_set",
  "flex_mode": "stretch",
  "horizontal_spacing": "10px",
  "horizontal_align": "left",
  "columns": [
    {
      "tag": "column",
      "width": "auto",
      "elements": [
        {
          "tag": "button",
          "text": { "tag": "plain_text", "content": "批准运行" },
          "type": "primary_filled",
          "width": "fill",
          "behaviors": [
            {
              "type": "open_url",
              "default_url": "{{callback_url}}/allow?id={{request_id}}"
            }
          ]
        }
      ]
    }
    // ... 其他按钮
  ]
}
```

**决策理由：**
- `flex_mode: "stretch"` 让按钮填充可用空间
- `width: "auto"` 让列宽度由内容决定
- `width: "fill"` 让按钮填充列宽度
- `horizontal_spacing: "10px"` 设置按钮间距

#### 4. 按钮类型映射

| 操作 | 旧类型 | 新类型 |
|------|--------|--------|
| 批准运行 | `primary` | `primary_filled` |
| 始终允许 | `default` | `primary` |
| 拒绝运行 | `danger` | `danger` |
| 拒绝并中断 | `danger` | `danger_filled` |

**决策理由：** 使用 `filled` 样式突出主要操作（批准/中断），符合用户视觉预期。

#### 5. 提示文本样式

```json
{
  "tag": "div",
  "text": {
    "tag": "plain_text",
    "content": "请尽快操作以避免 Claude 超时等待",
    "text_size": "notation",
    "text_align": "left",
    "text_color": "grey"
  }
}
```

**决策理由：** 使用 `notation` 小字体 + `grey` 颜色，使提示信息低调但不显眼。

### 模板变量保持不变

所有现有的模板变量保持不变，确保与现有代码的兼容性：

| 变量 | 用途 |
|------|------|
| `{{template_color}}` | 卡片 header 颜色 |
| `{{tool_name}}` | 工具名称 |
| `{{project_name}}` | 项目名称 |
| `{{timestamp}}` | 时间戳 |
| `{{command}}` | Bash 命令 |
| `{{file_path}}` | 文件路径 |
| `{{description}}` | 描述 |
| `{{detail_elements}}` | 详情元素子模板 |
| `{{buttons_json}}` | 按钮 JSON |
| `{{callback_url}}` | 回调服务 URL |
| `{{request_id}}` | 请求 ID |

### 迁移策略

1. **渐进式升级** - 先升级权限请求卡片，其他通知卡片后续升级
2. **测试先行** - 在开发环境验证新格式后再部署
3. **回滚准备** - 保留旧模板文件的备份版本
