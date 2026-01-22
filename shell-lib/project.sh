#!/bin/bash
# =============================================================================
# shell-lib/project.sh - 项目路径函数库
#
# 提供获取项目根目录的统一方法
#
# 函数:
#   get_project_root()   - 获取项目根目录路径
#
# 环境变量:
#   PROJECT_ROOT         - 项目根目录路径（自动设置并导出）
#
# 使用示例:
#   source shell-lib/project.sh
#   echo "$PROJECT_ROOT"
#   或者
#   local root="$(get_project_root)"
# =============================================================================

# =============================================================================
# 获取项目根目录
# =============================================================================
# 功能：获取当前项目的根目录路径
# 用法：get_project_root
# 输出：项目根目录的绝对路径
#
# 实现原理：
#   1. 使用 readlink -f 解析软链接，获取真实文件路径
#   2. 从 shell-lib 目录向上一级到达项目根目录
#
# 示例：
#   PROJECT_ROOT="$(get_project_root)"
#   cd "$PROJECT_ROOT"
# =============================================================================
get_project_root() {
    local real_lib_dir
    real_lib_dir="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
    printf '%s' "$(cd "${real_lib_dir}/.." && pwd)"
}

# 初始化并导出 PROJECT_ROOT 变量
if [ -z "$PROJECT_ROOT" ]; then
    PROJECT_ROOT="$(get_project_root)"
    export PROJECT_ROOT
fi
