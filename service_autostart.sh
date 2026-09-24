#!/bin/bash

SESSION_NAME="mid360_tmux"
CONTAINER_NAME="mid360-orin-dev"

COLOR_INFO=$'\033[0;32m'
COLOR_WARN=$'\033[0;33m'
COLOR_ERROR=$'\033[0;31m'
COLOR_PROMPT=$'\033[0;36m'
COLOR_RESET=$'\033[0m'

log_info()  { echo -e "${COLOR_INFO}[INFO]  $(date '+%H:%M:%S') [TMUX] $1${COLOR_RESET}"; }
log_warn()  { echo -e "${COLOR_WARN}[WARN]  $(date '+%H:%M:%S') [TMUX] $1${COLOR_RESET}"; }
log_error() { echo -e "${COLOR_ERROR}[ERROR] $(date '+%H:%M:%S') [TMUX] $1${COLOR_RESET}"; }

log_info "正在初始化宿主机环境与显示权限..."
export DISPLAY=:0
xhost +local:root > /dev/null 2>&1

# 检查容器是否存在
if ! docker ps -a --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}\$"; then
    log_error "未找到容器 [${CONTAINER_NAME}]，无法启动托管服务。"
    exit 1 
fi

# 检查并启动容器
if ! docker ps --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}\$"; then
    log_warn "容器处于休眠状态，正在拉起容器..."
    docker start "${CONTAINER_NAME}" > /dev/null
    
    WAIT_TIME=0
    log_info "等待 Docker 守护进程状态同步..."
    while ! docker ps --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}\$"; do
        sleep 1
        WAIT_TIME=$((WAIT_TIME+1))
        if [ $WAIT_TIME -ge 10 ]; then
            log_error "容器状态切换超时 (10s)。"
            exit 1
        fi
    done
    log_info "容器状态确认: Up。"
fi

log_info "正在创建 Tmux 会话: ${SESSION_NAME}..."
tmux has-session -t "$SESSION_NAME" 2>/dev/null && tmux kill-session -t "$SESSION_NAME"

tmux new-session -d -s "$SESSION_NAME"
tmux split-window -h -t "$SESSION_NAME:0.0"

log_info "正在向会话窗格注入启动命令..."
# Pane 0.0: 定位系统
tmux send-keys -t "$SESSION_NAME:0.0" "docker exec -it ${CONTAINER_NAME} bash -c './run_localization.sh'" C-m

# Pane 0.1: 串口驱动节点
tmux send-keys -t "$SESSION_NAME:0.1" "docker exec -it ${CONTAINER_NAME} bash -c 'source /opt/ros/humble/setup.bash && source install/setup.bash && python3 src/gpio_uart.py'" C-m

echo -e "${COLOR_PROMPT}======================================================${COLOR_RESET}"
log_info "后台服务启动完成。接入监控终端请执行:"
echo -e "  tmux a -t ${SESSION_NAME}"
echo -e "${COLOR_PROMPT}======================================================${COLOR_RESET}"