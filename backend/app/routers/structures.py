"""Endpoints for serving structure files to the 3D viewer."""

import gzip
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Job, LibraryEntry, User
from ..auth import get_current_user

router = APIRouter(prefix="/api/jobs/{job_id}/structures", tags=["structures"])

PDB_MIRROR = Path("/usr2/pdb/data/structures/divided/pdb")


def _read_pdb_file(path: Path) -> str:
    """Read a PDB file, decompressing if gzipped."""
    if path.suffix == ".gz":
        with gzip.open(path, "rt") as f:
            return f.read()
    return path.read_text()


@router.get("/query")
def get_query_structure(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Serve the query PDB file that was uploaded with this job."""
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    params = job.parameters or {}
    upload_path = params.get("upload_path")
    if not upload_path:
        raise HTTPException(status_code=404, detail="No upload file recorded")

    path = Path(upload_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Upload file not found on disk")

    content = _read_pdb_file(path)
    return Response(content=content, media_type="chemical/x-pdb")


@router.get("/hit/{hit_code}")
def get_hit_structure(
    job_id: uuid.UUID,
    hit_code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Serve a hit's PDB file from the local PDB mirror."""
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Look up the library entry to get pdb_id
    entry = (
        db.query(LibraryEntry)
        .filter(LibraryEntry.library_id == job.library_id, LibraryEntry.code == hit_code)
        .first()
    )

    if entry and entry.pdb_id:
        pdb_id = entry.pdb_id.lower()
    else:
        # Fall back: extract pdb_id from the code
        # ECOD codes like "e1a6mA1" -> pdb_id "1a6m"
        # PDB codes like "1a6mA" -> pdb_id "1a6m"
        code = hit_code
        if code.startswith("e") and len(code) >= 6:
            pdb_id = code[1:5].lower()
        elif len(code) >= 5:
            pdb_id = code[:4].lower()
        else:
            raise HTTPException(status_code=404, detail="Cannot determine PDB ID")

    # Look up in the local PDB mirror
    mid = pdb_id[1:3]
    pdb_path = PDB_MIRROR / mid / f"pdb{pdb_id}.ent.gz"

    if not pdb_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"PDB file not found: {pdb_id}",
        )

    content = _read_pdb_file(pdb_path)
    return Response(content=content, media_type="chemical/x-pdb")
