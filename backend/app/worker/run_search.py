"""SLURM worker script: runs a DALI search job and writes results to the DB."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

# Add backend to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.config import settings
from app.database import SessionLocal
from app.models import Job, Result
from app.services.search import run_search


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()

    job_id = UUID(args.job_id)
    work_dir = Path(args.work_dir)

    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job is None:
            print(f"Job {job_id} not found in database", file=sys.stderr)
            sys.exit(1)

        # Mark running
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        params = job.parameters or {}
        library_dat_dir = job.library.dat_dir

        # Run the search
        results = run_search(
            query_pdb_path=params["upload_path"],
            query_chain=params.get("query_chain", "A"),
            query_code=job.query_code,
            library_dat_dir=library_dat_dir,
            work_dir=str(work_dir),
            z_cut=params.get("z_cut", 2.0),
            skip_wolf=params.get("skip_wolf", False),
            max_rounds=params.get("max_rounds", 10),
        )

        # Store results in DB
        for r in results:
            db.add(Result(
                job_id=job_id,
                hit_cd2=r["hit_cd2"],
                zscore=r["zscore"],
                score=r.get("score"),
                rmsd=r.get("rmsd"),
                nblock=r.get("nblock"),
                blocks=r.get("blocks"),
                rotation=r.get("rotation"),
                translation=r.get("translation"),
                alignments=r.get("alignments"),
                round=r.get("round", 0),
            ))

        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        print(f"Job {job_id} completed: {len(results)} hits")

    except Exception as e:
        job.status = "failed"
        job.error_message = str(e).encode("ascii", "replace").decode("ascii")[:500]
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        print(f"Job {job_id} failed: {e}", file=sys.stderr)
        sys.exit(1)

    finally:
        db.close()


if __name__ == "__main__":
    main()
