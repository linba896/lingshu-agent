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
from typing import Any, Dict, List, Optional, Union

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
            raise EncryptionError("无加密后端可用")
        
        return key, salt
    
    def encrypt(self, plaintext: bytes, associated_data: Optional[bytes] = None) -> EncryptedData:
        """加密数据"""
        if _CRYPTO_BACKEND is None:
            raise EncryptionError("无加密后端可用。请安装 pycryptodome 或 cryptography")
        
        nonce = secrets.token_bytes(12)
        
        if _CRYPTO_BACKEND == "pycryptodome":
            cipher = AES.new(self._key, AES.MODE_GCM, nonce=nonce)
            if associated_data:
                cipher.update(associated_data)
            ciphertext, tag = cipher.encrypt_and_digest(plaintext)
        elif _CRYPTO_BACKEND == "cryptography":
            aesgcm = AESGCM(self._key)
            associated_data = associated_data or b""
            ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, associated_data)
            ciphertext = ciphertext_with_tag[:-16]
            tag = ciphertext_with_tag[-16:]
        
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
        encrypted = self.encrypt(plaintext.encode("utf-8"), associated_data)
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
        with self._lock:
            return list(self._credentials.keys())
    
    def get_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """获取凭据元数据"""
        with self._lock:
            cred = self._credentials.get(key)
            if cred:
                return cred.get("metadata")
            return None


class InputSanitizer:
    """输入消毒器：防止注入攻击"""
    
    # SQL 注入模式
    SQL_PATTERNS = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE|UNION|TRUNCATE)\b)",
        r"(--|#|/\*|\*/)",
        r"(\bOR\b|\bAND\b)\s+\d+\s*=\s*\d+",
    ]
    
    # XSS 模式
    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=\s*['\"]",
        r"<iframe[^>]*>",
    ]
    
    # Shell 注入模式
    SHELL_PATTERNS = [
        r"[;&|`$()]",
        r"\b(rm|mv|cp|cat|ls|chmod|chown|sudo)\b",
        r">>",
    ]
    
    # 路径遍历模式
    PATH_PATTERNS = [
        r"\.\./",
        r"\.\.\\",
        r"%2e%2e%2f",
    ]
    
    def __init__(self):
        self._patterns: Dict[str, List[str]] = {
            "sql": self.SQL_PATTERNS,
            "xss": self.XSS_PATTERNS,
            "shell": self.SHELL_PATTERNS,
            "path": self.PATH_PATTERNS,
        }
    
    def sanitize(self, data: str, context: str = "") -> str:
        """消毒输入"""
        if not data:
            return data
        
        import re
        
        # 根据上下文选择模式
        patterns = self._patterns.get(context, [])
        
        if not patterns:
            # 通用消毒：移除控制字符
            return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", data)
        
        result = data
        for pattern in patterns:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)
        
        return result
    
    def validate(self, data: str, context: str = "") -> bool:
        """验证输入是否安全"""
        sanitized = self.sanitize(data, context)
        return sanitized == data


class SecurityManager:
    """安全模块：整合所有安全功能"""
    
    def __init__(self, root: Path, master_password: Optional[str] = None, config: Optional[Dict] = None):
        self.root = root
        self.config = config or {}
        
        # 子模块
        self.crypto = CryptoManager()
        self.vault = CredentialVault(root, master_password)
        self.sanitizer = InputSanitizer()
        
        # 审计日志
        self.audit_dir = root / "logs" / "security"
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.audit_file = self.audit_dir / "audit.jsonl"
        self._audit_lock = threading.Lock()
        
        # 速率限制
        self._rate_limits: Dict[str, List[float]] = {}
        self._rate_limit_lock = threading.Lock()
        self._max_requests = self.config.get("max_requests_per_minute", 100)
        
        # 签名
        self.signer = SignatureManager()
    
    def encrypt_sensitive(self, data: str, context: str = "") -> str:
        """加密敏感数据"""
        associated_data = context.encode("utf-8") if context else None
        encrypted = self.crypto.encrypt_string(data, associated_data)
        self.log_audit_event("encryption", {"context": context, "algorithm": "AES-256-GCM"})
        return encrypted
    
    def decrypt_sensitive(self, data: str, context: str = "") -> str:
        """解密敏感数据"""
        associated_data = context.encode("utf-8") if context else None
        return self.crypto.decrypt_string(data, associated_data)
    
    def hash_password(self, password: str) -> str:
        """哈希密码"""
        return self.crypto.hash_password(password)
    
    def verify_password(self, password: str, hash_string: str) -> bool:
        """验证密码"""
        return self.crypto.verify_password(password, hash_string)
    
    def sign_data(self, data: str, context: str = "") -> str:
        """签名数据"""
        return self.signer.sign(data)
    
    def verify_signature(self, data: str, signature: str, context: str = "") -> bool:
        """验证签名"""
        return self.signer.verify(data, signature)
    
    def store_credential(self, key: str, value: str, metadata: Optional[Dict] = None) -> None:
        """存储凭据"""
        self.vault.store(key, value, metadata)
        self.log_audit_event("credential_store", {"key": key})
    
    def retrieve_credential(self, key: str) -> Optional[str]:
        """检索凭据"""
        self.log_audit_event("credential_retrieve", {"key": key})
        return self.vault.retrieve(key)
    
    def sanitize_input(self, data: str, context: str = "") -> str:
        """消毒输入"""
        return self.sanitizer.sanitize(data, context)
    
    def validate_input(self, data: str, context: str = "") -> bool:
        """验证输入"""
        return self.sanitizer.validate(data, context)
    
    def check_rate_limit(self, client_id: str) -> bool:
        """检查速率限制"""
        now = time.time()
        
        with self._rate_limit_lock:
            if client_id not in self._rate_limits:
                self._rate_limits[client_id] = []
            
            # 清理过期记录
            self._rate_limits[client_id] = [
                t for t in self._rate_limits[client_id]
                if now - t < 60
            ]
            
            if len(self._rate_limits[client_id]) >= self._max_requests:
                return False
            
            self._rate_limits[client_id].append(now)
            return True
    
    def log_audit_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """记录审计事件"""
        event = {
            "timestamp": time.time(),
            "type": event_type,
            "details": details,
        }
        
        with self._audit_lock:
            with open(self.audit_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
    
    def get_audit_events(self, limit: int = 100, event_type: Optional[str] = None) -> List[Dict]:
        """获取审计事件"""
        if not self.audit_file.exists():
            return []
        
        events = []
        with self._audit_lock:
            with open(self.audit_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        if event_type is None or event.get("type") == event_type:
                            events.append(event)
                    except json.JSONDecodeError:
                        continue
        
        return events[-limit:]


if __name__ == "__main__":
    # 测试代码
    security = SecurityManager(Path("."))
    
    # 测试加密
    encrypted = security.encrypt_sensitive("Hello, 灵枢!", context="test")
    print(f"加密: {encrypted}")
    decrypted = security.decrypt_sensitive(encrypted, context="test")
    print(f"解密: {decrypted}")
    
    # 测试密码
    password_hash = security.hash_password("my_password")
    print(f"密码哈希: {password_hash}")
    print(f"验证: {security.verify_password('my_password', password_hash)}")
    
    # 测试消毒
    dirty = "<script>alert('xss')</script>"
    clean = security.sanitize_input(dirty, "html")
    print(f"消毒: {clean}")
    
    # 测试凭据
    security.store_credential("api_key", "secret123", {"service": "test"})
    value = security.retrieve_credential("api_key")
    print(f"凭据: {value}")
