"""
ECOD library preprocessing: register representative domains and import to .dat format.

Usage:
    # Step 1: Register all ECOD rep domains in the DB
    python3 scripts/preprocess_ecod.py register

    # Step 2: Submit SLURM array job to import them
    python3 scripts/preprocess_ecod.py submit

    # Step 3 (or standalone): Import a batch of entries by index range
    python3 scripts/preprocess_ecod.py import --start 0 --end 100
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.config import settings
from app.database import SessionLocal, init_db
from app.models import Library, LibraryEntry

PDB_MIRROR = "/usr2/pdb/data/structures/divided/pdb"
BATCH_SIZE = 500  # entries per SLURM array task


def pdb_path(pdb_id: str) -> str:
    """Resolve PDB file path in the local mirror."""
    mid = pdb_id[1:3].lower()
    return f"{PDB_MIRROR}/{mid}/pdb{pdb_id.lower()}.ent.gz"


def get_ecod_domains():
    """Query ECOD representative domains with classification from ecod_protein DB."""
    import psycopg2
    conn = psycopg2.connect(
        host=settings.db_host, port=settings.db_port,
        dbname=settings.db_name, user=settings.db_user,
        password=settings.db_password,
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT d.id, d.ecod_uid, d.domain_id, d.range_definition, d.sequence_length,
               p.pdb_id, p.chain_id,
               f.a_group_id, f.x_group_id, f.h_group_id, f.t_group_id, f.f_group_id,
               dr.range_definition as pdb_range
        FROM ecod_commons.domains d
        JOIN ecod_commons.proteins p ON d.protein_id = p.id
        LEFT JOIN ecod_commons.f_group_assignments f ON f.domain_id = d.id
        LEFT JOIN ecod_commons.domain_ranges dr ON dr.domain_id = d.id AND dr.range_type = 'pdb'
        WHERE d.is_representative = true
          AND d.is_obsolete = false
          AND p.source_type = 'pdb'
        ORDER BY d.id
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def register(args):
    """Register ECOD representative domains in the library_entries table."""
    init_db()
    db = SessionLocal()

    lib = db.query(Library).filter(Library.lib_type == "ecod").first()
    if lib is None:
        print("ERROR: No ECOD library found in DB. Run init_db.py first.")
        sys.exit(1)

    existing = db.query(LibraryEntry).filter(LibraryEntry.library_id == lib.id).count()
    if existing > 0:
        print(f"Library already has {existing} entries. Use --force to re-register.")
        if not args.force:
            return
        db.query(LibraryEntry).filter(LibraryEntry.library_id == lib.id).delete()
        db.commit()
        print("Cleared existing entries.")

    print("Querying ECOD representative domains...")
    rows = get_ecod_domains()
    print(f"Found {len(rows)} representative domains.")

    # Filter to those with existing PDB files
    entries = []
    skipped = 0
    for row in rows:
        db_id, ecod_uid, domain_id, range_def, seq_len, pdb_id, chain_id, \
            a_group, x_group, h_group, t_group, f_group, pdb_range = row

        pdb_file = pdb_path(pdb_id)
        if not os.path.exists(pdb_file):
            skipped += 1
            continue

        # Use PDB-numbered range for masking; fall back to ECOD range
        effective_range = pdb_range if pdb_range else range_def

        # Use ECOD domain_id as the code (e.g. "e1f0xA1")
        entries.append(LibraryEntry(
            library_id=lib.id,
            code=domain_id,
            pdb_id=pdb_id,
            chain_id=chain_id,
            domain_range=effective_range,
            nres=seq_len,
            ecod_domain_id=domain_id,
            ecod_uid=ecod_uid,
            a_group=a_group,
            x_group=x_group,
            h_group=h_group,
            t_group=t_group,
            f_group=f_group,
            status="pending",
        ))

    print(f"Registering {len(entries)} entries ({skipped} skipped — PDB file not found).")

    # Bulk insert in batches
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
    lib = db.query(Library).filter(Library.lib_type == "ecod").first()
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

    # Batch over ALL entries (not just pending) so offsets are stable
    n_tasks = (total + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"{pending} pending of {total} total -> {n_tasks} array tasks of {BATCH_SIZE} each")

    script_path = settings.data_dir / "ecod_import.sh"
    settings.ecod_dat_dir.mkdir(parents=True, exist_ok=True)

    worker = Path(__file__).resolve()
    script = f"""#!/bin/bash
#SBATCH --job-name=ecod_import
#SBATCH --output={settings.data_dir}/logs/ecod_import_%A_%a.out
#SBATCH --error={settings.data_dir}/logs/ecod_import_%A_%a.err
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
    lib = db.query(Library).filter(Library.lib_type == "ecod").first()
    dat_dir = Path(lib.dat_dir)
    dat_dir.mkdir(parents=True, exist_ok=True)

    # Query by stable code order, filter to pending in Python
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

            # If domain has a sub-range, mask to just the domain residues
            if entry.domain_range and ":" in entry.domain_range:
                keep_indices = _parse_range_to_indices(
                    entry.domain_range, entry.chain_id, protein
                )
                if keep_indices is not None and len(keep_indices) < protein.nres:
                    protein = dali.mask_protein(protein, keep_indices, entry.code)

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


def _parse_range_to_indices(range_def, chain_id, protein):
    """Parse ECOD range definition to 0-based residue indices.

    Range format: "A:274-319,A:377-567" or "A:1-99"
    Uses protein.resid_map (list of integer PDB residue numbers).
    """
    resid_map = protein.resid_map
    if not resid_map or len(resid_map) != protein.nres:
        return None

    keep = set()
    for segment in range_def.split(","):
        segment = segment.strip()
        if not segment:
            continue

        # Parse "A:274-319" or just "274-319"
        if ":" in segment:
            _, seg_range = segment.split(":", 1)
        else:
            seg_range = segment

        if "-" in seg_range:
            start_str, end_str = seg_range.split("-", 1)
        else:
            start_str = end_str = seg_range

        try:
            start_num = int(start_str)
            end_num = int(end_str)
        except ValueError:
            continue

        for idx, resnum in enumerate(resid_map):
            if start_num <= resnum <= end_num:
                keep.add(idx)

    if not keep:
        return None

    return sorted(keep)


def main():
    parser = argparse.ArgumentParser(description="ECOD library preprocessing")
    sub = parser.add_subparsers(dest="command")

    reg = sub.add_parser("register", help="Register ECOD domains in DB")
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
