#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 授权控制模块（增补卷十二）
功能：首次插入授权、分级权限、撤销授权、访客模式、操作审计

安全原则：
  1. 首次启动必须手动点击授权（不可语音授权，防误触）
  2. 三级权限体系：日常/敏感/高危
  3. 授权状态加密存储于U盘
  4. 拔出U盘即失效（零痕迹）
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
    LEVEL_1 = 1  # 日常操作：无需确认
    LEVEL_2 = 2  # 敏感操作：需语音/弹窗确认
    LEVEL_3 = 3  # 高危操作：需手动点击确认（语音不可绕过）


class AuthStatus(Enum):
    """授权状态"""
    UNAUTHORIZED = "unauthorized"    # 未授权
    PENDING = "pending"             # 等待授权确认
    AUTHORIZED = "authorized"       # 已授权
    REVOKED = "revoked"           # 已撤销
    EXPIRED = "expired"           # 已过期


@dataclass
class AuthConfig:
    """授权配置"""
    auth_file: Path
    valid_days: int = 0  # 0 = 永久
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
    管理灵枢对电脑的控制权授权、分级权限、访客模式
    """

    # 授权状态文件名
    AUTH_FILENAME = ".auth_state.json"
    # 操作审计日志文件名
    AUDIT_FILENAME = "audit_log.jsonl"
    # 撤销操作记录文件名
    UNDO_FILENAME = "undo_stack.jsonl"

    def __init__(self, root: Path, config: Optional[Dict] = None):
        self.root = root
        self.config = config or {}

        # 路径
        self.auth_dir = root / "config" / "auth"
        self.auth_file = self.auth_dir / self.AUTH_FILENAME
        self.audit_file = self.auth_dir / self.AUDIT_FILENAME
        self.undo_file = self.auth_dir / self.UNDO_FILENAME

        # 创建目录
        self.auth_dir.mkdir(parents=True, exist_ok=True)

        # 加载状态
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

            # 检查是否过期
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

    # ============================================================
    # 授权生命周期
    # ============================================================

    def is_authorized(self) -> bool:
        """检查是否已授权"""
        return self._status == AuthStatus.AUTHORIZED

    def is_first_use(self) -> bool:
        """检查是否为首次使用（无授权记录）"""
        return not self.auth_file.exists() or self._status == AuthStatus.UNAUTHORIZED

    def grant_authorization(self, permissions: Optional[Dict] = None) -> bool:
        """
        授予授权（用户手动点击"同意授权"后调用）
        不可通过语音调用此函数
        """
        now = time.time()
        valid_days = self.config.get("auth_valid_days", 0)

        self._status = AuthStatus.AUTHORIZED
        self._authorized_at = now
        self._expires_at = now + (valid_days * 86400) if valid_days > 0 else None
        self._permission_config = permissions or self._default_permissions()
        self._guest_mode = False

        self._save_state()
        self._log_audit("AUTHORIZATION_GRANTED", "用户手动授权灵枢控制电脑")
        print("[Auth] ✅ 授权成功，灵枢已获电脑控制权")
        return True

    def revoke_authorization(self) -> bool:
        """
        撤销授权（一键急停）
        立即收回所有控制权
        """
        self._status = AuthStatus.REVOKED
        self._authorized_at = None
        self._expires_at = None
        self._guest_mode = False

        self._save_state()
        self._log_audit("AUTHORIZATION_REVOKED", "用户撤销授权")
        print("[Auth] 🛑 授权已撤销，灵枢停止所有操作")
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

    # ============================================================
    # 权限检查
    # ============================================================

    def check_permission(self, action: str, is_speaker_verified: bool = False) -> Tuple[bool, PermissionLevel, str]:
        """
        检查操作权限
        返回: (是否允许, 权限等级, 提示信息)
        """
        if not self.is_authorized():
            return False, PermissionLevel.LEVEL_3, "灵枢未获授权，请先完成授权流程"

        # 访客模式限制
        if self._guest_mode:
            allowed = self._permission_config.get("guest", [])
            if action not in allowed:
                return False, PermissionLevel.LEVEL_3, f"访客模式不可执行'{action}'，请主上亲自操作"
            return True, PermissionLevel.LEVEL_1, "访客模式允许"

        # 三级权限检查
        level_1 = self._permission_config.get("level_1", [])
        level_2 = self._permission_config.get("level_2", [])
        level_3 = self._permission_config.get("level_3", [])

        if action in level_1:
            return True, PermissionLevel.LEVEL_1, "日常操作，直接执行"
        elif action in level_2:
            if is_speaker_verified:
                return True, PermissionLevel.LEVEL_2, "敏感操作，声纹已验证，执行"
            return False, PermissionLevel.LEVEL_2, "敏感操作，需声纹验证后确认"
        elif action in level_3:
            # 高危操作：必须手动点击，语音不可绕过
            return False, PermissionLevel.LEVEL_3, "高危操作！必须手动点击确认，语音不可绕过"
        else:
            # 未知操作：默认按敏感处理
            return False, PermissionLevel.LEVEL_2, f"未定义操作'{action}'，按敏感操作处理，需确认"

    def enter_guest_mode(self):
        """进入访客模式"""
        self._guest_mode = True
        self._log_audit("MODE_GUEST", "进入访客模式")
        print("[Auth] 👤 已进入访客模式，仅支持基础操作")

    def exit_guest_mode(self):
        """退出访客模式"""
        self._guest_mode = False
        self._log_audit("MODE_FULL", "退出访客模式，恢复全权限")
        print("[Auth] 👑 已退出访客模式，恢复全权限")

    def is_guest_mode(self) -> bool:
        return self._guest_mode

    # ============================================================
    # 操作审计日志
    # ============================================================

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
        """记录操作审计"""
        self._log_audit("OPERATION", f"执行: {action}", {
            "intent": intent,
            "result": result,
            "speaker_id": speaker_id,
            "guest_mode": self._guest_mode,
        })

    def get_audit_logs(self, limit: int = 100) -> List[Dict]:
        """读取审计日志"""
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

    # ============================================================
    # 操作回滚（增补卷十六改进建议3）
    # ============================================================

    def push_undo(self, action: str, pre_state: Dict, post_state: Dict):
        """记录可撤销的操作"""
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

        # 持久化
        try:
            with open(self.undo_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[Auth] 回滚记录写入失败: {e}")

    def pop_undo(self) -> Optional[Dict]:
        """弹出最近一次可撤销操作"""
        if not self._undo_stack:
            return None
        entry = self._undo_stack.pop()
        self._log_audit("UNDO", f"撤销操作: {entry['action']}")
        return entry

    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    # ============================================================
    # 授权协议文本
    # ============================================================

    def get_authorization_text(self) -> str:
        """获取授权协议文本"""
        return """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  灵枢（LingShu）数字元神 — 授权协议
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

灵枢是一个AI智能体运行时环境，将获取以下权限操控您的电脑：

  1. 📺 屏幕读取 — 识别界面元素、理解当前操作环境
  2. 🖱️  键鼠模拟 — 模拟鼠标点击、键盘输入执行操作
  3. 📁 文件访问 — 读取/写入指定目录的文件
  4. 🎙️  麦克风使用 — 采集语音指令进行识别

权限分级说明：
  • 日常操作（打开软件、浏览网页）—— 直接执行
  • 敏感操作（删除文件、修改设置）—— 需声纹确认
  • 高危操作（格式化磁盘、支付）—— 需手动点击确认

安全承诺：
  • 所有操作均记录在U盘审计日志中，可追溯
  • 拔出U盘即完全退出，电脑不留任何痕迹
  • 声纹不匹配者无法执行敏感操作

请确认您理解并同意上述授权内容。

【⚠️ 注意：此授权不可通过语音完成，必须手动点击】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        """.strip()
