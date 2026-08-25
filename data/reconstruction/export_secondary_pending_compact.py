"""Export compact pending-only secondary review tables by evidence class."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "data" / "reconstruction"
QUEUE = RECON / "secondary_media_substantive_review_queue.csv"


def read_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


rows = read_rows(QUEUE)
fields = [
    "candidate_id", "title", "year", "publisher", "url", "evidence_class",
    "retrieved_lonmin_mentions", "retrieved_sibanye_mentions", "case_terms",
    "case_mentions_total", "event_terms", "event_distinct_terms", "social_terms",
    "social_distinct_terms", "corporate_terms", "corporate_distinct_terms",
]
for klass, stem in [
    ("strong_case_context_supported", "secondary_pending_strong_case_compact"),
    ("possible_lonmin_substantive_context", "secondary_pending_possible_lonmin_compact"),
]:
    chosen = [{k: r.get(k, "") for k in fields} for r in rows if r.get("evidence_class") == klass]
    with (RECON / f"{stem}.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(chosen)
    (RECON / f"{stem}.json").write_text(json.dumps(chosen, indent=2), encoding="utf-8")
    print(stem, len(chosen))
