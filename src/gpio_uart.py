#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from tf2_ros import TransformException
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener
import math
import serial
import sys
import threading
import queue

# ================= 坐标与算法配置 =================
SRC_X_CM = 0
SRC_Y_CM = 0
DST_X_CM = 0
DST_Y_CM = 0

ENABLE_KALMAN = 1

# ================= 硬件通信配置 =================
UART_PORT = '/dev/ttyTHS1'
BAUD_RATE = 115200
# ============================================

def calculate_crc8(data_str):
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
    return x_cm + (DST_X_CM - SRC_X_CM), y_cm + (DST_Y_CM - SRC_Y_CM)

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
        
        # ================= 异步打印架构初始化 =================
        self.print_queue = queue.Queue(maxsize=200) 
        self.print_thread = threading.Thread(target=self._async_print_worker, daemon=True)
        self.print_thread.start()
        # ======================================================

        try:
            self.ser = serial.Serial(UART_PORT, BAUD_RATE, timeout=0)
            self.ser.reset_output_buffer() 
            print(f"[INFO] 硬件串口已开启: {UART_PORT} (波特率: {BAUD_RATE})", flush=True)
        except Exception as e:
            print(f"[ERROR] 无法打开串口 {UART_PORT}。原因: {e}", flush=True)
            sys.exit(1)

        self.timer = self.create_timer(0.01, self.on_timer)

    def _async_print_worker(self):
        while True:
            msg = self.print_queue.get()
            print(msg, flush=True)
            self.print_queue.task_done()

    def _adaptive_scales(self, innovation_abs, threshold):
        if threshold <= 0.0:
            return 1.0, 1.0
        motion_level = min(1.0, innovation_abs / threshold)
        q_scale = 1.0 + motion_level * (self.max_q_boost - 1.0)
        r_scale = 1.0 - motion_level * (1.0 - self.min_r_scale)
        return q_scale, r_scale

    def on_timer(self):
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
                x_cm, y_cm, z_cm, yaw_deg = x_cm_raw, y_cm_raw, z_cm_raw, yaw_deg_raw

            x_cm, y_cm = transform_xy_cm(x_cm, y_cm)
            
            payload = f"[{x_cm:.1f};{y_cm:.1f};{z_cm:.1f};{yaw_deg:.1f}]"
            crc_val = calculate_crc8(payload)
            msg = f"{payload}{crc_val:02X}\r\n"
            
            try:
                self.ser.write(msg.encode('utf-8')) 
                self.ser.flush()
                
                print_msg = f"[TX] {msg.strip()}"
                try:
                    self.print_queue.put_nowait(print_msg)
                except queue.Full:
                    pass
                    
            except serial.SerialException as e:
                try:
                    self.print_queue.put_nowait(f"[WARN] 串口写入异常: {e}")
                except queue.Full:
                    pass
            
        except TransformException:
            pass 

def main():
    rclpy.init()
    node = PoseListener()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        print("\n[INFO] 接收到终端中断信号，正在终止节点...")
    finally:
        if node.ser is not None and node.ser.is_open:
            node.ser.close()
            print(f"[INFO] 串口资源 {UART_PORT} 已释放。")
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()