# 工作流与实操指南

本文档整理了本项目从底层雷达通信到上层应用的工作流和实操指南以及一些常见问题的解决方案，旨在帮助开发者快速上手和高效开发。

## 常用脚本

这里会讲解根目录中的脚本的使用方法。

### [rebuild.sh](../rebuild.sh)

用于编译当前 ROS 2 工作空间，并在编译成功后加载 `install/setup.bash`。

#### 用法

```bash
source ./rebuild.sh
```

脚本执行 `colcon build` 增量编译。编译失败时返回错误码并停止；编译成功后执行 `source install/setup.bash`。

> 如果希望脚本中的环境变量影响当前终端，建议使用 `source rebuild.sh`。直接执行 `bash rebuild.sh` 时，环境变量只在脚本进程中生效。

### [start_mid360.sh](../start_mid360.sh)

用于启动 Livox MID-360 雷达驱动。

#### 用法

```bash
./start_mid360.sh
```

脚本会依次加载 ROS 2 Humble 和当前工作空间环境，然后启动：

- Launch 文件：`livox_ros_driver2/msg_MID360_launch.py`
- 点云话题：`/livox/lidar`
- IMU 话题：`/livox/imu`

如果找不到 `install/setup.bash`，需要先执行 `rebuild.sh`。该脚本使用 `exec` 启动 ROS 2 节点，退出驱动时直接按 `Ctrl + C`。

### [run_fastlio2.sh](../run_fastlio2.sh)

用于同时启动 MID-360 驱动和 FAST-LIO2 前端里程计。

#### 用法

```bash
./run_fastlio2.sh
```

启动流程如下：

1. 后台启动 `start_mid360.sh`。
2. 等待 2 秒。
3. 启动 `fastlio2/lio_launch.py`。
4. 等待终端输入 `q`，然后终止记录的驱动和 FAST-LIO2 进程。

该脚本要求工作空间已经编译，并且 `fastlio2` 包中存在 `lio_launch.py`。

### [run_pointlio.sh](../run_pointlio.sh)

用于同时启动 MID-360 驱动和 Point-LIO 前端里程计。

#### 用法

```bash
./run_pointlio.sh
```

脚本启动 `start_mid360.sh` 后等待 2 秒，再启动 Point-LIO 的 `point_lio/mapping_mid360.launch.py`。运行过程中输入 `q` 会终止记录的雷达驱动和 Point-LIO 进程。

### [run_mapping.sh](../run_mapping.sh)

用于启动 FAST-LIO2 前端和 PGO 后端，执行在线建图并保存点云地图。

#### 用法

```bash
./run_mapping.sh
```

启动流程如下：

1. 后台启动 `fastlio2/lio_launch.py`。
2. 等待 2 秒。
3. 后台启动 `pgo/pgo_launch.py`。
4. 输入 `s` 调用 `/pgo/save_maps` 服务，将地图保存到工作空间根目录。
5. 输入 `q` 终止建图进程并退出。

保存地图使用的服务请求为：

```text
/pgo/save_maps
interface/srv/SaveMaps
file_path: <工作空间根目录>/
save_patches: true
```

注意：当前脚本没有启动 `start_mid360.sh`，因此运行前必须确认 MID-360 驱动已经在其他终端运行。退出分支中使用了未定义的 `PID_LIDAR`，该变量不会对应有效的雷达进程；如需完整清理雷达进程，应先单独停止驱动，或在脚本中补充驱动启动和 PID 管理。

### [run_localization.sh](../run_localization.sh)

用于启动全局定位系统，支持 Point-LIO 和 FAST-LIO2 两种前端，并可从终端发布初始位姿。

#### 用法

```bash
# 默认使用 Point-LIO，不自动注入初始位姿
./run_localization.sh

# 使用 FAST-LIO2，不自动注入初始位姿
./run_localization.sh fastlio2

# 使用 Point-LIO，启动 5 秒后自动注入原点
./run_localization.sh pointlio true
```

参数说明：

| 参数 | 可选值 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `frontend` | `pointlio`、`fastlio2` | `pointlio` | 选择定位前端 |
| `auto_zero_inject` | `true`、`false` | `false` | 是否在启动 5 秒后发布 `(0, 0, 0)` 初始位姿 |

对应的定位 Launch 文件为：

- Point-LIO：`localizer/localizer_pointlio.py`
- FAST-LIO2：`localizer/localizer_fastlio2.py`

启动后可在终端输入以下格式发布初始位姿：

```text
X(cm) Y(cm) Yaw(deg)
```

例如：

```text
60 180 176
```

脚本会将厘米转换为米，将偏航角转换为四元数，并发布到 `/initialpose`，坐标系为 `map`。也可以在 RViz2 中使用 `2D Pose Estimate` 设置初始位姿。按 `Ctrl + C` 会终止定位进程和雷达驱动。

### [record_bag.sh](../record_bag.sh)

用于记录 MID-360 的点云和 IMU 数据，生成 ROS 2 bag 文件。

#### 用法

```bash
./record_bag.sh
```

数据默认保存到：

```text
bags/scan_YYYY_MM_DD-HH_MM_SS/
```

脚本记录以下话题：

- `/livox/lidar`
- `/livox/imu`

开始录制前应确认雷达驱动已经运行。按 `Ctrl + C` 停止录制；录制完成后，目录中会生成 `metadata.yaml` 和对应的数据库文件。

### [run_docker_jetson.sh](../run_docker_jetson.sh)

用于启动或连接 Jetson 上的 Docker 容器，并进入容器交互终端。

#### 用法

```bash
./run_docker_jetson.sh
```

脚本固定使用容器名 `mid360-orin-dev`，执行流程如下：

1. 设置 `DISPLAY=:0`，并执行 `xhost +local:root`。
2. 检查目标容器是否存在。
3. 如果容器未运行，执行 `docker start mid360-orin-dev`。
4. 执行 `docker exec -it mid360-orin-dev /bin/bash` 进入容器。

如果容器不存在，脚本会直接退出。容器内部的 ROS 2 命令需要另外加载 `/opt/ros/humble/setup.bash` 和工作空间的 `install/setup.bash`。

### [service_autostart.sh](../service_autostart.sh)

用于通过 Docker 和 tmux 自动启动定位服务及串口节点，适合开机后或远程场景下托管运行。

#### 用法

```bash
./service_autostart.sh
```

脚本固定使用：

- tmux 会话：`mid360_tmux`
- Docker 容器：`mid360-orin-dev`
- 窗格 0.0：执行容器内的 `./run_localization.sh`
- 窗格 0.1：加载 ROS 2 和工作空间环境，然后执行 `python3 src/gpio_uart.py`

脚本会先检查并启动容器，再创建一个水平分屏的 tmux 会话。启动完成后，可使用以下命令接入监控：

```bash
tmux a -t mid360_tmux
```

如果已有同名 tmux 会话，脚本会先将其删除再重新创建。运行前需要确保 Docker、tmux、`xhost` 可用，并且容器内工作空间路径与脚本中的相对路径一致。

## 串口输出节点

以下 Python 节点负责读取 ROS 2 中的位姿数据，经过厘米和角度单位转换、可选的卡尔曼滤波以及 CRC-8 校验后，通过串口发送如下格式的数据：

```text
[x_cm;y_cm;z_cm;yaw_deg]CRC\r\n
```

运行前需要先加载 ROS 2 Humble 和当前工作空间环境，并确保已安装 `pyserial`。三个节点应根据位姿来源和硬件平台选择其中一个运行，避免多个节点同时向同一串口发送数据。

### [src/odom_to_serial.py](../src/odom_to_serial.py)

用于直接订阅里程计话题并将位姿发送到自动发现的 USB 转串口设备。

#### 用法

```bash
python3 src/odom_to_serial.py
```

节点同时监听以下话题：

- `/fastlio2/lio_odom`
- `/aft_mapped_to_init`

串口设备通过 VID/PID 自动识别，当前支持 CH340、CP210X 和 FTDI，波特率为 `115200`。收到任一话题消息后，节点会提取位置和 yaw 角，使用自适应卡尔曼滤波处理，再立即发送串口数据。未检测到设备时会持续扫描，串口断开后也会自动尝试重连。

### [src/tf_to_serial.py](../src/tf_to_serial.py)

用于查询 TF 树中的 `map -> body` 变换，并将最新位姿发送到自动发现的 USB 转串口设备。

#### 用法

```bash
python3 src/tf_to_serial.py
```

节点以 `100 Hz` 定时查询 TF，并通过时间戳跳过重复变换。默认启用卡尔曼滤波和自适应参数调整，并支持通过 `SRC_X_CM`、`SRC_Y_CM`、`DST_X_CM`、`DST_Y_CM` 配置 XY 坐标偏移。串口设备通过 VID/PID 自动识别，波特率为 `115200`。

适合系统已经发布稳定 TF 位姿、但没有合适 Odometry 话题可直接订阅的场景。

### [src/tf_to_uart_jetson.py](../src/tf_to_uart_jetson.py)

用于 Jetson 平台，通过固定硬件 UART 将 `map -> body` TF 位姿发送给下游控制器。

#### 用法

```bash
python3 src/tf_to_uart_jetson.py
```

脚本默认使用 `/dev/ttyTHS1` 和 `115200` 波特率，启动时会直接打开该设备；如硬件接口不同，需要修改脚本顶部的 `UART_PORT` 和 `BAUD_RATE`。它同样以 `100 Hz` 查询 TF、默认启用卡尔曼滤波和 XY 坐标偏移，并使用独立线程处理终端打印，减少串口发送受到日志输出阻塞的影响。

## 推荐工作流

### 首次编译

```bash
source ./rebuild.sh
```

### 启动驱动

```bash
./start_mid360.sh
```

### 记录数据

在另一个终端执行：

```bash
./record_bag.sh
```

### 在线运行

根据任务选择以下入口：

```bash
./run_fastlio2.sh       # FAST-LIO2 前端
./run_pointlio.sh       # Point-LIO 前端
./run_mapping.sh        # FAST-LIO2 + PGO 建图
./run_localization.sh   # 全局定位
```

### 离线精细化建图与部署

推荐按照“设备录制、PC 精细化建图、设备端定位、串口输出”的顺序执行：

#### 1. 录制数据

在设备端启动 MID-360 驱动，并使用 `record_bag.sh` 录制点云和 IMU 数据。录制完成后按 `Ctrl + C` 停止记录。

#### 2. 拷贝到本地

使用 `scp` 将生成的 bag 目录传输到本地建图工作空间。

#### 3. 本地精细化建图

本地建图需要两个终端，分别运行 `run_mapping.sh` 和数据包回放。终端一启动建图流程：

```bash
./run_mapping.sh
```

终端二播放已拷贝到本地的 bag：

```bash
ros2 bag play <本地工作空间>/bags/scan_YYYY_MM_DD-HH_MM_SS/
```

建图过程中输入 `s` 保存地图，并记录地图实际输出目录和文件名。`run_mapping.sh` 默认将地图保存到工作空间根目录，具体位置以终端输出和 PGO 配置为准。

#### 4. 回传地图

建图完成后，使用 `scp` 将生成的地图文件或地图目录传回设备对应路径。

#### 5. 启动定位

在设备端启动定位。默认使用 Point-LIO，也可以指定 FAST-LIO2：

```bash
./run_localization.sh
./run_localization.sh fastlio2
```

#### 6. 启动串口发送

确认定位系统已经发布 Odometry 或 `map -> body` TF 后，再选择一个串口节点发送位姿：

```bash
python3 src/odom_to_serial.py       # 订阅 Odometry
python3 src/tf_to_serial.py         # 读取 map -> body TF
python3 src/tf_to_uart_jetson.py    # Jetson 固定硬件 UART
```

三个节点只应选择一个运行。启动前确认串口设备、波特率和下游控制器的数据格式配置正确。

## 常见检查

查看当前 ROS 2 话题：

```bash
ros2 topic list
```

查看点云和 IMU 是否发布：

```bash
ros2 topic hz /livox/lidar
ros2 topic hz /livox/imu
```

查看定位服务是否存在：

```bash
ros2 service list | grep pgo
```

如果脚本提示找不到工作空间环境，先确认以下文件存在：

```text
source ./rebuild.sh
```