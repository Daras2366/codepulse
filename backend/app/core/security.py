from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta, timezone
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import bcrypt

from app.core.config import settings

# Direct Argon2 hasher for new passwords
argon2_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hash a password using Argon2."""
    return argon2_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash.
    Supports both bcrypt (legacy) and argon2 hashes.
    Returns True if verification succeeds, False otherwise.
    """
    # Try Argon2 first (newer, more secure)
    if hashed_password.startswith("$argon2"):
        try:
            argon2_hasher.verify(hashed_password, plain_password)
            return True
        except VerifyMismatchError:
            return False
        except Exception:
            return False

    # Try bcrypt (legacy)
    if hashed_password.startswith("$2"):
        try:
            # bcrypt has a 72-byte limit - encode as UTF-8 and truncate at 72 bytes
            # This preserves the historical bcrypt behavior
            password_bytes = plain_password.encode("utf-8")
            if len(password_bytes) > 72:
                password_bytes = password_bytes[:72]

            # Use bcrypt directly for verification
            return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
        except Exception:
            return False

    # Unknown hash format
    return False


def needs_rehash(hashed_password: str) -> bool:
    """Check if a password hash needs to be upgraded to Argon2."""
    return not hashed_password.startswith("$argon2")


def create_access_token(data: dict):

    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    return encoded_jwt