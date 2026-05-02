"""Security utilities for authentication and authorization"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT
security = HTTPBearer()


class SecurityService:
    """Security utilities for JWT and password management"""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password with bcrypt"""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def create_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None,
        token_type: str = "access"
    ) -> str:
        """
        Create JWT token

        Args:
            data: Token payload
            expires_delta: Token expiration time
            token_type: Token type (access or refresh)

        Returns:
            Encoded JWT token
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            if token_type == "access":
                expire = datetime.now(timezone.utc) + timedelta(
                    minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
                )
            else:  # refresh token
                expire = datetime.now(timezone.utc) + timedelta(
                    days=settings.REFRESH_TOKEN_EXPIRE_DAYS
                )

        to_encode.update({"exp": expire, "type": token_type})

        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )

        return encoded_jwt

    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Dict[str, Any]:
        """
        Verify JWT token

        Args:
            token: JWT token
            token_type: Expected token type

        Returns:
            Token payload

        Raises:
            HTTPException: If token is invalid
        """
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )

            # Verify token type
            if payload.get("type") != token_type:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type",
                )

            return payload

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

    @staticmethod
    def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
        """
        Get current user from JWT token

        Can be used as a dependency in FastAPI routes
        """
        token = credentials.credentials
        payload = SecurityService.verify_token(token, token_type="access")
        user_id = payload.get("sub")

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        return {"user_id": user_id, "email": payload.get("email")}
