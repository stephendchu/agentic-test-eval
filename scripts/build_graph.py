"""Build the repo knowledge graph (test-to-code + co-modification + lifetimes).

Usage:
    .venv/bin/python scripts/build_graph.py --max-history 3000
"""

from __future__ import annotations

import argparse

from atw.config import CFG
from atw.graph.build import build_graph


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-history", type=int, default=3000,
                    help="commits to walk for co-modification + lifetime stats")
    args = ap.parse_args()

    print(f"Building graph for {CFG.repo.name} (history depth {args.max_history})...")
    g = build_graph(max_history=args.max_history)
    n_imp_edges = sum(len(v) for v in g.imports_inverse.values())
    n_comod_pairs = sum(len(v) for v in g.comod.values())
    print(f"  prod files          : {len(g.prod_files)}")
    print(f"  test files          : {len(g.test_files)}")
    print(f"  import edges (p->t)  : {n_imp_edges}  over {len(g.imports_inverse)} prod files")
    print(f"  co-mod pairs (p,t)   : {n_comod_pairs}  over {len(g.comod)} prod files")
    print(f"  files with history   : {len(g.file_stats)}")
    print("  saved -> data/graph/graph.json")


if __name__ == "__main__":
    main()
