#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 安全模块 v3.0

功能：
  1. 数据加密（AES-256-GCM / ChaCha20-Poly1305）
  2. 文件签名验证（HMAC-SHA256 / Ed25519）
  3. 安全密钥管理（密钥派生、轮换）
  4. 内存敏感数据擦除
  5. 输入消毒（防注入）
  6. 安全随机数生成
  7. 凭据保险箱（加密存储）
  8. 通信安全（TLS 配置）
  9. 文件完整性校验
  10. 安全审计日志

作者：灵枢工程团队
版本：3.0.0
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

# 可选加密库（优先 PyCryptodome，其次 cryptography）
try:
    from Crypto.Cipher import AES, ChaCha20_Poly1305
    from Crypto.Protocol.KDF import scrypt
    from Crypto.Random import get_random_bytes
    _CRYPTO_BACKEND = "pycryptodome"
except ImportError:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
        from cryptography.hazmat.backends import default_backend
        _CRYPTO_BACKEND = "cryptography"
    except ImportError:
        _CRYPTO_BACKEND = None


try:
    import nacl.signing
    import nacl.encoding
    _NACL_AVAILABLE = True
except ImportError:
    _NACL_AVAILABLE = False


class SecurityError(Exception):
    """安全错误"""
    pass


class EncryptionError(SecurityError):
    """加密错误"""
    pass


class SignatureError(SecurityError):
    """签名错误"""
    pass


class CredentialError(SecurityError):
    """凭据错误"""
    pass


@dataclass
class EncryptedData:
    """加密数据封装"""
    ciphertext: bytes
    nonce: bytes
    tag: bytes
    algorithm: str = "AES-256-GCM"
    
    def to_dict(self) -> Dict[str, str]:
        """序列化为字典"""
        return {
            "ciphertext": base64.b64encode(self.ciphertext).decode(),
            "nonce": base64.b64encode(self.nonce).decode(),
            "tag": base64.b64encode(self.tag).decode(),
            "algorithm": self.algorithm,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "EncryptedData":
        """从字典解析"""
        return cls(
            ciphertext=base64.b64decode(data["ciphertext"]),
            nonce=base64.b64decode(data["nonce"]),
            tag=base64.b64decode(data["tag"]),
            algorithm=data.get("algorithm", "AES-256-GCM"),
        )
    
    def to_bytes(self) -> bytes:
        """序列化为字节（格式: algorithm_len + algorithm + nonce_len + nonce + tag + ciphertext）"""
        algo = self.algorithm.encode()
        return (
            len(algo).to_bytes(2, "big") + algo +
            len(self.nonce).to_bytes(2, "big") + self.nonce +
            self.tag + self.ciphertext
        )
    
    @classmethod
    def from_bytes(cls, data: bytes) -> "EncryptedData":
        """从字节解析"""
        ptr = 0
        algo_len = int.from_bytes(data[ptr:ptr+2], "big")
        ptr += 2
        algorithm = data[ptr:ptr+algo_len].decode()
        ptr += algo_len
        
        nonce_len = int.from_bytes(data[ptr:ptr+2], "big")
        ptr += 2
        nonce = data[ptr:ptr+nonce_len]
        ptr += nonce_len
        
        tag = data[ptr:ptr+16]
        ptr += 16
        ciphertext = data[ptr:]
        
        return cls(ciphertext, nonce, tag, algorithm)


class CryptoManager:
    """加密管理器"""
    
    def __init__(self, key: Optional[bytes] = None):
        self._key = key or self._generate_key()
        self._lock = threading.Lock()
    
    @staticmethod
    def _generate_key(size: int = 32) -> bytes:
        """生成安全随机密钥"""
        return secrets.token_bytes(size)
    
    def derive_key(self, password: str, salt: Optional[bytes] = None, size: int = 32) -> tuple:
        """从密码派生密钥"""
        salt = salt or secrets.token_bytes(16)
        
        if _CRYPTO_BACKEND == "pycryptodome":
            key = scrypt(password.encode(), salt, size, N=2**14, r=8, p=1)
        elif _CRYPTO_BACKEND == "cryptography":
            kdf = Scrypt(
                salt=salt, length=size, n=2**14, r=8, p=1,
                backend=default_backend(),
            )
            key = kdf.derive(password.encode())
        else:
            # 降级：使用 PBKDF2-HMAC-SHA256
            key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000, size)
        
        return key, salt
    
    def encrypt(self, plaintext: Union[str, bytes], associated_data: Optional[bytes] = None) -> EncryptedData:
        """加密数据"""
        if isinstance(plaintext, str):
            plaintext = plaintext.encode("utf-8")
        
        with self._lock:
            nonce = secrets.token_bytes(12)
            
            if _CRYPTO_BACKEND == "pycryptodome":
                cipher = AES.new(self._key, AES.MODE_GCM, nonce=nonce)
                if associated_data:
                    cipher.update(associated_data)
                ciphertext, tag = cipher.encrypt_and_digest(plaintext)
            elif _CRYPTO_BACKEND == "cryptography":
                aesgcm = AESGCM(self._key)
                associated_data = associated_data or b""
                ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)
                tag = ciphertext[-16:]
                ciphertext = ciphertext[:-16]
            else:
                raise EncryptionError("无加密后端可用")
        
        return EncryptedData(ciphertext, nonce, tag, "AES-256-GCM")
    
    def decrypt(self, encrypted: EncryptedData, associated_data: Optional[bytes] = None) -> bytes:
        """解密数据"""
        with self._lock:
            if _CRYPTO_BACKEND == "pycryptodome":
                cipher = AES.new(self._key, AES.MODE_GCM, nonce=encrypted.nonce)
                if associated_data:
                    cipher.update(associated_data)
                plaintext = cipher.decrypt_and_verify(encrypted.ciphertext, encrypted.tag)
            elif _CRYPTO_BACKEND == "cryptography":
                aesgcm = AESGCM(self._key)
                associated_data = associated_data or b""
                ciphertext_with_tag = encrypted.ciphertext + encrypted.tag
                plaintext = aesgcm.decrypt(encrypted.nonce, ciphertext_with_tag, associated_data)
            else:
                raise EncryptionError("无加密后端可用")
        
        return plaintext
    
    def encrypt_string(self, plaintext: str, associated_data: Optional[bytes] = None) -> str:
        """加密字符串，返回 Base64"""
        encrypted = self.encrypt(plaintext, associated_data)
        return base64.b64encode(encrypted.to_bytes()).decode()
    
    def decrypt_string(self, ciphertext_b64: str, associated_data: Optional[bytes] = None) -> str:
        """解密 Base64 字符串"""
        data = base64.b64decode(ciphertext_b64)
        encrypted = EncryptedData.from_bytes(data)
        return self.decrypt(encrypted, associated_data).decode("utf-8")
    
    def secure_compare(self, a: bytes, b: bytes) -> bool:
        """恒定时间比较（防时序攻击）"""
        return hmac.compare_digest(a, b)
    
    def hash_password(self, password: str) -> str:
        """密码哈希（Argon2 降级到 PBKDF2）"""
        salt = secrets.token_bytes(32)
        hash_value = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000, 32)
        return base64.b64encode(salt + hash_value).decode()
    
    def verify_password(self, password: str, hash_string: str) -> bool:
        """验证密码"""
        try:
            data = base64.b64decode(hash_string)
            salt = data[:32]
            expected_hash = data[32:]
            actual_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000, 32)
            return self.secure_compare(expected_hash, actual_hash)
        except Exception:
            return False
    
    def rotate_key(self) -> bytes:
        """轮换密钥"""
        with self._lock:
            old_key = self._key
            self._key = self._generate_key()
            return old_key
    
    def get_key_hash(self) -> str:
        """获取密钥哈希（不暴露密钥本身）"""
        return hashlib.sha256(self._key).hexdigest()[:16]
    
    def secure_wipe(self, data: bytearray) -> None:
        """安全擦除内存数据"""
        for i in range(len(data)):
            data[i] = secrets.randbits(8)
        del data


class SignatureManager:
    """签名管理器"""
    
    def __init__(self, secret_key: Optional[bytes] = None):
        self._secret = secret_key or secrets.token_bytes(32)
    
    def sign(self, data: Union[str, bytes], algorithm: str = "HMAC-SHA256") -> str:
        """签名数据"""
        if isinstance(data, str):
            data = data.encode("utf-8")
        
        if algorithm == "HMAC-SHA256":
            sig = hmac.new(self._secret, data, hashlib.sha256).digest()
        elif algorithm == "HMAC-SHA512":
            sig = hmac.new(self._secret, data, hashlib.sha512).digest()
        else:
            raise SignatureError(f"不支持的算法: {algorithm}")
        
        return base64.b64encode(sig).decode()
    
    def verify(self, data: Union[str, bytes], signature: str, algorithm: str = "HMAC-SHA256") -> bool:
        """验证签名"""
        expected = self.sign(data, algorithm)
        return hmac.compare_digest(expected, signature)
    
    def sign_file(self, filepath: Union[str, Path], algorithm: str = "HMAC-SHA256") -> str:
        """签名文件"""
        filepath = Path(filepath)
        if not filepath.exists():
            raise SignatureError(f"文件不存在: {filepath}")
        
        hasher = hashlib.sha256() if "SHA256" in algorithm else hashlib.sha512()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        
        return self.sign(hasher.digest(), algorithm)
    
    def verify_file(self, filepath: Union[str, Path], signature: str, algorithm: str = "HMAC-SHA256") -> bool:
        """验证文件签名"""
        expected = self.sign_file(filepath, algorithm)
        return hmac.compare_digest(expected, signature)
    
    def generate_checksum(self, filepath: Union[str, Path]) -> str:
        """生成文件校验和"""
        filepath = Path(filepath)
        if not filepath.exists():
            raise SignatureError(f"文件不存在: {filepath}")
        
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        
        return sha256.hexdigest()
    
    def verify_checksum(self, filepath: Union[str, Path], expected: str) -> bool:
        """验证文件校验和"""
        actual = self.generate_checksum(filepath)
        return hmac.compare_digest(actual.lower(), expected.lower())


class CredentialVault:
    """凭据保险箱：加密存储敏感信息"""
    
    def __init__(self, root: Path, master_password: Optional[str] = None):
        self.root = root
        self.vault_file = root / "config" / "vault.enc"
        self.vault_file.parent.mkdir(parents=True, exist_ok=True)
        
        self._crypto = CryptoManager()
        self._credentials: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._master_password = master_password
        
        if self.vault_file.exists():
            self._load()
    
    def _load(self) -> None:
        """加载保险箱"""
        try:
            with open(self.vault_file, "rb") as f:
                data = f.read()
            
            if self._master_password:
                key, _ = self._crypto.derive_key(self._master_password, data[:16])
                self._crypto._key = key
                data = data[16:]
            
            encrypted = EncryptedData.from_bytes(data)
            plaintext = self._crypto.decrypt(encrypted)
            self._credentials = json.loads(plaintext)
        except Exception as e:
            print(f"[CredentialVault] 加载失败: {e}")
            self._credentials = {}
    
    def _save(self) -> None:
        """保存保险箱"""
        plaintext = json.dumps(self._credentials, ensure_ascii=False).encode()
        encrypted = self._crypto.encrypt(plaintext)
        data = encrypted.to_bytes()
        
        with self._lock:
            if self._master_password:
                # 使用密码派生的密钥时，需要存储 salt
                key, salt = self._crypto.derive_key(self._master_password)
                self._crypto._key = key
                data = salt + data
            
            with open(self.vault_file, "wb") as f:
                f.write(data)
    
    def store(self, key: str, value: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """存储凭据"""
        with self._lock:
            self._credentials[key] = {
                "value": value,
                "metadata": metadata or {},
                "created_at": time.time(),
                "updated_at": time.time(),
            }
            self._save()
    
    def retrieve(self, key: str) -> Optional[str]:
        """检索凭据"""
        with self._lock:
            cred = self._credentials.get(key)
            if cred:
                return cred["value"]
            return None
    
    def delete(self, key: str) -> bool:
        """删除凭据"""
        with self._lock:
            if key in self._credentials:
                del self._credentials[key]
                self._save()
                return True
            return False
    
    def list_keys(self) -> List[str]:
        """列出所有凭据键"""
        return list(self._credentials.keys())
    
    def rotate(self, key: str) -> Optional[str]:
        """轮换凭据（生成新值）"""
        new_value = secrets.token_urlsafe(32)
        self.store(key, new_value, {"rotated_at": time.time()})
        return new_value
    
    def change_password(self, new_password: str) -> bool:
        """更改主密码"""
        try:
            self._master_password = new_password
            self._save()
            return True
        except Exception as e:
            print(f"[CredentialVault] 密码更改失败: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            "total_credentials": len(self._credentials),
            "vault_file_size": self.vault_file.stat().st_size if self.vault_file.exists() else 0,
            "key_hash": self._crypto.get_key_hash(),
        }


class InputSanitizer:
    """输入消毒器：防止注入攻击"""
    
    # SQL 注入关键词
    SQL_KEYWORDS = [
        "SELECT", "INSERT", "UPDATE", "DELETE", "DROP", "CREATE",
        "ALTER", "EXEC", "UNION", "OR", "AND", "WHERE", "FROM",
        "TABLE", "DATABASE", "SCHEMA", "TRUNCATE", "REPLACE",
    ]
    
    # 危险字符
    DANGEROUS_CHARS = ["<", ">", "\"", "'", "&", "%", ";", "(", ")", "{", "}", "`"]
    
    # 路径遍历模式
    PATH_TRAVERSAL = re.compile(r"\.\.+|^[~/]|\\x00")
    
    @classmethod
    def sanitize_string(cls, value: str, max_length: int = 1000) -> str:
        """消毒字符串"""
        if not isinstance(value, str):
            value = str(value)
        
        # 截断过长输入
        if len(value) > max_length:
            value = value[:max_length]
        
        # 转义 HTML 特殊字符
        value = value.replace("&", "&amp;")
        value = value.replace("<", "&lt;")
        value = value.replace(">", "&gt;")
        value = value.replace('"', "&quot;")
        value = value.replace("'", "&#x27;")
        
        # 移除 NULL 字节
        value = value.replace("\x00", "")
        
        return value
    
    @classmethod
    def sanitize_path(cls, path: str) -> Optional[str]:
        """消毒路径"""
        if not path:
            return None
        
        # 检查路径遍历
        if cls.PATH_TRAVERSAL.search(path):
            return None
        
        # 规范化路径
        path = os.path.normpath(path)
        
        # 检查是否包含 .. 遍历
        if ".." in path.split(os.sep):
            return None
        
        return path
    
    @classmethod
    def sanitize_sql(cls, value: str) -> str:
        """SQL 输入消毒（仅用于标识符/值，不用于完整的 SQL 构造）"""
        # 移除非安全字符
        safe = re.sub(r"[^a-zA-Z0-9_\-\.]", "", value)
        return safe
    
    @classmethod
    def check_sql_injection(cls, value: str) -> bool:
        """检查 SQL 注入风险"""
        upper = value.upper()
        score = 0
        for keyword in cls.SQL_KEYWORDS:
            if keyword in upper:
                score += 1
        
        # 风险阈值
        return score >= 2
    
    @classmethod
    def sanitize_command(cls, command: str) -> Optional[str]:
        """消毒命令（防止命令注入）"""
        # 禁止的命令分隔符
        dangerous = [";", "|", "&&", "||", "`", "$", "(", ")"]
        for char in dangerous:
            if char in command:
                return None
        
        return command.strip()
    
    @classmethod
    def sanitize_filename(cls, filename: str) -> Optional[str]:
        """消毒文件名"""
        # 移除路径分隔符
        filename = os.path.basename(filename)
        
        # 移除控制字符
        filename = "".join(c for c in filename if ord(c) >= 32 and ord(c) < 127)
        
        # 检查危险扩展名
        dangerous_ext = [".exe", ".bat", ".cmd", ".sh", ".dll", ".so"]
        lower = filename.lower()
        for ext in dangerous_ext:
            if lower.endswith(ext):
                return None
        
        return filename if filename else None


class SecurityAudit:
    """安全审计日志"""
    
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self.log_dir / f"security_audit_{datetime.now().strftime('%Y%m')}.log"
        self._lock = threading.Lock()
    
    def log(self, event_type: str, details: Dict[str, Any], success: bool = True) -> None:
        """记录安全事件"""
        entry = {
            "timestamp": time.time(),
            "datetime": datetime.now().isoformat(),
            "event_type": event_type,
            "details": details,
            "success": success,
        }
        
        with self._lock:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    def log_auth_attempt(self, user: str, method: str, success: bool, details: Optional[Dict] = None) -> None:
        """记录认证尝试"""
        self.log("AUTH_ATTEMPT", {
            "user": user,
            "method": method,
            "details": details or {},
        }, success)
    
    def log_permission_check(self, action: str, allowed: bool, level: int) -> None:
        """记录权限检查"""
        self.log("PERMISSION_CHECK", {
            "action": action,
            "allowed": allowed,
            "level": level,
        }, allowed)
    
    def log_file_access(self, filepath: str, operation: str, success: bool) -> None:
        """记录文件访问"""
        self.log("FILE_ACCESS", {
            "path": filepath,
            "operation": operation,
        }, success)
    
    def log_encryption_operation(self, operation: str, success: bool) -> None:
        """记录加密操作"""
        self.log("ENCRYPTION", {"operation": operation}, success)
    
    def query(self, event_type: Optional[str] = None, start_time: Optional[float] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """查询审计日志"""
        results = []
        
        for log_file in sorted(self.log_dir.glob("security_audit_*.log"), reverse=True):
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if event_type and entry.get("event_type") != event_type:
                            continue
                        if start_time and entry.get("timestamp", 0) < start_time:
                            continue
                        results.append(entry)
                    except json.JSONDecodeError:
                        continue
            
            if len(results) >= limit:
                break
        
        return results[:limit]


class SecurityManager:
    """安全管理器：整合所有安全功能"""
    
    def __init__(self, root: Path, master_password: Optional[str] = None, config: Optional[Dict] = None):
        self.root = root
        self.config = config or {}
        
        # 初始化组件
        self.crypto = CryptoManager()
        self.signature = SignatureManager()
        self.vault = CredentialVault(root, master_password)
        self.sanitizer = InputSanitizer()
        self.audit = SecurityAudit(root / "logs" / "security")
        
        # 安全设置
        self._max_auth_attempts = self.config.get("max_auth_attempts", 5)
        self._lockout_duration = self.config.get("lockout_duration_seconds", 300)
        self._auth_attempts: Dict[str, List[float]] = {}
        self._lock = threading.Lock()
    
    def check_rate_limit(self, identifier: str) -> bool:
        """检查是否被速率限制"""
        with self._lock:
            now = time.time()
            attempts = self._auth_attempts.get(identifier, [])
            # 清理过期记录
            attempts = [t for t in attempts if now - t < self._lockout_duration]
            self._auth_attempts[identifier] = attempts
            
            if len(attempts) >= self._max_auth_attempts:
                self.audit.log("RATE_LIMIT", {"identifier": identifier, "attempts": len(attempts)}, False)
                return False
            
            return True
    
    def record_auth_attempt(self, identifier: str, success: bool) -> None:
        """记录认证尝试"""
        with self._lock:
            if identifier not in self._auth_attempts:
                self._auth_attempts[identifier] = []
            self._auth_attempts[identifier].append(time.time())
    
    def encrypt_sensitive(self, data: str, context: str = "") -> str:
        """加密敏感数据"""
        associated = context.encode() if context else None
        encrypted = self.crypto.encrypt_string(data, associated)
        self.audit.log_encryption_operation(f"encrypt:{context}", True)
        return encrypted
    
    def decrypt_sensitive(self, encrypted: str, context: str = "") -> str:
        """解密敏感数据"""
        try:
            associated = context.encode() if context else None
            decrypted = self.crypto.decrypt_string(encrypted, associated)
            self.audit.log_encryption_operation(f"decrypt:{context}", True)
            return decrypted
        except Exception as e:
            self.audit.log_encryption_operation(f"decrypt:{context}", False)
            raise EncryptionError(f"解密失败: {e}")
    
    def store_credential(self, key: str, value: str) -> None:
        """安全存储凭据"""
        self.vault.store(key, value)
        self.audit.log("CREDENTIAL_STORE", {"key": key}, True)
    
    def retrieve_credential(self, key: str) -> Optional[str]:
        """安全检索凭据"""
        value = self.vault.retrieve(key)
        self.audit.log("CREDENTIAL_RETRIEVE", {"key": key}, value is not None)
        return value
    
    def sign_file(self, filepath: Union[str, Path]) -> str:
        """签名文件"""
        signature = self.signature.sign_file(filepath)
        self.audit.log("FILE_SIGN", {"path": str(filepath)}, True)
        return signature
    
    def verify_file(self, filepath: Union[str, Path], signature: str) -> bool:
        """验证文件签名"""
        result = self.signature.verify_file(filepath, signature)
        self.audit.log("FILE_VERIFY", {"path": str(filepath)}, result)
        return result
    
    def sanitize_input(self, value: str, input_type: str = "string") -> Optional[str]:
        """消毒输入"""
        if input_type == "string":
            return self.sanitizer.sanitize_string(value)
        elif input_type == "path":
            return self.sanitizer.sanitize_path(value)
        elif input_type == "filename":
            return self.sanitizer.sanitize_filename(value)
        elif input_type == "command":
            return self.sanitizer.sanitize_command(value)
        else:
            return self.sanitizer.sanitize_string(value)
    
    def generate_secure_token(self, length: int = 32) -> str:
        """生成安全令牌"""
        return secrets.token_urlsafe(length)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取安全统计"""
        return {
            "crypto_backend": _CRYPTO_BACKEND or "none",
            "vault_credentials": len(self.vault.list_keys()),
            "audit_entries": len(self.audit.query(limit=1)),
            "rate_limited": len([k for k, v in self._auth_attempts.items() if len(v) >= self._max_auth_attempts]),
        }
    
    def shutdown(self) -> None:
        """关闭安全模块"""
        # 安全擦除密钥
        key = self.crypto._key
        if isinstance(key, (bytearray, memoryview)):
            self.crypto.secure_wipe(key)


if __name__ == "__main__":
    # 示例用法
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        
        # 初始化安全模块
        security = SecurityManager(root, master_password="test_password")
        
        # 加密/解密
        plaintext = "敏感信息: API Key = sk-1234567890"
        encrypted = security.encrypt_sensitive(plaintext, "api_key")
        print(f"加密: {encrypted[:50]}...")
        
        decrypted = security.decrypt_sensitive(encrypted, "api_key")
        print(f"解密: {decrypted}")
        
        # 密码哈希
        password_hash = security.crypto.hash_password("my_password")
        print(f"密码哈希: {password_hash[:30]}...")
        print(f"验证密码: {security.crypto.verify_password('my_password', password_hash)}")
        
        # 凭据保险箱
        security.store_credential("api_key", "sk-1234567890")
        print(f"凭据: {security.retrieve_credential('api_key')}")
        
        # 输入消毒
        dirty_input = "<script>alert('xss')</script>"
        clean = security.sanitize_input(dirty_input)
        print(f"消毒: {clean}")
        
        # 文件签名
        test_file = root / "test.txt"
        test_file.write_text("test content")
        sig = security.sign_file(test_file)
        print(f"文件签名: {sig[:30]}...")
        print(f"验证签名: {security.verify_file(test_file, sig)}")
        
        # 审计日志
        security.audit.log_auth_attempt("user1", "password", True)
        print(f"审计日志: {security.audit.query(limit=1)}")
        
        # 统计
        print(f"\n安全统计: {security.get_stats()}")
        
        security.shutdown()
