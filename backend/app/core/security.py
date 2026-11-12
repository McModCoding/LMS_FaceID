import secrets
import string
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from threading import Lock

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# In-memory rate limiter per IP+username
_login_attempts: dict[str, list[datetime]] = defaultdict(list)
_lock = Lock()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def generate_temp_password(length: int = 10) -> str:
    """Generate a random temporary password containing letters and digits."""
    length = max(length, 8)
    alphabet = string.ascii_letters + string.digits
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(c.isalpha() for c in password) and any(c.isdigit() for c in password):
            return password


def is_rate_limited(key: str) -> bool:
    """Kiểm tra xem key (IP+username) có vượt quá giới hạn 5 lần đăng nhập sai trong 15 phút hay không."""
    now = datetime.now(UTC)
    window = timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
    with _lock:
        attempts = _login_attempts[key]
        _login_attempts[key] = [t for t in attempts if now - t < window]
        return len(_login_attempts[key]) >= settings.LOGIN_MAX_ATTEMPTS


def record_failed_attempt(key: str) -> None:
    with _lock:
        _login_attempts[key].append(datetime.now(UTC))


def clear_attempts(key: str) -> None:
    with _lock:
        _login_attempts.pop(key, None)
