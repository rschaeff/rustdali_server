# RustDALI Server

## Project Goal

Build an internal structural search service on top of the `dali_rust` library
(a validated Rust reimplementation of DaliLite.v5). The service allows users to
submit protein query structures and search them against pre-processed reference
libraries, with results displayed in an interactive web UI.

### Target Libraries

- **ECOD domain library** — curated domain representatives from the ECOD
  classification. Searches identify evolutionary relationships at the domain
  level.
- **PDB protein library** — full PDB chain representatives. Searches identify
  structural neighbors across the entire PDB.

### Core Components

1. **Library preprocessing** — Batch import of ECOD/PDB structures into `.dat`
   format (DSSP + domain decomposition + distance matrices). Runs periodically
   as upstream databases update.

2. **Search engine** — Backend that accepts a query structure (PDB/CIF),
   imports it, and runs `dali_rust` search/iterative_search against the
   selected target library. Jobs are dispatched to the leda SLURM cluster.

3. **Job tracking** — Persistent state in PostgreSQL: job submission, SLURM
   dispatch, status polling, result storage. Users can submit and return later.

4. **Authentication** — Lightweight auth (API keys or simple login) to
   associate jobs with users and restrict access. Not full enterprise SSO.

5. **Web frontend (Next.js / React)** — UI for:
   - Job submission: upload PDB/CIF, select target library, set parameters
   - Job status / history dashboard
   - Results viewer:
     - Structure superposition (3D, via Mol* or NGL)
     - Residue-level alignment viewer (blocks, Z-scores, RMSD)

### Non-Goals (for now)

- Public-facing deployment (internal only)
- User management beyond lightweight auth
- Custom library upload by users
- Real-time streaming of partial results


## Implementation Plan

### Phase 0: Project Scaffold

- Initialize the repo structure:
  ```
  rustdali_server/
    backend/              Python (FastAPI)
      app/
        main.py           FastAPI app entry point
        config.py         Settings (DB, SLURM, paths)
        auth.py           Lightweight auth (API keys)
        models.py         SQLAlchemy / DB models
        schemas.py        Pydantic request/response schemas
        routers/
          jobs.py         Job CRUD + submission endpoints
          results.py      Result retrieval endpoints
          libraries.py    Library listing / status
        services/
          slurm.py        SLURM job submission + polling
          search.py       dali_rust invocation wrapper
          import.py       PDB/CIF import via dali_rust
        worker/
          run_search.py   SLURM job script entry point
      alembic/            DB migrations
      requirements.txt
    frontend/             Next.js / React
      src/
        app/              App router pages
        components/
          StructureViewer.tsx   Mol* 3D superposition
          AlignmentViewer.tsx   Residue-level alignment
          JobTable.tsx          Job list / status
          SubmitForm.tsx        Job submission form
        lib/
          api.ts          Backend API client
    scripts/
      preprocess_ecod.py  ECOD library import
      preprocess_pdb.py   PDB library import
    docs/
      PROJECT.md          This file
  ```
- Set up the dali_rust Python bindings as a dependency (built via maturin
  from `../dali_cl/dali_rust/dali-python`).
- Create the PostgreSQL database and initial schema.

### Phase 1: Library Preprocessing

Batch import of target libraries into `.dat` format.

- **ECOD**: Download ECOD domain definitions + PDB files. For each domain,
  extract the relevant chain/residue range, run `dali.import_pdb()`, write
  `.dat` via `dali.write_dat()`. Store metadata (ECOD id, T/H/F/X group,
  domain boundaries) in Postgres.
- **PDB**: Download PDB representative chains (e.g., from PDB clusters at
  30/40/70/90/95/100% identity). Import each chain, write `.dat`. Store
  metadata.
- Both preprocessing jobs run as SLURM array jobs for parallelism.
- Output: a directory of `.dat` files per library, plus a Postgres table of
  library entries with metadata.

### Phase 2: Search Backend

FastAPI service that accepts queries and dispatches SLURM jobs.

- **POST /api/jobs** — Upload PDB/CIF, select library, set parameters
  (z_cut, skip_wolf, max_rounds). Returns job ID.
- **GET /api/jobs/{id}** — Poll job status (queued, running, completed,
  failed).
- **GET /api/jobs/{id}/results** — Retrieve results (list of hits with
  Z-score, RMSD, alignment blocks, rotation/translation).
- **GET /api/jobs** — List user's jobs.

Flow:
1. User uploads query structure via API.
2. Backend imports it (`dali.import_pdb`), writes `.dat` to job working dir.
3. Backend submits a SLURM job (`sbatch`) that runs `worker/run_search.py`:
   - Creates a `ProteinStore` pointed at the target library `.dat` dir.
   - Adds the query protein to the store.
   - Calls `dali.search_database()` or `dali.iterative_search()`.
   - Writes results to JSON in the job working dir.
   - Updates job status in Postgres.
4. Backend polls SLURM (`sacct`/`squeue`) or the worker updates status
   directly via DB.

### Phase 3: Job Tracking + Auth

- **PostgreSQL schema**:
  - `users`: id, name, api_key, created_at
  - `libraries`: id, name, type (ecod/pdb), dat_dir, entry_count, updated_at
  - `jobs`: id, user_id, library_id, status, query_code, parameters (JSON),
    slurm_job_id, submitted_at, started_at, completed_at, error_message
  - `results`: id, job_id, hit_cd2, zscore, score, rmsd, nblock, blocks
    (JSON), rotation (JSON), translation (JSON), alignments (JSON), round
- **Auth**: API key in `Authorization` header. Middleware checks key against
  `users` table. Simple — no sessions, no OAuth.
- **Status transitions**: queued -> submitted -> running -> completed | failed

### Phase 4: Frontend

Next.js app with:

- **Submit page** (`/submit`):
  - File upload (PDB/CIF)
  - Library selector (ECOD domains / PDB chains)
  - Parameter controls (z-score cutoff, skip_wolf toggle)
  - Submit button -> POST /api/jobs

- **Dashboard page** (`/jobs`):
  - Table of user's jobs: id, query, library, status, submitted time
  - Auto-refresh for pending jobs
  - Click to view results

- **Results page** (`/jobs/[id]`):
  - Hit table: sortable by Z-score, RMSD, nblock
  - Click a hit to open detail view

- **Detail view** (`/jobs/[id]/hits/[cd2]`):
  - **Structure superposition**: Mol* viewer showing query (color A)
    superposed on hit (color B) using the rotation/translation from the
    alignment. Load both structures, apply transform, highlight aligned
    regions.
  - **Alignment viewer**: Block-level alignment diagram showing which
    residue ranges in query map to which ranges in hit. Color by
    secondary structure. Show sequence threading.

### Phase 5: Polish + Deploy

- Error handling and retries for SLURM failures
- Job cleanup (expire old jobs, delete working dirs)
- Library update automation (cron/systemd timer for ECOD/PDB refresh)
- Basic logging and monitoring
- Internal deployment (systemd services for backend, nginx reverse proxy
  for frontend)


## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Backend framework | FastAPI (Python) | Direct access to dali_rust PyO3 bindings; async; good for I/O-bound API |
| Database | PostgreSQL | Already available (psycopg2); robust; JSON columns for flexible result storage |
| Job dispatch | SLURM (sbatch) | leda cluster available; searches are CPU-bound; natural fit |
| 3D viewer | Mol* | Modern, actively maintained, supports superposition transforms |
| Frontend | Next.js (App Router) | React ecosystem; SSR for initial load; good DX |
| Auth | API keys | Simplest viable approach for internal tool |
| Library storage | Flat .dat files + Postgres metadata | Matches dali_rust ProteinStore expectations; metadata in DB for search/filter |


## Dependencies

- `dali_rust` Python bindings (via maturin from `../dali_cl/dali_rust/dali-python`)
- Python 3.11+, FastAPI, SQLAlchemy, Alembic, psycopg2
- Node.js 20+, Next.js 14+, Mol* (molstar npm package)
- PostgreSQL 14+
- SLURM (leda cluster)
