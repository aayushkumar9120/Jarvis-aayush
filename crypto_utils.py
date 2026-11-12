"""Encryption + password hashing helpers for Jarvis.

* Chat history is encrypted at rest with Fernet (AES-128-CBC + HMAC) when the
  `cryptography` package is installed. Without it, Jarvis keeps working but
  stores plain text (and tells you in the sidebar).
* Passwords are hashed with PBKDF2-HMAC-SHA256 (stdlib only).

Key storage: env var JARVIS_ENCRYPTION_KEY, otherwise a local `.jarvis_key`
file that is created on first run. BACK THAT FILE UP - without it, old
encrypted history cannot be read.
"""
import hashlib
import hmac
import os
import secrets

try:
    from cryptography.fernet import Fernet, InvalidToken
    HAS_CRYPTO = True
except ImportError:  # pragma: no cover
    HAS_CRYPTO = False

KEY_FILE = ".jarvis_key"
ENC_PREFIX = "enc:v1:"
PBKDF_ITERS = 200_000
_fernet = None


def _get_fernet():
    global _fernet
    if not HAS_CRYPTO:
        return None
    if _fernet is not None:
        return _fernet
    key = os.environ.get("JARVIS_ENCRYPTION_KEY")
    if not key:
        if os.path.exists(KEY_FILE):
            with open(KEY_FILE, "rb") as f:
                key = f.read().strip()
        else:
            key = Fernet.generate_key()
            with open(KEY_FILE, "wb") as f:
                f.write(key)
            try:
                os.chmod(KEY_FILE, 0o600)
            except OSError:
                pass
    if isinstance(key, str):
        key = key.encode()
    _fernet = Fernet(key)
    return _fernet


def encryption_active() -> bool:
    try:
        return _get_fernet() is not None
    except Exception:
        return False


def encrypt_text(text: str) -> str:
    f = _get_fernet()
    if f is None or text is None:
        return text
    return ENC_PREFIX + f.encrypt(text.encode("utf-8")).decode("ascii")


def decrypt_text(token: str) -> str:
    if not isinstance(token, str) or not token.startswith(ENC_PREFIX):
        return token
    f = _get_fernet()
    if f is None:
        return "[encrypted - install `cryptography` to read]"
    try:
        return f.decrypt(token[len(ENC_PREFIX):].encode("ascii")).decode("utf-8")
    except InvalidToken:
        return "[unreadable - encryption key does not match]"


# ---------------- passwords ----------------
def is_hashed(value) -> bool:
    return isinstance(value, str) and value.startswith("pbkdf2$")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF_ITERS)
    return f"pbkdf2${PBKDF_ITERS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored) -> bool:
    if not is_hashed(stored):  # legacy plain-text entry (auto-migrated on startup)
        return hmac.compare_digest(password.encode("utf-8"), str(stored).encode("utf-8"))
    try:
        _, iters, salt_hex, dk_hex = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(calc.hex(), dk_hex)
    except Exception:
        return False
