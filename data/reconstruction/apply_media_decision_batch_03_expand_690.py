"""Expand the substantive-decision ledger to all 690 archive title-trigger rows.

Batch 03 carries forward reviewed decisions from batches 01-02 and applies only
additional high-confidence, transparent rules to records still pending:

- strong early-2012 Lonmin event context -> include
- strong routine corporate/financial context -> exclude
- Marikana-name-only routine project/corporate context -> exclude
- strong case context -> include only when an additional conservative guard is
  met: a case-process title, >=4 distinct labour/event signals, >=2 distinct
  social/governance signals, or a highly specific Farlam/Wonderkop/Nkaneng/Bapo
  term.

All other records remain pending. These are substantive eligibility decisions
before duplicate resolution, not stance labels or model-derived selections.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "data" / "reconstruction"
EVIDENCE = RECON / "media_targeted_substantive_evidence.csv"
LOW_LEDGER = RECON / "media_substantive_decision_ledger.csv"
OUT = RECON / "media_substantive_decision_ledger.csv"
SUMMARY = RECON / "media_substantive_decision_summary.json"


def read_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def as_int(v) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def as_bool(v) -> bool:
    return str(v or "").strip().lower() == "true"


old_rows = read_rows(LOW_LEDGER)
old_by_id = {r["candidate_id"]: r for r in old_rows}
evidence_rows = read_rows(EVIDENCE)
if len(evidence_rows) != 690:
    raise RuntimeError(f"Expected 690 evidence rows, found {len(evidence_rows)}")

rows = []
batch3_applied = Counter()
for e in evidence_rows:
    cid = e.get("candidate_id", "")
    existing = old_by_id.get(cid)

    base = {
        "candidate_id": cid,
        "title": e.get("title", ""),
        "year": e.get("year", ""),
        "publication_date_from_url": e.get("publication_date_from_url", ""),
        "publisher": e.get("publisher", ""),
        "url": e.get("url", ""),
        "retrieved_text_words": e.get("retrieved_text_words", ""),
        "retrieved_text_sha256": e.get("retrieved_text_sha256", ""),
        "evidence_class": e.get("evidence_class", ""),
        "event_terms": e.get("event_terms", ""),
        "social_terms": e.get("social_terms", ""),
        "corporate_terms": e.get("corporate_terms", ""),
        "decision_status": "pending_substantive_review",
        "final_decision": "",
        "reason_code": "review_ambiguous",
        "decision_note": "Pending substantive review after conservative batch-03 screening.",
        "decision_provenance": "pending_after_batch_03_2026-08-23",
    }

    # Carry forward the already reviewed 154-row decisions and pending states.
    if existing:
        for k in ["decision_status", "final_decision", "reason_code", "decision_note", "decision_provenance"]:
            base[k] = existing.get(k, base[k])

    if base["decision_status"] == "pending_substantive_review":
        klass = e.get("evidence_class", "")
        if klass == "strong_early_2012_event_context":
            base.update({
                "decision_status": "final_batch_03",
                "final_decision": "include",
                "reason_code": "include_case_central",
                "decision_note": (
                    "Included by conservative whole-queue review: contemporaneous August-October 2012 Lonmin coverage has multiple "
                    "independent strike/worker/police/death/wage/union signals, so literal 'Marikana' is not required."
                ),
                "decision_provenance": "review_batch_03_conservative_whole_queue_2026-08-23",
            })
            batch3_applied["include_strong_early_2012_event_context"] += 1
        elif klass == "strong_routine_corporate_signal":
            base.update({
                "decision_status": "final_batch_03",
                "final_decision": "exclude",
                "reason_code": "exclude_general_corporate_financial",
                "decision_note": (
                    "Excluded by conservative whole-queue review: title and text are dominated by routine corporate/financial/production "
                    "material with minimal case-event/community evidence."
                ),
                "decision_provenance": "review_batch_03_conservative_whole_queue_2026-08-23",
            })
            batch3_applied["exclude_strong_routine_corporate_signal"] += 1
        elif klass == "case_name_only_routine_project_or_corporate_signal":
            base.update({
                "decision_status": "final_batch_03",
                "final_decision": "exclude",
                "reason_code": "exclude_general_corporate_financial",
                "decision_note": (
                    "Excluded by conservative whole-queue review: 'Marikana' or another case/place name is used in a routine mine/project/"
                    "corporate context without substantive labour, justice, community or governance treatment."
                ),
                "decision_provenance": "review_batch_03_conservative_whole_queue_2026-08-23",
            })
            batch3_applied["exclude_case_name_only_project_or_corporate"] += 1
        elif klass == "strong_case_context_supported":
            case_terms = {x for x in (e.get("case_terms") or "").split(";") if x}
            event_distinct = as_int(e.get("event_distinct_terms"))
            social_distinct = as_int(e.get("social_distinct_terms"))
            title_case = as_bool(e.get("title_has_case_process_signal"))
            highly_specific_term = bool(case_terms & {"farlam", "wonderkop", "nkaneng", "bapo"})
            if title_case or event_distinct >= 4 or social_distinct >= 2 or highly_specific_term:
                base.update({
                    "decision_status": "final_batch_03",
                    "final_decision": "include",
                    "reason_code": "include_case_central",
                    "decision_note": (
                        "Included by conservative whole-queue review: a Marikana/Farlam/Wonderkop/Nkaneng/Bapo signal is reinforced by "
                        "a case-process title, strong labour/event context, multiple social/governance dimensions, or a highly specific case term."
                    ),
                    "decision_provenance": "review_batch_03_conservative_whole_queue_2026-08-23",
                })
                batch3_applied["include_guarded_strong_case_context"] += 1

    rows.append(base)

rows.sort(key=lambda r: r["candidate_id"])
with OUT.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

status_counts = Counter(r["decision_status"] for r in rows)
reason_counts = Counter(r["reason_code"] for r in rows)
final_rows = [r for r in rows if r["decision_status"].startswith("final_")]
evidence_counts = Counter(e.get("evidence_class", "") for e in evidence_rows)
summary = {
    "ledger_scope": "all_690_archive_title_trigger_media_candidates",
    "records_in_ledger": len(rows),
    "final_decisions_made": len(final_rows),
    "final_inclusions": sum(r["final_decision"] == "include" for r in final_rows),
    "final_exclusions": sum(r["final_decision"] == "exclude" for r in final_rows),
    "pending_substantive_review": sum(r["decision_status"] == "pending_substantive_review" for r in rows),
    "decision_status_counts": dict(status_counts),
    "reason_code_counts": dict(reason_counts),
    "batch_03_applied_counts": dict(batch3_applied),
    "evidence_class_counts": dict(evidence_counts),
    "important_note": (
        "Batch 03 expands the ledger to all 690 title-trigger records and applies only conservative high-confidence decisions. "
        "Possible-context, likely-corporate, ambiguous, low-context and acquisition-exception records remain pending. Duplicate resolution "
        "still follows substantive eligibility review. No stance labels, class targets or model outputs were used."
    )
}
SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
