"""
Pydantic schemas for Auth API requests and responses.
"""
import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """Request body for POST /api/v1/auth/register."""
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    department: str | None = Field(default=None, max_length=150)
    gdpr_consent: bool

    @field_validator("gdpr_consent")
    @classmethod
    def consent_must_be_given(cls, v: bool) -> bool:
        if not v:
            raise ValueError("GDPR consent is required to create an account")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    """Request body for POST /api/v1/auth/login."""
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    """Request body for POST /api/v1/auth/forgot-password."""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Request body for POST /api/v1/auth/reset-password."""
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class MFAVerifyRequest(BaseModel):
    """Request body for POST /api/v1/auth/verify-mfa."""
    totp_code: str = Field(..., min_length=6, max_length=6)
    pre_auth_token: str


# ── Response schemas ──────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    """Serialised user — safe to return to client (no secrets)."""
    id: int
    email: str
    first_name: str
    last_name: str
    role: str
    department: str | None
    mfa_enabled: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("role", mode="before")
    @classmethod
    def extract_role_value(cls, v):
        # UserRole enum → string
        return v.value if hasattr(v, "value") else v


class AuthResponse(BaseModel):
    """Returned by /login or /verify-mfa when authentication is complete."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    requires_mfa: bool = False


class PreAuthResponse(BaseModel):
    """Returned by /login when the account has MFA enabled.
    The client must complete MFA at /verify-mfa before receiving a full token."""
    pre_auth_token: str
    requires_mfa: bool = True


class TokenResponse(BaseModel):
    """Returned by /refresh — new access token only."""
    access_token: str
    token_type: str = "bearer"
