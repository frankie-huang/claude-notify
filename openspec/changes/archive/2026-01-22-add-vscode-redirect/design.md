## Context

用户在飞书中点击权限请求卡片按钮后，当前流程：
1. 浏览器打开回调服务 URL（如 `http://localhost:8080/allow?id=xxx`）
2. 回调服务处理决策，返回确认页面
3. 用户手动切换到 VSCode 查看结果

期望流程：
1. 浏览器打开回调服务 URL
2. 回调服务处理决策，返回确认页面
3. **页面自动跳转到 VSCode 并聚焦终端**

## Goals / Non-Goals

**Goals:**
- 支持可选的 VSCode 自动跳转功能
- 通过环境变量配置，兼容不同的 VSCode Remote 环境
- 跳转后聚焦到终端，方便用户查看执行结果

**Non-Goals:**
- 不开发 VSCode 扩展
- 不改变现有的回调接口协议
- 不强制要求用户配置 VSCode

## Decisions

### 1. 使用 VSCode URI Scheme 实现跳转

VSCode 支持通过 URI Scheme 打开文件和执行命令：
- 本地: `vscode://file/path/to/project`
- Remote SSH: `vscode://vscode-remote/ssh-remote+hostname/path/to/project`
- WSL: `vscode://vscode-remote/wsl+distro/path/to/project`

用户配置 `VSCODE_REMOTE_PREFIX` 环境变量（不含路径部分），系统自动拼接项目路径：
```
VSCODE_REMOTE_PREFIX=vscode://vscode-remote/ssh-remote+myserver
```

完整 URI 示例：`vscode://vscode-remote/ssh-remote+myserver/home/user/project`

### 2. 使用 JavaScript 在页面加载后跳转

响应页面通过 JavaScript 实现跳转：
```javascript
// 仅当配置了 VSCODE_REMOTE_PREFIX 时执行
if (vscodeUri) {
    setTimeout(() => {
        window.location.href = vscodeUri;
    }, 500); // 短暂延迟，让用户看到操作结果
}
```

### 3. 聚焦终端

VSCode URI 支持 `goto` 参数指定打开的视图。可以尝试使用以下方式聚焦终端：
- 打开项目后，终端通常会保持之前的状态
- 如果需要更精确的控制，可能需要 VSCode 扩展支持（超出本次范围）

初始实现：仅打开项目目录，依赖用户的 VSCode 布局设置。

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 浏览器可能阻止自动跳转 | 使用 `window.location.href` 而非 `window.open()`；页面由用户主动点击触发 |
| VSCode 未安装或 URI Handler 未注册 | 跳转失败时不影响决策已处理的事实；页面显示"操作成功" |
| 不同平台 URI 格式不同 | 由用户配置正确的 `VSCODE_REMOTE_PREFIX` |

## UI 设计决策

1. **跳转提示**: 页面显示"正在跳转到 VSCode..."的提示，让用户知道即将发生跳转
2. **跳转失败处理**: 如果跳转失败（超时未离开页面），显示错误提示并提供手动打开的链接
