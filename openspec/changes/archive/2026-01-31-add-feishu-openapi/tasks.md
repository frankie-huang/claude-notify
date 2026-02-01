# Tasks: 飞书 OpenAPI 发送消息功能

## 1. 后端核心模块
- [x] 1.1 创建 `src/server/services/feishu_api.py`
- [x] 1.2 扩展 `src/server/config.py` 新增配置项

## 2. HTTP 端点
- [x] 2.1 扩展 `handlers/feishu.py` 添加消息发送处理
- [x] 2.2 修改 `handlers/callback.py` 添加路由分发
- [x] 2.3 修改 `main.py` 初始化服务

## 3. Shell 集成
- [x] 3.1 重构 `lib/feishu.sh` 支持双模式
- [x] 3.2 更新 `.env.example` 和 `install.sh`

## 4. 文档更新
- [x] 4.1 更新 README.md 环境变量说明
