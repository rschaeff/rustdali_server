"""SLURM job submission and status checking."""

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent

from ..config import settings

# sacct states that indicate the job is done
_TERMINAL_STATES = {
    "COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY",
    "NODE_FAIL", "PREEMPTED", "DEADLINE",
}


def submit_search_job(job) -> str:
    """Submit a DALI search job to SLURM via sbatch.

    Args:
        job: Job ORM object with id, work_dir, parameters, library, query_code.

    Returns:
        SLURM job ID string.

    Raises:
        RuntimeError on sbatch failure.
    """
    work_dir = Path(job.work_dir)
    script_path = work_dir / "run.sh"
    worker_script = Path(__file__).resolve().parent.parent / "worker" / "run_search.py"

    script = dedent(f"""\
        #!/bin/bash
        #SBATCH --job-name=dali_{job.id}
        #SBATCH --output={work_dir}/slurm_%j.out
        #SBATCH --error={work_dir}/slurm_%j.err
        #SBATCH --partition={settings.slurm_partition}
        #SBATCH --cpus-per-task={settings.slurm_cpus_per_task}
        #SBATCH --mem={settings.slurm_mem_gb}G
        #SBATCH --time={settings.slurm_time_limit}
        {f'#SBATCH --account={settings.slurm_account}' if settings.slurm_account else ''}

        source ~/.bashrc

        export PYTHONIOENCODING=utf-8
        export PGCLIENTENCODING=UTF8
        export LC_ALL=en_US.UTF-8
        unset OMP_PROC_BIND

        python3 {worker_script} \\
            --job-id {job.id} \\
            --work-dir {work_dir}
    """)

    script_path.write_text(script)

    result = subprocess.run(
        ["sbatch", str(script_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"sbatch failed: {result.stderr.strip()}")

    # Parse "Submitted batch job 12345"
    slurm_id = result.stdout.strip().split()[-1]
    return slurm_id


def check_slurm_status(slurm_job_id: str) -> dict:
    """Check SLURM job status via sacct.

    Returns dict with keys: state, exit_code, elapsed, max_rss.
    """
    result = subprocess.run(
        [
            "sacct", "-j", slurm_job_id,
            "--format=State,ExitCode,Elapsed,MaxRSS",
            "--noheader", "--parsable2",
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return {"state": "UNKNOWN"}

    lines = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
    if not lines:
        return {"state": "UNKNOWN"}

    # First line is the overall job state
    parts = lines[0].split("|")
    state = parts[0].split()[0] if parts[0] else "UNKNOWN"
    # Strip trailing "+" from states like "CANCELLED+"
    state = state.rstrip("+")

    info = {"state": state}
    if len(parts) > 1:
        info["exit_code"] = parts[1]
    if len(parts) > 2:
        info["elapsed"] = parts[2]
    # MaxRSS is on the .batch step (second line)
    if len(lines) > 1:
        batch_parts = lines[1].split("|")
        if len(batch_parts) > 3 and batch_parts[3]:
            info["max_rss"] = batch_parts[3]

    return info


_SLURM_ERROR_MESSAGES = {
    "TIMEOUT": "SLURM job exceeded time limit",
    "OUT_OF_MEMORY": "SLURM job exceeded memory limit",
    "NODE_FAIL": "SLURM node failure",
    "PREEMPTED": "SLURM job was preempted",
    "CANCELLED": "SLURM job was cancelled",
    "DEADLINE": "SLURM job missed deadline",
}


def sync_job_status(job, db) -> bool:
    """Sync a job's status with SLURM if it's still in a non-terminal DB state.

    Returns True if the job status was updated.
    """
    # Only sync jobs that are submitted/running (worker hasn't reported back)
    if job.status not in ("submitted", "running"):
        return False
    if not job.slurm_job_id:
        return False

    info = check_slurm_status(job.slurm_job_id)
    slurm_state = info.get("state", "UNKNOWN")

    if slurm_state == "UNKNOWN":
        return False

    # If SLURM says running/pending, update job status to match
    if slurm_state == "PENDING" and job.status != "submitted":
        job.status = "submitted"
        db.commit()
        return True

    if slurm_state == "RUNNING" and job.status != "running":
        job.status = "running"
        if not job.started_at:
            job.started_at = datetime.now(timezone.utc)
        db.commit()
        return True

    # If SLURM says completed but our DB doesn't reflect it, the worker
    # should have updated the DB. If it didn't, something went wrong.
    if slurm_state == "COMPLETED" and job.status not in ("completed", "failed"):
        # Worker didn't update — mark as failed with explanation
        job.status = "failed"
        job.error_message = "SLURM job completed but worker did not update status"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        return True

    # SLURM-side failure — the worker may not have had a chance to report
    if slurm_state in _TERMINAL_STATES and slurm_state != "COMPLETED":
        msg = _SLURM_ERROR_MESSAGES.get(slurm_state, f"SLURM job ended: {slurm_state}")
        if info.get("exit_code"):
            msg += f" (exit {info['exit_code']})"
        job.status = "failed"
        job.error_message = msg
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        return True

    return False
