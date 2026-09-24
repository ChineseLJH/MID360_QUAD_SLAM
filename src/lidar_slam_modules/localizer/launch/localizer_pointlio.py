import launch
import launch_ros.actions
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    rviz_cfg = PathJoinSubstitution(
        [FindPackageShare("localizer"), "rviz", "localizer.rviz"]
    )
    localizer_config_path = PathJoinSubstitution(
        [FindPackageShare("localizer"), "config", "localizer.yaml"]
    )

    # 1. 指向你 Point-LIO 的配置文件 (原来是 fastlio 的 config)
    point_lio_config_path = PathJoinSubstitution(
        [FindPackageShare("point_lio"), "config", "mid360.yaml"]
    )

    return launch.LaunchDescription(
        [
            # ========================================================
            # 2. 核心替换：换成你的 Point-LIO 节点
            # ========================================================
            launch_ros.actions.Node(
                package="point_lio",
                executable="pointlio_mapping",
                name="laserMapping",
                output="screen",
                parameters=[
                    point_lio_config_path,  # 加载基础 YAML 配置
                    {
                        # 这里放入你之前建图时用到的 Point-LIO 特有参数
                        'use_imu_as_input': False,
                        'prop_at_freq_of_imu': True,
                        'check_satu': True,
                        'init_map_size': 10,
                        'point_filter_num': 3,
                        'space_down_sample': True,
                        'filter_size_surf': 0.5,
                        'filter_size_map': 0.5,
                        'cube_side_length': 1000.0,
                        'runtime_pos_log_enable': False,
                        # 让 Point-LIO 发布 body 坐标系点云，供 localizer 订阅
                        'publish.scan_bodyframe_pub_en': True,
                        # 让 Point-LIO 直接发布 camera_init -> body 的 TF，便于 RViz 显示 body 点云
                        'odom_child_frame_id': 'body',
                    }
                ],
                # 🌟 最重要的一步：伪装话题！让 Localizer 以为还是 FAST-LIO 在发数据
                remappings=[
                    ('/aft_mapped_to_init', '/fastlio2/lio_odom'),
                    ('/cloud_registered', '/fastlio2/cloud_registered'),
                    ('/cloud_registered_body', '/fastlio2/body_cloud')
                ]
            ),

            # ========================================================
            # 3. 保持不变的 Localizer 节点
            # ========================================================
            launch_ros.actions.Node(
                package="localizer",
                namespace="localizer",
                executable="localizer_node",
                name="localizer_node",
                output="screen",
                parameters=[
                    {
                        "config_path": localizer_config_path.perform(
                            launch.LaunchContext()
                        )
                    }
                ],
            ),

            # ========================================================
            # 4. 保持不变的 RViz 节点
            # ========================================================
            launch_ros.actions.Node(
                package="rviz2",
                namespace="localizer",
                executable="rviz2",
                name="rviz2",
                output="screen",
                arguments=["-d", rviz_cfg.perform(launch.LaunchContext())],
            )
        ]
    )
