#!/bin/bash

# 1. 刷新全局环境变量
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/install/setup.bash"

# 定义标准输出颜色
COLOR_INFO=$'\033[0;32m'
COLOR_WARN=$'\033[0;33m'
COLOR_PROMPT=$'\033[0;36m'
COLOR_RESET=$'\033[0m'

log_info() { echo -e "${COLOR_INFO}[INFO]  $(date '+%H:%M:%S') [POINT-LIO] $1${COLOR_RESET}"; }
log_warn() { echo -e "${COLOR_WARN}[WARN]  $(date '+%H:%M:%S') [POINT-LIO] $1${COLOR_RESET}"; }

log_info "正在启动 MID-360 雷达驱动..."
bash "${SCRIPT_DIR}/start_mid360.sh" &
PID_LIDAR=$!

# 等待2秒，确保雷达驱动和 TF 树基础准备完毕
sleep 2

log_info "正在启动 Point-LIO 状态估计节点..."
# 注意：使用针对 MID-360 的专属 launch 文件
ros2 launch point_lio mapping_mid360.launch.py &
PID_LIO=$!

log_info "Point-LIO 系统已就绪。键入 'q' 安全终止所有节点。"

# 3. 监听键盘按键
while true; do
    read -p "${COLOR_PROMPT}>> [q]: ${COLOR_RESET}" USER_INPUT
    if [ "$USER_INPUT" == "q" ]; then
        log_warn "接收到终止信号，正在关闭关联进程..."
        
        kill $PID_LIDAR $PID_LIO
        
        log_info "所有进程已终止，系统安全退出。"
        break
    fi
done