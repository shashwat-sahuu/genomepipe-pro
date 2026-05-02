"""Authentication routes"""
import logging
from datetime import timedelta
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session

from app.models.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserResponse,
    ErrorResponse,
)
from app.models.database import User
from app.models.db_manager import get_db
from app.utils.security import SecurityService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse)
async def register(
    request: UserRegisterRequest,
    db: Session = Depends(get_db)
) -> UserResponse:
    """
    Register a new user

    Returns:
        User information
    """
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    existing_username = db.query(User).filter(User.username == request.username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )

    # Hash password
    hashed_password = SecurityService.hash_password(request.password)

    # Create user
    new_user = User(
        email=request.email,
        username=request.username,
        password_hash=hashed_password,
        full_name=request.full_name,
        is_active=True
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info(f"New user registered: {new_user.email}")

    return UserResponse(
        id=new_user.id,
        email=new_user.email,
        username=new_user.username,
        full_name=new_user.full_name,
        is_active=new_user.is_active,
        created_at=new_user.created_at,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: UserLoginRequest,
    db: Session = Depends(get_db)
) -> TokenResponse:
    """
    User login with email and password

    Returns:
        JWT access and refresh tokens
    """
    # Find user by email
    user = db.query(User).filter(User.email == request.email).first()

    if not user or not SecurityService.verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )

    # Create tokens
    access_token_expires = timedelta(minutes=30)
    access_token = SecurityService.create_token(
        data={"sub": user.id, "email": user.email},
        expires_delta=access_token_expires,
        token_type="access"
    )

    refresh_token = SecurityService.create_token(
        data={"sub": user.id, "email": user.email},
        token_type="refresh"
    )

    logger.info(f"User logged in: {user.email}")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=1800  # 30 minutes
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: dict,
    db: Session = Depends(get_db)
) -> TokenResponse:
    """
    Refresh access token using refresh token

    Request body:
        - refresh_token: Refresh token

    Returns:
        New access token
    """
    refresh_token_str = request.get("refresh_token")

    if not refresh_token_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh token required"
        )

    # Verify refresh token
    payload = SecurityService.verify_token(refresh_token_str, token_type="refresh")
    user_id = payload.get("sub")

    # Get user
    user = db.query(User).filter(User.id == user_id).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    # Create new access token
    access_token_expires = timedelta(minutes=30)
    new_access_token = SecurityService.create_token(
        data={"sub": user.id, "email": user.email},
        expires_delta=access_token_expires,
        token_type="access"
    )

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=refresh_token_str,
        token_type="bearer",
        expires_in=1800
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: dict = Depends(SecurityService.get_current_user),
    db: Session = Depends(get_db)
) -> UserResponse:
    """
    Get current user information

    Returns:
        User information
    """
    user = db.query(User).filter(User.id == current_user["user_id"]).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post("/logout")
async def logout(current_user: dict = Depends(SecurityService.get_current_user)):
    """
    Logout user (invalidate tokens on client side)

    Note: Token invalidation is handled client-side in production.
    For production, implement token blacklist or use short-lived tokens.
    """
    logger.info(f"User logged out: {current_user['email']}")

    return {
        "message": "Logged out successfully",
        "user_id": current_user["user_id"]
    }
