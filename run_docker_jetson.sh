#!/bin/bash

CONTAINER_NAME="mid360-orin-dev"

COLOR_INFO=$'\033[0;32m'
COLOR_WARN=$'\033[0;33m'
COLOR_ERROR=$'\033[0;31m'
COLOR_RESET=$'\033[0m'

log_info()  { echo -e "${COLOR_INFO}[INFO]  $(date '+%H:%M:%S') [DOCKER] $1${COLOR_RESET}"; }
log_warn()  { echo -e "${COLOR_WARN}[WARN]  $(date '+%H:%M:%S') [DOCKER] $1${COLOR_RESET}"; }
log_error() { echo -e "${COLOR_ERROR}[ERROR] $(date '+%H:%M:%S') [DOCKER] $1${COLOR_RESET}"; }

log_info "正在配置宿主机显示权限 (xhost)..."
export DISPLAY=:0
xhost +local:root > /dev/null 2>&1

log_info "正在校验容器 [${CONTAINER_NAME}] 状态..."

# 检查容器是否存在
if ! docker ps -a --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}\$"; then
    log_error "未找到目标容器 [${CONTAINER_NAME}]。请确认镜像或容器构建状态。"
    exit 1
else
    # 检查容器是否处于运行状态
    if ! docker ps --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}\$"; then
        log_warn "容器处于停止状态，正在拉起容器..."
        docker start "${CONTAINER_NAME}" > /dev/null
    else
        log_info "容器已在运行状态。"
    fi
fi

log_info "正在接入容器交互终端..."
docker exec -it "${CONTAINER_NAME}" /bin/bash