# Tasks: Remove jq Dependency

## 1. Implementation

- [x] 1.1 创建原生 JSON 解析函数
  - `json_get_string`: 提取顶层字符串字段（如 `tool_name`）
  - `json_get_nested`: 提取嵌套对象中的字段（如 `tool_input.command`）
  - 使用 grep + sed + awk 实现

- [x] 1.2 重构解析逻辑
  - 抽取公共的字段提取逻辑为函数
  - jq 和原生命令使用相同的变量名和逻辑结构
  - 确保两种解析方式输出一致

- [x] 1.3 更新工具类型处理
  - Bash: 提取 `command` 和 `description`
  - Edit: 提取 `file_path`
  - Write: 提取 `file_path`
  - Read: 提取 `file_path`
  - Glob: 提取 `pattern`
  - Grep: 提取 `pattern` 和 `path`
  - WebFetch/WebSearch: 提取 `url` 或 `query`

## 2. Testing

- [x] 2.1 创建测试用例
  - Bash 命令权限请求
  - 文件操作权限请求
  - 包含特殊字符的命令

- [x] 2.2 验证无 jq 环境
  - 临时移除 PATH 中的 jq
  - 验证原生命令解析正确

## 3. Documentation

- [x] 3.1 更新 README
  - 说明 jq 为可选依赖
  - 说明原生命令解析能力
