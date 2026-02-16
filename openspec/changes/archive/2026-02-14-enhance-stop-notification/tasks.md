# 任务清单：优化 Stop 事件通知内容

## 阶段 1：JSONL 解析逻辑重构

### 1.1 新增 extract_response_from_file 函数
- [ ] 在 `src/hooks/stop.sh` 中实现 `extract_response_from_file(transcript_file, max_retries)`
- [ ] jq 路径：找最近 user text 消息，收集其后所有 assistant 的 text 和 thinking
- [ ] python3 路径：同上逻辑的 python3 实现
- [ ] 返回 JSON 对象 `{text, thinking, session_id}`
- [ ] 保留重试机制（处理文件未写完的竞态）

### 1.2 新增 extract_response 函数
- [ ] 在 `src/hooks/stop.sh` 中实现 `extract_response(transcript_path)` 替代 `find_last_assistant`
- [ ] 先在主 transcript 中提取
- [ ] 主 transcript 无 text 内容时回退到 subagents 目录
- [ ] subagent 文件中无 user 消息时收集所有 assistant text/thinking

### 1.3 移除旧函数
- [ ] 移除 `find_last_assistant_in_file()`
- [ ] 移除 `find_last_assistant()`

## 阶段 2：卡片模板与渲染

### 2.1 新增 thinking 子模板
- [ ] 创建 `src/templates/feishu/thinking-element.json`（collapsible_panel 折叠面板）

### 2.2 修改 stop 卡片模板
- [ ] 在 `src/templates/feishu/stop-card.json` 中添加 `{{thinking_element}}` 占位符

### 2.3 修改 feishu.sh 渲染逻辑
- [ ] `render_template()`：将 `thinking_element` 加入 JSON 片段免转义列表
- [ ] `render_template()`：将 `thinking_content` 加入 response_content 同级转义分支
- [ ] `render_sub_template()`：添加 `"thinking"` 类型支持
- [ ] `build_stop_card()`：添加第 5 个参数 `thinking_content`，条件构建 thinking_element

## 阶段 3：主流程集成

### 3.1 更新 send_stop_notification_async
- [ ] 读取 `STOP_THINKING_MAX_LENGTH` 配置
- [ ] 调用 `extract_response` 替代 `find_last_assistant`
- [ ] 分别提取 text 和 thinking 内容
- [ ] 对 thinking 和 text 分别截断
- [ ] STOP_THINKING_MAX_LENGTH=0 时跳过 thinking
- [ ] 传递 thinking 给 `build_stop_card`

## 阶段 4：配置与文档

### 4.1 配置文件更新
- [ ] `.env.example` 添加 `STOP_THINKING_MAX_LENGTH=5000`
- [ ] `install.sh` 的 `generate_env_template()` 同步添加

### 4.2 文档更新
- [ ] 更新 README.md 相关说明

## 依赖关系

```
1.1 ──> 1.2 ──> 1.3
                 │
2.1 ──> 2.2      │
         │       │
2.3 ────┘       │
                 │
1.3 + 2.3 ──> 3.1 ──> 4.1 ──> 4.2
```

## 并行化建议

- 阶段 1（JSONL 解析）和 阶段 2（卡片模板）可以并行开发
- 阶段 3 依赖前两者完成
- 阶段 4 最后执行
