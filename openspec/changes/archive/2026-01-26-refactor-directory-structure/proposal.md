# Change: 重构项目目录结构

## Why

当前项目根目录文件较多（15 个一级目录/文件），随着项目发展，结构变得不够清晰。用户希望：
1. 把源代码统一放入 `src/` 目录，保持根目录简洁
2. 入口脚本（hook、start）放在 `src/` 一级便于快速定位
3. 提高代码复用性，抽象公共逻辑
4. 增强路径自适应能力，减少未来重构时的路径更新工作

## What Changes

### 目录结构变化

**当前结构：**
```
claude-notify/
├── hooks/           # Hook 脚本
├── server/          # Python 服务
├── shell-lib/       # Shell 库
├── shared/          # 跨语言共享
├── config/          # 配置
├── templates/       # 模板
├── local-proxy/     # VSCode 代理
├── docs/            # 文档
├── log/             # 日志
├── openspec/        # 规范
├── test/            # 测试
├── install.sh       # 安装脚本
└── ...              # 其他根目录文件
```

**重构后结构：**
```
claude-notify/
├── src/                    # 源代码目录
│   ├── hook-router.sh      # Hook 统一入口（配置到 Claude Code）
│   ├── start-server.sh     # 服务启动脚本
│   │
│   ├── hooks/              # Hook 处理逻辑
│   │   ├── permission.sh   # 权限请求处理
│   │   └── webhook.sh      # 通用通知处理
│   │
│   ├── server/             # Python 回调服务
│   │   ├── main.py
│   │   ├── config.py
│   │   └── ...
│   │
│   ├── lib/                # Shell 函数库
│   │   ├── core.sh         # 核心：路径、环境、日志
│   │   ├── json.sh
│   │   ├── feishu.sh
│   │   ├── socket.sh
│   │   └── ...
│   │
│   ├── shared/             # 跨语言共享
│   │   └── ...
│   │
│   ├── config/             # 配置文件
│   │   └── tools.json
│   │
│   ├── templates/          # 模板
│   │   └── feishu/
│   │
│   └── proxy/              # VSCode 代理
│       └── vscode-ssh-proxy.py
│
├── docs/                   # 文档
├── log/                    # 日志（运行时生成）
├── openspec/               # 规范
├── test/                   # 测试
│
├── install.sh              # 安装脚本
├── README.md
├── CHANGELOG.md
├── CLAUDE.md
├── LICENSE
├── .env.example
└── .gitignore
```

### 关键设计点

1. **统一 Hook 路由入口**
   - `src/hook-router.sh` - 所有 Hook 的统一入口，Claude Code 只需配置这一个路径
   - `src/start-server.sh` - 服务启动脚本
   - 入口脚本置于 `src/` 一级，便于快速定位

2. **路径自适应机制**
   - 所有脚本使用 `get_project_root()` 获取项目根目录
   - 通过统一的路径变量（如 `$SRC_DIR`、`$LIB_DIR`）引用子目录
   - 路径变量集中定义在 `src/lib/core.sh`

3. **代码复用优化**
   - 合并 `project.sh`、`env.sh`、`log.sh` 到 `lib/core.sh`
   - 减少重复的初始化逻辑
   - 统一的函数加载方式

4. **向后兼容**
   - `install.sh` 位置不变
   - 更新 Claude Code Hook 配置路径

## Impact

### 受影响的规范
- `project-structure` - 需要完全重写

### 受影响的代码
- 所有 Shell 脚本中的路径引用
- 所有 Python 文件中的路径引用
- `install.sh` 中的路径定义
- `README.md` 中的目录说明

### 受影响的配置
- Claude Code `settings.json` 中的 hook 路径
- `.env.example` 中的路径相关说明

### 迁移注意事项
- 现有用户需要重新运行 `install.sh` 更新 hook 路径配置
- 日志目录 `log/` 保持不变，无需迁移
