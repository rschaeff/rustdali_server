"""DALI search execution — called by the SLURM worker."""

import json
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
    protein = dali.import_pdb(query_pdb_path, query_chain, query_code)
    query_dat = work_path / f"{query_code}.dat"
    dali.write_dat(protein, str(query_dat))

    # Build store from library + query
    store = dali.ProteinStore(library_dat_dir)
    store.add_protein(protein)

    # Discover targets (all .dat files in library)
    targets = [
        p.stem for p in Path(library_dat_dir).glob("*.dat")
        if p.stem != query_code
    ]

    if not targets:
        return []

    # Run iterative search
    hits = dali.iterative_search(
        query_code, targets, store,
        min_zscore=z_cut,
        skip_wolf=skip_wolf,
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
