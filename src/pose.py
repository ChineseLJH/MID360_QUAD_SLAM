#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
import math
import serial
import serial.tools.list_ports
import time

def calculate_crc8(data_str):
    """计算标准 CRC-8 校验值"""
    crc = 0x00
    for char in data_str:
        crc ^= ord(char)
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ 0x07
            else:
                crc <<= 1
            crc &= 0xFF
    return crc

class KalmanFilter1D:
    def __init__(self, process_variance=0.01, measurement_variance=1.0, initial_value=0.0):
        self.q = process_variance
        self.r = measurement_variance
        self.p = 1.0
        self.x = initial_value
        self.initialized = False
        
    def update(self, measurement, q_scale=1.0, r_scale=1.0):
        if not self.initialized:
            self.x = measurement
            self.initialized = True
            return self.x

        q_eff = self.q * max(0.001, q_scale)
        r_eff = self.r * max(0.001, r_scale)

        self.p = self.p + q_eff
        k = self.p / (self.p + r_eff)
        self.x = self.x + k * (measurement - self.x)
        self.p = (1 - k) * self.p
        return self.x

def wrap_angle_deg(angle_deg):
    return (angle_deg + 180.0) % 360.0 - 180.0

class AngleKalmanFilter1D(KalmanFilter1D):
    def update(self, measurement, q_scale=1.0, r_scale=1.0):
        if not self.initialized:
            self.x = wrap_angle_deg(measurement)
            self.initialized = True
            return self.x

        q_eff = self.q * max(0.001, q_scale)
        r_eff = self.r * max(0.001, r_scale)

        self.p = self.p + q_eff
        k = self.p / (self.p + r_eff)
        innovation = wrap_angle_deg(measurement - self.x)
        self.x = wrap_angle_deg(self.x + k * innovation)
        self.p = (1 - k) * self.p
        return self.x

class OdomSerialListener(Node):
    def __init__(self):
        super().__init__('odom_serial_listener')
        
        # ================= 双路监听里程计话题 =================
        self.sub_fastlio = self.create_subscription(
            Odometry,
            '/fastlio2/lio_odom',
            self.odom_callback,
            10
        )
        
        self.sub_pointlio = self.create_subscription(
            Odometry,
            '/aft_mapped_to_init',
            self.odom_callback,
            10
        )
        
        # ================= 卡尔曼滤波参数 =================
        self.kf_x = KalmanFilter1D(process_variance=0.0008, measurement_variance=2.0)
        self.kf_y = KalmanFilter1D(process_variance=0.0008, measurement_variance=2.0)
        self.kf_z = KalmanFilter1D(process_variance=0.0008, measurement_variance=2.5)
        self.kf_yaw = AngleKalmanFilter1D(process_variance=0.0015, measurement_variance=4.0)

        self.motion_threshold_cm = 1.2
        self.motion_threshold_yaw_deg = 2.0
        self.max_q_boost = 14.0
        self.min_r_scale = 0.20
        
        # ================= 串口配置区块 =================
        self.SERIAL_DEVICE_DB = {
            "CH340":  (0x1A86, 0x7523),
            "CP210X": (0x10C4, 0xEA60),
            "FTDI":   (0x0403, 0x6001),
        }

        self.baudrate = 115200
        self.ser = None
        self.serial_scan_interval_sec = 1.0
        self.last_serial_scan_time = 0.0
        self.last_no_serial_log_time = 0.0

        self._refresh_serial_connection(force=True)
        self.create_timer(self.serial_scan_interval_sec, self._refresh_serial_connection)

        self.get_logger().info("里程计订阅节点已就绪 (话题: /fastlio2/lio_odom, /aft_mapped_to_init)")

    def _adaptive_scales(self, innovation_abs, threshold):
        if threshold <= 0.0:
            return 1.0, 1.0
        motion_level = min(1.0, innovation_abs / threshold)
        q_scale = 1.0 + motion_level * (self.max_q_boost - 1.0)
        r_scale = 1.0 - motion_level * (1.0 - self.min_r_scale)
        return q_scale, r_scale

    def _auto_discover_port(self):
        for port in serial.tools.list_ports.comports():
            for name, (vid, pid) in self.SERIAL_DEVICE_DB.items():
                if port.vid == vid and port.pid == pid:
                    self.get_logger().info(
                        f"检测到设备: {name} (VID:{hex(vid)} PID:{hex(pid)}) -> {port.device}"
                    )
                    return port.device
        return None

    def _refresh_serial_connection(self, force=False):
        now = time.monotonic()
        if not force and (now - self.last_serial_scan_time) < self.serial_scan_interval_sec:
            return
        self.last_serial_scan_time = now

        if self.ser is not None and getattr(self.ser, 'is_open', False):
            return

        target_port = self._auto_discover_port()
        if target_port:
            try:
                self.ser = serial.Serial(target_port, self.baudrate, timeout=1)
                self.get_logger().info(f"串口已建立连接: {target_port}")
                return
            except (serial.SerialException, OSError) as e:
                self.get_logger().warning(f"打开串口失败: {e}")

        if (now - self.last_no_serial_log_time) >= 5.0:
            self.last_no_serial_log_time = now
            self.get_logger().info("未发现匹配串口设备，持续扫描中...")

    def euler_from_quaternion(self, x, y, z, w):
        """将四元数转换为欧拉角 (返回角度制)"""
        t3 = +2.0 * (w * z + x * y)
        t4 = +1.0 - 2.0 * (y * y + z * z)
        yaw = math.degrees(math.atan2(t3, t4))
        return yaw

    def odom_callback(self, msg):
        x_cm_raw = msg.pose.pose.position.x * 100.0
        y_cm_raw = msg.pose.pose.position.y * 100.0
        z_cm_raw = msg.pose.pose.position.z * 100.0
        
        q = msg.pose.pose.orientation
        yaw_deg_raw = self.euler_from_quaternion(q.x, q.y, q.z, q.w)
        
        x_innovation = abs(x_cm_raw - self.kf_x.x) if self.kf_x.initialized else 0.0
        y_innovation = abs(y_cm_raw - self.kf_y.x) if self.kf_y.initialized else 0.0
        z_innovation = abs(z_cm_raw - self.kf_z.x) if self.kf_z.initialized else 0.0
        yaw_innovation = abs(wrap_angle_deg(yaw_deg_raw - self.kf_yaw.x)) if self.kf_yaw.initialized else 0.0

        x_q, x_r = self._adaptive_scales(x_innovation, self.motion_threshold_cm)
        y_q, y_r = self._adaptive_scales(y_innovation, self.motion_threshold_cm)
        z_q, z_r = self._adaptive_scales(z_innovation, self.motion_threshold_cm)
        yaw_q, yaw_r = self._adaptive_scales(yaw_innovation, self.motion_threshold_yaw_deg)

        x_cm = self.kf_x.update(x_cm_raw, q_scale=x_q, r_scale=x_r)
        y_cm = self.kf_y.update(y_cm_raw, q_scale=y_q, r_scale=y_r)
        z_cm = self.kf_z.update(z_cm_raw, q_scale=z_q, r_scale=z_r)
        yaw_deg = self.kf_yaw.update(yaw_deg_raw, q_scale=yaw_q, r_scale=yaw_r)
        
        payload = f"[{x_cm:.1f};{y_cm:.1f};{z_cm:.1f};{yaw_deg:.1f}]"
        crc_val = calculate_crc8(payload)
        out_msg = f"{payload}{crc_val:02X}\r\n"
        
        if self.ser is not None and self.ser.is_open:
            try:
                self.ser.write(out_msg.encode('utf-8')) 
                print(f"\r[TX] {out_msg.strip()}          ", end="", flush=True)
            except serial.SerialException as e:
                print(f"\n[ERROR] 串口通信异常中断: {e}")
                self.ser.close()
                self.ser = None
        else:
            print(f"\r[DISCONNECTED] {out_msg.strip()}          ", end="", flush=True)

def main(args=None):
    rclpy.init(args=args)
    node = OdomSerialListener()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        print("\n[INFO] 接收到终端中断信号，正在终止节点...")
    finally:
        if hasattr(node, 'ser') and node.ser is not None and node.ser.is_open:
            node.ser.close()
            print("[INFO] 串口资源已释放。")
            
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()