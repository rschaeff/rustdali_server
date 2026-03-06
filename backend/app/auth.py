"""Lightweight API key authentication."""

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User

api_key_scheme = APIKeyHeader(name=settings.api_key_header, auto_error=False)


def get_current_user(
    api_key: str | None = Security(api_key_scheme),
    db: Session = Depends(get_db),
) -> User:
    if api_key is None:
        raise HTTPException(status_code=401, detail="Missing API key")
    user = db.query(User).filter(User.api_key == api_key).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return user


def require_admin(api_key: str | None = Security(api_key_scheme)) -> str:
    """Verify the request carries the admin API key (from .env)."""
    if not settings.admin_api_key:
        raise HTTPException(status_code=503, detail="Admin API key not configured")
    if api_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Admin access required")
    return api_key
