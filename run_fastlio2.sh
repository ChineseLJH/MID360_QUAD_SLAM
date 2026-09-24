#!/bin/bash

# 1. 刷新全局环境变量
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/install/setup.bash"

# 定义标准输出颜色
COLOR_INFO=$'\033[0;32m'
COLOR_WARN=$'\033[0;33m'
COLOR_PROMPT=$'\033[0;36m'
COLOR_RESET=$'\033[0m'

log_info() { echo -e "${COLOR_INFO}[INFO]  $(date '+%H:%M:%S') [FAST-LIO2] $1${COLOR_RESET}"; }
log_warn() { echo -e "${COLOR_WARN}[WARN]  $(date '+%H:%M:%S') [FAST-LIO2] $1${COLOR_RESET}"; }

log_info "正在启动 MID-360 雷达驱动..."
bash "${SCRIPT_DIR}/start_mid360.sh" &
PID_LIDAR=$!

# 等待2秒，确保雷达驱动和 TF 树基础准备完毕
sleep 2

log_info "正在启动 FAST-LIO2 状态估计节点..."
# 注意：如果你的 FAST-LIO2 启动文件不叫 lio_launch.py，请将下面这行替换为实际的 launch 文件名
ros2 launch fastlio2 lio_launch.py &
PID_LIO=$!

log_info "FAST-LIO2 系统已就绪。键入 'q' 安全终止所有节点。"

# 3. 监听键盘按键
while true; do
    read -p "${COLOR_PROMPT}>> [q]: ${COLOR_RESET}" USER_INPUT
    if [ "$USER_INPUT" == "q" ]; then
        log_warn "接收到终止信号，正在关闭关联进程..."
        
        # 杀掉之前在后台运行的雷达和LIO进程
        kill $PID_LIDAR $PID_LIO
        
        log_info "所有进程已终止，系统安全退出。"
        break
    fi
done