#!/bin/bash

# ==============================================================================
# LIVOX-MID-360 全局定位统一启动入口
#
# 调用格式:
#   ./run_localization.sh [frontend] [auto_zero_inject]
#
# 参数说明:
#   frontend:         前端类型，严格校验 pointlio（默认）或 fastlio2
#   auto_zero_inject: 是否在启动5秒后自动注入(0,0,0)原点，可选 true 或 false（默认）
#
# 示例:
#   ./run_localization.sh                      # 默认 Point-LIO，不自动注入原点
#   ./run_localization.sh fastlio2             # 使用 FAST-LIO2，手动输入位姿
#   ./run_localization.sh pointlio true        # Point-LIO，且5秒后自动注入 (0,0,0)
# ==============================================================================

# 1. 动态锚定当前脚本物理目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}" || exit 1

# 日志输出函数
COLOR_INFO=$'\033[0;32m'
COLOR_WARN=$'\033[0;33m'
COLOR_ERROR=$'\033[0;31m'
COLOR_PROMPT=$'\033[0;36m'
COLOR_RESET=$'\033[0m'

log_info()  { echo -e "${COLOR_INFO}[INFO]  $(date '+%H:%M:%S') [LOCALIZATION] $1${COLOR_RESET}"; }
log_warn()  { echo -e "${COLOR_WARN}[WARN]  $(date '+%H:%M:%S') [LOCALIZATION] $1${COLOR_RESET}"; }
log_error() { echo -e "${COLOR_ERROR}[ERROR] $(date '+%H:%M:%S') [LOCALIZATION] $1${COLOR_RESET}"; }

# 2. 严谨加载底层 ROS 2 与工作空间环境
source /opt/ros/humble/setup.bash 2>/dev/null || true

if [ -f "${SCRIPT_DIR}/install/setup.bash" ]; then
    source "${SCRIPT_DIR}/install/setup.bash"
else
    log_error "找不到 ROS 2 工作空间环境 (install/setup.bash)，请先执行编译！"
    exit 1
fi

# 3. 显式校验前端参数
FRONTEND="${1:-pointlio}"
AUTO_INJECT="${2:-false}"

case "$FRONTEND" in
    pointlio)
        LAUNCH_FILE="localizer_pointlio.py"
        log_info "定位前端选择: Point-LIO (${LAUNCH_FILE})"
        ;;
    fastlio2)
        LAUNCH_FILE="localizer_fastlio2.py"
        log_info "定位前端选择: FAST-LIO2 (${LAUNCH_FILE})"
        ;;
    *)
        log_error "未知前端类型: '$FRONTEND'。可选值: [pointlio | fastlio2]"
        exit 2
        ;;
esac

# 4. 启动雷达驱动
log_info "启动 MID-360 雷达驱动..."
bash "${SCRIPT_DIR}/start_mid360.sh" &
PID_LIDAR=$!
sleep 2

# 5. 启动定位节点与前端
log_info "启动 Localizer 定位模块: ${LAUNCH_FILE}..."
ros2 launch localizer "$LAUNCH_FILE" &
PID_LOC=$!

# 6. 位姿发布核心函数 (cm/deg 换算为 m/四元数)
publish_initial_pose() {
    local input_x_cm="$1"
    local input_y_cm="$2"
    local input_yaw="$3"

    local x_m y_m qz qw
    x_m=$(awk -v x="$input_x_cm" 'BEGIN {printf "%.4f", x / 100.0}')
    y_m=$(awk -v y="$input_y_cm" 'BEGIN {printf "%.4f", y / 100.0}')

    qz=$(awk -v yaw="$input_yaw" 'BEGIN {print sin(yaw * 3.14159265 / 360)}')
    qw=$(awk -v yaw="$input_yaw" 'BEGIN {print cos(yaw * 3.14159265 / 360)}')

    log_info "向 /initialpose 注入位姿 -> X: ${x_m}m, Y: ${y_m}m, Yaw: ${input_yaw}°"

    ros2 topic pub -1 /initialpose geometry_msgs/msg/PoseWithCovarianceStamped \
    "{header: {frame_id: 'map'}, pose: {pose: {position: {x: $x_m, y: $y_m, z: 0.0}, orientation: {x: 0.0, y: 0.0, z: $qz, w: $qw}}}}" \
    > /dev/null 2>&1 &
}

# 7. 进程清理
cleanup() {
    echo -e "\n"
    trap - SIGINT SIGTERM EXIT
    log_warn "捕获退出信号，正在终止雷达驱动与定位模块..."
    kill $PID_LIDAR $PID_LOC 2>/dev/null
    log_info "定位系统安全退出。"
    exit 0
}
trap cleanup SIGINT SIGTERM

# 8. 条件执行自动原点注入
if [ "$AUTO_INJECT" == "true" ]; then
    AUTO_INJECT_DELAY=5
    log_warn "已开启自动注入：系统将在 ${AUTO_INJECT_DELAY} 秒后注入默认位姿 (0, 0, 0)..."
    sleep "$AUTO_INJECT_DELAY"
    publish_initial_pose 0 0 0
else
    log_info "已跳过自动原点注入，等待终端输入或 RViz 标定。"
fi

echo -e "${COLOR_PROMPT}======================================================${COLOR_RESET}"
log_info "定位系统已就绪！"
echo -e "  [INPUT] 终端输入: 格式 [X(cm) Y(cm) Yaw(deg)] (示例: 60 180 176)"
echo -e "  [INPUT] 界面标定: 前往 RViz2 点击顶栏 '2D Pose Estimate'"
echo -e "  [INPUT] 安全退出: 按 Ctrl + C (仅退出驱动与定位进程)"
echo -e "${COLOR_PROMPT}======================================================${COLOR_RESET}"

# 9. 监听终端输入
while read -p "${COLOR_PROMPT}>> [X Y Yaw]: ${COLOR_RESET}" INPUT_X_CM INPUT_Y_CM INPUT_YAW; do
    if [[ "$INPUT_X_CM" =~ ^-?[0-9]+(\.[0-9]+)?$ ]] && \
       [[ "$INPUT_Y_CM" =~ ^-?[0-9]+(\.[0-9]+)?$ ]] && \
       [[ "$INPUT_YAW" =~ ^-?[0-9]+(\.[0-9]+)?$ ]]; then
        publish_initial_pose "$INPUT_X_CM" "$INPUT_Y_CM" "$INPUT_YAW"
    else
        if [ -n "$INPUT_X_CM" ]; then
            log_error "输入格式错误！必须提供三个有效数值，示例: 60 180 176"
        fi
    fi
done

# EOF 触发退出
cleanup