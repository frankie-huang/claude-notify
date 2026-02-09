## 1. 后端接口

- [x] 1.1 实现 `/claude/browse-dirs` 接口
  - 在 `callback.py` 中新增路由处理
  - 验证 auth_token
  - 接收 path 和 limit 参数
  - 调用 `os.listdir` 列出子目录，过滤隐藏目录和文件
  - 返回 `{dirs, parent, current}` 格式

## 2. 卡片 UI 改造

- [x] 2.1 修改 `_send_new_session_card` 函数
  - 在 `select_static`（常用目录）之后添加 `input` 组件（name=`custom_dir`）
  - 添加优先级提示文本
  - 添加"浏览"按钮（name=`browse_btn`，type=default）
  - 使用 `column_set` 将输入框和浏览按钮并排
  - 无历史目录时，隐藏 select_static 常用目录下拉

## 3. 回调处理改造

- [x] 3.1 修改 `_handle_new_session_form` 函数
  - 根据按钮 trigger_name 区分"浏览"和"创建"操作
  - 创建操作：按 custom_dir > browse_result > directory 优先级确定目录
  - 浏览操作：调用 browse-dirs 接口，构建并返回更新后的卡片

- [x] 3.2 实现 `_build_browse_result_card` 函数
  - 接收浏览结果、当前路径、原始 prompt 等参数
  - 构建包含浏览结果 select_static 的新卡片
  - 通过 default_value 回填 prompt 和 custom_dir 的值
  - 浏览结果为空时显示"该目录下没有子目录"提示

- [x] 3.3 实现 `_handle_browse_directory` 函数
  - 处理浏览按钮点击
  - 调用 browse-dirs 接口获取子目录列表
  - 构建并返回更新后的卡片

## 4. 飞书网关获取浏览结果

- [x] 4.1 实现 `_fetch_browse_dirs_from_callback` 函数
  - 类似现有的 `_fetch_recent_dirs_from_callback`
  - 调用 `/claude/browse-dirs` 接口
  - 传递 auth_token、path、limit 参数
  - 返回目录列表和路径信息

## 5. 测试验证

- [ ] 5.1 测试 browse-dirs 接口
  - 正常路径浏览
  - 路径不存在时的错误处理
  - 非绝对路径时的参数验证
  - 隐藏目录过滤

- [ ] 5.2 测试卡片交互流程
  - 自定义路径输入 + 创建会话
  - 浏览目录 → 选择 → 创建会话
  - 无历史目录时的表现
  - 自定义路径优先级验证

- [ ] 5.3 测试边界场景
  - 根目录浏览
  - 空目录浏览
  - 权限不足的目录
  - 自定义路径与下拉选择同时填写
