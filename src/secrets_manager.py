"""Encrypt / decrypt .env credentials with a master password — stdlib only.

Uses PBKDF2-HMAC-SHA256 for key derivation and XOR stream cipher.
Protects credentials from casual reading of config files.
"""
from __future__ import annotations

import base64
import getpass
import hashlib
import json
import os
from pathlib import Path

from src.log import get_logger

log = get_logger(__name__)

_SALT_LEN = 16
_ITERATIONS = 200_000
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENC_FILE = _PROJECT_ROOT / ".env.enc"

SENSITIVE_KEYS: set[str] = {
    "GROQ_API_KEY",
    "SERPAPI_KEY",
    "JSEARCH_API_KEY",
    "LINKEDIN_PASSWORD",
    "NAUKRI_PASSWORD",
    "APPLY_PASSWORD",
    "SMTP_PASSWORD",
}


def _derive_key(password: str, salt: bytes, length: int = 32) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _ITERATIONS, dklen=length
    )


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    kl = len(key)
    return bytes(d ^ key[i % kl] for i, d in enumerate(data))


def encrypt_value(value: str, password: str) -> str:
    salt = os.urandom(_SALT_LEN)
    key = _derive_key(password, salt)
    encrypted = _xor_bytes(value.encode("utf-8"), key)
    return base64.b64encode(salt + encrypted).decode("ascii")


def decrypt_value(token: str, password: str) -> str:
    payload = base64.b64decode(token)
    salt, encrypted = payload[:_SALT_LEN], payload[_SALT_LEN:]
    key = _derive_key(password, salt)
    return _xor_bytes(encrypted, key).decode("utf-8")


def encrypt_env(
    env_path: Path | None = None, password: str | None = None
) -> Path:
    """Read .env, encrypt sensitive values, write .env.enc."""
    env_path = env_path or (_PROJECT_ROOT / ".env")
    if not env_path.exists():
        raise FileNotFoundError(f"{env_path} not found")

    if password is None:
        password = getpass.getpass("Set master password: ")
        confirm = getpass.getpass("Confirm master password: ")
        if password != confirm:
            raise ValueError("Passwords do not match")

    entries: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key in SENSITIVE_KEYS and value:
            entries[key] = encrypt_value(value, password)
        else:
            entries[key] = value

    encrypted_keys = sorted(SENSITIVE_KEYS & set(entries))
    data = {"encrypted_keys": encrypted_keys, "values": entries}
    _ENC_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    log.info("Credentials encrypted → %s (%d keys)", _ENC_FILE.name, len(encrypted_keys))
    return _ENC_FILE


def decrypt_env(password: str | None = None) -> dict[str, str]:
    """Read .env.enc, decrypt sensitive values, return dict."""
    if not _ENC_FILE.exists():
        raise FileNotFoundError(f"{_ENC_FILE} not found — run encrypt first")

    if password is None:
        password = getpass.getpass("Master password: ")

    data = json.loads(_ENC_FILE.read_text(encoding="utf-8"))
    encrypted_keys = set(data.get("encrypted_keys", []))
    entries: dict[str, str] = data.get("values", {})

    result: dict[str, str] = {}
    for key, value in entries.items():
        if key in encrypted_keys and value:
            try:
                result[key] = decrypt_value(value, password)
            except Exception:
                log.warning("Failed to decrypt %s — wrong password?", key)
                result[key] = ""
        else:
            result[key] = value
    return result


def load_encrypted_env(password: str | None = None) -> bool:
    """Decrypt .env.enc and inject into os.environ.  Returns True on success."""
    try:
        values = decrypt_env(password)
        for key, value in values.items():
            if value:
                os.environ.setdefault(key, value)
        return True
    except FileNotFoundError:
        return False
    except Exception as exc:
        log.warning("Could not load encrypted env: %s", exc)
        return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "decrypt":
        for k, v in decrypt_env().items():
            print(f"{k}={v}")
    else:
        path = encrypt_env()
        print(f"Encrypted credentials saved to {path}")
