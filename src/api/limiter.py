"""
Shared slowapi rate limiter instance.
Imported by both auth.py routes and main.py (middleware registration)
to avoid circular imports.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
