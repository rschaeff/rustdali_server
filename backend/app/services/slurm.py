"""SLURM job submission and status checking."""

import subprocess
from pathlib import Path
from textwrap import dedent

from ..config import settings


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


def check_job_status(slurm_job_id: str) -> str:
    """Check SLURM job status via sacct.

    Returns one of: PENDING, RUNNING, COMPLETED, FAILED, CANCELLED, UNKNOWN.
    """
    result = subprocess.run(
        ["sacct", "-j", slurm_job_id, "--format=State", "--noheader", "--parsable2"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return "UNKNOWN"

    states = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
    if not states:
        return "UNKNOWN"

    # First line is the overall job state
    return states[0].split()[0] if states[0] else "UNKNOWN"
