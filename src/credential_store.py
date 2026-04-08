"""Fernet-based credential storage for guangdada.net login."""

import json
import os
from pathlib import Path

from cryptography.fernet import Fernet


CREDENTIAL_DIR = Path.home() / ".openclaw" / "credentials"
CREDENTIAL_FILE = CREDENTIAL_DIR / "guangdada.enc"
KEY_FILE = CREDENTIAL_DIR / ".guangdada.key"


def _ensure_dir():
    CREDENTIAL_DIR.mkdir(parents=True, exist_ok=True)


def _get_or_create_key() -> bytes:
    _ensure_dir()
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    return key


def save_credentials(username: str, password: str):
    key = _get_or_create_key()
    fernet = Fernet(key)
    payload = json.dumps({"username": username, "password": password}).encode()
    encrypted = fernet.encrypt(payload)
    _ensure_dir()
    CREDENTIAL_FILE.write_bytes(encrypted)


def load_credentials() -> dict | None:
    if not CREDENTIAL_FILE.exists() or not KEY_FILE.exists():
        return None
    key = KEY_FILE.read_bytes()
    fernet = Fernet(key)
    try:
        decrypted = fernet.decrypt(CREDENTIAL_FILE.read_bytes())
        return json.loads(decrypted)
    except Exception:
        return None


def clear_credentials():
    for f in (CREDENTIAL_FILE, KEY_FILE):
        if f.exists():
            f.unlink()
