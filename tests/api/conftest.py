"""
API test configuration — patches DATABASE_URL to SQLite in-memory
before any src.database import so no PostgreSQL server is needed.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SETTINGS_ENCRYPTION_KEY", "test-enc-key-32-chars-padded!!")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-for-tests-only!!")
