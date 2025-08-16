import base64
import hmac
import os
import time
from hashlib import sha256
from math import radians, cos, sin, asin, sqrt


def get_secret_key() -> str:
    return os.getenv("SECRET_KEY", "dev_secret_change_me")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def time_window_step(window_seconds: int = 30) -> int:
    return int(time.time() // window_seconds)


def generate_qr_token(lecture_id: int, window_seconds: int = 30) -> str:
    step = time_window_step(window_seconds)
    secret = get_secret_key().encode()
    msg = f"lecture:{lecture_id}:step:{step}".encode()
    digest = hmac.new(secret, msg, sha256).digest()
    return _b64url(digest[:16])


def is_valid_qr_token(token: str, lecture_id: int, window_seconds: int = 30, drift_windows: int = 1) -> bool:
    secret = get_secret_key().encode()
    now_step = time_window_step(window_seconds)
    for offset in range(-drift_windows, drift_windows + 1):
        step = now_step + offset
        msg = f"lecture:{lecture_id}:step:{step}".encode()
        digest = hmac.new(secret, msg, sha256).digest()
        candidate = _b64url(digest[:16])
        if hmac.compare_digest(candidate, token):
            return True
    return False


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # Radius of Earth in meters
    R = 6371000.0

    phi1 = radians(lat1)
    phi2 = radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)

    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    c = 2 * asin(sqrt(a))

    return R * c