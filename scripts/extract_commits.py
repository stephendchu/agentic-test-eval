"""Mine the labeled eval set from the target repo's git history.

Usage:
    .venv/bin/python scripts/extract_commits.py --limit 100
"""

from __future__ import annotations

import argparse

from atw.config import CFG
from atw.ingest.commit_extractor import extract


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=CFG.n_commits_full,
                    help="max qualifying commits to collect")
    ap.add_argument("--after", default=CFG.post_cutoff_after,
                    help="only commits after this ISO date (contamination control)")
    ap.add_argument("--max-scan", type=int, default=20_000,
                    help="safety bound on commits walked")
    args = ap.parse_args()

    print(f"Target repo : {CFG.repo.name} ({CFG.repo.url})")
    print(f"After date  : {args.after}  |  limit: {args.limit}")
    recs = extract(after=args.after, limit=args.limit, max_scan=args.max_scan)
    print(f"\nExtracted {len(recs)} qualifying commits -> data/commits/")
    for r in recs[:12]:
        print(f"  {r.sha[:10]}  {r.date[:10]}  +{r.added_test_functions}tf  "
              f"{len(r.prod_files)}prod/{len(r.test_files)}test  {r.subject[:55]}")


if __name__ == "__main__":
    main()
