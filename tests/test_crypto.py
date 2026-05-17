from pydeepseek_tui.config.crypto import encrypt_key, decrypt_key


class TestCrypto:
    def test_encrypt_decrypt_roundtrip(self):
        original = "sk-abcdefghijklmnop1234567890"
        encrypted = encrypt_key(original)
        assert encrypted != original
        assert decrypt_key(encrypted) == original

    def test_encrypt_produces_base64_output(self):
        key = "sk-fixed-key-for-test"
        encrypted = encrypt_key(key)
        assert len(encrypted) > 0
        assert encrypted != key
        # O output deve ser Fernet (base64 URL-safe)
        assert encrypted.startswith("g")

    def test_decrypt_invalid_raises(self):
        import pytest
        with pytest.raises(Exception):
            decrypt_key("dado-invalido-nao-encriptado")
