<div align="center">
  <img src="docs/images/team_logo.png" width="120" alt="MEIC Logo" />
  
  # MID360 Quadruped SLAM Stack
</div>

> 面向四足仿生机器人的 Livox MID-360 激光雷达 SLAM、全局重定位与边缘端部署一体化方案
>
> Developed by Shenyang University of Technology (MEIC Team) for ROBOCON 2026.

## 项目介绍

本项目源自沈阳工业大学 **MEIC 战队** 在第二十五届全国大学生机器人大赛（ROBOCON 2026）马术赛道中采用的四足仿生机器人雷达定位方案，在障碍赛上取得两项全国一等奖（第六名、第十名）。该方案针对四足机器人在剧烈运动中的定位与通信问题，构建了一整套完整的环境解耦、易于复现的机载雷达定位方案。

## 项目特点

### 1. 全流程容器化封装

* **Docker 环境封装**：提供完整的 Docker 容器化部署方案，将ros2、雷达驱动和算法依赖部署在Docker容器中，支持在本地边缘端快速部署与运行。
* **一键启动脚本**：提供[一键启动脚本](service_autostart.sh)，支持设备开机自启动后在tmux中查看运行状态，方便在边缘端进行远程调试。

### 2. 针对边缘端四足机器人优化

* **支持两种前端里程计方案**：针对不同的振动情况，分别可以选用 fastlio2 和 pointlio 两种不同的前端里程计方案。
* **与下位机通信**：针对四足机器人在运动中可能出现 USB 设备断连的情况，提供自动重连机制以及使用 GPIO 串口进行传输的python脚本。

## 文档导航

|  文档  |  核心内容 |
| :----: | :----: |
| [本地部署教程](docs/local_setup.md) | 本地 docker 容器化部署指南 |
| [端侧部署教程](docs/edge_deployment.md) | 端侧 docker 容器化部署指南 |
| [脚本与工作流](docs/workflow_tips.md) | 脚本介绍与使用指南 |
| [参数调优指南](docs/tuning_guide.md) | 里程计与驱动参数调优指南 |

本项目端侧部署基于 NVIDIA Jetson Orin 系列边缘计算设备。

## 致谢与参考

本项目基于以下优秀的开源算法与 ROS 2 移植工作进行构建与二次开发，在此向原作者及开源贡献者表示感谢：

* **核心算法**：
  * [FAST-LIO](https://github.com/hku-mars/FAST_LIO)：香港大学 MARS 实验室开源的高频激光惯导紧耦合里程计框架。
  * [Point-LIO](https://github.com/hku-mars/Point-LIO)：香港大学 MARS 实验室开源的适用于高动态场景的逐点激光惯导里程计。
* **ROS 2 适配与工程参考**：
  * [FASTLIO2_ROS2](https://github.com/liangheming/FASTLIO2_ROS2)：由 @liangheming 维护的 FAST-LIO2 ROS 2 移植版本。
  * [point_lio_ros2](https://github.com/dfloreaa/point_lio_ros2)：由 @dfloreaa 维护的 Point-LIO ROS 2 移植版本。

## 开源协议

本项目采用 [GNU General Public License v2.0](LICENSE) (GPL-2.0) 协议开源。