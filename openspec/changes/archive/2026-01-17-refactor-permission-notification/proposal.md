# Change: 重构权限请求通知和审批功能

## Why

当前代码存在以下问题，需要通过重构解决：

1. **代码重复严重**：
   - `permission-notify.sh` 中 JSON 解析逻辑重复出现多次（jq/python3/grep-sed 三种方式）
   - 飞书卡片构建逻辑在 `send_interactive_card()` 和 `run_fallback_mode()` 中几乎完全重复
   - 工具详情提取逻辑（Bash/Edit/Write/Read）在多处重复

2. **职责不清晰**：
   - Shell 脚本承担了过多职责（JSON 解析、卡片构建、Socket 通信、决策输出）
   - 回调服务器同时处理 HTTP 路由、请求管理、规则写入、响应渲染

3. **可维护性差**：
   - 新增工具类型需要修改多处代码
   - 超时配置分散在多个文件中
   - 错误处理逻辑重复且不一致

4. **可测试性差**：
   - 大量逻辑耦合在主流程中，难以单独测试
   - 缺乏模块化设计

## What Changes

### 1. Shell 脚本重构

**抽离复用模块**：
- `lib/json-parser.sh` - JSON 解析函数库（统一 jq/python3/grep-sed 三种方式）
- `lib/feishu-card.sh` - 飞书卡片构建函数库
- `lib/tool-formatter.sh` - 工具详情格式化函数库
- `lib/socket-comm.sh` - Socket 通信函数库
- `lib/log.sh` - 日志函数库

**重构 permission-notify.sh**：
- 拆分为更小的函数
- 引用共享库
- 简化主流程

### 2. Python 服务重构

**抽离模块**：
- `callback-server/handlers/` - HTTP 请求处理器
- `callback-server/services/request_manager.py` - 请求管理服务
- `callback-server/services/rule_writer.py` - 规则写入服务
- `callback-server/templates/` - HTML 响应模板

**重构 server.py**：
- 拆分为更小的模块
- 使用依赖注入提升可测试性

### 3. 配置统一

- 将所有配置集中到 `config/` 目录
- 支持环境变量覆盖
- 提供合理的默认值

## Impact

- **受影响的规范**: `specs/permission-notify/spec.md`（需要补充模块化要求）
- **受影响的代码**:
  - `permission-notify.sh` - 主要重构目标
  - `callback-server/server.py` - 次要重构目标
  - `callback-server/socket-client.py` - 可能需要调整
- **不受影响的功能**: 所有现有功能保持不变，仅改变内部实现结构

## Risk Assessment

- **低风险**: 重构不改变对外接口，仅改变内部实现
- **测试策略**: 通过集成测试验证现有功能不受影响
- **回滚策略**: 可随时回退到重构前的代码
