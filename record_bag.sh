#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/install/setup.bash"

COLOR_INFO=$'\033[0;32m'
COLOR_PROMPT=$'\033[0;36m'
COLOR_RESET=$'\033[0m'

log_info() { echo -e "${COLOR_INFO}[INFO]  $(date '+%H:%M:%S') [RECORD] $1${COLOR_RESET}"; }

CURRENT_TIME=$(date +"%Y_%m_%d-%H_%M_%S")
BAG_DIR="${SCRIPT_DIR}/bags/scan_${CURRENT_TIME}"

echo -e "${COLOR_PROMPT}======================================================${COLOR_RESET}"
log_info "ROS 2 数据记录节点启动"
echo -e "  - 存储路径: ${BAG_DIR}"
echo -e "  - 记录话题: /livox/lidar, /livox/imu"
echo -e "  - 终止录制: 按 Ctrl + C"
echo -e "${COLOR_PROMPT}======================================================${COLOR_RESET}"

ros2 bag record -o "${BAG_DIR}" /livox/lidar /livox/imu