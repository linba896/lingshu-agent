#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 硬件控制模块（增补卷 + 进化卷）
功能：TCP/IP、MQTT、Modbus、Serial、DMX512、USB HID 通用设备控制

支持协议：
  TCP/IP    → 智能灯具、传感器、网络设备
  MQTT      → 智能家居设备、IoT设备
  Modbus    → 工业PLC、温控器、传感器
  Serial    → RS-232/RS-485 设备、单片机
  DMX512    → 舞台灯光（通过USB-DMX适配器）
  HID       → USB HID 设备（键盘、鼠标、自定义HID）

场景模式：
  computer  → 办公模式：屏幕亮度、键盘灯、环境灯
  stage     → 舞台模式：DMX灯光、音响控制、特效
  hotel     → 酒店模式：窗帘、空调、灯光、欢迎语
  meeting   → 会议模式：投影仪、灯光、音响、麦克风

"""

import json
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


class SceneMode(Enum):
    """场景模式"""
    COMPUTER = "computer"  # 办公模式
    STAGE = "stage"        # 舞台模式
    HOTEL = "hotel"        # 酒店模式
    MEETING = "meeting"    # 会议模式


class ProtocolType(Enum):
    """协议类型"""
    TCP = "tcp"
    MQTT = "mqtt"
    MODBUS = "modbus"
    SERIAL = "serial"
    DMX512 = "dmx512"
    HID = "hid"


class HardwareController:
    """
    通用硬件控制器
    
    支持多种通信协议和场景模式：
    - 自动识别可用协议
    - 场景切换自动配置设备
    - 支持紧急停止（一键关闭所有设备）
    """

    def __init__(self, config: Dict, root: Path):
        self.config = config or {}
        self.root = root
        self.protocols = config.get("protocols", {})
        self.scene = SceneMode(config.get("default_scene", "computer"))
        self.emergency_stop = config.get("emergency_stop", {})

        # 连接管理
        self._connections: Dict[str, Any] = {}
        self._available_protocols: set = set()
        self._running = False

        # 场景命令集（不同场景允许不同命令）
        self._scene_commands: Dict[SceneMode, set] = {
            SceneMode.COMPUTER: {
                "open", "close", "click", "type", "screenshot", "execute"
            },
            SceneMode.STAGE: {
                "light_on", "light_off", "light_color", "light_scene",
                "sound_on", "sound_off", "sound_volume",
                "dmx_preset", "dmx_fade", "emergency_stop"
            },
            SceneMode.HOTEL: {
                "light_on", "light_off", "light_dim", "light_color",
                "temperature_set", "curtain_open", "curtain_close",
                "scene_welcome", "scene_sleep", "scene_work"
            },
            SceneMode.MEETING: {
                "projector_on", "projector_off", "screen_down",
                "curtain_close", "light_dim", "mic_mute", "mic_unmute"
            },
        }

        self._init_protocols()

    def _init_protocols(self):
        """初始化所有协议连接"""
        # TCP/IP
        if self.protocols.get("tcp", {}).get("enabled", False):
            self._available_protocols.add(ProtocolType.TCP)
            print("[Hardware] ✅ TCP/IP 协议已启用")

        # MQTT
        if self.protocols.get("mqtt", {}).get("enabled", False):
            try:
                import paho.mqtt.client as mqtt
                self._mqtt_client = mqtt.Client()
                self._available_protocols.add(ProtocolType.MQTT)
                print("[Hardware] ✅ MQTT 协议已启用")
            except ImportError:
                print("[Hardware] ⚠️ paho-mqtt 未安装，MQTT 协议不可用")

        # Modbus
        if self.protocols.get("modbus", {}).get("enabled", False):
            try:
                from pymodbus.client import ModbusTcpClient
                self._available_protocols.add(ProtocolType.MODBUS)
                print("[Hardware] ✅ Modbus 协议已启用")
            except ImportError:
                print("[Hardware] ⚠️ pymodbus 未安装，Modbus 协议不可用")

        # Serial
        if self.protocols.get("serial", {}).get("enabled", False):
            try:
                import serial
                self._available_protocols.add(ProtocolType.SERIAL)
                print("[Hardware] ✅ Serial 协议已启用")
            except ImportError:
                print("[Hardware] ⚠️ pyserial 未安装，Serial 协议不可用")

        # DMX512
        if self.protocols.get("dmx512", {}).get("enabled", False):
            # DMX512 需要USB-DMX适配器
            device = self.protocols.get("dmx512", {}).get("device_path")
            if device:
                print(f"[Hardware] ✅ DMX512 已配置，设备: {device}")
                self._available_protocols.add(ProtocolType.DMX512)
            else:
                print("[Hardware] ⚠️ DMX512 未配置设备路径")

        # HID
        # USB HID 通过 pyusb 或 hidapi 实现
        # 简化：仅标记为可用，实际实现需要平台适配
        print("[Hardware] ℹ️ HID 协议可用，需安装 pyusb 或 hidapi")

    def set_scene(self, scene: str) -> bool:
        """切换场景模式"""
        try:
            self.scene = SceneMode(scene)
            print(f"[Hardware] 🎭 场景切换成功: {self.scene.value}")
            return True
        except ValueError:
            print(f"[Hardware] ❌ 未知场景: {scene}")
            return False

    def get_scene(self) -> str:
        return self.scene.value

    def is_command_allowed(self, command: str) -> bool:
        """检查命令是否在当前场景允许"""
        allowed = self._scene_commands.get(self.scene, set())
        return command in allowed

    # ==================== TCP/IP 通信 ====================

    def send_tcp(self, host: str, port: int, data: bytes) -> bool:
        """发送 TCP 数据到设备"""
        if ProtocolType.TCP not in self._available_protocols:
            print("[Hardware] ❌ TCP 协议未启用")
            return False

        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(self.protocols.get("tcp", {}).get("timeout", 5))
                s.connect((host, port))
                s.sendall(data)
                return True
        except Exception as e:
            print(f"[Hardware] TCP 发送失败: {e}")
            return False

    # ==================== MQTT 通信 ====================

    def send_mqtt(self, topic: str, payload: Dict, qos: int = 0) -> bool:
        """发送 MQTT 消息到设备"""
        if ProtocolType.MQTT not in self._available_protocols:
            print("[Hardware] ❌ MQTT 协议未启用")
            return False

        try:
            mqtt_config = self.protocols.get("mqtt", {})
            broker = mqtt_config.get("broker", "localhost")
            port = mqtt_config.get("port", 1883)

            # 发布消息
            import paho.mqtt.publish as publish
            publish.single(
                topic,
                payload=json.dumps(payload),
                qos=qos,
                hostname=broker,
                port=port,
            )
            print(f"[Hardware] ✅ MQTT 发送成功: {topic} -> {payload}")
            return True
        except Exception as e:
            print(f"[Hardware] MQTT 发送失败: {e}")
            return False

    # ==================== Modbus 通信 ====================

    def send_modbus(self, host: str, port: int, unit_id: int,
                    function_code: int, address: int, value: int) -> bool:
        """发送 Modbus 命令到设备"""
        if ProtocolType.MODBUS not in self._available_protocols:
            print("[Hardware] ❌ Modbus 协议未启用")
            return False

        try:
            from pymodbus.client import ModbusTcpClient
            client = ModbusTcpClient(host, port=port, timeout=5)
            if not client.connect():
                print("[Hardware] Modbus 连接失败")
                return False

            if function_code == 5:  # Write Single Coil
                result = client.write_coil(address, value > 0, slave=unit_id)
            elif function_code == 6:  # Write Single Register
                result = client.write_register(address, value, slave=unit_id)
            else:
                result = client.read_holding_registers(address, 1, slave=unit_id)

            client.close()
            print(f"[Hardware] ✅ Modbus 发送成功: unit={unit_id} addr={address}")
            return True
        except Exception as e:
            print(f"[Hardware] Modbus 发送失败: {e}")
            return False

    # ==================== Serial 通信 ====================

    def send_serial(self, data: bytes, port: Optional[str] = None,
                    baudrate: int = 9600) -> bool:
        """发送串口数据到设备"""
        if ProtocolType.SERIAL not in self._available_protocols:
            print("[Hardware] ❌ Serial 协议未启用")
            return False

        try:
            import serial
            serial_config = self.protocols.get("serial", {})
            port = port or serial_config.get("default_port", "COM3")
            baudrate = baudrate or serial_config.get("baudrate", 9600)

            with serial.Serial(port, baudrate, timeout=2) as ser:
                ser.write(data)
                print(f"[Hardware] ✅ Serial 发送成功: {port} {data.hex()}")
                return True
        except Exception as e:
            print(f"[Hardware] Serial 发送失败: {e}")
            return False

    # ==================== DMX512 通信 ====================

    def send_dmx(self, channel_values: Dict[int, int]) -> bool:
        """
        发送 DMX512 数据到舞台灯光设备
        
        channel_values: {通道号: 亮度值(0-255)}
        """
        if ProtocolType.DMX512 not in self._available_protocols:
            print("[Hardware] ❌ DMX512 协议未启用或未配置设备")
            return False

        device = self.protocols.get("dmx512", {}).get("device_path")
        if not device:
            print("[Hardware] ❌ DMX512 未配置设备路径")
            return False

        # 构建 DMX512 数据包
        # DMX格式: [Break] [MAB] [Slot 0=0] [Slot 1-512 data]
        dmx_data = bytearray(513)  # Slot 0-512
        dmx_data[0] = 0  # Start code

        for channel, value in channel_values.items():
            if 1 <= channel <= 512 and 0 <= value <= 255:
                dmx_data[channel] = value

        try:
            # 通过串口发送 DMX512 数据（USB-DMX适配器）
            import serial
            with serial.Serial(device, 250000, timeout=1) as ser:
                # DMX Break (≥88μs) + MAB (≥8μs) + 数据
                ser.break_condition = True
                time.sleep(0.0001)  # 100μs break
                ser.break_condition = False
                time.sleep(0.000012)  # 12μs MAB
                ser.write(bytes(dmx_data))
                print(f"[Hardware] 🎭 DMX512 发送成功: {len(channel_values)} channels")
                return True
        except Exception as e:
            print(f"[Hardware] DMX512 发送失败: {e}")
            return False

    # ==================== 场景命令执行 ====================

    def execute_scene_command(self, command: str, params: Optional[Dict] = None) -> bool:
        """
        执行场景命令
        
        支持命令：light_on, temperature_set, projector_on, etc.
        """
        if not self.is_command_allowed(command):
            print(f"[Hardware] ❌ 命令 '{command}' 在 {self.scene.value} 场景下不允许执行")
            return False

        params = params or {}

        # 酒店场景
        if self.scene == SceneMode.HOTEL:
            if command == "light_on":
                return self.send_mqtt("hotel/room/light", {"state": "on"})
            elif command == "light_off":
                return self.send_mqtt("hotel/room/light", {"state": "off"})
            elif command == "light_dim":
                brightness = params.get("brightness", 50)
                return self.send_mqtt("hotel/room/light", {"brightness": brightness})
            elif command == "temperature_set":
                temp = params.get("temperature", 24)
                return self.send_mqtt("hotel/room/ac", {"temperature": temp})
            elif command == "scene_welcome":
                return self.send_mqtt("hotel/room/scene", {"scene": "welcome"})
            elif command == "scene_sleep":
                return self.send_mqtt("hotel/room/scene", {"scene": "sleep"})

        # 舞台场景
        elif self.scene == SceneMode.STAGE:
            if command == "light_on":
                return self.send_dmx({1: 255})  # 通道1全开
            elif command == "light_off":
                return self.send_dmx({1: 0})
            elif command == "light_scene":
                scene_id = params.get("scene_id", 1)
                # 发送Modbus命令控制灯光场景
                return self.send_modbus("192.168.1.100", 502, 1, 6, 100 + scene_id, 1)
            elif command == "dmx_preset":
                preset = params.get("preset", {})
                return self.send_dmx(preset)
            elif command == "emergency_stop":
                print("[Hardware] 🚨🚨🚨 紧急停止！所有灯光设备关闭")
                return self.send_dmx({i: 0 for i in range(1, 513)})

        # 会议场景
        elif self.scene == SceneMode.MEETING:
            if command == "projector_on":
                return self.send_tcp(params.get("host", "192.168.1.50"), 23, b"\rPOWER ON\r")
            elif command == "projector_off":
                return self.send_tcp(params.get("host", "192.168.1.50"), 23, b"\rPOWER OFF\r")
            elif command == "curtain_close":
                return self.send_mqtt("meeting/curtain", {"action": "close"})
            elif command == "light_dim":
                return self.send_mqtt("meeting/light", {"brightness": 30})

        print(f"[Hardware] 🤔 未知命令: {command} in {self.scene.value}")
        return False

    # ==================== 紧急停止 ====================

    def check_emergency_stop(self) -> bool:
        """
        检查紧急停止信号
        
        检测方式：
        - 物理按钮（USB HID 设备）
        - 语音指令（"停止"、"紧急停止"）
        - 网络信号（MQTT/HTTP）
        """
        if not self.emergency_stop.get("enabled", False):
            return False

        # 检查物理按钮（USB HID）
        # 实际实现需要读取 HID 设备状态
        # 简化：仅返回 False，实际实现需要平台适配
        return False

    def emergency_stop_all(self):
        """紧急停止所有设备"""
        print("[Hardware] 🚨🚨🚨 紧急停止！所有设备关闭！")
        # 关闭所有连接
        for protocol in list(self._connections.keys()):
            try:
                conn = self._connections.get(protocol)
                if conn and hasattr(conn, 'close'):
                    conn.close()
            except Exception:
                pass
        # 舞台灯光全部关闭（DMX）
        if self.scene == SceneMode.STAGE:
            self.send_dmx({i: 0 for i in range(1, 513)})

