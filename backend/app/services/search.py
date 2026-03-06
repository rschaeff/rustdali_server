"""DALI search execution — called by the SLURM worker."""

import json
import os
from pathlib import Path

import dali


def run_search(
    query_pdb_path: str,
    query_chain: str,
    query_code: str,
    library_dat_dir: str,
    work_dir: str,
    z_cut: float = 2.0,
    skip_wolf: bool = False,
    max_rounds: int = 10,
) -> list[dict]:
    """Import query, run search, return serializable results.

    Args:
        query_pdb_path: Path to uploaded PDB/CIF file.
        query_chain: Chain ID to extract.
        query_code: Code to assign to the query protein.
        library_dat_dir: Directory containing target library .dat files.
        work_dir: Job working directory for intermediate files.
        z_cut: Z-score cutoff.
        skip_wolf: Whether to skip the WOLF path.
        max_rounds: Maximum iterative search rounds.

    Returns:
        List of result dicts ready for JSON serialization / DB insertion.
    """
    work_path = Path(work_dir)

    # Import query structure
    # Note: import_pdb appends chain to code, e.g. "1enh" + chain "A" -> "1enhA"
    protein = dali.import_pdb(query_pdb_path, query_chain, query_code)
    actual_code = protein.code

    # Create a store directory under work_dir with symlinks to library .dat files.
    # This avoids polluting the library dir with query/masked protein .dat files
    # written by add_protein() and iterative_search().
    store_dir = work_path / "store"
    store_dir.mkdir(exist_ok=True)
    lib_path = Path(library_dat_dir)
    for dat_file in lib_path.glob("*.dat"):
        link = store_dir / dat_file.name
        if not link.exists():
            os.symlink(dat_file, link)

    # Build store from work_dir and add query protein
    store = dali.ProteinStore(str(store_dir))
    store.add_protein(protein)

    # Discover targets (all library .dat files, excluding query)
    targets = [
        dat_file.stem for dat_file in lib_path.glob("*.dat")
        if dat_file.stem != actual_code
    ]

    if not targets:
        return []

    # Run iterative search
    hits = dali.iterative_search(
        actual_code, targets, store,
        min_zscore=z_cut,
        skip_wolf=skip_wolf,
        max_rounds=max_rounds,
    )

    # Serialize results
    results = []
    for hit in hits:
        results.append({
            "hit_cd2": hit.cd2,
            "zscore": hit.zscore,
            "score": hit.score,
            "rmsd": hit.rmsd,
            "nblock": hit.nblock,
            "blocks": [
                {"l1": b.l1, "r1": b.r1, "l2": b.l2, "r2": b.r2}
                for b in hit.blocks
            ],
            "rotation": hit.rotation,
            "translation": hit.translation,
            "alignments": hit.alignments,
            "round": hit.round,
        })

    # Also write results to JSON in work dir for debugging
    results_path = work_path / "results.json"
    results_path.write_text(json.dumps(results, indent=2))

    return results
