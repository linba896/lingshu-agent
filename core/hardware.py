#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 硬件控制模块（增补卷十四 + 进化卷六）
功能：TCP/IP、MQTT、Modbus、Serial、DMX512、USB HID 通用设备控制

协议矩阵：
  TCP/IP    → 智能照明、空调、网络设备
  MQTT      → 物联网设备、智能家居
  Modbus    → 工业PLC、舞台设备
  Serial    → 老式控台、RS-232/RS-485设备
  DMX512    → 专业舞台灯光（需USB-DMX转换器）
  HID       → USB HID设备（相机、医疗仪器等）

场景模式：
  computer → 电脑控制模式（默认）
  stage    → 舞台控制模式（启用DMX/HID）
  hotel    → 酒店控制模式（启用MQTT/Modbus）
  meeting  → 会议控制模式（启用投影/窗帘）
"""

import json
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


class SceneMode(Enum):
    """场景模式"""
    COMPUTER = "computer"  # 电脑控制
    STAGE = "stage"        # 舞台控制
    HOTEL = "hotel"        # 酒店控制
    MEETING = "meeting"    # 会议控制


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
    支持多种协议与场景模式切换
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

        # 场景指令集（不同模式允许不同指令）
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
        """初始化各协议连接"""
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
                print("[Hardware] ⚠️ paho-mqtt 未安装，MQTT 不可用")

        # Modbus
        if self.protocols.get("modbus", {}).get("enabled", False):
            try:
                from pymodbus.client import ModbusTcpClient
                self._available_protocols.add(ProtocolType.MODBUS)
                print("[Hardware] ✅ Modbus 协议已启用")
            except ImportError:
                print("[Hardware] ⚠️ pymodbus 未安装，Modbus 不可用")

        # Serial
        if self.protocols.get("serial", {}).get("enabled", False):
            try:
                import serial
                self._available_protocols.add(ProtocolType.SERIAL)
                print("[Hardware] ✅ Serial 协议已启用")
            except ImportError:
                print("[Hardware] ⚠️ pyserial 未安装，Serial 不可用")

        # DMX512
        if self.protocols.get("dmx512", {}).get("enabled", False):
            # DMX512 需要外接USB-DMX转换器
            device = self.protocols.get("dmx512", {}).get("device_path")
            if device:
                print(f"[Hardware] ✅ DMX512 已配置: {device}")
                self._available_protocols.add(ProtocolType.DMX512)
            else:
                print("[Hardware] ⚠️ DMX512 未配置设备路径")

        # HID
        # USB HID 控制需要 libusb 和 pyusb，暂不默认启用
        print("[Hardware] ℹ️ HID 协议需额外配置（USB HID设备）")

    def set_scene(self, scene: str) -> bool:
        """切换场景模式"""
        try:
            self.scene = SceneMode(scene)
            print(f"[Hardware] 🎬 场景切换为: {self.scene.value}")
            return True
        except ValueError:
            print(f"[Hardware] ❌ 未知场景: {scene}")
            return False

    def get_scene(self) -> str:
        return self.scene.value

    def is_command_allowed(self, command: str) -> bool:
        """检查当前场景是否允许该指令"""
        allowed = self._scene_commands.get(self.scene, set())
        return command in allowed

    # ============================================================
    # TCP/IP 控制
    # ============================================================

    def send_tcp(self, host: str, port: int, data: bytes) -> bool:
        """通过TCP发送控制指令"""
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

    # ============================================================
    # MQTT 控制
    # ============================================================

    def send_mqtt(self, topic: str, payload: Dict, qos: int = 0) -> bool:
        """通过MQTT发布控制指令"""
        if ProtocolType.MQTT not in self._available_protocols:
            print("[Hardware] ❌ MQTT 协议未启用")
            return False

        try:
            mqtt_config = self.protocols.get("mqtt", {})
            broker = mqtt_config.get("broker", "localhost")
            port = mqtt_config.get("port", 1883)

            # 简单连接发送
            import paho.mqtt.publish as publish
            publish.single(
                topic,
                payload=json.dumps(payload),
                qos=qos,
                hostname=broker,
                port=port,
            )
            print(f"[Hardware] 📡 MQTT 已发送: {topic} -> {payload}")
            return True
        except Exception as e:
            print(f"[Hardware] MQTT 发送失败: {e}")
            return False

    # ============================================================
    # Modbus 控制
    # ============================================================

    def send_modbus(self, host: str, port: int, unit_id: int,
                    function_code: int, address: int, value: int) -> bool:
        """通过Modbus发送控制指令"""
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
            print(f"[Hardware] 🔌 Modbus 已发送: unit={unit_id} addr={addr}")
            return True
        except Exception as e:
            print(f"[Hardware] Modbus 发送失败: {e}")
            return False

    # ============================================================
    # Serial 控制
    # ============================================================

    def send_serial(self, data: bytes, port: Optional[str] = None,
                    baudrate: int = 9600) -> bool:
        """通过串口发送控制指令"""
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
                print(f"[Hardware] 🔌 Serial 已发送: {port} {data.hex()}")
                return True
        except Exception as e:
            print(f"[Hardware] Serial 发送失败: {e}")
            return False

    # ============================================================
    # DMX512 控制
    # ============================================================

    def send_dmx(self, channel_values: Dict[int, int]) -> bool:
        """
        通过DMX512发送灯光控制指令
        channel_values: {通道号: 亮度值(0-255)}
        """
        if ProtocolType.DMX512 not in self._available_protocols:
            print("[Hardware] ❌ DMX512 协议未启用或未配置设备")
            return False

        device = self.protocols.get("dmx512", {}).get("device_path")
        if not device:
            print("[Hardware] ❌ DMX512 设备未配置")
            return False

        # 构造DMX512数据帧
        # DMX帧: [Break] [MAB] [Slot 0=0] [Slot 1-512 data]
        dmx_data = bytearray(513)  # Slot 0-512
        dmx_data[0] = 0  # Start code

        for channel, value in channel_values.items():
            if 1 <= channel <= 512 and 0 <= value <= 255:
                dmx_data[channel] = value

        try:
            # 通过串口发送DMX（USB-DMX转换器通常模拟串口）
            import serial
            with serial.Serial(device, 250000, timeout=1) as ser:
                # DMX Break (~88μs) + MAB (~8μs) + 数据
                ser.break_condition = True
                time.sleep(0.0001)  # 100μs break
                ser.break_condition = False
                time.sleep(0.000012)  # 12μs MAB
                ser.write(bytes(dmx_data))
                print(f"[Hardware] 🎭 DMX512 已发送: {len(channel_values)} channels")
                return True
        except Exception as e:
            print(f"[Hardware] DMX512 发送失败: {e}")
            return False

    # ============================================================
    # 场景快捷指令
    # ============================================================

    def execute_scene_command(self, command: str, params: Optional[Dict] = None) -> bool:
        """
        执行场景快捷指令
        例如：light_on, temperature_set, projector_on, etc.
        """
        if not self.is_command_allowed(command):
            print(f"[Hardware] ❌ 指令 '{command}' 在 {self.scene.value} 模式下不可用")
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
                # 发送预设场景指令
                return self.send_modbus("192.168.1.100", 502, 1, 6, 100 + scene_id, 1)
            elif command == "dmx_preset":
                preset = params.get("preset", {})
                return self.send_dmx(preset)
            elif command == "emergency_stop":
                print("[Hardware] 🚨 舞台急停！所有灯光归零")
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

        print(f"[Hardware] ⚠️ 未实现的指令: {command} in {self.scene.value}")
        return False

    # ============================================================
    # 物理急停按钮
    # ============================================================

    def check_emergency_stop(self) -> bool:
        """
        检查物理急停按钮状态
        返回True表示急停已触发
        """
        if not self.emergency_stop.get("enabled", False):
            return False

        # 简化实现：检查USB HID急停按钮
        # 实际可用pyusb或HID库监听特定VID/PID设备
        vid = self.emergency_stop.get("device_vid")
        pid = self.emergency_stop.get("device_pid")

        if not vid or not pid:
            return False

        # 这里为占位，实际实现需集成HID库
        return False

    def emergency_stop_all(self):
        """触发全局急停"""
        print("[Hardware] 🚨🚨🚨 全局急停触发！切断所有控制信号！")
        # 关闭所有连接
        for protocol in list(self._connections.keys()):
            try:
                conn = self._connections.get(protocol)
                if conn and hasattr(conn, 'close'):
                    conn.close()
            except Exception:
                pass
        # 舞台场景：DMX全部归零
        if self.scene == SceneMode.STAGE:
            self.send_dmx({i: 0 for i in range(1, 513)})
