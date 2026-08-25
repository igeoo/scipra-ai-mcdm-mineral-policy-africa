"""Apply explicit reviewed decisions for batch 02 of the 154 low-signal records.

This file uses explicit candidate-ID allowlists after row-level review of title,
date and targeted acquired-text evidence. Batch-02 explicit review supersedes a
broader batch-01 reason when the same record appears here, preserving the more
specific decision provenance. Ambiguous ownership-transition and extraction-stub
records remain unresolved.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "data" / "reconstruction"
LEDGER = RECON / "media_substantive_decision_ledger.csv"
SUMMARY = RECON / "media_substantive_decision_summary.json"

INCLUDE_IDS = {
    "DISC-MEDIA-0366", "DISC-MEDIA-0367", "DISC-MEDIA-0370", "DISC-MEDIA-0371",
    "DISC-MEDIA-0373", "DISC-MEDIA-0409", "DISC-MEDIA-0418", "DISC-MEDIA-0420",
    "DISC-MEDIA-0440", "DISC-MEDIA-0495", "DISC-MEDIA-0512", "DISC-MEDIA-0515",
    "DISC-MEDIA-0518", "DISC-MEDIA-0530", "DISC-MEDIA-0540", "DISC-MEDIA-0591",
    "DISC-MEDIA-0687",
}

EXCLUDE_CORPORATE_IDS = {
    "DISC-MEDIA-0261", "DISC-MEDIA-0377", "DISC-MEDIA-0379", "DISC-MEDIA-0380",
    "DISC-MEDIA-0430", "DISC-MEDIA-0439", "DISC-MEDIA-0461", "DISC-MEDIA-0479",
    "DISC-MEDIA-0529", "DISC-MEDIA-0534", "DISC-MEDIA-0535", "DISC-MEDIA-0537",
    "DISC-MEDIA-0547", "DISC-MEDIA-0552", "DISC-MEDIA-0581", "DISC-MEDIA-0586",
    "DISC-MEDIA-0597", "DISC-MEDIA-0603", "DISC-MEDIA-0614", "DISC-MEDIA-0632",
    "DISC-MEDIA-0641", "DISC-MEDIA-0642", "DISC-MEDIA-0643", "DISC-MEDIA-0671",
    "DISC-MEDIA-0673", "DISC-MEDIA-0682", "DISC-MEDIA-0685",
}

EXCLUDE_OTHER_EVENT_IDS = {
    "DISC-MEDIA-0362", "DISC-MEDIA-0483", "DISC-MEDIA-0484", "DISC-MEDIA-0485",
    "DISC-MEDIA-0486", "DISC-MEDIA-0511", "DISC-MEDIA-0580", "DISC-MEDIA-0622",
}


def read_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


rows = read_rows(LEDGER)
by_id = {r["candidate_id"]: r for r in rows}
requested = INCLUDE_IDS | EXCLUDE_CORPORATE_IDS | EXCLUDE_OTHER_EVENT_IDS
missing = sorted(requested - set(by_id))
if missing:
    raise RuntimeError(f"Batch 02 candidate IDs missing from ledger: {missing}")

for cid in sorted(INCLUDE_IDS):
    r = by_id[cid]
    r["decision_status"] = "final_batch_02"
    r["final_decision"] = "include"
    r["reason_code"] = "include_case_central"
    r["decision_note"] = (
        "Included after explicit row-level review under the locked longitudinal scope: the record substantively concerns "
        "Lonmin labour relations, AMCU/NUM dynamics, wages, strike/work-stoppage activity, 2014 platinum-strike effects, "
        "or living/community conditions rather than routine corporate reporting."
    )
    r["decision_provenance"] = "review_batch_02_explicit_id_review_2026-08-23"

for cid in sorted(EXCLUDE_CORPORATE_IDS):
    r = by_id[cid]
    r["decision_status"] = "final_batch_02"
    r["final_decision"] = "exclude"
    r["reason_code"] = "exclude_general_corporate_financial"
    r["decision_note"] = (
        "Excluded after explicit row-level review: the substantive focus is routine corporate finance, management, securities, "
        "transaction/deal mechanics, production/market outlook, contracting or non-South-African asset activity rather than the "
        "Marikana/Lonmin policy case."
    )
    r["decision_provenance"] = "review_batch_02_explicit_id_review_2026-08-23"

for cid in sorted(EXCLUDE_OTHER_EVENT_IDS):
    r = by_id[cid]
    r["decision_status"] = "final_batch_02"
    r["final_decision"] = "exclude"
    r["reason_code"] = "exclude_other_mine_or_event"
    r["decision_note"] = (
        "Excluded after explicit row-level review: this is a later isolated operational mine/shaft accident or fatality, not the "
        "August 2012 Marikana killings, their justice/accountability process, or another declared longitudinal case theme."
    )
    r["decision_provenance"] = "review_batch_02_explicit_id_review_2026-08-23"

with LEDGER.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

status_counts = Counter(r["decision_status"] for r in rows)
reason_counts = Counter(r["reason_code"] for r in rows)
final_rows = [r for r in rows if r["decision_status"].startswith("final_")]
batch2_rows = [r for r in rows if r["decision_status"] == "final_batch_02"]
batch2_reasons = Counter(r["reason_code"] for r in batch2_rows)
summary = {
    "ledger_scope": "154_lonmin_only_low_case_signal_records",
    "records_in_ledger": len(rows),
    "final_decisions_made": len(final_rows),
    "final_inclusions": sum(r["final_decision"] == "include" for r in final_rows),
    "final_exclusions": sum(r["final_decision"] == "exclude" for r in final_rows),
    "pending_substantive_review": sum(r["decision_status"] == "pending_substantive_review" for r in rows),
    "decision_status_counts": dict(status_counts),
    "reason_code_counts": dict(reason_counts),
    "batch_02_review_list_sizes": {
        "include_case_central": len(INCLUDE_IDS),
        "exclude_general_corporate_financial": len(EXCLUDE_CORPORATE_IDS),
        "exclude_other_mine_or_event": len(EXCLUDE_OTHER_EVENT_IDS),
    },
    "batch_02_applied_counts": dict(batch2_reasons),
    "important_note": (
        "Batch 02 uses explicit reviewed candidate-ID lists and supersedes a generic batch-01 reason where a more specific reviewed "
        "reason is available. Ambiguous ownership-transition, merger/job/community and extraction-stub records remain pending. "
        "No stance label, historical class target or model result was used."
    )
}
SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
