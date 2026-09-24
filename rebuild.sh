#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 定义标准输出颜色
COLOR_INFO=$'\033[0;32m'
COLOR_ERROR=$'\033[0;31m'
COLOR_RESET=$'\033[0m'

log_info()  { echo -e "${COLOR_INFO}[INFO]  $(date '+%H:%M:%S') [BUILD] $1${COLOR_RESET}"; }
log_error() { echo -e "${COLOR_ERROR}[ERROR] $(date '+%H:%M:%S') [BUILD] $1${COLOR_RESET}"; }

log_info "正在切换至工作空间根目录..."
cd "${SCRIPT_DIR}" || { log_error "找不到工作空间目录 ${SCRIPT_DIR}"; return 1 2>/dev/null || exit 1; }

log_info "开始执行增量编译 (colcon build)..."
colcon build

if [ $? -ne 0 ]; then
    log_error "编译失败，请检查上方编译器报错输出。"
    return 1 2>/dev/null || exit 1
fi

log_info "正在刷新当前终端工作空间环境变量..."
source "${SCRIPT_DIR}/install/setup.bash"

log_info "工作空间编译与环境配置完成，新配置已生效。"