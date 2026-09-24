# 参数调优指南

本指南介绍在四足机器人上使用 LIVOX-MID-360 时的参数调优方法。调参应优先使用实际录制的 rosbag 进行对比，单次只修改一组相关参数，并观察轨迹、姿态和点云匹配是否稳定。

## 一、里程计调参

里程计参数分为 FAST-LIO2 和 Point-LIO 两套配置。两者都依赖 `/livox/lidar` 与 `/livox/imu`，但协方差和置信度参数的含义不同，不能直接照搬数值。

### 1. FAST-LIO2

配置文件：[`src/lidar_slam_modules/fastlio2/config/lio.yaml`](../src/lidar_slam_modules/fastlio2/config/lio.yaml)

#### IMU 噪声与协方差

FAST-LIO2 通过以下参数描述 IMU 噪声和偏置随机游走：

| 参数 | 作用 | 调整方向 |
| --- | --- | --- |
| `na` | 加速度计噪声 | 实际加速度噪声较大时增大 |
| `ng` | 陀螺仪连续时间高斯白噪声 | 实际角速度噪声较大时增大 |
| `nb` | YAML 中的额外参数 | 当前源码未读取，修改不会生效 |
| `nba` | 加速度计偏置随机游走 | 偏置变化明显时增大 |
| `nbg` | 陀螺仪偏置随机游走 | 陀螺仪零偏变化明显时增大 |

当前 FAST-LIO2 源码实际将 `ng` 注入角速度噪声通道，将 `na` 注入加速度噪声通道，并将 `nbg`、`nba` 用于陀螺仪和加速度计偏置随机游走。虽然 `lio.yaml` 中存在 `nb`，但当前 `Config` 结构体和参数加载代码没有读取它，因此不要把 `nb` 当作当前版本中已生效的调参项。`na`、`ng`、`nba`、`nbg` 越大，表示越不信任对应的 IMU 预测或偏置模型，激光匹配对状态的修正作用相对增强；数值过大可能导致运动响应变差，数值过小则可能使 IMU 噪声过度影响轨迹。

#### 激光测量置信度

`lidar_cov_inv` 是激光测量协方差的倒数，用于控制激光匹配结果的置信度：

- 增大 `lidar_cov_inv`：提高对激光测量的信任，轨迹更容易跟随点云匹配结果。
- 减小 `lidar_cov_inv`：降低对激光测量的信任，IMU 预测占比提高。

如果环境中存在大量动态物体、稀疏点云或严重遮挡，不宜盲目增大该参数。`lidar_min_range`、`lidar_max_range`、`lidar_filter_num` 也会影响有效点数量，应先确认点云质量再调整置信度。

#### 建议调参顺序

1. 保持 `na`、`ng`、`nba`、`nbg` 为传感器标定或当前稳定值；忽略当前源码未使用的 `nb`。
2. 通过静止和缓慢运动数据确认 IMU 预测是否稳定。
3. 小步调整 `lidar_cov_inv`，比较激光匹配对轨迹的修正效果。
4. 最后再调整 `na`、`ng` 以及偏置随机游走参数，处理快速运动时的漂移或抖动。

### 2. Point-LIO

配置文件：[`src/lidar_slam_modules/point_lio_ros2/config/mid360.yaml`](../src/lidar_slam_modules/point_lio_ros2/config/mid360.yaml)

#### IMU 协方差与置信度

参数配置：[`src/lidar_slam_modules/point_lio_ros2/config/mid360.yaml`](../src/lidar_slam_modules/point_lio_ros2/config/mid360.yaml)

启动覆盖：[`src/lidar_slam_modules/point_lio_ros2/launch/mapping_mid360.launch.py`](../src/lidar_slam_modules/point_lio_ros2/launch/mapping_mid360.launch.py)

Point-LIO 有两种状态传递模式，由 `use_imu_as_input` 控制。当前 MID-360 launch 设置为 `false`，因此当前系统使用“以 IMU 为测量”模式：状态方程推演机器人运动，IMU 读数作为观测参考参与滤波更新，而不是直接作为输入进行位姿数值积分。这样可以降低四足机器人足端冲击直接污染位姿积分的风险。源码默认值为 `true`，切换其他 launch 或修改启动参数后，应重新确认实际模式。

#### 核心调参项：IMU 作为测量

当前模式下，重点调整观测协方差和激光测量参数。`acc_cov_input` 与 `gyr_cov_input` 属于 IMU 输入模式，在当前 `use_imu_as_input: false` 时不作为当前解算路径的重点参数，不应与测量模式参数混合调整：

| 参数 | 当前值 | 调整方向 |
| --- | ---: | --- |
| `imu_meas_acc_cov` | `0.01` | 增大可降低对加速度读数的信任，抑制踏地冲击导致的姿态倾斜和高度跳变；过大可能使加减速响应变迟缓。 |
| `imu_meas_omg_cov` | `0.01` | 增大可降低对角速度毛刺的信任，平抑机身扭转冲击；过大可能增加偏航角收敛滞后。 |
| `lidar_meas_cov` | `0.01` | 减小可提高点云匹配权重，使位姿更多依靠环境几何修正；环境退化或动态障碍物较多时不宜盲目减小。 |
| `acc_cov_output` | `500.0` | 当前量级可作为起始值；调整时结合加速度响应和姿态稳定性验证。 |
| `gyr_cov_output` | `1000.0` | 当前量级可作为起始值；调整时结合角速度响应和偏航稳定性验证。 |

协方差越小，表示越信任对应的模型或观测；协方差越大，表示越不信任。四足机器人上应逐步增大 `imu_meas_acc_cov`，观察系统鲁棒性与精确度。

`lidar_meas_cov` 控制激光测量协方差，也会影响点云约束的置信度：减小它会提高对激光测量的信任，增大它会降低激光测量的影响。若点云存在噪声、遮挡或动态目标，应谨慎降低该值。

#### IMU 饱和截止保护

当前 Point-LIO 配置没有独立的 IMU 低通截止频率参数。所谓 IMU“截止”由以下饱和阈值实现：

| 参数 | 当前值 | 作用 |
| --- | ---: | --- |
| `satu_acc` | `3.5` | 加速度饱和阈值 |
| `satu_gyro` | `34.5` | 角速度饱和阈值 |

当 IMU 数据达到约 `0.99` 倍阈值时，Point-LIO 会将对应的 IMU 观测残差置零，等效于暂时忽略该异常观测，避免冲击或超量程数据破坏状态估计。阈值过小会误判正常的快速运动，阈值过大则可能放过传感器异常值，因此应参考 IMU 的量程和实际运动峰值设置。

## 二、驱动调参

驱动启动配置文件：[`src/livox_ros_driver2/launch_ROS2/msg_MID360_launch.py`](../src/livox_ros_driver2/launch_ROS2/msg_MID360_launch.py)

### MID-360 发布频率

驱动发布频率由 `publish_freq` 控制，当前配置为 `25.0` Hz：

```python
publish_freq = 25.0
```

#### 单包计算削峰与单核负载

MID-360 硬件的采样率由设备决定，单位时间内产生的激光点总量基本不因 `publish_freq` 改变。`publish_freq` 的作用主要是将连续数据按不同时间窗口切片打包后发布：

- `10 Hz`：时间窗口约为 `100 ms`，单包约 `20,000` 点。
- `25 Hz`：时间窗口约为 `40 ms`，单包约 `8,000` 点。

上述点数是基于当前雷达数据量的近似值，实际数量会受设备配置、网络传输和驱动数据格式影响。10 Hz 下单包点数较多，FAST-LIO2 和 Point-LIO 的点云预处理、近邻搜索及优化会在较短时间内集中执行，单核可能出现瞬时满载，导致处理延迟。提高到 25 Hz 后，单位时间总点数基本不变，但单次处理的数据量减少，计算负载更均匀，有利于降低单包处理峰值。

因此，`publish_freq` 提高并不等于降低总计算量，而是将总负载分散到更多、更小的数据包中。最终仍需通过 `ros2 topic hz`、节点处理延迟和 CPU 使用率验证实际效果。

#### 与点云下采样的配合

发布频率提高后，每个点云切片的点数减少。如果下采样比例保持不变，单次优化参与的有效点数也会减少，可能削弱点云几何约束。应根据实际点数和 CPU 负载同步调整下采样参数。

##### FAST-LIO2

FAST-LIO2 使用 [`lio.yaml`](../src/lidar_slam_modules/fastlio2/config/lio.yaml) 中的 `lidar_filter_num` 对输入点云进行等间隔抽取：

| 参数 | 当前值 | 含义 |
| --- | ---: | --- |
| `lidar_filter_num` | `3` | 每隔 3 个输入点保留 1 个点 |

如果从 10 Hz 切换到 25 Hz，建议不要继续使用过大的过滤步长。当前 `3` 相比每 6 点保留 1 点能保留更多有效点，可作为 MID-360 的起始配置；若点云约束不足，可继续减小该值，若单核负载过高则适当增大，并结合轨迹稳定性验证。

##### Point-LIO

Point-LIO 的 MID-360 launch 在 [`mapping_mid360.launch.py`](../src/lidar_slam_modules/point_lio_ros2/launch/mapping_mid360.launch.py) 中设置了以下下采样参数：

| 参数 | 当前值 | 作用 |
| --- | ---: | --- |
| `point_filter_num` | `3` | 输入点云预处理时每隔 3 个点保留 1 个点 |
| `space_down_sample` | `true` | 开启地图点的空间体素下采样 |
| `filter_size_surf` | `0.1` | 点云表面特征的体素尺寸，单位为米 |
| `filter_size_map` | `0.1` | 地图点空间下采样的体素尺寸，单位为米 |

其中，`point_filter_num` 直接影响单帧参与匹配的点数；数值越小，保留点越多、几何约束越强，但 CPU 和内存负载越高。`filter_size_surf` 和 `filter_size_map` 影响空间体素下采样，数值越小也会保留更多空间细节。建议先保持 `space_down_sample: true`，优先小步调整 `point_filter_num`；只有确认地图点过度稀疏时，再减小体素尺寸。若 CPU 瞬时负载过高，则反向增大过滤步长或体素尺寸。

FAST-LIO2 的 `lidar_filter_num` 和 Point-LIO 的 `point_filter_num` 彼此独立，切换里程计时需要分别确认，不能只修改其中一个。

调整原则如下：

- 提高 `publish_freq`：单位时间内发布更多 LiDAR 数据，运动细节和匹配更新更密集，但 CPU、网络和点云处理负载会增加。
- 降低 `publish_freq`：降低系统负载，但快速运动时可能减少有效匹配，增加轨迹离散感。
- 发布频率应与 Point-LIO 的 `imu_time_inte`、FAST-LIO2 的处理能力和实际雷达输出保持一致。

修改后使用 [`start_mid360.sh`](../start_mid360.sh) 重新启动驱动，并通过以下命令确认实际频率：

```bash
ros2 topic hz /livox/lidar
ros2 topic hz /livox/imu
```

如果实际频率明显低于配置值，应先检查网络、驱动日志和主机负载，再继续调整里程计置信度。驱动频率变化后，还应重新确认 Point-LIO 的 `imu_time_inte` 以及 rosbag 回放时的时间同步状态。

