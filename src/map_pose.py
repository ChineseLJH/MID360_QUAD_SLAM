#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from tf2_ros import TransformException
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener
import math
import serial
import serial.tools.list_ports
import time

# --- 核心特征指纹库 ---
SERIAL_DEVICE_DB = {
    "CH340":  (0x1A86, 0x7523),
    "CP210X": (0x10C4, 0xEA60),
    "FTDI":   (0x0403, 0x6001),
}

# 坐标转换锚点
SRC_X_CM = 0
SRC_Y_CM = 0
DST_X_CM = 0
DST_Y_CM = 0

ENABLE_KALMAN = 1

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

def transform_xy_cm(x_cm, y_cm):
    offset_x = DST_X_CM - SRC_X_CM
    offset_y = DST_Y_CM - SRC_Y_CM
    return x_cm + offset_x, y_cm + offset_y

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

class PoseListener(Node):
    def __init__(self):
        super().__init__('pose_listener')
        
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        
        self.kf_x = KalmanFilter1D(process_variance=0.0008, measurement_variance=2.0)
        self.kf_y = KalmanFilter1D(process_variance=0.0008, measurement_variance=2.0)
        self.kf_z = KalmanFilter1D(process_variance=0.0008, measurement_variance=2.5)
        self.kf_yaw = AngleKalmanFilter1D(process_variance=0.0015, measurement_variance=4.0)

        self.motion_threshold_cm = 1.2
        self.motion_threshold_yaw_deg = 2.0
        self.max_q_boost = 14.0
        self.min_r_scale = 0.20
        self.last_tf_stamp_ns = None
        
        # ================= 串口配置区块 =================
        self.baudrate = 115200
        self.ser = None
        self.serial_scan_interval_sec = 1.0
        self.last_serial_scan_time = 0.0
        self.last_no_serial_log_time = 0.0

        self._refresh_serial_connection(force=True)
        self.timer = self.create_timer(0.01, self.on_timer)

    def _auto_discover_port(self):
        """底层总线扫描：遍历指纹库锁定所有支持的串口"""
        for port in serial.tools.list_ports.comports():
            for name, (vid, pid) in SERIAL_DEVICE_DB.items():
                if port.vid == vid and port.pid == pid:
                    print(
                        f"[INFO] 识别到目标设备: {name} (VID:{hex(vid)} PID:{hex(pid)}) -> {port.device}",
                        flush=True,
                    )
                    return port.device
        return None

    def _refresh_serial_connection(self, force=False):
        now = time.monotonic()
        if not force and (now - self.last_serial_scan_time) < self.serial_scan_interval_sec:
            return
        self.last_serial_scan_time = now

        if self.ser is not None and self.ser.is_open:
            return

        target_port = self._auto_discover_port()
        if target_port:
            try:
                self.ser = serial.Serial(target_port, self.baudrate, timeout=1)
                print(f"[INFO] 串口连接已建立: {target_port}", flush=True)
                return
            except (serial.SerialException, OSError) as e:
                print(f"[ERROR] 无法打开串口设备: {e}", flush=True)

        if (now - self.last_no_serial_log_time) >= 5.0:
            self.last_no_serial_log_time = now
            print("[INFO] 未检索到有效 USB 转串口设备，保持后台轮询...", flush=True)

    def _adaptive_scales(self, innovation_abs, threshold):
        if threshold <= 0.0:
            return 1.0, 1.0
        motion_level = min(1.0, innovation_abs / threshold)
        q_scale = 1.0 + motion_level * (self.max_q_boost - 1.0)
        r_scale = 1.0 - motion_level * (1.0 - self.min_r_scale)
        return q_scale, r_scale

    def on_timer(self):
        self._refresh_serial_connection()

        try:
            t = self.tf_buffer.lookup_transform('map', 'body', rclpy.time.Time())

            stamp_ns = t.header.stamp.sec * 1_000_000_000 + t.header.stamp.nanosec
            if self.last_tf_stamp_ns is not None and stamp_ns == self.last_tf_stamp_ns:
                return
            self.last_tf_stamp_ns = stamp_ns
            
            x_cm_raw = t.transform.translation.x * 100.0
            y_cm_raw = t.transform.translation.y * 100.0
            z_cm_raw = t.transform.translation.z * 100.0
            
            q = t.transform.rotation
            siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
            cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
            yaw_deg_raw = math.degrees(math.atan2(siny_cosp, cosy_cosp))
            
            if ENABLE_KALMAN:
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
            else:
                x_cm = x_cm_raw
                y_cm = y_cm_raw
                z_cm = z_cm_raw
                yaw_deg = yaw_deg_raw

            x_cm, y_cm = transform_xy_cm(x_cm, y_cm)
            
            payload = f"[{x_cm:.1f};{y_cm:.1f};{z_cm:.1f};{yaw_deg:.1f}]"
            crc_val = calculate_crc8(payload)
            msg = f"{payload}{crc_val:02X}\r\n"
            
            if self.ser is not None and self.ser.is_open:
                try:
                    self.ser.write(msg.encode('utf-8')) 
                    print(f"[TX] {msg.strip()}", flush=True)
                except serial.SerialException as e:
                    print(f"[ERROR] 串口通信中断: {e}")
                    try:
                        self.ser.close()
                    except Exception:
                        pass
                    self.ser = None
            else:
                print(f"[DISCONNECTED] {msg.strip()}", flush=True)
            
        except TransformException:
            pass

def main():
    rclpy.init()
    node = PoseListener()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        print("\n[INFO] 接收到中断信号，正在终止节点...")
    finally:
        if node.ser is not None and node.ser.is_open:
            node.ser.close()
            print("[INFO] 串口资源已释放。")
            
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()