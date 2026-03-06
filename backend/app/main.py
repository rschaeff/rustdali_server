"""FastAPI application entry point."""

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_db
from .routers import admin, jobs, results, libraries, structures

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("rustdali")

app = FastAPI(
    title="RustDALI Server",
    description="Protein structural search service powered by dali_rust",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    start = time.time()
    response = await call_next(request)
    elapsed = (time.time() - start) * 1000
    logger.info(
        "%s %s %d %.0fms [%s]",
        request.method, request.url.path, response.status_code, elapsed, request_id,
    )
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(admin.router)
app.include_router(jobs.router)
app.include_router(results.router)
app.include_router(libraries.router)
app.include_router(structures.router)


@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("RustDALI Server started on %s:%d", settings.host, settings.port)


@app.get("/api/health")
def health():
    return {"status": "ok"}
