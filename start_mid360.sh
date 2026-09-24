#!/bin/bash

# 定义标准输出颜色
COLOR_INFO=$'\033[0;32m'
COLOR_ERROR=$'\033[0;31m'
COLOR_RESET=$'\033[0m'

log_info()  { echo -e "${COLOR_INFO}[INFO]  $(date '+%H:%M:%S') [DRIVER] $1${COLOR_RESET}"; }
log_error() { echo -e "${COLOR_ERROR}[ERROR] $(date '+%H:%M:%S') [DRIVER] $1${COLOR_RESET}"; }

# 1. 动态锚定工作空间路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 2. 加载底层系统与工作空间环境
source /opt/ros/humble/setup.bash 2>/dev/null || true

if [ -f "${SCRIPT_DIR}/install/setup.bash" ]; then
    source "${SCRIPT_DIR}/install/setup.bash"
else
    log_error "未找到 install/setup.bash，请先编译工作空间。"
    exit 1
fi

# 3. 驱动初始化日志
log_info "正在启动 Livox MID-360 核心驱动 (launch: msg_MID360_launch.py)..."
log_info "数据输出配置: /livox/lidar (PointCloud2), /livox/imu (Imu)"

# 4. 执行启动
exec ros2 launch livox_ros_driver2 msg_MID360_launch.py