"""
PDB chain library preprocessing: register 70% identity cluster reps and import to .dat format.

Usage:
    # Step 1: Register PDB chain representatives in the DB
    python3 scripts/preprocess_pdb.py register

    # Step 2: Submit SLURM array job to import them
    python3 scripts/preprocess_pdb.py submit

    # Step 3 (or standalone): Import a batch of entries by index range
    python3 scripts/preprocess_pdb.py import --start 0 --end 100
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.config import settings
from app.database import SessionLocal, init_db
from app.models import Library, LibraryEntry

PDB_MIRROR = "/usr2/pdb/data/structures/divided/pdb"
CLUSTERING_RUN_ID = 1  # cd-hit at 70% identity
MIN_LENGTH = 30
MAX_LENGTH = 5000
BATCH_SIZE = 500


def pdb_path(pdb_id: str) -> str:
    """Resolve PDB file path in the local mirror."""
    mid = pdb_id[1:3].lower()
    return f"{PDB_MIRROR}/{mid}/pdb{pdb_id.lower()}.ent.gz"


def get_pdb_reps():
    """Query 70% identity cluster representatives from ecod_protein DB."""
    import psycopg2
    conn = psycopg2.connect(
        host=settings.db_host, port=settings.db_port,
        dbname=settings.db_name, user=settings.db_user,
        password=settings.db_password,
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT p.source_id, p.pdb_id, p.chain_id, p.sequence_length
        FROM ecod_commons.protein_clusters pc
        JOIN ecod_commons.proteins p ON p.source_id = pc.representative_source_id
        WHERE pc.clustering_run_id = %s
          AND p.source_type = 'pdb'
          AND p.sequence_length IS NOT NULL
          AND p.sequence_length >= %s
          AND p.sequence_length <= %s
          AND length(p.chain_id) = 1
        ORDER BY p.source_id
    """, (CLUSTERING_RUN_ID, MIN_LENGTH, MAX_LENGTH))
    rows = cur.fetchall()
    conn.close()
    return rows


def register(args):
    """Register PDB chain representatives in the library_entries table."""
    init_db()
    db = SessionLocal()

    lib = db.query(Library).filter(Library.lib_type == "pdb").first()
    if lib is None:
        print("ERROR: No PDB library found in DB. Run init_db.py first.")
        sys.exit(1)

    existing = db.query(LibraryEntry).filter(LibraryEntry.library_id == lib.id).count()
    if existing > 0:
        print(f"Library already has {existing} entries. Use --force to re-register.")
        if not args.force:
            return
        db.query(LibraryEntry).filter(LibraryEntry.library_id == lib.id).delete()
        db.commit()
        print("Cleared existing entries.")

    print("Querying PDB 70% identity cluster representatives...")
    rows = get_pdb_reps()
    print(f"Found {len(rows)} single-chain representatives.")

    entries = []
    skipped = 0
    seen_codes = set()
    for source_id, pdb_id, chain_id, seq_len in rows:
        pdb_file = pdb_path(pdb_id)
        if not os.path.exists(pdb_file):
            skipped += 1
            continue

        # Code format: pdb_chain, e.g. "1a05A"
        code = f"{pdb_id}{chain_id}"
        if code in seen_codes:
            continue
        seen_codes.add(code)

        entries.append(LibraryEntry(
            library_id=lib.id,
            code=code,
            pdb_id=pdb_id,
            chain_id=chain_id,
            nres=seq_len,
            status="pending",
        ))

    print(f"Registering {len(entries)} entries ({skipped} skipped — PDB file not found).")

    for i in range(0, len(entries), 1000):
        db.add_all(entries[i:i + 1000])
        db.commit()
        print(f"  inserted {min(i + 1000, len(entries))}/{len(entries)}")

    lib.entry_count = len(entries)
    db.commit()
    db.close()
    print("Done.")


def submit(args):
    """Submit a SLURM array job to import all pending entries."""
    db = SessionLocal()
    lib = db.query(Library).filter(Library.lib_type == "pdb").first()
    total = db.query(LibraryEntry).filter(LibraryEntry.library_id == lib.id).count()
    pending = (
        db.query(LibraryEntry)
        .filter(LibraryEntry.library_id == lib.id, LibraryEntry.status == "pending")
        .count()
    )
    db.close()

    if pending == 0:
        print("No pending entries to import.")
        return

    n_tasks = (total + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"{pending} pending of {total} total -> {n_tasks} array tasks of {BATCH_SIZE} each")

    script_path = settings.data_dir / "pdb_import.sh"
    settings.pdb_dat_dir.mkdir(parents=True, exist_ok=True)

    worker = Path(__file__).resolve()
    script = f"""#!/bin/bash
#SBATCH --job-name=pdb_import
#SBATCH --output={settings.data_dir}/logs/pdb_import_%A_%a.out
#SBATCH --error={settings.data_dir}/logs/pdb_import_%A_%a.err
#SBATCH --array=0-{n_tasks - 1}
#SBATCH --partition={settings.slurm_partition}
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=2:00:00
{f'#SBATCH --account={settings.slurm_account}' if settings.slurm_account else ''}

source ~/.bashrc
export PYTHONIOENCODING=utf-8
export PGCLIENTENCODING=UTF8
export LC_ALL=en_US.UTF-8

START=$(( $SLURM_ARRAY_TASK_ID * {BATCH_SIZE} ))
END=$(( $START + {BATCH_SIZE} ))

python3 {worker} import --start $START --end $END
"""
    (settings.data_dir / "logs").mkdir(parents=True, exist_ok=True)
    script_path.write_text(script)

    result = subprocess.run(["sbatch", str(script_path)], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"sbatch failed: {result.stderr.strip()}")
        sys.exit(1)

    print(f"Submitted: {result.stdout.strip()}")


def import_batch(args):
    """Import a range of pending entries to .dat files."""
    import dali

    db = SessionLocal()
    lib = db.query(Library).filter(Library.lib_type == "pdb").first()
    dat_dir = Path(lib.dat_dir)
    dat_dir.mkdir(parents=True, exist_ok=True)

    all_entries = (
        db.query(LibraryEntry)
        .filter(LibraryEntry.library_id == lib.id)
        .order_by(LibraryEntry.code)
        .offset(args.start)
        .limit(args.end - args.start)
        .all()
    )
    entries = [e for e in all_entries if e.status == "pending"]

    print(f"Importing entries [{args.start}:{args.end}], {len(entries)} pending of {len(all_entries)} in slice.")

    imported = 0
    failed = 0
    for entry in entries:
        dat_path = dat_dir / f"{entry.code}.dat"
        if dat_path.exists():
            entry.status = "imported"
            imported += 1
            continue

        try:
            pdb_file = pdb_path(entry.pdb_id)
            protein = dali.import_pdb(pdb_file, entry.chain_id, entry.code)
            dali.write_dat(protein, str(dat_path))
            entry.nres = protein.nres
            entry.nseg = protein.nseg
            entry.status = "imported"
            imported += 1
        except Exception as e:
            entry.status = "failed"
            entry.error_message = str(e).encode("ascii", "replace").decode("ascii")[:500]
            failed += 1

        if (imported + failed) % 50 == 0:
            try:
                db.commit()
            except Exception as commit_err:
                print(f"  Commit error at {imported + failed}: {commit_err}")
                db.rollback()

    try:
        db.commit()
    except Exception as commit_err:
        print(f"  Final commit error: {commit_err}")
        db.rollback()
    db.close()
    print(f"Done: {imported} imported, {failed} failed.")


def main():
    parser = argparse.ArgumentParser(description="PDB library preprocessing")
    sub = parser.add_subparsers(dest="command")

    reg = sub.add_parser("register", help="Register PDB chain reps in DB")
    reg.add_argument("--force", action="store_true", help="Re-register (clear existing)")

    sub.add_parser("submit", help="Submit SLURM array job")

    imp = sub.add_parser("import", help="Import a batch of entries")
    imp.add_argument("--start", type=int, required=True)
    imp.add_argument("--end", type=int, required=True)

    args = parser.parse_args()
    if args.command == "register":
        register(args)
    elif args.command == "submit":
        submit(args)
    elif args.command == "import":
        import_batch(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
