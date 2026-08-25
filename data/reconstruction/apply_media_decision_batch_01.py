"""Write the first reviewed substantive-decision batch for low-signal media.

This batch is intentionally narrow and implements decisions accepted after
review of the locked rubric and row-level targeted evidence:

- `strong_early_2012_event_context` -> include_case_central
- `strong_routine_corporate_signal` -> exclude_general_corporate_financial
- every other evidence class -> remains pending (`review_ambiguous`), not a
  final inclusion/exclusion decision.

This is not a model or stance-driven selection. The evidence classes are
transparent text-signal summaries and the batch rule is recorded explicitly so
reviewers can reproduce and challenge every decision.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "data" / "reconstruction"
INFILE = RECON / "low_signal_substantive_evidence.csv"
OUT = RECON / "media_substantive_decision_ledger.csv"
SUMMARY = RECON / "media_substantive_decision_summary.json"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


rows = []
counts: Counter[str] = Counter()
reason_counts: Counter[str] = Counter()
for r in read_rows(INFILE):
    evidence_class = (r.get("evidence_class") or "").strip()

    if evidence_class == "strong_early_2012_event_context":
        final_decision = "include"
        reason_code = "include_case_central"
        decision_status = "final_batch_01"
        decision_note = (
            "Included under the locked rubric: contemporaneous August-October 2012 Lonmin coverage has multiple independent "
            "strike/worker/police/death/wage/union signals. Literal 'Marikana' is not required for this early-event coverage."
        )
    elif evidence_class == "strong_routine_corporate_signal":
        final_decision = "exclude"
        reason_code = "exclude_general_corporate_financial"
        decision_status = "final_batch_01"
        decision_note = (
            "Excluded under the locked rubric: title and retrieved text are dominated by routine corporate, financial, production, "
            "transaction or project material, with no high-specificity Marikana-case term and minimal labour/community case evidence."
        )
    else:
        final_decision = ""
        reason_code = "review_ambiguous"
        decision_status = "pending_substantive_review"
        decision_note = (
            "Not decided in batch 01. Evidence is either ambiguous, only likely corporate, or suggests possible substantive labour/community context."
        )

    counts[decision_status] += 1
    reason_counts[reason_code] += 1
    rows.append({
        "candidate_id": r.get("candidate_id", ""),
        "title": r.get("title", ""),
        "year": r.get("year", ""),
        "publication_date_from_url": r.get("publication_date_from_url", ""),
        "publisher": r.get("publisher", ""),
        "url": r.get("url", ""),
        "retrieved_text_words": r.get("retrieved_text_words", ""),
        "retrieved_text_sha256": r.get("retrieved_text_sha256", ""),
        "evidence_class": evidence_class,
        "event_terms": r.get("event_terms", ""),
        "social_terms": r.get("social_terms", ""),
        "corporate_terms": r.get("corporate_terms", ""),
        "decision_status": decision_status,
        "final_decision": final_decision,
        "reason_code": reason_code,
        "decision_note": decision_note,
        "decision_provenance": "review_batch_01_locked_rubric_2026-08-23",
    })

if rows:
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

final_rows = [r for r in rows if r["decision_status"].startswith("final_")]
summary = {
    "ledger_scope": "154_lonmin_only_low_case_signal_records",
    "records_in_ledger": len(rows),
    "final_decisions_made": len(final_rows),
    "final_inclusions": sum(1 for r in final_rows if r["final_decision"] == "include"),
    "final_exclusions": sum(1 for r in final_rows if r["final_decision"] == "exclude"),
    "pending_substantive_review": sum(1 for r in rows if r["decision_status"] == "pending_substantive_review"),
    "decision_status_counts": dict(counts),
    "reason_code_counts": dict(reason_counts),
    "decision_rule": {
        "strong_early_2012_event_context": "include_case_central",
        "strong_routine_corporate_signal": "exclude_general_corporate_financial",
        "all_other_evidence_classes": "review_ambiguous_pending"
    },
    "important_note": (
        "Batch 01 is a deliberately high-confidence reviewed batch. Likely-routine-corporate, possible-case-context and ambiguous rows "
        "remain pending rather than being forced. No stance label, class target or model output was used."
    )
}
SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
