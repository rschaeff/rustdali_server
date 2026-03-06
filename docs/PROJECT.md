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


## Progress

### Phase 0: Project Scaffold -- COMPLETE

- Repo structure: `backend/` (FastAPI), `frontend/` (Next.js), `scripts/`
- FastAPI app with routers (jobs, results, libraries), Pydantic schemas,
  API key auth middleware
- PostgreSQL schema `rustdali` on `dione:45000/ecod_protein` with tables:
  `users`, `libraries`, `library_entries`, `jobs`, `results`
- Next.js frontend with pages: landing, submit, jobs dashboard, job detail,
  result detail (shell UI with Mol* placeholder)
- SLURM worker script wired to `dali_rust` via PyO3 bindings
- DB init script seeds admin user + ECOD/PDB library entries
- Secrets in `.env` (gitignored), `.env.example` committed

### Phase 1: Library Preprocessing -- COMPLETE

Batch import of target libraries into `.dat` format via SLURM array jobs.

**ECOD domain library** — 25,016 imported (99.3% of 25,203)
- Source: `ecod_commons.domains` (representative, non-obsolete, PDB-sourced)
  joined with `ecod_commons.f_group_assignments` for A/X/H/T/F classification
- Domain masking: PDB-numbered ranges from `ecod_commons.domain_ranges`
  (`range_type='pdb'`) used with `dali.mask_protein()` to extract sub-chain
  domains. The `domains.range_definition` column uses ECOD-internal numbering
  which does NOT match PDB author residue numbers.
- 187 failures: multi-chain domains (e.g. chain `A-B`), tiny proteins
- .dat files: `data/libraries/ecod/`

**PDB chain library** — 27,289 imported (98.8% of 27,620)
- Source: `ecod_commons.protein_clusters` (run_id=1, CD-HIT 70% identity)
  joined with `ecod_commons.proteins` (source_type='pdb')
- Filtered to: single-letter chain IDs, 30-5000 residues
- PDB files from local mirror at `/usr2/pdb/data/structures/divided/pdb/`
- 331 failures: tiny proteins, PDB parse errors
- .dat files: `data/libraries/pdb/`

**Issues resolved:**
- `resid_map` from `dali.import_pdb()` returns PDB author residue numbers;
  ECOD `domains.range_definition` uses different numbering — must use
  `domain_ranges` table with `range_type='pdb'`
- SLURM nodes use `iso8859_15` locale — set `PYTHONIOENCODING=utf-8`,
  `PGCLIENTENCODING=UTF8`, `LC_ALL=en_US.UTF-8` in job scripts
- `dali_rust` error messages contain Unicode box-drawing chars — sanitize
  to ASCII before DB storage to avoid psycopg2 encoding errors
- Offset-based batch queries shift when entries change status — use stable
  code ordering with status filtering in Python


### Phase 2: Search Backend -- COMPLETE

End-to-end search pipeline: upload PDB -> import -> SLURM dispatch -> dali
search -> results in DB. Tested against both full libraries.

- Worker (`run_search.py`) verified against 25K ECOD and 27K PDB libraries
- Target list constructed from library dir glob (all `.dat` stems)
- Worker updates job status directly in DB (queued -> running -> completed/failed)
- Full SLURM round-trip tested: sbatch -> leda node -> results in DB
- Test query: myoglobin (101m) found e1a6mA1 (z=28.5, ECOD) and 8kfhA
  (z=28.2, PDB) — correct globin matches
- Search time: ~15 min for 25K ECOD library on single leda node (4 CPUs)

**Issues resolved:**
- `ProteinStore.add_protein()` writes .dat files to the store's directory;
  creating the store from the library dir polluted it with query and masked
  protein files. Fixed by creating a `store/` subdirectory in the job's
  work_dir with symlinks to library .dat files.
- `max_rounds` parameter was accepted by `run_search()` but not forwarded
  to `dali.iterative_search()`.
- SLURM job scripts were missing UTF-8 encoding exports and `unset
  OMP_PROC_BIND` (required by dali_rust/foldseek on SLURM nodes).
- Worker error messages not sanitized for Unicode before DB storage.


### Phase 3: Job Tracking + Auth -- COMPLETE

Hardened job lifecycle and operational robustness.

- SLURM failure detection via `sacct`: handles TIMEOUT, OUT_OF_MEMORY,
  NODE_FAIL, PREEMPTED, CANCELLED with descriptive error messages
- `sync_job_status()` called on-demand when GET /api/jobs/{id} is polled
- Admin bulk sync: POST /api/admin/jobs/sync checks all in-flight jobs
- Job cleanup: POST /api/admin/jobs/cleanup deletes expired jobs + work dirs
  (configurable retention, dry-run by default)
- Admin user management: POST/GET /api/admin/users (gated by admin API key
  from .env, separate from per-user API keys)
- Admin auth via `require_admin` dependency checking RUSTDALI_ADMIN_API_KEY

### Phase 4: Frontend -- COMPLETE

Functional pages with real data and 3D structure visualization.

- **Layout**: ECOD-themed (Inter font, sticky header, active nav
  highlighting, blue-600 primary accent)
- **Settings page**: API key entry with save/test connection
- **Submit page**: file upload, library selector, parameter controls
- **Jobs dashboard**: auto-refresh polling (stops when all terminal),
  status badges, timestamps
- **Job detail**: Lali column, running indicator, timing display,
  stops polling when terminal
- **Result detail**:
  - Mol* 3D structure viewer (dynamic import, loads query + hit PDB)
  - Alignment block visualization (bar diagram)
  - Breadcrumb navigation
- **Structure serving**: new `/api/jobs/{id}/structures/query` and
  `/api/jobs/{id}/structures/hit/{code}` endpoints serve decompressed
  PDB files from work_dir and local PDB mirror respectively


### Phase 5: Polish + Deploy -- COMPLETE

- Structured request logging with request IDs (`X-Request-ID` header)
- systemd units: `rustdali-backend.service` (uvicorn), `rustdali-frontend.service` (Next.js)
- nginx reverse proxy: `/api/` → backend:8000, `/` → frontend:3000
- Deploy files in `deploy/` directory
- Health endpoint at `/api/health`

## Remaining Phases

- Library update automation (re-run preprocessing on ECOD/PDB updates)


## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Backend framework | FastAPI (Python) | Direct access to dali_rust PyO3 bindings; async; good for I/O-bound API |
| Database | PostgreSQL | Already available (psycopg2); robust; JSON columns for flexible result storage |
| DB schema | `rustdali` on `ecod_protein` | Co-located with ECOD data for easy joins during preprocessing |
| Job dispatch | SLURM (sbatch) | leda cluster available; searches are CPU-bound; natural fit |
| 3D viewer | Mol* | Modern, actively maintained, supports superposition transforms |
| Frontend | Next.js (App Router) | React ecosystem; SSR for initial load; good DX |
| Auth | API keys | Simplest viable approach for internal tool |
| Library storage | Flat .dat files + Postgres metadata | Matches dali_rust ProteinStore expectations; metadata in DB for search/filter |
| ECOD domain ranges | `domain_ranges.range_type='pdb'` | Author-numbered residues match `dali.import_pdb()` resid_map |
| PDB representatives | CD-HIT 70% identity clusters | ~28K chains — large enough for comprehensive coverage, small enough for feasible search times |
| SLURM encoding | Explicit UTF-8 env vars in job scripts | leda nodes default to iso8859_15; psycopg2 chokes on Unicode error messages |
| Search store isolation | Symlinked store dir per job in work_dir | Prevents query/masked .dat files from polluting shared library directories |


## Project Structure

```
rustdali_server/
  .env                    Secrets (gitignored)
  .env.example            Template for .env
  backend/
    app/
      main.py             FastAPI entry point
      config.py           Settings from .env via pydantic-settings
      database.py         SQLAlchemy engine, sessions, schema init
      auth.py             API key middleware
      models.py           ORM: User, Library, LibraryEntry, Job, Result
      schemas.py          Pydantic request/response types
      routers/
        admin.py          Admin: users, job sync, cleanup
        jobs.py           POST/GET /api/jobs
        results.py        GET /api/jobs/{id}/results
        libraries.py      GET /api/libraries
        structures.py     PDB file serving for Mol* viewer
      services/
        slurm.py          sbatch submission + sacct polling
        search.py         dali_rust search wrapper
      worker/
        run_search.py     SLURM job entry point
    requirements.txt
  frontend/
    src/
      app/                Next.js App Router pages
        page.tsx           Landing
        submit/page.tsx    Job submission
        jobs/page.tsx      Job dashboard
        jobs/[id]/page.tsx Job detail + results table
        jobs/[id]/results/[resultId]/page.tsx  Hit detail
      components/
        StructureViewer.tsx Mol* 3D viewer component
      lib/api.ts          Typed API client
  scripts/
    init_db.py            Create schema, seed user + libraries
    preprocess_ecod.py    ECOD domain import (register/submit/import)
    preprocess_pdb.py     PDB chain import (register/submit/import)
    check_import_status.py  Monitor import progress
  data/                   (gitignored)
    libraries/ecod/       25,016 .dat files
    libraries/pdb/        27,289 .dat files
    jobs/                 Per-job working directories
    logs/                 SLURM import logs
  deploy/
    rustdali-backend.service   systemd unit for FastAPI/uvicorn
    rustdali-frontend.service  systemd unit for Next.js
    rustdali.nginx.conf        nginx reverse proxy config
  docs/
    PROJECT.md            This file
```


## Dependencies

- `dali_rust` Python bindings (via maturin from `../dali_cl/dali_rust/dali-python`)
- Python 3.11+, FastAPI, SQLAlchemy, Alembic, psycopg2, pydantic-settings
- Node.js 20+, Next.js 14+, Mol* (molstar — Phase 4)
- PostgreSQL 17 (on dione:45000)
- SLURM (leda cluster, partition: All)
