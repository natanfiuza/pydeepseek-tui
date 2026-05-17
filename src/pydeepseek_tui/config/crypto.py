import base64
import getpass
import uuid
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

def _get_machine_id() -> str:
    """Gera um identificador único combinando o usuário e o hardware."""
    user = getpass.getuser()
    node = str(uuid.getnode())
    return f"{user}-{node}"

def _get_fernet() -> Fernet:
    """Deriva a chave mestra da máquina e inicializa o algoritmo Fernet."""
    machine_id = _get_machine_id().encode()
    salt = b"pydeepseek_tui_salt_v1" # Salt estático para manter consistência local
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(machine_id))
    return Fernet(key)

def encrypt_key(api_key: str) -> str:
    """Criptografa a chave da API em texto plano."""
    f = _get_fernet()
    return f.encrypt(api_key.encode()).decode()

def decrypt_key(encrypted_key: str) -> str:
    """Descriptografa a chave da API de volta para texto plano."""
    f = _get_fernet()
    return f.decrypt(encrypted_key.encode()).decode()