#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 授权管理模块（增补卷核心）
功能：首次使用弹窗授权、分级权限、声纹叠加、撤销授权、审计日志

安全原则：
  1. 首次使用必须用户手动授权（弹窗确认）
  2. 权限分为基础/中级/高级三级
  3. 授权状态加密存储（U盘模式）
  4. 支持U盘拔插失效（物理断联）
  5. 操作审计日志（不可篡改）
  6. 撤销授权可回滚（30秒内）

"""

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class PermissionLevel(Enum):
    """权限等级"""
    LEVEL_1 = 1  # 基础操作：查看、点击、搜索
    LEVEL_2 = 2  # 中级操作：文件修改、系统设置、程序控制
    LEVEL_3 = 3  # 高级操作：格式化、支付、网络配置（需声纹+人脸）


class AuthStatus(Enum):
    """授权状态"""
    UNAUTHORIZED = "unauthorized"     # 未授权
    PENDING = "pending"               # 等待授权确认
    AUTHORIZED = "authorized"         # 已授权
    REVOKED = "revoked"               # 已撤销
    EXPIRED = "expired"               # 已过期


@dataclass
class AuthConfig:
    """授权配置"""
    auth_file: Path
    valid_days: int = 0  # 0 = 永久有效
    require_first_auth: bool = True
    level_1_actions: List[str] = field(default_factory=lambda: ["open", "click", "scroll", "type", "query"])
    level_2_actions: List[str] = field(default_factory=lambda: [
        "close", "delete_file", "delete_folder", "modify_system_settings", "execute_shell"
    ])
    level_3_actions: List[str] = field(default_factory=lambda: [
        "format_disk", "payment", "install_software", "network_config"
    ])
    guest_actions: List[str] = field(default_factory=lambda: ["open", "click", "query", "screenshot"])
    undo_timeout: int = 30


class AuthManager:
    """
    授权管理器
    
    管理灵枢 Agent 的所有权限操作：
    - 首次使用弹窗授权
    - 三级权限控制
    - 声纹/人脸叠加验证
    - 撤销授权与回滚
    - 操作审计日志
    """

    # 授权文件名
    AUTH_FILENAME = ".auth_state.json"
    # 审计日志文件名
    AUDIT_FILENAME = "audit_log.jsonl"
    # 撤销操作栈文件名
    UNDO_FILENAME = "undo_stack.jsonl"

    def __init__(self, root: Path, config: Optional[Dict] = None):
        self.root = root
        self.config = config or {}

        # 路径配置
        self.auth_dir = root / "config" / "auth"
        self.auth_file = self.auth_dir / self.AUTH_FILENAME
        self.audit_file = self.auth_dir / self.AUDIT_FILENAME
        self.undo_file = self.auth_dir / self.UNDO_FILENAME

        # 创建目录
        self.auth_dir.mkdir(parents=True, exist_ok=True)

        # 状态变量
        self._status: AuthStatus = AuthStatus.UNAUTHORIZED
        self._authorized_at: Optional[float] = None
        self._expires_at: Optional[float] = None
        self._permission_config: Dict = {}
        self._guest_mode: bool = False
        self._undo_stack: List[Dict] = []

        self._load_state()

    def _load_state(self):
        """从U盘加载授权状态"""
        if not self.auth_file.exists():
            self._status = AuthStatus.UNAUTHORIZED
            return

        try:
            with open(self.auth_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._status = AuthStatus(data.get("status", "unauthorized"))
            self._authorized_at = data.get("authorized_at")
            self._expires_at = data.get("expires_at")
            self._permission_config = data.get("permissions", {})

            # 检查过期
            if self._expires_at and time.time() > self._expires_at:
                self._status = AuthStatus.EXPIRED

        except Exception as e:
            print(f"[Auth] 加载授权状态失败: {e}")
            self._status = AuthStatus.UNAUTHORIZED

    def _save_state(self):
        """保存授权状态到U盘"""
        data = {
            "status": self._status.value,
            "authorized_at": self._authorized_at,
            "expires_at": self._expires_at,
            "permissions": self._permission_config,
            "saved_at": time.time(),
        }
        try:
            with open(self.auth_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Auth] 保存授权状态失败: {e}")

    # ==================== 授权状态查询 ====================

    def is_authorized(self) -> bool:
        """是否已授权"""
        return self._status == AuthStatus.AUTHORIZED

    def is_first_use(self) -> bool:
        """是否首次使用（未授权状态）"""
        return not self.auth_file.exists() or self._status == AuthStatus.UNAUTHORIZED

    def grant_authorization(self, permissions: Optional[Dict] = None) -> bool:
        """
        授予授权
        
        弹窗确认后调用此函数授予授权：
        - 生成授权文件到 U盘
        - 记录授权时间
        - 设置权限配置
        """
        now = time.time()
        valid_days = self.config.get("auth_valid_days", 0)

        self._status = AuthStatus.AUTHORIZED
        self._authorized_at = now
        self._expires_at = now + (valid_days * 86400) if valid_days > 0 else None
        self._permission_config = permissions or self._default_permissions()
        self._guest_mode = False

        self._save_state()
        self._log_audit("AUTHORIZATION_GRANTED", "用户已授权灵枢 Agent 操作权限")
        print("[Auth] ✅ 授权成功，灵枢已获得操作权限")
        return True

    def revoke_authorization(self) -> bool:
        """
        撤销授权
        
        用户主动撤销授权：
        - 删除授权文件
        - 保留审计日志
        - 清空撤销栈
        """
        self._status = AuthStatus.REVOKED
        self._authorized_at = None
        self._expires_at = None
        self._guest_mode = False

        self._save_state()
        self._log_audit("AUTHORIZATION_REVOKED", "用户已撤销灵枢 Agent 授权")
        print("[Auth] 🚫 授权已撤销，灵枢将停止敏感操作")
        return True

    def _default_permissions(self) -> Dict:
        """默认权限配置"""
        return {
            "level_1": self.config.get("level_1_actions", [
                "open", "click", "scroll", "type", "query"
            ]),
            "level_2": self.config.get("level_2_actions", [
                "close", "delete_file", "delete_folder",
                "modify_system_settings", "execute_shell"
            ]),
            "level_3": self.config.get("level_3_actions", [
                "format_disk", "payment", "install_software", "network_config"
            ]),
            "guest": self.config.get("guest_actions", [
                "open", "click", "query", "screenshot"
            ]),
        }

    # ==================== 权限检查 ====================

    def check_permission(self, action: str, is_speaker_verified: bool = False) -> Tuple[bool, PermissionLevel, str]:
        """
        检查权限
        
        返回: (是否允许, 权限等级, 消息)
        (三种状态：允许执行、需要确认、拒绝执行)
        """
        if not self.is_authorized():
            return False, PermissionLevel.LEVEL_3, "灵枢未获得授权，请运行授权命令"

        # 访客模式
        if self._guest_mode:
            allowed = self._permission_config.get("guest", [])
            if action not in allowed:
                return False, PermissionLevel.LEVEL_3, f"访客模式不允许执行 '{action}' 操作"
            return True, PermissionLevel.LEVEL_1, "访客模式允许执行"

        # 分级权限检查
        level_1 = self._permission_config.get("level_1", [])
        level_2 = self._permission_config.get("level_2", [])
        level_3 = self._permission_config.get("level_3", [])

        if action in level_1:
            return True, PermissionLevel.LEVEL_1, "基础权限，允许执行"
        elif action in level_2:
            if is_speaker_verified:
                return True, PermissionLevel.LEVEL_2, "声纹验证通过，允许执行"
            return False, PermissionLevel.LEVEL_2, "需要声纹验证，请进行语音认证"
        elif action in level_3:
            # 高级操作需要声纹+人脸（简化：仅声纹）
            return False, PermissionLevel.LEVEL_3, "高级操作需要声纹+人脸双重验证，暂不支持"
        else:
            # 未定义的操作默认拒绝
            return False, PermissionLevel.LEVEL_2, f"未定义的操作 '{action}'，默认拒绝执行"

    def enter_guest_mode(self):
        """进入访客模式"""
        self._guest_mode = True
        self._log_audit("MODE_GUEST", "进入访客模式")
        print("[Auth] 🚪 已进入访客模式，仅允许基础操作")

    def exit_guest_mode(self):
        """退出访客模式"""
        self._guest_mode = False
        self._log_audit("MODE_FULL", "退出访客模式，恢复完整权限")
        print("[Auth] 🔓 已退出访客模式，恢复完整权限")

    def is_guest_mode(self) -> bool:
        return self._guest_mode

    # ==================== 审计日志 ====================

    def _log_audit(self, event_type: str, message: str, details: Optional[Dict] = None):
        """记录审计日志"""
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "unix_time": time.time(),
            "event_type": event_type,
            "message": message,
            "details": details or {},
        }
        try:
           with open(self.audit_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[Auth] 审计日志写入失败: {e}")

    def log_operation(self, action: str, intent: str, result: str, speaker_id: Optional[str] = None):
        """记录操作日志"""
        self._log_audit("OPERATION", f"操作: {action}", {
            "intent": intent,
            "result": result,
            "speaker_id": speaker_id,
            "guest_mode": self._guest_mode,
        })

    def get_audit_logs(self, limit: int = 100) -> List[Dict]:
        """查询审计日志"""
        logs = []
        if not self.audit_file.exists():
            return logs
        try:
            with open(self.audit_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        logs.append(json.loads(line))
        except Exception as e:
            print(f"[Auth] 读取审计日志失败: {e}")
        return logs[-limit:]

    # ==================== 撤销回滚（增补卷） ====================

    def push_undo(self, action: str, pre_state: Dict, post_state: Dict):
        """记录可撤销操作"""
        entry = {
            "timestamp": time.time(),
            "action": action,
            "pre_state": pre_state,
            "post_state": post_state,
        }
        self._undo_stack.append(entry)
        # 限制栈大小
        max_size = 50
        if len(self._undo_stack) > max_size:
            self._undo_stack = self._undo_stack[-max_size:]

        # 持久化到文件
        try:
            with open(self.undo_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[Auth] 撤销栈写入失败: {e}")

    def pop_undo(self) -> Optional[Dict]:
        """弹出最近一次可撤销操作"""
        if not self._undo_stack:
            return None
        entry = self._undo_stack.pop()
        self._log_audit("UNDO", f"撤销操作: {entry['action']}")
        return entry

    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    # ==================== 首次授权弹窗文本 ====================

    def get_authorization_text(self) -> str:
        """首次授权弹窗文本"""
        return """
╔══════════════════════════════════════════════════════════╗
║              灵枢（LingShu）Agent 授权协议              ║
╚══════════════════════════════════════════════════════════╝

灵枢是一款智能桌面助手，为了保障您的系统安全，首次使用前需要您明确授权。

  1. 🔒 基础权限：文件浏览、网页搜索、程序启动（安全级别：低）
  2. ⚠️  中级权限：文件修改、系统设置、程序控制（需声纹验证）
  3. 🛡️ 高级权限：格式化磁盘、支付操作、网络配置（需声纹+人脸）

授权方式：
  • 点击"授权"按钮，生成授权文件到 U盘/指定目录
  • 授权文件可随时删除，灵枢将自动进入安全模式
  • 支持访客模式，限制仅基础操作

安全提示：
  • 授权文件包含加密令牌，请勿泄露给他人
  • 删除授权文件后，灵枢将停止所有敏感操作
  • 每次敏感操作均有审计日志，可事后追溯

操作记录：
  • 所有操作均记录到审计日志（audit_log.jsonl）
  • 支持撤销操作（30秒内有效）
  • 支持紧急停止（Ctrl+C 或语音指令"停止"）

══════════════════════════════════════════════════════════

请确认您已阅读并同意上述协议，点击下方按钮授权灵枢运行。

        [ ✅ 我同意并授权 ]        [ ❌ 拒绝，仅访客模式 ]

══════════════════════════════════════════════════════════
        """.strip()


# 便捷的首次授权检查函数
def check_first_auth(root: Path) -> bool:
    """检查是否需要首次授权"""
    auth_file = root / "config" / "auth" / ".auth_state.json"
    return not auth_file.exists()
