"""Admin endpoints for user management and job maintenance."""

import secrets
import shutil
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Job, User
from ..schemas import UserCreate, UserOut, UserOutWithKey
from ..auth import require_admin
from ..services.slurm import sync_job_status

router = APIRouter(prefix="/api/admin", tags=["admin"])


# --- User management ---

@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    return db.query(User).order_by(User.created_at).all()


@router.post("/users", response_model=UserOutWithKey, status_code=201)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    existing = db.query(User).filter(User.name == body.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="User name already exists")
    user = User(name=body.name, api_key=secrets.token_urlsafe(32))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# --- Job status sync ---

@router.post("/jobs/sync")
def sync_all_jobs(
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """Sync status of all non-terminal jobs with SLURM."""
    jobs = db.query(Job).filter(Job.status.in_(["submitted", "running"])).all()
    updated = 0
    for job in jobs:
        if sync_job_status(job, db):
            updated += 1
    return {"checked": len(jobs), "updated": updated}


# --- Job cleanup ---

@router.post("/jobs/cleanup")
def cleanup_old_jobs(
    days: int = settings.job_retention_days,
    dry_run: bool = True,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """Delete completed/failed jobs older than `days` days.

    Pass dry_run=false to actually delete.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    old_jobs = (
        db.query(Job)
        .filter(
            Job.status.in_(["completed", "failed"]),
            Job.completed_at < cutoff,
        )
        .all()
    )

    deleted = []
    for job in old_jobs:
        deleted.append({"id": str(job.id), "status": job.status, "completed_at": str(job.completed_at)})
        if not dry_run:
            # Remove work directory
            if job.work_dir:
                work_dir = settings.jobs_dir / str(job.id)
                if work_dir.exists():
                    shutil.rmtree(work_dir)
            db.delete(job)

    if not dry_run:
        db.commit()

    return {"dry_run": dry_run, "days": days, "jobs_to_delete": len(deleted), "jobs": deleted}
