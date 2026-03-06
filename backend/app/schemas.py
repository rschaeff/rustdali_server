"""Pydantic request/response schemas."""

from __future__ import annotations
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# --- Auth ---

class UserOut(BaseModel):
    id: UUID
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)


class UserOutWithKey(BaseModel):
    id: UUID
    name: str
    api_key: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Libraries ---

class LibraryOut(BaseModel):
    id: UUID
    name: str
    lib_type: str
    entry_count: int
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Jobs ---

class JobSubmit(BaseModel):
    library_id: UUID
    query_chain: str = "A"
    query_code: str | None = None
    z_cut: float = Field(default=2.0, ge=0.0)
    skip_wolf: bool = False
    max_rounds: int = Field(default=10, ge=1, le=100)


class JobOut(BaseModel):
    id: UUID
    status: str
    query_code: str
    query_filename: str | None
    parameters: dict
    slurm_job_id: str | None
    submitted_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    library: LibraryOut

    model_config = {"from_attributes": True}


# --- Results ---

class AlignmentBlockOut(BaseModel):
    l1: int
    r1: int
    l2: int
    r2: int


class ResultOut(BaseModel):
    id: UUID
    hit_cd2: str
    zscore: float
    score: float | None
    rmsd: float | None
    nblock: int | None
    blocks: list[AlignmentBlockOut] | None
    rotation: list[list[float]] | None
    translation: list[float] | None
    alignments: list[list[int]] | None
    round: int

    model_config = {"from_attributes": True}
