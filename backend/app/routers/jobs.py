"""Job submission and status endpoints."""

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Job, Library, User
from ..schemas import JobSubmit, JobOut
from ..auth import get_current_user
from ..services.slurm import submit_search_job, sync_job_status

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("", response_model=JobOut, status_code=201)
def submit_job(
    file: UploadFile = File(...),
    library_id: str = Form(...),
    query_chain: str = Form("A"),
    query_code: str | None = Form(None),
    z_cut: float = Form(2.0),
    skip_wolf: bool = Form(False),
    max_rounds: int = Form(10),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Validate library exists
    lib = db.query(Library).filter(Library.id == library_id).first()
    if lib is None:
        raise HTTPException(status_code=404, detail="Library not found")

    # Create job
    job_id = uuid.uuid4()
    code = query_code or file.filename.rsplit(".", 1)[0][:64]
    work_dir = settings.jobs_dir / str(job_id)
    work_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded file
    upload_path = work_dir / file.filename
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    params = {
        "query_chain": query_chain,
        "z_cut": z_cut,
        "skip_wolf": skip_wolf,
        "max_rounds": max_rounds,
        "upload_path": str(upload_path),
    }

    job = Job(
        id=job_id,
        user_id=user.id,
        library_id=lib.id,
        status="queued",
        query_code=code,
        query_filename=file.filename,
        parameters=params,
        work_dir=str(work_dir),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Submit to SLURM
    try:
        slurm_id = submit_search_job(job)
        job.status = "submitted"
        job.slurm_job_id = slurm_id
        db.commit()
        db.refresh(job)
    except Exception as e:
        job.status = "failed"
        job.error_message = f"SLURM submission failed: {e}"
        db.commit()
        db.refresh(job)

    return job


@router.get("", response_model=list[JobOut])
def list_jobs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return (
        db.query(Job)
        .filter(Job.user_id == user.id)
        .order_by(Job.submitted_at.desc())
        .all()
    )


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    # Sync with SLURM if job is still in-flight
    sync_job_status(job, db)
    return job
