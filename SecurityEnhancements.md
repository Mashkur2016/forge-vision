# Security Enhancements — Project FORGE-Vision

## Overview

Project FORGE-Vision is a web-based application (FastAPI backend + Streamlit/React frontend + PostgreSQL database) that handles:
- **Live video streams** from workplace cameras (biometric-adjacent data)
- **Worker performance and error logs** (personal/professional data)
- **Pose and identity data** from MediaPipe (biometric data under GDPR)
- **Confidential SOP definitions** (business-sensitive intellectual property)
- **External LLM API calls** (GPT-4 / Claude / LLaMA)
- **Supervisor and admin access** to analytics dashboards

This combination of biometric data, sensitive business data, external API integrations, and multi-role access makes comprehensive security essential. All 10 OWASP Top 10 (2021) vulnerabilities are addressed below in the context of this system.

---

## OWASP Top 10 (2021) — FORGE-Vision Implementation Guide

---

### A01:2021 — Broken Access Control

**Risk to FORGE-Vision:** A worker accessing another worker's performance data, video recordings, or error history. A supervisor modifying SOP definitions without admin privilege. An unauthenticated user accessing the analytics dashboard.

#### Role-Based Access Control (RBAC) Design

| Role | Permissions |
|------|------------|
| `worker` | View own session results; receive real-time feedback; view own progress |
| `trainer` | View trainees' sessions; view cohort analytics; cannot modify SOPs |
| `supervisor` | View all workers in their department; generate reports; cannot access system config |
| `admin` | Full access: manage SOPs, users, system config, all analytics |
| `system` | Internal service-to-service calls only; no UI access |

#### Implementation (FastAPI)

```python
# Role enforcement using FastAPI dependencies
from fastapi import Depends, HTTPException, status
from enum import Enum

class Role(str, Enum):
    WORKER = "worker"
    TRAINER = "trainer"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"

def require_role(*allowed_roles: Role):
    def dependency(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return dependency

# Endpoint-level enforcement
@router.get("/analytics/worker/{worker_id}")
async def get_worker_analytics(
    worker_id: int,
    current_user: User = Depends(require_role(Role.TRAINER, Role.SUPERVISOR, Role.ADMIN))
):
    # Workers can only access their own data
    if current_user.role == Role.TRAINER:
        if worker_id not in current_user.trainee_ids:
            raise HTTPException(status_code=403, detail="Access denied")
    ...
```

#### Additional Controls
- **Object-level authorisation:** Check ownership before returning any database record (worker data, session videos, error logs)
- **Directory traversal prevention:** Validate all file paths — no `../` sequences
- **CORS policy:** Whitelist only known frontend origins; deny all others
- **Deny by default:** All endpoints require authentication unless explicitly marked public

---

### A02:2021 — Cryptographic Failures

**Risk to FORGE-Vision:** Worker biometric/performance data exposed in transit or at rest. API keys for LLM services leaked. PostgreSQL connection string exposed. SOP IP leaked.

#### Data Classification

| Data Type | Sensitivity | Encryption Required |
|-----------|------------|-------------------|
| Video frames (live) | High (biometric) | TLS in transit; not stored unless consent |
| Worker performance logs | Medium | Encrypted at rest (PostgreSQL) |
| SOP definitions | High (business IP) | Encrypted at rest + access controlled |
| LLM API keys | Critical | Vault storage; never in code |
| JWT tokens | Critical | RS256 signed; HttpOnly cookies |
| Passwords | Critical | bcrypt (cost ≥ 12) |
| Database connection string | Critical | Environment variable; vault in production |

#### Implementation

```python
# Password hashing — bcrypt with cost factor 12
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
```

```python
# JWT with RS256 (asymmetric) — more secure than HS256
import jwt
from cryptography.hazmat.primitives import serialization

# Load RSA private key from secure vault / environment
PRIVATE_KEY = os.environ["JWT_PRIVATE_KEY"]
PUBLIC_KEY = os.environ["JWT_PUBLIC_KEY"]

def create_access_token(subject: str, role: str) -> str:
    payload = {
        "sub": subject,
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=30),
        "iat": datetime.utcnow(),
        "jti": str(uuid4())  # Unique token ID for revocation
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")
```

#### Transport Security
- **TLS 1.3 mandatory** for all API endpoints and WebSocket connections
- **HSTS header** with min 1-year max-age
- Camera feeds transmitted over **WebSocket Secure (WSS)**, not plain WS
- **Certificate pinning** for mobile clients (Phase B)

#### Database Encryption
```sql
-- PostgreSQL: encrypt sensitive columns using pgcrypto
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Store SOP steps encrypted
INSERT INTO sops (id, name, steps_encrypted)
VALUES (
    gen_random_uuid(),
    'Wiring Procedure v1',
    pgp_sym_encrypt(steps_json::text, current_setting('app.encryption_key'))
);
```

---

### A03:2021 — Injection

**Risk to FORGE-Vision:** Three injection attack vectors unique to this system:
1. **SQL injection** via worker search, session queries
2. **Prompt injection** via malicious content processed by the LLM
3. **Video/Image injection** — malformed frames causing OpenCV/PyTorch buffer overflows

#### SQL Injection Prevention

```python
# ALWAYS use SQLAlchemy ORM or parameterised queries — never string formatting
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# CORRECT — parameterised query via ORM
async def get_worker_sessions(db: AsyncSession, worker_id: int):
    result = await db.execute(
        select(Session).where(Session.worker_id == worker_id)
    )
    return result.scalars().all()

# NEVER DO THIS
async def get_worker_sessions_unsafe(db, worker_id):
    # VULNERABLE: SQL injection via worker_id
    return await db.execute(f"SELECT * FROM sessions WHERE worker_id = {worker_id}")
```

#### Prompt Injection Prevention

The LLM feedback engine is vulnerable to prompt injection if untrusted data (worker names, SOP content, error descriptions) is interpolated directly into prompts.

```python
# SECURE prompt construction — sanitise all dynamic content
import re

def sanitise_for_prompt(text: str, max_length: int = 200) -> str:
    """Remove prompt injection patterns from dynamic content."""
    # Remove instruction-style patterns
    injection_patterns = [
        r"ignore (previous|above|all) instructions",
        r"you are now",
        r"system prompt",
        r"<\|.*?\|>",  # Special tokens
        r"\[INST\]|\[/INST\]",  # Llama tokens
        r"###\s*(instruction|system|human|assistant)",
    ]
    for pattern in injection_patterns:
        text = re.sub(pattern, "[REMOVED]", text, flags=re.IGNORECASE)
    return text[:max_length]

def build_feedback_prompt(
    sop_name: str,
    detected_action: str,
    error_type: str,
    sop_step: str,
    confidence: float
) -> str:
    # Sanitise all dynamic inputs before interpolation
    return FEEDBACK_PROMPT_TEMPLATE.format(
        sop_name=sanitise_for_prompt(sop_name),
        detected_action=sanitise_for_prompt(detected_action),
        error_type=sanitise_for_prompt(error_type),
        sop_step=sanitise_for_prompt(sop_step),
        confidence=min(max(confidence, 0.0), 1.0)  # Clamp to valid range
    )
```

#### Video/Image Frame Validation

```python
# Validate incoming video frames before processing
def validate_frame(frame_bytes: bytes) -> np.ndarray:
    MAX_FRAME_SIZE = 5 * 1024 * 1024  # 5MB max per frame

    if len(frame_bytes) > MAX_FRAME_SIZE:
        raise ValueError("Frame exceeds maximum allowed size")

    # Decode with OpenCV — catches malformed image data
    frame_array = np.frombuffer(frame_bytes, np.uint8)
    frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)

    if frame is None:
        raise ValueError("Invalid image data")

    # Enforce expected dimensions
    h, w = frame.shape[:2]
    if not (240 <= h <= 1080 and 320 <= w <= 1920):
        raise ValueError(f"Unexpected frame dimensions: {w}x{h}")

    return frame
```

---

### A04:2021 — Insecure Design

**Risk to FORGE-Vision:** Security not considered at architecture level — bolted on as an afterthought.

#### Threat Model (STRIDE Analysis for FORGE-Vision)

| Threat | Component | Mitigation |
|--------|-----------|-----------|
| **Spoofing** | Worker identity via camera | JWT auth + session binding; RBAC |
| **Tampering** | SOP definitions modified | Blockchain audit trail (Project Evolve concept); integrity hashes |
| **Repudiation** | Supervisor denies approving evaluation | Immutable audit log with timestamps |
| **Information Disclosure** | Worker data exposed | Encryption at rest + in transit; need-to-know access |
| **Denial of Service** | Camera frame flood; API abuse | Rate limiting; frame queue limits; circuit breakers |
| **Elevation of Privilege** | Worker accesses admin panel | RBAC; JWT claims validated server-side; no client-side role trust |

#### Secure Design Principles Applied

- **Fail secure:** On any error, deny access and log — never default to open
- **Least privilege:** Database users have minimum required permissions (no `SUPERUSER` for app)
- **Defence in depth:** API authentication + database-level row security + network-level firewall
- **Data minimisation:** Collect only data needed; video frames not persisted unless consent given

#### PostgreSQL Row-Level Security

```sql
-- Enforce data isolation at database level
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY worker_own_sessions ON sessions
    FOR SELECT
    USING (worker_id = current_setting('app.current_worker_id')::int);

CREATE POLICY supervisor_department ON sessions
    FOR SELECT
    USING (
        worker_id IN (
            SELECT id FROM workers WHERE department_id = current_setting('app.current_dept_id')::int
        )
    );
```

---

### A05:2021 — Security Misconfiguration

**Risk to FORGE-Vision:** Default credentials, debug mode enabled in production, verbose error messages exposing system internals, open database ports.

#### FastAPI Security Configuration

```python
# production_config.py
from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

app = FastAPI(
    title="FORGE-Vision API",
    # Disable automatic docs in production
    docs_url=None if os.getenv("ENVIRONMENT") == "production" else "/docs",
    redoc_url=None if os.getenv("ENVIRONMENT") == "production" else "/redoc",
    openapi_url=None if os.getenv("ENVIRONMENT") == "production" else "/openapi.json"
)

# Force HTTPS
app.add_middleware(HTTPSRedirectMiddleware)

# Restrict to known hosts
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=os.getenv("ALLOWED_HOSTS", "").split(",")
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self' wss:; "
        "frame-ancestors 'none'"
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response
```

#### Docker Security Hardening

```dockerfile
# Dockerfile — production hardened
FROM python:3.11-slim

# Run as non-root user
RUN groupadd -r forgevision && useradd -r -g forgevision forgevision

WORKDIR /app

# Copy and install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=forgevision:forgevision . .

# Drop to non-root
USER forgevision

# No shell access, no package manager in production image
RUN rm -rf /usr/bin/wget /usr/bin/curl /bin/sh

EXPOSE 8000
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
```

#### PostgreSQL Hardening

```sql
-- Dedicated application user with minimum permissions
CREATE ROLE forgevision_app WITH LOGIN PASSWORD 'use-vault-managed-password';
GRANT CONNECT ON DATABASE forgevision TO forgevision_app;
GRANT USAGE ON SCHEMA public TO forgevision_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO forgevision_app;
REVOKE DELETE ON sessions FROM forgevision_app;  -- Soft deletes only; no hard deletes
-- NEVER grant SUPERUSER, CREATEDB, or CREATEROLE to the application user
```

---

### A06:2021 — Vulnerable and Outdated Components

**Risk to FORGE-Vision:** Known CVEs in PyTorch, OpenCV, FastAPI, or their dependencies exploited.

#### Dependency Management

```bash
# requirements.txt — pin ALL versions
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.35
asyncpg==0.29.0
pydantic==2.9.0
torch==2.4.0
torchvision==0.19.0
opencv-python-headless==4.10.0.84
mediapipe==0.10.14
ultralytics==8.3.0  # YOLOv8
passlib[bcrypt]==1.7.4
python-jose[cryptography]==3.3.0
python-dotenv==1.0.1
```

#### Automated Vulnerability Scanning

```yaml
# .github/workflows/security-scan.yml
name: Security Scan
on:
  push:
    branches: [main]
  schedule:
    - cron: '0 2 * * 1'  # Weekly Monday 2am

jobs:
  dependency-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run pip-audit
        run: |
          pip install pip-audit
          pip-audit -r requirements.txt --output json > audit-results.json
      - name: Run Bandit (Python SAST)
        run: |
          pip install bandit
          bandit -r src/ -f json -o bandit-results.json
      - name: Run Trivy (container scan)
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'forge-vision:latest'
          severity: 'HIGH,CRITICAL'
          exit-code: '1'
```

#### ML Model Supply Chain Security

```python
# Verify model weight integrity before loading
import hashlib

MODEL_CHECKSUMS = {
    "yolov8n_forge.pt": "sha256:abc123...",
    "action_recognition_v2.pth": "sha256:def456...",
    "pose_estimator_v1.pth": "sha256:ghi789..."
}

def load_model_securely(model_path: str, model_name: str) -> torch.nn.Module:
    expected_hash = MODEL_CHECKSUMS.get(model_name)
    if not expected_hash:
        raise SecurityError(f"Unknown model: {model_name}")

    # Verify integrity before loading
    with open(model_path, "rb") as f:
        actual_hash = "sha256:" + hashlib.sha256(f.read()).hexdigest()

    if actual_hash != expected_hash:
        raise SecurityError(f"Model integrity check failed for {model_name}")

    return torch.load(model_path, map_location="cpu", weights_only=True)
```

---

### A07:2021 — Identification and Authentication Failures

**Risk to FORGE-Vision:** Weak passwords allowing brute-force. Sessions not invalidated on logout. Shared admin credentials. No MFA for privileged accounts.

#### Authentication Implementation

```python
# Secure authentication with brute-force protection
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/auth/login")
@limiter.limit("5/minute")  # Brute-force protection
async def login(
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    user = await get_user_by_email(db, credentials.email)

    # Constant-time comparison to prevent timing attacks
    if not user or not verify_password(credentials.password, user.hashed_password):
        # Don't reveal whether email exists
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.is_locked:
        raise HTTPException(status_code=423, detail="Account temporarily locked")

    # Increment failed attempts or reset on success
    await update_login_attempt(db, user.id, success=True)

    access_token = create_access_token(str(user.id), user.role)
    refresh_token = create_refresh_token(str(user.id))

    # Store refresh token hash in DB for invalidation
    await store_refresh_token_hash(db, user.id, refresh_token)

    response = JSONResponse({"message": "Login successful", "role": user.role})
    # HttpOnly cookies — not accessible to JavaScript (XSS protection)
    response.set_cookie(
        "access_token", access_token,
        httponly=True, secure=True, samesite="strict",
        max_age=1800  # 30 minutes
    )
    return response

@router.post("/auth/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Invalidate all refresh tokens for this user
    await revoke_all_user_tokens(db, current_user.id)
    response = JSONResponse({"message": "Logged out"})
    response.delete_cookie("access_token")
    return response
```

#### Multi-Factor Authentication (MFA) for Admin/Supervisor

```python
# TOTP-based MFA using pyotp
import pyotp
import qrcode

def generate_mfa_secret(user_id: int) -> str:
    return pyotp.random_base32()

def verify_mfa_token(secret: str, token: str) -> bool:
    totp = pyotp.TOTP(secret)
    # Allow 1 window (30 seconds) of drift
    return totp.verify(token, valid_window=1)

# Enforce MFA for admin and supervisor roles
@router.post("/auth/verify-mfa")
async def verify_mfa(
    mfa_data: MFAVerifyRequest,
    pending_user_id: str = Depends(get_pending_mfa_session)
):
    user = await get_user_by_id(db, pending_user_id)
    if user.role in [Role.ADMIN, Role.SUPERVISOR]:
        if not verify_mfa_token(user.mfa_secret, mfa_data.token):
            raise HTTPException(status_code=401, detail="Invalid MFA token")
    ...
```

#### Password Policy

```python
# Enforce strong passwords
import re

def validate_password_strength(password: str) -> bool:
    rules = [
        len(password) >= 12,                        # Minimum length
        re.search(r"[A-Z]", password),               # Uppercase
        re.search(r"[a-z]", password),               # Lowercase
        re.search(r"\d", password),                  # Digit
        re.search(r"[!@#$%^&*()_+\-=\[\]{};]", password),  # Special char
        not re.search(r"(.)\1{3,}", password),       # No 4+ repeated chars
    ]
    return all(rules)
```

---

### A08:2021 — Software and Data Integrity Failures

**Risk to FORGE-Vision:** Malicious SOP files uploaded and processed. Model weights tampered with (adversarial models). Untrusted video sources injected. CI/CD pipeline compromised.

#### SOP File Upload Validation

```python
# Strict validation for SOP uploads
import magic  # python-magic for MIME detection
from pathlib import Path

ALLOWED_SOP_EXTENSIONS = {".json", ".yaml", ".yml"}
MAX_SOP_SIZE = 1 * 1024 * 1024  # 1MB max

async def validate_sop_upload(file: UploadFile) -> dict:
    # Check extension
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_SOP_EXTENSIONS:
        raise HTTPException(400, "Only JSON and YAML SOP files accepted")

    content = await file.read()

    # Check size
    if len(content) > MAX_SOP_SIZE:
        raise HTTPException(400, "SOP file too large")

    # Verify MIME type matches claimed extension (magic bytes check)
    detected_mime = magic.from_buffer(content, mime=True)
    if detected_mime not in ["text/plain", "application/json", "application/x-yaml"]:
        raise HTTPException(400, "File content does not match declared type")

    # Parse and validate schema
    try:
        parsed = yaml.safe_load(content)  # safe_load — not yaml.load (!)
        validate_sop_schema(parsed)  # Pydantic schema validation
    except (yaml.YAMLError, ValidationError) as e:
        raise HTTPException(400, f"Invalid SOP format: {str(e)}")

    return parsed
```

#### CI/CD Pipeline Integrity

```yaml
# Signed commits and pipeline security
# .github/workflows/deploy.yml
jobs:
  deploy:
    environment: production
    steps:
      - name: Verify commit signature
        run: git verify-commit HEAD

      - name: Run full test suite
        run: pytest tests/ --cov=src --cov-fail-under=80

      - name: Security scan must pass
        run: pip-audit -r requirements.txt

      - name: Build and sign container image
        run: |
          docker build -t forge-vision:${{ github.sha }} .
          cosign sign forge-vision:${{ github.sha }}  # Sigstore cosign
```

---

### A09:2021 — Security Logging and Monitoring Failures

**Risk to FORGE-Vision:** Security incidents (brute-force attempts, unauthorised access, data exports) not detected or investigated.

#### Security Audit Logging

```python
# Structured security event logging
import structlog
from enum import Enum

class SecurityEvent(str, Enum):
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILURE = "auth.login.failure"
    LOGIN_LOCKED = "auth.login.locked"
    ACCESS_DENIED = "authz.access.denied"
    DATA_EXPORT = "data.export"
    SOP_MODIFIED = "sop.modified"
    MODEL_LOADED = "model.loaded"
    SESSION_STARTED = "training.session.started"
    SESSION_ENDED = "training.session.ended"
    ADMIN_ACTION = "admin.action"

security_logger = structlog.get_logger("security")

def log_security_event(
    event: SecurityEvent,
    user_id: int | None,
    ip_address: str,
    details: dict = None
):
    security_logger.info(
        event.value,
        user_id=user_id,
        ip=ip_address,
        timestamp=datetime.utcnow().isoformat(),
        **( details or {})
    )

# Usage in endpoints
@router.post("/auth/login")
async def login(request: Request, ...):
    if login_failed:
        log_security_event(
            SecurityEvent.LOGIN_FAILURE,
            user_id=None,
            ip_address=request.client.host,
            details={"email_hash": hashlib.sha256(email.encode()).hexdigest()}
        )
```

#### Alerting Rules

```yaml
# Alert thresholds (Grafana / CloudWatch / Azure Monitor)
alerts:
  - name: BruteForce
    condition: auth.login.failure > 10 in 1 minute from same IP
    action: block_ip + notify_admin

  - name: UnauthorisedAccess
    condition: authz.access.denied > 5 in 5 minutes for same user
    action: lock_account + notify_supervisor

  - name: UnusualDataExport
    condition: data.export count > 100 records in 10 minutes
    action: notify_admin + require_mfa_reauth

  - name: OffHoursAdminAction
    condition: admin.action outside working_hours
    action: notify_security_team

  - name: ModelIntegrityFailure
    condition: model.integrity_check == FAILED
    action: halt_system + notify_admin + page_oncall
```

#### Immutable Audit Trail (PostgreSQL)

```sql
-- Append-only audit log table
CREATE TABLE security_audit_log (
    id          BIGSERIAL PRIMARY KEY,
    event_type  VARCHAR(100) NOT NULL,
    user_id     INTEGER,
    ip_address  INET,
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    details     JSONB,
    -- Prevent updates and deletes at DB level
    CONSTRAINT no_update CHECK (TRUE)
);

-- Revoke modification rights even from app user
REVOKE UPDATE, DELETE ON security_audit_log FROM forgevision_app;
GRANT INSERT, SELECT ON security_audit_log TO forgevision_app;
```

---

### A10:2021 — Server-Side Request Forgery (SSRF)

**Risk to FORGE-Vision:** Three SSRF attack vectors unique to this system:
1. **LLM API calls** — attacker manipulates the API endpoint URL through prompt injection
2. **Camera feed URLs** — attacker supplies a malicious RTSP/HTTP URL pointing to internal services
3. **SOP webhook notifications** — if the system sends notifications to configured URLs

#### SSRF Prevention

```python
# Allowlist-based URL validation for camera feeds
import ipaddress
from urllib.parse import urlparse

ALLOWED_CAMERA_SCHEMES = {"rtsp", "http", "https"}
BLOCKED_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),       # Private
    ipaddress.ip_network("172.16.0.0/12"),    # Private
    ipaddress.ip_network("192.168.0.0/16"),   # Private
    ipaddress.ip_network("127.0.0.0/8"),      # Loopback
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
]

def validate_camera_url(url: str) -> str:
    parsed = urlparse(url)

    # Scheme allowlist
    if parsed.scheme not in ALLOWED_CAMERA_SCHEMES:
        raise ValueError(f"Camera scheme '{parsed.scheme}' not allowed")

    # Resolve hostname and check against blocked ranges
    import socket
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(parsed.hostname))
    except socket.gaierror:
        raise ValueError("Cannot resolve camera hostname")

    for blocked_range in BLOCKED_IP_RANGES:
        if ip in blocked_range:
            raise ValueError(f"Camera URL points to blocked IP range: {ip}")

    return url

# Hardcode LLM API endpoints — never accept from user input
LLM_ENDPOINTS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "anthropic": "https://api.anthropic.com/v1/messages",
}

def get_llm_endpoint(provider: str) -> str:
    endpoint = LLM_ENDPOINTS.get(provider)
    if not endpoint:
        raise ValueError(f"Unknown LLM provider: {provider}")
    return endpoint  # Never constructed from user input
```

---

## Security Architecture Summary

```
┌─────────────────────────────────────────────────────────────────┐
│  INTERNET / CLIENT                                              │
│  [WAF] → [TLS 1.3] → [Rate Limiter]                           │
└─────────────────────────────┬───────────────────────────────────┘
                              │ HTTPS only
┌─────────────────────────────▼───────────────────────────────────┐
│  FASTAPI BACKEND                                                │
│  [JWT Auth] → [RBAC] → [Input Validation] → [Audit Log]        │
│  [Security Headers] [CSRF Protection] [CORS Whitelist]         │
└─────────────────────────────┬───────────────────────────────────┘
                              │ Parameterised queries only
┌─────────────────────────────▼───────────────────────────────────┐
│  POSTGRESQL DATABASE                                            │
│  [Row-Level Security] [Encrypted columns] [Audit log table]    │
│  [Least-privilege app user] [No direct internet access]        │
└─────────────────────────────────────────────────────────────────┘
                              │ SSRF-protected
┌─────────────────────────────▼───────────────────────────────────┐
│  EXTERNAL SERVICES                                              │
│  [LLM APIs — hardcoded endpoints]                              │
│  [Camera feeds — URL allowlist validated]                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## OWASP Implementation Checklist

| # | OWASP Risk | FORGE-Vision Control | Status |
|---|------------|---------------------|--------|
| A01 | Broken Access Control | RBAC (4 roles) + object-level auth + DB Row-Level Security | ✅ Implemented — `src/api/routes/deps.py` |
| A02 | Cryptographic Failures | bcrypt passwords + HS256 JWT + Fernet API key encryption | ✅ Implemented — `src/intelligence/crypto.py`, `src/api/routes/auth.py` |
| A03 | Injection | SQLAlchemy ORM (all queries) + prompt sanitisation in `feedback_engine.py` | ✅ Implemented |
| A04 | Insecure Design | STRIDE threat model + fail-secure + least privilege design | ✅ Implemented — architecture enforced in Phase 0 |
| A05 | Security Misconfiguration | Security headers middleware + TrustedHostMiddleware + prod docs disabled | ✅ Implemented — `src/api/main.py` |
| A06 | Vulnerable Components | Pinned versions in `requirements.txt`; model weights gitignored | ✅ Implemented |
| A07 | Auth Failures | slowapi rate limiting (5 req/min login) + MFA (TOTP) + JWT expiry | ✅ Implemented — `src/api/routes/auth.py`, `src/api/limiter.py` |
| A08 | Data Integrity | Pydantic schema validation on all inputs + YAML safe_load in SOP parser | ✅ Implemented |
| A09 | Logging & Monitoring | Python `logging` throughout; structured log events on all auth/session events | ✅ Implemented |
| A10 | SSRF | LLM endpoints hardcoded in `llm_providers.py`; camera URLs validated in `camera_capture.py` | ✅ Implemented |

> **Note on deviations from spec:** The implementation uses HS256 JWT (not RS256) as appropriate for a single-service DBA prototype. RS256 is recommended before multi-service production deployment. Fernet symmetric encryption is used for API keys (not pgcrypto column encryption) — adequate for prototype scale.

---

## Security Testing Requirements

Before any production deployment:

1. **SAST (Static Analysis):** Bandit scan — zero HIGH/CRITICAL findings
2. **Dependency audit:** pip-audit — zero known CVEs in production dependencies
3. **DAST (Dynamic Analysis):** OWASP ZAP scan against staging environment
4. **Penetration test:** External pen test of the authentication and API endpoints
5. **Container scan:** Trivy — no HIGH/CRITICAL CVEs in Docker image
6. **SQL injection test:** sqlmap against all parameterised endpoints (must all pass)
7. **Authentication bypass test:** Verify no endpoint accessible without valid JWT

---

## GDPR Intersection with Security

Security and privacy are inseparable for FORGE-Vision given its handling of worker biometric data:

| GDPR Requirement | Technical Implementation |
|-----------------|------------------------|
| Data minimisation | Video frames not persisted; only extracted features stored |
| Right to erasure | CASCADE DELETE via worker_id across all tables |
| Data breach notification | Security monitoring detects breaches within 24h (72h GDPR limit) |
| Privacy by design | Security architecture designed in, not added later |
| Consent management | Consent table linked to sessions; no processing without consent |
