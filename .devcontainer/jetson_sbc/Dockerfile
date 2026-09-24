FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=en_US.UTF-8

# 1. 替换 ARM64 中科大源、配置语言环境并注册 ROS 2 源
RUN sed -i 's/ports.ubuntu.com/mirrors.ustc.edu.cn/g; s/security.ubuntu.com/mirrors.ustc.edu.cn/g' /etc/apt/sources.list \
    && apt-get update && apt-get install -y --no-install-recommends \
       locales curl ca-certificates gnupg2 \
    && locale-gen en_US en_US.UTF-8 \
    && curl -sSL https://mirrors.ustc.edu.cn/rosdistro/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] https://mirrors.ustc.edu.cn/ros2/ubuntu jammy main" > /etc/apt/sources.list.d/ros2.list \
    && rm -rf /var/lib/apt/lists/*

# 2. 安装基础编译套件、抓包库、PCL与 ROS 2 完整桌面版
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git gdb \
    net-tools iputils-ping \
    libpcap-dev \
    libpcl-dev \
    ros-humble-desktop \
    ros-humble-pcl-conversions \
    ros-humble-pcl-ros \
    ros-humble-sensor-msgs-py \
    python3-colcon-common-extensions \
    && rm -rf /var/lib/apt/lists/*

# 3. 环境变量注入
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc

WORKDIR /workspaces/LIVOX-MID-360