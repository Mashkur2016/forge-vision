"""
Phase 4 test configuration.

Patches DATABASE_URL to SQLite in-memory BEFORE src.database.database is
imported, preventing asyncpg from being loaded during unit/integration tests.

This conftest.py is loaded by pytest before test file collection in this
directory, so the env override is in place when `src.database.*` is first
imported.
"""
import os

# Override DATABASE_URL before any import of src.database.database occurs.
# The SQLite URL works with aiosqlite; no PostgreSQL server is needed.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
