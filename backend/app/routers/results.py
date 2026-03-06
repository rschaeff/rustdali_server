"""Result retrieval endpoints."""

import gzip
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Job, Library, LibraryEntry, Result, User
from ..schemas import ResultOut, AlignmentOut
from ..auth import get_current_user

router = APIRouter(prefix="/api/jobs/{job_id}/results", tags=["results"])

PDB_MIRROR = Path("/usr2/pdb/data/structures/divided/pdb")

_THREE_TO_ONE = {
    "ALA": "A", "CYS": "C", "ASP": "D", "GLU": "E", "PHE": "F",
    "GLY": "G", "HIS": "H", "ILE": "I", "LYS": "K", "LEU": "L",
    "MET": "M", "ASN": "N", "PRO": "P", "GLN": "Q", "ARG": "R",
    "SER": "S", "THR": "T", "VAL": "V", "TRP": "W", "TYR": "Y",
}


def _extract_ca_sequence(pdb_path: Path, chain: str) -> tuple[str, list[int]]:
    """Extract CA sequence and residue numbers from a PDB file."""
    seen: set[str] = set()
    seq: list[str] = []
    resids: list[int] = []
    opener = gzip.open if pdb_path.suffix == ".gz" else open
    with opener(pdb_path, "rt") as f:
        for line in f:
            if line.startswith("ATOM") and line[21] == chain and line[12:16].strip() == "CA":
                reskey = line[22:27].strip()
                if reskey not in seen:
                    seen.add(reskey)
                    seq.append(_THREE_TO_ONE.get(line[17:20].strip(), "X"))
                    # Parse residue number (may have insertion code)
                    try:
                        resids.append(int(line[22:26].strip()))
                    except ValueError:
                        resids.append(len(seq))
    return "".join(seq), resids


def _chain_from_hit_code(hit_code: str, entry: LibraryEntry | None) -> str:
    """Extract chain ID from a hit code."""
    if entry and entry.chain_id:
        return entry.chain_id
    # ECOD: e1p7iA1 -> chain at position 5
    if hit_code.startswith("e") and len(hit_code) >= 6:
        return hit_code[5]
    # PDB: 1a6mA -> last char
    if len(hit_code) == 5:
        return hit_code[4]
    return "A"


def _pdb_id_from_hit_code(hit_code: str, entry: LibraryEntry | None) -> str:
    """Extract PDB ID from a hit code."""
    if entry and entry.pdb_id:
        return entry.pdb_id.lower()
    if hit_code.startswith("e") and len(hit_code) >= 6:
        return hit_code[1:5].lower()
    if len(hit_code) >= 5:
        return hit_code[:4].lower()
    return hit_code.lower()


@router.get("", response_model=list[ResultOut])
def list_results(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return (
        db.query(Result)
        .filter(Result.job_id == job_id)
        .order_by(Result.zscore.desc())
        .all()
    )


@router.get("/{result_id}", response_model=ResultOut)
def get_result(
    job_id: uuid.UUID,
    result_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    result = db.query(Result).filter(Result.id == result_id, Result.job_id == job_id).first()
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return result


def _build_alignment(
    query_seq: str,
    query_resids: list[int],
    hit_seq: str,
    hit_resids: list[int],
    pairs: list[list[int]],
) -> dict:
    """Build gapped alignment strings from per-residue position pairs.

    pairs: list of [query_idx, hit_idx] where indices are 1-based into
    the protein's residue arrays.
    """
    query_line = []
    match_line = []
    hit_line = []
    query_nums = []
    hit_nums = []

    prev_qi, prev_hi = None, None

    for qi, hi in pairs:
        # 1-based to 0-based
        qi0 = qi - 1
        hi0 = hi - 1

        # Insert gaps for discontinuities
        if prev_qi is not None:
            q_gap = qi - prev_qi - 1
            h_gap = hi - prev_hi - 1

            if q_gap > 0 and h_gap > 0:
                # Both sides have unaligned residues — show the longer,
                # gap the shorter
                n = max(q_gap, h_gap)
                q_insert = query_seq[prev_qi:qi0] if q_gap > 0 else ""
                h_insert = hit_seq[prev_hi:hi0] if h_gap > 0 else ""
                q_insert = q_insert.ljust(n, "-")
                h_insert = h_insert.ljust(n, "-")
                for k in range(n):
                    query_line.append(q_insert[k])
                    hit_line.append(h_insert[k])
                    match_line.append(" ")
                    query_nums.append(None)
                    hit_nums.append(None)
            elif q_gap > 0:
                for k in range(prev_qi, qi0):
                    query_line.append(query_seq[k])
                    hit_line.append("-")
                    match_line.append(" ")
                    query_nums.append(query_resids[k])
                    hit_nums.append(None)
            elif h_gap > 0:
                for k in range(prev_hi, hi0):
                    query_line.append("-")
                    hit_line.append(hit_seq[k])
                    match_line.append(" ")
                    query_nums.append(None)
                    hit_nums.append(hit_resids[k])

        qr = query_seq[qi0] if qi0 < len(query_seq) else "?"
        hr = hit_seq[hi0] if hi0 < len(hit_seq) else "?"

        query_line.append(qr)
        hit_line.append(hr)
        if qr == hr:
            match_line.append("|")
        else:
            match_line.append(".")
        query_nums.append(query_resids[qi0] if qi0 < len(query_resids) else None)
        hit_nums.append(hit_resids[hi0] if hi0 < len(hit_resids) else None)

        prev_qi, prev_hi = qi, hi

    return {
        "query_seq": "".join(query_line),
        "match_line": "".join(match_line),
        "hit_seq": "".join(hit_line),
        "query_resids": query_nums,
        "hit_resids": hit_nums,
    }


@router.get("/{result_id}/alignment", response_model=AlignmentOut)
def get_alignment(
    job_id: uuid.UUID,
    result_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return formatted pairwise alignment for a search hit."""
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    result = db.query(Result).filter(Result.id == result_id, Result.job_id == job_id).first()
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")

    if not result.alignments:
        raise HTTPException(status_code=404, detail="No alignment data for this result")

    # Get query sequence from uploaded PDB
    params = job.parameters or {}
    upload_path = Path(params.get("upload_path", ""))
    query_chain = params.get("query_chain", "A")
    if not upload_path.exists():
        raise HTTPException(status_code=404, detail="Query PDB file not found")
    query_seq, query_resids = _extract_ca_sequence(upload_path, query_chain)

    # Get hit sequence from PDB mirror
    entry = (
        db.query(LibraryEntry)
        .filter(LibraryEntry.library_id == job.library_id, LibraryEntry.code == result.hit_cd2)
        .first()
    )
    pdb_id = _pdb_id_from_hit_code(result.hit_cd2, entry)
    hit_chain = _chain_from_hit_code(result.hit_cd2, entry)
    mid = pdb_id[1:3]
    hit_pdb_path = PDB_MIRROR / mid / f"pdb{pdb_id}.ent.gz"
    if not hit_pdb_path.exists():
        raise HTTPException(status_code=404, detail=f"Hit PDB not found: {pdb_id}")
    hit_seq, hit_resids = _extract_ca_sequence(hit_pdb_path, hit_chain)

    alignment = _build_alignment(
        query_seq, query_resids,
        hit_seq, hit_resids,
        result.alignments,
    )

    return AlignmentOut(
        query_code=job.query_code,
        hit_code=result.hit_cd2,
        query_nres=len(query_seq),
        hit_nres=len(hit_seq),
        **alignment,
    )
