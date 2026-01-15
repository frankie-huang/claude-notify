# Change: Remove jq Dependency for JSON Parsing

## Why

当前 `permission-notify.sh` 脚本强依赖 `jq` 来解析 JSON 数据。如果系统未安装 `jq`，脚本会降级到只显示"无法解析详情"，丢失所有权限请求的详细信息。这在某些精简的服务器环境或容器中是不可接受的。

## What Changes

- 使用 Linux 原生命令（`grep`、`sed`、`awk`）实现完整的 JSON 解析功能
- 优先使用 `jq`（如果可用），否则使用原生命令解析
- 原生命令解析与 `jq` 解析功能完全一致，无功能降级
- 支持解析所有工具类型的 `tool_name` 和 `tool_input` 字段

## Impact

- Affected specs: `permission-notify`（修改 Error Handling requirement）
- Affected code: `permission-notify.sh`
  - 新增原生 JSON 解析函数
  - 修改解析逻辑，支持无 jq 环境
