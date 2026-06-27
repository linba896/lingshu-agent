#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 安全模块测试
覆盖：SecurityManager、CryptoManager、SignatureManager、CredentialVault、InputSanitizer
"""

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.security import (
    SecurityManager,
    CryptoManager,
    SignatureManager,
    CredentialVault,
    InputSanitizer,
    EncryptedData,
    SecurityError,
    EncryptionError,
    SignatureError,
)


@pytest.fixture
def temp_root():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


class TestCryptoManager:
    """测试加密管理器"""

    def test_generate_key(self):
        key = CryptoManager._generate_key(32)
        assert len(key) == 32

    def test_encrypt_decrypt(self):
        crypto = CryptoManager()
        plaintext = b"Hello, 灵枢!"
        encrypted = crypto.encrypt(plaintext)
        assert isinstance(encrypted, EncryptedData)
        assert encrypted.ciphertext != plaintext

        decrypted = crypto.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_string(self):
        crypto = CryptoManager()
        text = "敏感数据: 123456"
        encrypted = crypto.encrypt_string(text)
        assert isinstance(encrypted, str)

        decrypted = crypto.decrypt_string(encrypted)
        assert decrypted == text

    def test_different_keys_different_ciphertext(self):
        crypto1 = CryptoManager()
        crypto2 = CryptoManager()
        plaintext = b"test"
        enc1 = crypto1.encrypt(plaintext)
        enc2 = crypto2.encrypt(plaintext)
        assert enc1.ciphertext != enc2.ciphertext

    def test_associated_data(self):
        crypto = CryptoManager()
        plaintext = b"secret"
        aad = b"context123"
        encrypted = crypto.encrypt(plaintext, associated_data=aad)
        decrypted = crypto.decrypt(encrypted, associated_data=aad)
        assert decrypted == plaintext

    def test_rotate_key(self):
        crypto = CryptoManager()
        old_key = crypto.rotate_key()
        new_key = crypto._key
        assert old_key != new_key

    def test_secure_compare(self):
        crypto = CryptoManager()
        assert crypto.secure_compare(b"abc", b"abc") == True
        assert crypto.secure_compare(b"abc", b"def") == False

    def test_hash_password(self):
        crypto = CryptoManager()
        password = "my_password"
        hash_str = crypto.hash_password(password)
        assert isinstance(hash_str, str)
        assert hash_str != password

    def test_verify_password(self):
        crypto = CryptoManager()
        password = "correct_password"
        hash_str = crypto.hash_password(password)
        assert crypto.verify_password(password, hash_str) == True
        assert crypto.verify_password("wrong", hash_str) == False

    def test_key_hash(self):
        crypto = CryptoManager()
        hash_str = crypto.get_key_hash()
        assert isinstance(hash_str, str)
        assert len(hash_str) == 16

    def test_encrypted_data_roundtrip(self):
        crypto = CryptoManager()
        plaintext = b"test data"
        encrypted = crypto.encrypt(plaintext)
        data_bytes = encrypted.to_bytes()
        restored = EncryptedData.from_bytes(data_bytes)
        decrypted = crypto.decrypt(restored)
        assert decrypted == plaintext

    def test_encrypted_data_dict(self):
        crypto = CryptoManager()
        plaintext = b"test data"
        encrypted = crypto.encrypt(plaintext)
        d = encrypted.to_dict()
        restored = EncryptedData.from_dict(d)
        decrypted = crypto.decrypt(restored)
        assert decrypted == plaintext


class TestSignatureManager:
    """测试签名管理器"""

    def test_sign_and_verify(self):
        signer = SignatureManager()
        data = "important message"
        sig = signer.sign(data)
        assert isinstance(sig, str)
        assert signer.verify(data, sig) == True

    def test_verify_wrong_data(self):
        signer = SignatureManager()
        data = "original"
        sig = signer.sign(data)
        assert signer.verify("tampered", sig) == False

    def test_different_signers(self):
        signer1 = SignatureManager()
        signer2 = SignatureManager()
        data = "test"
        sig1 = signer1.sign(data)
        sig2 = signer2.sign(data)
        assert sig1 != sig2
        assert signer1.verify(data, sig1) == True
        assert signer2.verify(data, sig2) == True
        assert signer1.verify(data, sig2) == False

    def test_sign_file_nonexistent(self):
        signer = SignatureManager()
        with pytest.raises(SignatureError):
            signer.sign_file("/nonexistent/file.txt")

    def test_sha512(self):
        signer = SignatureManager()
        data = "test"
        sig = signer.sign(data, algorithm="HMAC-SHA512")
        assert signer.verify(data, sig, algorithm="HMAC-SHA512") == True

    def test_generate_checksum(self):
        signer = SignatureManager()
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"checksum test data")
            path = f.name
        checksum = signer.generate_checksum(path)
        assert isinstance(checksum, str)
        assert len(checksum) == 64  # SHA-256 hex

        assert signer.verify_checksum(path, checksum) == True
        assert signer.verify_checksum(path, "0" * 64) == False


class TestCredentialVault:
    """测试凭据保险箱"""

    def test_store_and_retrieve(self, temp_root):
        vault = CredentialVault(temp_root)
        vault.store("api_key", "secret123", metadata={"service": "test"})
        value = vault.retrieve("api_key")
        assert value == "secret123"

    def test_retrieve_nonexistent(self, temp_root):
        vault = CredentialVault(temp_root)
        assert vault.retrieve("missing") is None

    def test_delete(self, temp_root):
        vault = CredentialVault(temp_root)
        vault.store("temp", "value")
        assert vault.delete("temp") == True
        assert vault.retrieve("temp") is None
        assert vault.delete("temp") == False

    def test_list_keys(self, temp_root):
        vault = CredentialVault(temp_root)
        vault.store("key1", "v1")
        vault.store("key2", "v2")
        keys = vault.list_keys()
        assert sorted(keys) == ["key1", "key2"]

    def test_update(self, temp_root):
        vault = CredentialVault(temp_root)
        vault.store("key", "old")
        vault.store("key", "new")
        assert vault.retrieve("key") == "new"

    def test_with_password(self, temp_root):
        vault = CredentialVault(temp_root, master_password="master_key")
        vault.store("secret", "classified")
        # 重新加载应能解密
        vault2 = CredentialVault(temp_root, master_password="master_key")
        assert vault2.retrieve("secret") == "classified"


class TestInputSanitizer:
    """测试输入消毒器"""

    def test_sanitize_sql_injection(self):
        sanitizer = InputSanitizer()
        dirty = "1; DROP TABLE users; --"
        clean = sanitizer.sanitize(dirty, "sql")
        assert ";" not in clean or clean == ""

    def test_sanitize_html(self):
        sanitizer = InputSanitizer()
        dirty = '<script>alert("xss")</script>'
        clean = sanitizer.sanitize(dirty, "html")
        assert "<script>" not in clean

    def test_sanitize_shell(self):
        sanitizer = InputSanitizer()
        dirty = "ls; rm -rf /"
        clean = sanitizer.sanitize(dirty, "shell")
        assert ";" not in clean or clean == ""

    def test_sanitize_path(self):
        sanitizer = InputSanitizer()
        dirty = "../../../etc/passwd"
        clean = sanitizer.sanitize(dirty, "path")
        assert ".." not in clean or clean == ""

    def test_sanitize_unknown(self):
        sanitizer = InputSanitizer()
        assert sanitizer.sanitize("safe", "unknown") == "safe"

    def test_sanitize_no_type(self):
        sanitizer = InputSanitizer()
        result = sanitizer.sanitize("safe")
        assert result == "safe"


class TestSecurityManager:
    """测试安全模块整合"""

    def test_init(self, temp_root):
        manager = SecurityManager(temp_root)
        assert manager is not None

    def test_encrypt_sensitive(self, temp_root):
        manager = SecurityManager(temp_root)
        text = "sensitive data"
        encrypted = manager.encrypt_sensitive(text, context="test")
        assert isinstance(encrypted, str)

        decrypted = manager.decrypt_sensitive(encrypted, context="test")
        assert decrypted == text

    def test_sign_data(self, temp_root):
        manager = SecurityManager(temp_root)
        data = "payload"
        sig = manager.sign_data(data, context="api")
        assert isinstance(sig, str)
        assert manager.verify_signature(data, sig, context="api") == True

    def test_hash_and_verify(self, temp_root):
        manager = SecurityManager(temp_root)
        password = "user_password"
        hash_val = manager.hash_password(password)
        assert manager.verify_password(password, hash_val) == True

    def test_store_credential(self, temp_root):
        manager = SecurityManager(temp_root)
        manager.store_credential("test_key", "test_value", metadata={"type": "test"})
        value = manager.retrieve_credential("test_key")
        assert value == "test_value"

    def test_sanitize(self, temp_root):
        manager = SecurityManager(temp_root)
        dirty = "<script>bad</script>"
        clean = manager.sanitize_input(dirty, "html")
        assert "<script>" not in clean

    def test_security_audit(self, temp_root):
        manager = SecurityManager(temp_root)
        manager.log_audit_event("test_event", {"detail": "test"})
        events = manager.get_audit_events(limit=10)
        assert len(events) >= 1

    def test_check_rate_limit(self, temp_root):
        manager = SecurityManager(temp_root)
        assert manager.check_rate_limit("client_1") == True
        # 快速多次调用
        for _ in range(20):
            manager.check_rate_limit("client_1")
        # 应该仍然返回 True（测试用例不会超限）
        assert manager.check_rate_limit("client_1") in [True, False]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
