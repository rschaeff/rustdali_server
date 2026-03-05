"""SQLAlchemy ORM models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime, ForeignKey, JSON,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .database import Base
from .config import settings

SCHEMA = settings.db_schema


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": SCHEMA}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(128), nullable=False)
    api_key = Column(String(64), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    jobs = relationship("Job", back_populates="user")


class Library(Base):
    __tablename__ = "libraries"
    __table_args__ = {"schema": SCHEMA}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(64), unique=True, nullable=False)
    lib_type = Column(String(16), nullable=False)  # "ecod" or "pdb"
    dat_dir = Column(Text, nullable=False)
    entry_count = Column(Integer, default=0)
    updated_at = Column(DateTime(timezone=True), default=utcnow)

    jobs = relationship("Job", back_populates="library")
    entries = relationship("LibraryEntry", back_populates="library", cascade="all, delete-orphan")


class LibraryEntry(Base):
    __tablename__ = "library_entries"
    __table_args__ = (
        UniqueConstraint("library_id", "code", name="uq_library_code"),
        {"schema": SCHEMA},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    library_id = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.libraries.id"), nullable=False, index=True)
    code = Column(String(64), nullable=False, index=True)  # dat file stem, e.g. "e1f0xA1"
    pdb_id = Column(String(8))
    chain_id = Column(String(16))
    domain_range = Column(Text)  # e.g. "A:274-319,A:377-567"
    nres = Column(Integer)
    nseg = Column(Integer)
    # ECOD classification (null for PDB library)
    ecod_domain_id = Column(String(32))
    ecod_uid = Column(Integer)
    a_group = Column(String(16))
    x_group = Column(String(16))
    h_group = Column(String(16))
    t_group = Column(String(16))
    f_group = Column(String(16))
    # Processing status
    status = Column(String(16), default="pending")  # pending, imported, failed
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    library = relationship("Library", back_populates="entries")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = {"schema": SCHEMA}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.users.id"), nullable=False)
    library_id = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.libraries.id"), nullable=False)
    status = Column(String(16), nullable=False, default="queued", index=True)
    query_code = Column(String(64), nullable=False)
    query_filename = Column(String(256))
    parameters = Column(JSON, default=dict)
    slurm_job_id = Column(String(32))
    work_dir = Column(Text)
    submitted_at = Column(DateTime(timezone=True), default=utcnow)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    error_message = Column(Text)

    user = relationship("User", back_populates="jobs")
    library = relationship("Library", back_populates="jobs")
    results = relationship("Result", back_populates="job", cascade="all, delete-orphan")


class Result(Base):
    __tablename__ = "results"
    __table_args__ = {"schema": SCHEMA}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.jobs.id"), nullable=False, index=True)
    hit_cd2 = Column(String(64), nullable=False)
    zscore = Column(Float, nullable=False)
    score = Column(Float)
    rmsd = Column(Float)
    nblock = Column(Integer)
    blocks = Column(JSON)
    rotation = Column(JSON)
    translation = Column(JSON)
    alignments = Column(JSON)
    round = Column(Integer, default=0)

    job = relationship("Job", back_populates="results")
