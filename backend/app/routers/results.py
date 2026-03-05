"""Result retrieval endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Job, Result, User
from ..schemas import ResultOut
from ..auth import get_current_user

router = APIRouter(prefix="/api/jobs/{job_id}/results", tags=["results"])


@router.get("", response_model=list[ResultOut])
def list_results(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return (
        db.query(Result)
        .filter(Result.job_id == job_id)
        .order_by(Result.zscore.desc())
        .all()
    )


@router.get("/{result_id}", response_model=ResultOut)
def get_result(
    job_id: uuid.UUID,
    result_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    result = db.query(Result).filter(Result.id == result_id, Result.job_id == job_id).first()
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return result
