"""Build the pending-only reviewer queue for secondary archive media.

The decision ledger is the source of truth. Only records still marked
`pending_substantive_review` are emitted; evidence metadata is joined back in for
row-level review. This helper makes no membership decisions.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "data" / "reconstruction"
EVIDENCE = RECON / "secondary_media_targeted_evidence.csv"
LEDGER = RECON / "secondary_media_substantive_decision_ledger.csv"
OUT = RECON / "secondary_media_substantive_review_queue.csv"
SUMMARY = RECON / "secondary_media_substantive_review_queue_summary.json"

PRIORITY = {
    "strong_case_context_supported": 0,
    "possible_lonmin_substantive_context": 1,
    "case_term_low_context_review": 2,
    "lonmin_low_context_review": 3,
}


def read_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


evidence_rows = read_rows(EVIDENCE)
ledger_rows = read_rows(LEDGER)
if len(evidence_rows) != 1062 or len(ledger_rows) != 1062:
    raise RuntimeError(f"Expected 1062 evidence + ledger rows; got {len(evidence_rows)} and {len(ledger_rows)}")

evidence = {r["candidate_id"]: r for r in evidence_rows}
pending = [r for r in ledger_rows if r.get("decision_status") == "pending_substantive_review"]

out_rows = []
class_counts = Counter()
priority_counts = Counter()
publisher_counts = Counter()
for d in pending:
    r = evidence[d["candidate_id"]]
    klass = r.get("evidence_class", "")
    rank = PRIORITY.get(klass, 99)
    class_counts[klass] += 1
    priority_counts[str(rank)] += 1
    publisher_counts[r.get("publisher", "")] += 1
    out_rows.append({
        "candidate_id": r.get("candidate_id", ""),
        "review_priority": rank,
        "evidence_class": klass,
        "title": r.get("title", ""),
        "year": r.get("year", ""),
        "publication_date_from_url": r.get("publication_date_from_url", ""),
        "publisher": r.get("publisher", ""),
        "url": r.get("url", ""),
        "retrieved_text_words": r.get("retrieved_text_words", ""),
        "retrieved_text_sha256": r.get("retrieved_text_sha256", ""),
        "retrieved_lonmin_mentions": r.get("retrieved_lonmin_mentions", ""),
        "retrieved_sibanye_mentions": r.get("retrieved_sibanye_mentions", ""),
        "case_terms": r.get("case_terms", ""),
        "case_mentions_total": r.get("case_mentions_total", ""),
        "event_terms": r.get("event_terms", ""),
        "event_distinct_terms": r.get("event_distinct_terms", ""),
        "social_terms": r.get("social_terms", ""),
        "social_distinct_terms": r.get("social_distinct_terms", ""),
        "corporate_terms": r.get("corporate_terms", ""),
        "corporate_distinct_terms": r.get("corporate_distinct_terms", ""),
        "evidence_note": r.get("evidence_note", ""),
        "review_decision": "",
        "review_reason_code": "",
        "review_note": "",
    })

out_rows.sort(key=lambda r: (int(r["review_priority"]), r["year"], r["candidate_id"]))
with OUT.open("w", encoding="utf-8", newline="") as f:
    if out_rows:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader(); writer.writerows(out_rows)
    else:
        f.write("candidate_id,review_priority,evidence_class,title,year,publication_date_from_url,publisher,url\n")

summary = {
    "pending_records": len(out_rows),
    "evidence_class_counts": dict(class_counts),
    "review_priority_counts": dict(priority_counts),
    "publisher_counts": dict(publisher_counts),
    "priority_order": PRIORITY,
    "note": "Pending-only reviewer queue; blank review fields are intentional and no decision is made by this builder.",
}
SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
