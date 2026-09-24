FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=en_US.UTF-8

# 1. 替换为中科大 Ubuntu 源，配置语言环境并拉取 ROS 2 密钥
RUN sed -i 's|archive.ubuntu.com|mirrors.ustc.edu.cn|g; s|security.ubuntu.com|mirrors.ustc.edu.cn|g' /etc/apt/sources.list \
    && apt-get update && apt-get install -y --no-install-recommends \
       locales curl ca-certificates gnupg2 \
    && locale-gen en_US en_US.UTF-8 \
    && curl -sSL https://mirrors.ustc.edu.cn/rosdistro/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] https://mirrors.ustc.edu.cn/ros2/ubuntu jammy main" > /etc/apt/sources.list.d/ros2.list \
    && rm -rf /var/lib/apt/lists/*

# 2. 安装基础编译工具、网络调试工具、PCL点云库与 ROS 2 完整桌面版
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git gdb \
    net-tools iputils-ping \
    libpcl-dev \
    ros-humble-desktop \
    ros-humble-pcl-conversions \
    ros-humble-pcl-ros \
    python3-colcon-common-extensions \
    && rm -rf /var/lib/apt/lists/*

# 3. 注入 ROS 2 环境变量
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc

WORKDIR /workspace