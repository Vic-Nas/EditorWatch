import os
import json
from cryptography.fernet import Fernet
import gzip
import base64
import hashlib


def _get_cipher():
    key = os.environ.get('ENCRYPTION_KEY')
    if not key:
        key = Fernet.generate_key()
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt_data(data):
    cipher = _get_cipher()
    return cipher.encrypt(json.dumps(data).encode()).decode()


def decrypt_data(encrypted):
    cipher = _get_cipher()
    return json.loads(cipher.decrypt(encrypted.encode()).decode())


def get_events_from_submission(submission):
    """
    Decrypt and return event data from a Submission.
    Always returns compact format: { base_time: int, events: [[delta_ms, type, file, char_count], ...] }
    """
    if not submission or not getattr(submission, 'events_encrypted', None):
        return {'base_time': 0, 'events': []}
    try:
        data = decrypt_data(submission.events_encrypted)
        if isinstance(data, dict) and 'base_time' in data:
            return data
        return {'base_time': 0, 'events': []}
    except Exception:
        return {'base_time': 0, 'events': []}


def files_from_events(event_data):
    """
    Return sorted list of unique basenames from compact event data.
    Each event: [delta_ms, type, filename, char_count]
    """
    events = event_data.get('events', [])
    return sorted({e[2] for e in events if len(e) > 2 and e[2]})


def compress_text_to_b64(text: str) -> str:
    """Gzip-compress a UTF-8 string and return base64-encoded bytes as str."""
    if text is None:
        return ''
    compressed = gzip.compress(text.encode('utf-8'))
    return base64.b64encode(compressed).decode('ascii')


def decompress_b64_to_text(b64: str) -> str:
    """Decode base64 then gunzip to UTF-8 string."""
    if not b64:
        return ''
    raw = base64.b64decode(b64)
    return gzip.decompress(raw).decode('utf-8')


def sha256_of_b64(b64: str) -> str:
    """Return hex SHA256 of the decoded base64 bytes."""
    try:
        data = base64.b64decode(b64)
    except Exception:
        data = b''
    return hashlib.sha256(data).hexdigest()