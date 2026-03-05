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
