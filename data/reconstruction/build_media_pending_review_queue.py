"""Build a compact reviewer queue for archive-media records still undecided."""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "data" / "reconstruction"
LEDGER = RECON / "media_substantive_decision_ledger.csv"
EVIDENCE = RECON / "media_targeted_substantive_evidence.csv"
OUT = RECON / "media_pending_substantive_review.csv"
SUMMARY = RECON / "media_pending_substantive_review_summary.json"


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


ledger = read(LEDGER)
evidence = {r["candidate_id"]: r for r in read(EVIDENCE)}
rows = []
classes = Counter(); buckets = Counter(); publishers = Counter()
for d in ledger:
    if d.get("decision_status") != "pending_substantive_review":
        continue
    e = evidence.get(d["candidate_id"], {})
    klass = e.get("evidence_class", "")
    classes[klass] += 1
    buckets[e.get("prescreen_bucket", "")] += 1
    publishers[d.get("publisher", "")] += 1
    rows.append({
        "candidate_id": d.get("candidate_id", ""),
        "title": d.get("title", ""),
        "year": d.get("year", ""),
        "publication_date_from_url": d.get("publication_date_from_url", ""),
        "publisher": d.get("publisher", ""),
        "url": d.get("url", ""),
        "prescreen_bucket": e.get("prescreen_bucket", ""),
        "targeted_fetch_status": e.get("targeted_fetch_status", ""),
        "retrieved_text_words": e.get("retrieved_text_words", ""),
        "retrieved_text_sha256": e.get("retrieved_text_sha256", ""),
        "case_terms": e.get("case_terms", ""),
        "case_mentions_total": e.get("case_mentions_total", ""),
        "event_terms": e.get("event_terms", ""),
        "event_distinct_terms": e.get("event_distinct_terms", ""),
        "social_terms": e.get("social_terms", ""),
        "social_distinct_terms": e.get("social_distinct_terms", ""),
        "corporate_terms": e.get("corporate_terms", ""),
        "corporate_distinct_terms": e.get("corporate_distinct_terms", ""),
        "title_has_case_process_signal": e.get("title_has_case_process_signal", ""),
        "title_has_routine_corporate_signal": e.get("title_has_routine_corporate_signal", ""),
        "evidence_class": klass,
        "evidence_note": e.get("evidence_note", ""),
        "review_decision": "",
        "review_reason_code": "",
        "review_note": "",
    })

priority = {
    "acquisition_or_text_exception": 0,
    "case_term_low_context_review": 1,
    "possible_substantive_case_context": 2,
    "likely_routine_corporate_signal": 3,
    "ambiguous_low_signal": 4,
}
rows.sort(key=lambda r: (priority.get(r["evidence_class"], 9), r["year"], r["candidate_id"]))
if rows:
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
summary = {
    "pending_records": len(rows),
    "evidence_class_counts": dict(classes),
    "prescreen_bucket_counts": dict(buckets),
    "publisher_counts": dict(publishers),
    "note": "Pending-only queue. Blank review fields are intentional; no record in this file has been forced into the corpus."
}
SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
