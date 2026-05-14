"""
config/crypto.py
================

Criptografia e descriptografia de API keys usando Fernet (AES-128-CBC + HMAC).
A master key é derivada de atributos da máquina local via PBKDF2-HMAC-SHA256,
sem necessidade de senha adicional do usuário.

Fluxo:
  1. Coleta machine-id + username como "segredo" da máquina
  2. Deriva uma chave Fernet com PBKDF2 (310.000 iterações — OWASP 2024)
  3. Usa a chave para cifrar/decifrar a API key
  4. O valor criptografado é salvo em ~/.deepseek-tui/.env como base64 URL-safe
"""

from __future__ import annotations

import base64
import hashlib
import os
import platform
import subprocess
import sys
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Salt fixo derivado do nome do pacote — não é segredo, apenas evita
# ataques de rainbow table genéricos. O segredo real é o machine-id.
_SALT: bytes = hashlib.sha256(b"pydeepseek-tui-v1").digest()

# Iterações PBKDF2 recomendadas pela OWASP para HMAC-SHA256 (2024)
_PBKDF2_ITERATIONS: int = 310_000


def _get_machine_secret() -> bytes:
    """
    Obtém um segredo único desta máquina combinando machine-id e username.

    Estratégia por plataforma:
    - Linux  : /etc/machine-id ou /var/lib/dbus/machine-id
    - macOS  : IOPlatformUUID via ioreg
    - Windows: MachineGuid via registro
    - Fallback: hostname + username (menos único, mas funcional)
    """
    username = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
    machine_id = _read_machine_id()
    secret = f"{machine_id}::{username}::pydeepseek-tui"
    return secret.encode("utf-8")


def _read_machine_id() -> str:
    """Lê o identificador único da máquina conforme o sistema operacional."""
    system = platform.system()

    if system == "Linux":
        for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            try:
                content = Path(path).read_text(encoding="utf-8").strip()
                if content:
                    return content
            except OSError:
                continue

    elif system == "Darwin":
        try:
            result = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.splitlines():
                if "IOPlatformUUID" in line:
                    parts = line.split('"')
                    if len(parts) >= 4:
                        return parts[-2]
        except (OSError, subprocess.TimeoutExpired):
            pass

    elif system == "Windows":
        try:
            result = subprocess.run(
                ["reg", "query", r"HKLM\SOFTWARE\Microsoft\Cryptography", "/v", "MachineGuid"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.splitlines():
                if "MachineGuid" in line:
                    return line.split()[-1]
        except (OSError, subprocess.TimeoutExpired):
            pass

    # Fallback universal
    return platform.node() or "fallback-node"


def _derive_fernet_key(secret: bytes) -> bytes:
    """
    Deriva uma chave Fernet (32 bytes) a partir do segredo da máquina
    usando PBKDF2-HMAC-SHA256.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=_PBKDF2_ITERATIONS,
    )
    raw_key = kdf.derive(secret)
    return base64.urlsafe_b64encode(raw_key)


def _get_fernet() -> Fernet:
    """Instancia o Fernet com a chave derivada da máquina atual."""
    secret = _get_machine_secret()
    key = _derive_fernet_key(secret)
    return Fernet(key)


def encrypt_api_key(api_key: str) -> str:
    """
    Cifra uma API key em texto plano e retorna a string criptografada.

    Args:
        api_key: A API key em texto plano (ex: "sk-xxxxxxxxxxxxxxxx")

    Returns:
        String criptografada em base64 URL-safe (segura para salvar no .env)

    Raises:
        ValueError: Se api_key for vazia
    """
    if not api_key or not api_key.strip():
        raise ValueError("A API key não pode ser vazia.")

    fernet = _get_fernet()
    encrypted_bytes = fernet.encrypt(api_key.strip().encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_api_key(encrypted_key: str) -> str:
    """
    Descriptografa uma API key previamente cifrada nesta máquina.

    Args:
        encrypted_key: String criptografada salva no .env

    Returns:
        API key em texto plano

    Raises:
        ValueError: Se a chave não puder ser descriptografada
                    (máquina diferente ou valor corrompido)
    """
    if not encrypted_key or not encrypted_key.strip():
        raise ValueError("A chave criptografada não pode ser vazia.")

    fernet = _get_fernet()
    try:
        decrypted_bytes = fernet.decrypt(encrypted_key.strip().encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except InvalidToken as exc:
        raise ValueError(
            "Não foi possível descriptografar a API key. "
            "Isso pode ocorrer se o arquivo .env foi copiado de outra máquina. "
            "Execute 'pydeepseek-tui config' para reconfigurar."
        ) from exc


def is_encrypted(value: str) -> bool:
    """
    Verifica heuristicamente se um valor parece ser uma chave Fernet cifrada.
    Tokens Fernet sempre começam com 'gAAAAA' após base64 URL-safe encoding.

    Args:
        value: String a verificar

    Returns:
        True se parecer um token Fernet válido
    """
    return bool(value and value.strip().startswith("gAAAAA") and len(value.strip()) > 50)


def mask_api_key(api_key: str) -> str:
    """
    Retorna uma versão mascarada da API key para exibição segura em logs/TUI.

    Exemplo: "sk-abc123xyz" → "sk-abc1****xyz"

    Args:
        api_key: API key em texto plano

    Returns:
        String mascarada
    """
    if not api_key:
        return "****"
    if len(api_key) <= 8:
        return "****"
    prefix = api_key[:6]
    suffix = api_key[-4:]
    return f"{prefix}****{suffix}"


if __name__ == "__main__":
    # Teste rápido de sanidade (não usar em produção)
    test_key = "sk-test-1234567890abcdef"
    print(f"Original:      {test_key}")

    encrypted = encrypt_api_key(test_key)
    print(f"Criptografado: {encrypted[:40]}...")

    decrypted = decrypt_api_key(encrypted)
    print(f"Decriptografado: {decrypted}")

    assert decrypted == test_key, "ERRO: descriptografia falhou!"
    print("✓ Criptografia OK")

    print(f"Mascarado: {mask_api_key(test_key)}")
    print(f"É cifrado (original): {is_encrypted(test_key)}")
    print(f"É cifrado (encrypted): {is_encrypted(encrypted)}")
    sys.exit(0)
