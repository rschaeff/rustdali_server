"""Library listing endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Library
from ..schemas import LibraryOut
from ..auth import get_current_user

router = APIRouter(prefix="/api/libraries", tags=["libraries"])


@router.get("", response_model=list[LibraryOut])
def list_libraries(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return db.query(Library).order_by(Library.name).all()
