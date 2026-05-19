from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from app.core.config import settings

# Setup password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """Generates a secure cryptographically hashed password representation.
    
    Args:
        password (str): Plaintext password string.
        
    Returns:
        str: Hashed password string.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against its stored cryptographic hash.
    
    Args:
        plain_password (str): Input plaintext password.
        hashed_password (str): Stored bcrypt hash.
        
    Returns:
        bool: True if passwords match, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a signed JSON Web Token (JWT) containing the user subject.
    
    Args:
        subject (str): The unique subject identifier (e.g. user UUID string).
        expires_delta (Optional[timedelta]): Token lifespan interval.
        
    Returns:
        str: Encrypted JWT string.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "iat": datetime.now(timezone.utc)
    }
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates an incoming JWT token against signature and expiration.
    
    Args:
        token (str): Signed JWT token string.
        
    Returns:
        Optional[Dict[str, Any]]: Decoded payload claims dictionary, or None if validation fails.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
