# RustDALI Server

Internal structural search service built on [dali_rust](https://github.com/rschaeff/dali_rust), a Rust reimplementation of DaliLite.v5 for protein structure comparison.

Users submit protein query structures (PDB/mmCIF) and search against pre-processed reference libraries. Jobs run on a SLURM cluster and results are displayed in an interactive web UI with 3D structure superposition.

## Target Libraries

- **ECOD domains** — ~25K representative domains from the [ECOD](http://prodata.swmed.edu/ecod/) classification. Identifies evolutionary relationships at the domain level.
- **PDB chains** — ~27K full-chain representatives (CD-HIT 70% identity clusters). Identifies structural neighbors across the PDB.

## Architecture

| Component | Stack |
|-----------|-------|
| Backend | FastAPI (Python) with dali_rust PyO3 bindings |
| Compute | SLURM batch jobs |
| Database | PostgreSQL (`rustdali` schema) |
| Frontend | Next.js / React with Mol* 3D viewer |
| Auth | API key (X-API-Key header) |

## Project Structure

```
backend/
  app/
    main.py           FastAPI entry point
    config.py          Settings from .env
    database.py        SQLAlchemy engine + sessions
    models.py          ORM models (User, Library, Job, Result, ...)
    schemas.py         Pydantic request/response types
    auth.py            API key middleware
    routers/           API route handlers
    services/          SLURM submission, search wrapper
    worker/            SLURM job entry point
frontend/
  src/app/             Next.js App Router pages
  src/lib/api.ts       Typed API client
scripts/
  init_db.py           Create schema, seed data
  preprocess_ecod.py   ECOD domain library import
  preprocess_pdb.py    PDB chain library import
data/                  (gitignored) .dat libraries, job dirs, logs
docs/
  PROJECT.md           Detailed project plan and status
```

## Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 17
- SLURM cluster access
- `dali_rust` Python bindings (built via maturin from `dali-python/`)

### Configuration

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Required variables: database credentials, admin API key, SLURM partition.

### Backend

```bash
cd backend
pip install -r requirements.txt
python ../scripts/init_db.py      # create schema + seed data
uvicorn app.main:app --reload     # start API server
```

### Frontend

```bash
cd frontend
npm install
npm run dev                       # start dev server on :3000
```

### Library Preprocessing

Import ECOD domains and PDB chains into `.dat` format (runs on SLURM):

```bash
python scripts/preprocess_ecod.py register   # register entries from DB
python scripts/preprocess_ecod.py submit      # launch SLURM array job
python scripts/preprocess_pdb.py register
python scripts/preprocess_pdb.py submit
```

## API

All endpoints require `X-API-Key` header.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/libraries` | List available search libraries |
| POST | `/api/jobs` | Submit a search job (multipart file upload) |
| GET | `/api/jobs` | List user's jobs |
| GET | `/api/jobs/{id}` | Job status and details |
| GET | `/api/jobs/{id}/results` | Search results (ordered by Z-score) |

## License

Internal use only.
