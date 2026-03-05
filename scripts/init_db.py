"""Initialize the database schema and seed a default user + libraries."""

import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.config import settings
from app.database import init_db, SessionLocal
from app.models import User, Library


def main():
    print(f"Connecting to {settings.db_host}:{settings.db_port}/{settings.db_name}")
    print(f"Creating schema '{settings.db_schema}' and tables...")
    init_db()

    db = SessionLocal()
    try:
        # Create default user if none exists
        if db.query(User).count() == 0:
            api_key = secrets.token_urlsafe(32)
            user = User(name="admin", api_key=api_key)
            db.add(user)
            db.commit()
            print(f"\nCreated default user 'admin'")
            print(f"API key: {api_key}")
            print("Save this key -- it won't be shown again.")
        else:
            print("\nUsers already exist, skipping seed.")

        # Create libraries if none exist
        if db.query(Library).count() == 0:
            ecod_dir = settings.ecod_dat_dir
            pdb_dir = settings.pdb_dat_dir
            ecod_dir.mkdir(parents=True, exist_ok=True)
            pdb_dir.mkdir(parents=True, exist_ok=True)

            db.add(Library(
                name="ECOD domains",
                lib_type="ecod",
                dat_dir=str(ecod_dir),
            ))
            db.add(Library(
                name="PDB chains",
                lib_type="pdb",
                dat_dir=str(pdb_dir),
            ))
            db.commit()
            print("Created ECOD and PDB library entries.")
        else:
            print("Libraries already exist, skipping seed.")

    finally:
        db.close()

    print("\nDone. Start the server with:")
    print("  cd backend && uvicorn app.main:app --reload")


if __name__ == "__main__":
    main()
