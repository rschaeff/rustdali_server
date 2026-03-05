"""Check import status for both libraries."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.database import SessionLocal
from app.models import Library, LibraryEntry
from sqlalchemy import func


def main():
    db = SessionLocal()

    for lib in db.query(Library).order_by(Library.name).all():
        counts = (
            db.query(LibraryEntry.status, func.count())
            .filter(LibraryEntry.library_id == lib.id)
            .group_by(LibraryEntry.status)
            .all()
        )
        status_map = dict(counts)
        total = sum(status_map.values())
        print(f"\n{lib.name} ({lib.lib_type}):")
        print(f"  Total:    {total}")
        for status in ["imported", "pending", "failed"]:
            n = status_map.get(status, 0)
            pct = f"({n * 100 / total:.1f}%)" if total > 0 else ""
            print(f"  {status:10s} {n:>6d} {pct}")

        # Show sample failures
        if status_map.get("failed", 0) > 0:
            failures = (
                db.query(LibraryEntry)
                .filter(LibraryEntry.library_id == lib.id, LibraryEntry.status == "failed")
                .limit(5)
                .all()
            )
            print(f"  Sample failures:")
            for f in failures:
                print(f"    {f.code}: {f.error_message}")

        # .dat file count
        dat_dir = Path(lib.dat_dir)
        if dat_dir.exists():
            dat_count = len(list(dat_dir.glob("*.dat")))
            print(f"  .dat files on disk: {dat_count}")

    db.close()


if __name__ == "__main__":
    main()
