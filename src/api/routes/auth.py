"""
Authentication routes for FORGE-Vision.

Endpoints:
    POST /api/v1/auth/register        — create account
    POST /api/v1/auth/login           — issue tokens (or pre-auth token if MFA required)
    POST /api/v1/auth/logout          — clear refresh cookie
    POST /api/v1/auth/refresh         — exchange refresh cookie for new access token
    POST /api/v1/auth/forgot-password — request password reset link
    POST /api/v1/auth/reset-password  — set new password using reset token
    POST /api/v1/auth/verify-mfa      — complete TOTP MFA, receive full tokens
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import pyotp
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.limiter import limiter
from src.api.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MFAVerifyRequest,
    PreAuthResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)
from src.config import settings
from src.database.database import get_db
from src.database.models import User, UserRole
from src.intelligence.crypto import decrypt_api_key

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# A static hash used for timing-safe checks when the user does not exist.
# Computed once at module load — never used as a real password.
_DUMMY_HASH = pwd_context.hash("dummy-password-for-timing-safety")


# ── Internal helpers ──────────────────────────────────────────────────────────

def _hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _create_token(user_id: int, token_type: str, expire_delta: timedelta) -> str:
    expire = datetime.now(timezone.utc) + expire_delta
    return jwt.encode(
        {"sub": str(user_id), "type": token_type, "exp": expire},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def _create_access_token(user_id: int) -> str:
    return _create_token(
        user_id, "access", timedelta(minutes=settings.JWT_ACCESS_EXPIRE_MINUTES)
    )


def _create_refresh_token(user_id: int) -> str:
    return _create_token(
        user_id, "refresh", timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)
    )


def _create_pre_auth_token(user_id: int) -> str:
    """Short-lived token for the MFA step — NOT usable for API access."""
    return _create_token(user_id, "pre_auth", timedelta(minutes=5))


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        max_age=settings.JWT_REFRESH_EXPIRE_DAYS * 86400,
        path="/api/v1/auth/refresh",  # scoped to refresh endpoint only
    )


def _hash_reset_token(plain_token: str) -> str:
    return hashlib.sha256(plain_token.encode()).hexdigest()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Validate a Bearer access token and return the current user. Used by Streamlit token handoff."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token = authorization[len("Bearer "):]
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id: str | None = payload.get("sub")
        if not user_id or payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return UserResponse.model_validate(user)


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
@limiter.limit("5/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Create a new user account. GDPR consent required."""
    # Check email uniqueness
    existing = await db.execute(select(User).where(User.email == body.email.lower()))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists",
        )

    user = User(
        email=body.email.lower(),
        first_name=body.first_name.strip(),
        last_name=body.last_name.strip(),
        password_hash=_hash_password(body.password),
        role=UserRole.staff,  # default role; admin can elevate later
        department=body.department.strip() if body.department else None,
        gdpr_consent=True,
        consent_given_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()  # assigns user.id before commit
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate with email + password.
    Returns AuthResponse (full tokens) or PreAuthResponse (MFA required).
    """
    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()

    # Always run a password verification to prevent timing-based user enumeration.
    password_ok = _verify_password(
        body.password,
        user.password_hash if user is not None else _DUMMY_HASH,
    )

    if user is None or not password_ok or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Update last login
    user.last_login = datetime.now(timezone.utc)
    await db.flush()

    # MFA required for admin / supervisor when enabled
    if user.mfa_enabled and user.role in (UserRole.admin, UserRole.manager):
        pre_auth_token = _create_pre_auth_token(user.id)
        return PreAuthResponse(pre_auth_token=pre_auth_token)

    # Full authentication — issue tokens
    access_token = _create_access_token(user.id)
    refresh_token = _create_refresh_token(user.id)
    _set_refresh_cookie(response, refresh_token)

    return AuthResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/logout")
async def logout(response: Response):
    """Clear the refresh token cookie."""
    response.delete_cookie(key="refresh_token", path="/api/v1/auth/refresh")
    return {"message": "Logged out successfully"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Exchange a valid refresh token cookie for a new access token."""
    if refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )
    try:
        payload = jwt.decode(
            refresh_token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        if user_id is None or token_type != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Rotate refresh token (sliding window)
    new_access_token = _create_access_token(user.id)
    new_refresh_token = _create_refresh_token(user.id)
    _set_refresh_cookie(response, new_refresh_token)

    return TokenResponse(access_token=new_access_token)


@router.post("/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Request a password reset link.
    Always returns HTTP 200 regardless of whether the email exists
    (prevents user enumeration).
    """
    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()

    if user is not None and user.is_active:
        plain_token = secrets.token_urlsafe(32)
        user.password_reset_token_hash = _hash_reset_token(plain_token)
        user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        await db.flush()

        from src.api.services.email_service import send_password_reset_email
        await send_password_reset_email(to_email=user.email, token=plain_token)

    return {"message": "If that email is registered, a reset link has been sent"}


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Set a new password using a valid reset token."""
    token_hash = _hash_reset_token(body.token)
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(User).where(
            User.password_reset_token_hash == token_hash,
            User.password_reset_expires_at > now,
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user.password_hash = _hash_password(body.new_password)
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    await db.flush()

    return {"message": "Password reset successfully"}


@router.post("/verify-mfa")
@limiter.limit("5/minute")
async def verify_mfa(
    request: Request,
    body: MFAVerifyRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Complete the MFA step for accounts with TOTP enabled.
    Exchanges a valid pre_auth_token + TOTP code for full access/refresh tokens.
    """
    # Validate pre-auth token
    try:
        payload = jwt.decode(
            body.pre_auth_token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        if user_id is None or token_type != "pre_auth":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or not user.mfa_secret_enc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="MFA not configured")

    # Decrypt TOTP secret and verify code
    totp_secret = decrypt_api_key(user.mfa_secret_enc)
    totp = pyotp.TOTP(totp_secret)
    if not totp.verify(body.totp_code, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA code",
        )

    user.last_login = datetime.now(timezone.utc)
    await db.flush()

    access_token = _create_access_token(user.id)
    refresh_token_value = _create_refresh_token(user.id)
    _set_refresh_cookie(response, refresh_token_value)

    return AuthResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user),
    )
