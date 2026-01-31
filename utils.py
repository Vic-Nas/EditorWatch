import os
import json
from cryptography.fernet import Fernet


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
    """Safely return event list from a Submission object (may be encrypted or empty)."""
    if not submission or not getattr(submission, 'events_encrypted', None):
        return []
    try:
        return decrypt_data(submission.events_encrypted)
    except Exception:
        return []


def files_from_events(events):
    """Return normalized set/list of basenames touched in events."""
    files = { (e.get('file') or '').split('/')[-1] for e in events if e.get('file') }
    return sorted(f for f in files if f)
