#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢端口检测脚本（Phase 7 联调优化）
功能：检测所有服务端口占用情况，自动分配备用端口

检测端口：
  - 7860: Gradio GUI 面板
  - 1883: MQTT Broker
  - 502: Modbus TCP
  - 22: SSH
  - 自定义端口

使用方式：
  python scripts/port_check.py --check-all
  python scripts/port_check.py --port 7860
"""

import argparse
import socket
import sys
from pathlib import Path
from typing import Dict, List, Optional


# 灵枢默认端口配置
DEFAULT_PORTS = {
    "gradio_gui": 7860,
    "mqtt_broker": 1883,
    "modbus_tcp": 502,
    "ssh": 22,
    "http_api": 8080,
    "websocket": 8765,
}


def check_port(port: int, host: str = "127.0.0.1") -> bool:
    """检查端口是否被占用"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex((host, port))
            return result == 0  # 0 表示端口被占用
    except Exception:
        return False


def find_free_port(start_port: int, end_port: int = 65535, host: str = "127.0.0.1") -> Optional[int]:
    """查找可用端口"""
    for port in range(start_port, end_port + 1):
        if not check_port(port, host):
            return port
    return None


def check_all_ports() -> Dict[str, Dict]:
    """检查所有默认端口"""
    results = {}
    for name, port in DEFAULT_PORTS.items():
        is_occupied = check_port(port)
        results[name] = {
            "port": port,
            "occupied": is_occupied,
            "status": "🔴 占用" if is_occupied else "🟢 可用",
        }
        if is_occupied:
            free_port = find_free_port(port + 1)
            results[name]["suggested_port"] = free_port
    return results


def main():
    parser = argparse.ArgumentParser(description="灵枢端口检测工具")
    parser.add_argument("--check-all", action="store_true", help="检查所有默认端口")
    parser.add_argument("--port", type=int, help="检测指定端口")
    parser.add_argument("--find-free", type=int, help="从指定端口开始查找可用端口")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="主机地址")
    args = parser.parse_args()
    
    if args.check_all:
        print("=" * 60)
        print("  灵枢服务端口检测")
        print("=" * 60)
        
        results = check_all_ports()
        
        for name, info in results.items():
            print(f"\n  {name:20s} 端口: {info['port']:5d}  {info['status']}")
            if info.get('suggested_port'):
                print(f"  {'':20s} 建议备用端口: {info['suggested_port']}")
        
        occupied = [name for name, info in results.items() if info['occupied']]
        if occupied:
            print(f"\n⚠️  {len(occupied)} 个端口被占用，建议修改配置使用备用端口")
        else:
            print("\n✅ 所有端口可用，配置无需修改")
    
    elif args.port is not None:
        is_occupied = check_port(args.port, args.host)
        status = "🔴 占用" if is_occupied else "🟢 可用"
        print(f"端口 {args.port}: {status}")
        
        if is_occupied:
            free_port = find_free_port(args.port + 1, host=args.host)
            if free_port:
                print(f"建议备用端口: {free_port}")
    
    elif args.find_free is not None:
        free_port = find_free_port(args.find_free, host=args.host)
        if free_port:
            print(f"✅ 找到可用端口: {free_port}")
        else:
            print(f"❌ 未找到可用端口（从 {args.find_free} 开始）")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
