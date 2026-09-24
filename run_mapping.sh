#!/bin/bash

# 1. 刷新全局环境变量
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/install/setup.bash"

# 定义标准终端输出颜色与日志层级
COLOR_INFO=$'\033[0;32m'
COLOR_WARN=$'\033[0;33m'
COLOR_ERROR=$'\033[0;31m'
COLOR_PROMPT=$'\033[0;36m'
COLOR_RESET=$'\033[0m'

# 封装日志打印函数，标准化输出格式
log_info()  { echo -e "${COLOR_INFO}[INFO]  $(date '+%H:%M:%S') [MAPPING] $1${COLOR_RESET}"; }
log_warn()  { echo -e "${COLOR_WARN}[WARN]  $(date '+%H:%M:%S') [MAPPING] $1${COLOR_RESET}"; }
log_error() { echo -e "${COLOR_ERROR}[ERROR] $(date '+%H:%M:%S') [MAPPING] $1${COLOR_RESET}"; }

# 2. 核心进程启动
log_info "正在初始化 FAST-LIO2 前端里程计节点..."
ros2 launch fastlio2 lio_launch.py > /dev/null 2>&1 &
PID_LIO=$!
sleep 2

log_info "正在加载 PGO 后端图优化节点..."
ros2 launch pgo pgo_launch.py > /dev/null 2>&1 &
PID_PGO=$!
sleep 2

echo -e "${COLOR_PROMPT}======================================================${COLOR_RESET}"
log_info "建图系统已就绪。可用控制指令:"
echo -e "  [s] 保存点云地图"
echo -e "  [q] 终止全部进程并退出"
echo -e "${COLOR_PROMPT}======================================================${COLOR_RESET}"

# 3. 监听终端输入与系统状态
while true; do
    read -p "${COLOR_PROMPT}>> [s/q]: ${COLOR_RESET}" USER_INPUT
    
    if [ "$USER_INPUT" == "s" ]; then
        SAVE_PATH="${SCRIPT_DIR}/"
        log_info "正在请求服务 /pgo/save_maps 保存地图..."
        
        # 执行服务调用，隐藏非必要标准输出，保留标准错误
        ros2 service call /pgo/save_maps interface/srv/SaveMaps "{file_path: '$SAVE_PATH', save_patches: true}" > /dev/null 2>&1
        
        # 捕获系统调用返回码以验证执行状态
        if [ $? -eq 0 ]; then
            log_info "点云地图已成功保存至: $SAVE_PATH"
        else
            log_error "服务调用失败，请检查 PGO 节点运行状态与话题通信拓扑。"
        fi
        
    elif [ "$USER_INPUT" == "q" ]; then
        log_warn "接收到退出指令，正在终止建图进程..."
        kill $PID_LIDAR $PID_LIO $PID_PGO 2>/dev/null
        log_info "进程已清理，系统安全退出。"
        break
    else
        log_warn "未知指令: '$USER_INPUT'。键入 's' 保存地图，或 'q' 退出系统。"
    fi
done