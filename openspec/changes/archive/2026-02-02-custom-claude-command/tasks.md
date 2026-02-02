## 1. 环境变量配置

- [x] 1.1 在 `.env.example` 中新增 `CLAUDE_COMMAND` 配置说明
- [x] 1.2 在 `install.sh` 的 `generate_env_template()` 函数中同步添加配置

## 2. 代码实现

- [x] 2.1 修改 `src/server/handlers/claude.py`，从环境变量读取 Claude 命令
- [x] 2.2 通过登录 shell（`bash -lc`）执行命令，支持 shell 配置文件中的别名
- [x] 2.3 使用 `shlex.quote()` 安全处理 prompt 中的特殊字符
- [x] 2.4 保持默认值为 `claude`，确保向后兼容
- [x] 2.5 更新日志输出，显示实际执行的完整命令

## 3. 测试验证

- [ ] 3.1 验证默认配置（不设置环境变量）使用 `claude` 命令
- [ ] 3.2 验证配置 `claude-glm` 后正确使用该命令
- [ ] 3.3 验证配置带参数的命令（如 `claude --setting opus`）
- [ ] 3.4 验证 shell 配置文件中定义的别名可以被正确识别

## 4. 文档更新

- [x] 4.1 更新 `docs/feishu-reply-continue-session.md`，新增配置说明章节
- [x] 4.2 更新说明支持 shell 别名的特性
