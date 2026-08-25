"""Apply source-specific reviewed decisions for media batch 04.

Batch 04 resolves only records whose substantive focus can be defended from the
locked scope plus row-level evidence/title/date/source checks. It adds no stance
labels and does not use class balance or model outcomes.
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

# Direct Marikana memory, accountability, policing, justice, or substantive
# Lonmin labour/social-condition records.
INCLUDE_CASE_IDS = {
    "DISC-MEDIA-0286",  # 2021 Marikana memorialisation; source-specific recovery confirms 2012 killings/victims focus
    "DISC-MEDIA-0546",  # LRC: SAPS and Lonmin responsibility for deaths/injuries
    "DISC-MEDIA-0554",  # Farlam Commission / lack of prosecutions
    "DISC-MEDIA-0559",  # SAPS lessons/correction after Marikana
    "DISC-MEDIA-0566",  # victims' families, compensation and calls for justice
    "DISC-MEDIA-0582",  # Lonmin miners' health/social conditions with strike, wages, housing and commission context
    "DISC-MEDIA-0588",  # explicit Marikana massacre remembrance/accountability
    "DISC-MEDIA-0658",  # substantive Lonmin labour/strike relations
    "DISC-MEDIA-0686",  # explicit policing lessons from Marikana
}

# Ownership transition was prospectively declared in scope. These records are
# not included merely because they are merger stories: they have direct labour,
# retrenchment/community or union-contestation dimensions.
INCLUDE_OWNERSHIP_TRANSITION_IDS = {
    "DISC-MEDIA-0369",  # AMCU challenges Sibanye-Lonmin merger over job losses
    "DISC-MEDIA-0644",  # AMCU appeal in final merger stage, labour/community context
    "DISC-MEDIA-0675",  # merger approval with retrenchment moratorium
}

# Clear operation/project/company items where Marikana/Lonmin is a location or
# corporate identifier rather than the case under study.
EXCLUDE_ROUTINE_IDS = {
    "DISC-MEDIA-0432",  # chair retirement
    "DISC-MEDIA-0446",  # production ramp-up/output article
    "DISC-MEDIA-0464",  # rights-issue prospectus
    "DISC-MEDIA-0494",  # compressed-air cost saving
    "DISC-MEDIA-0498",  # operational mine-safety performance at Marikana
    "DISC-MEDIA-0510",  # furnace shutdown
    "DISC-MEDIA-0563",  # K4 PGM mining project update; Marikana is operation/project name
    "DISC-MEDIA-0638",  # deal-attractions presentation
    "DISC-MEDIA-0639",  # duplicate/republication of deal-attractions presentation
    "DISC-MEDIA-0664",  # debt/streaming/corporate-finance story
    "DISC-MEDIA-0668",  # nickel beneficiation plant at Lonmin refinery
    "DISC-MEDIA-0669",  # republication of nickel plant story
    "DISC-MEDIA-0684",  # chute-supply contract at Marikana operation
}

# Marikana is used mainly as a comparator/reference; the substantive historical
# subject is the Sasol strike, so it is outside the strict case corpus.
EXCLUDE_ANALOGICAL_IDS = {
    "DISC-MEDIA-0337",
}


def read_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


rows = read_rows(LEDGER)
by_id = {r["candidate_id"]: r for r in rows}
requested = INCLUDE_CASE_IDS | INCLUDE_OWNERSHIP_TRANSITION_IDS | EXCLUDE_ROUTINE_IDS | EXCLUDE_ANALOGICAL_IDS
missing = sorted(requested - set(by_id))
if missing:
    raise RuntimeError(f"Batch 04 candidate IDs missing from ledger: {missing}")

# Refuse to silently overwrite a prior final decision. This keeps batch-04
# provenance auditable and forces an explicit correction if a conflict exists.
conflicts = sorted(cid for cid in requested if by_id[cid].get("decision_status", "").startswith("final_"))
if conflicts:
    raise RuntimeError(f"Batch 04 expected pending rows but found prior final decisions: {conflicts}")

for cid in sorted(INCLUDE_CASE_IDS):
    r = by_id[cid]
    r.update({
        "decision_status": "final_batch_04",
        "final_decision": "include",
        "reason_code": "include_case_central",
        "decision_note": (
            "Included after source-specific Batch-04 review: substantive focus is Marikana memory, justice/accountability, policing, "
            "victims/compensation, or a declared longitudinal Lonmin labour/social-condition theme."
        ),
        "decision_provenance": "review_batch_04_source_specific_2026-08-23",
    })

for cid in sorted(INCLUDE_OWNERSHIP_TRANSITION_IDS):
    r = by_id[cid]
    r.update({
        "decision_status": "final_batch_04",
        "final_decision": "include",
        "reason_code": "include_lonmin_ownership_transition_labour_governance",
        "decision_note": (
            "Included after source-specific Batch-04 review under the prospectively declared ownership-transition scope: the "
            "Sibanye-Lonmin transition is substantively tied to union contestation, job losses/retrenchment or community/labour governance."
        ),
        "decision_provenance": "review_batch_04_source_specific_2026-08-23",
    })

for cid in sorted(EXCLUDE_ROUTINE_IDS):
    r = by_id[cid]
    r.update({
        "decision_status": "final_batch_04",
        "final_decision": "exclude",
        "reason_code": "exclude_general_corporate_financial",
        "decision_note": (
            "Excluded after source-specific Batch-04 review: substantive focus is routine production, plant/project activity, finance, "
            "management, contracting or mine-operation performance; Marikana/Lonmin is primarily an operation or corporate identifier."
        ),
        "decision_provenance": "review_batch_04_source_specific_2026-08-23",
    })

for cid in sorted(EXCLUDE_ANALOGICAL_IDS):
    r = by_id[cid]
    r.update({
        "decision_status": "final_batch_04",
        "final_decision": "exclude",
        "reason_code": "exclude_analogical_marikana_reference",
        "decision_note": (
            "Excluded after source-specific Batch-04 review: Marikana is used as an analogy/comparator, while the substantive subject "
            "is another historical strike/event rather than the Marikana/Lonmin case."
        ),
        "decision_provenance": "review_batch_04_source_specific_2026-08-23",
    })

with LEDGER.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)

status_counts = Counter(r["decision_status"] for r in rows)
reason_counts = Counter(r["reason_code"] for r in rows)
final_rows = [r for r in rows if r["decision_status"].startswith("final_")]
batch4_rows = [r for r in rows if r["decision_status"] == "final_batch_04"]
summary = {
    "ledger_scope": "all_690_archive_title_trigger_media_candidates",
    "records_in_ledger": len(rows),
    "final_decisions_made": len(final_rows),
    "final_inclusions": sum(r["final_decision"] == "include" for r in final_rows),
    "final_exclusions": sum(r["final_decision"] == "exclude" for r in final_rows),
    "pending_substantive_review": sum(r["decision_status"] == "pending_substantive_review" for r in rows),
    "decision_status_counts": dict(status_counts),
    "reason_code_counts": dict(reason_counts),
    "batch_04_applied_counts": dict(Counter(r["reason_code"] for r in batch4_rows)),
    "important_note": (
        "Batch 04 is source-specific and explicit-ID based. It resolves direct justice/policing/memory and qualified ownership-transition "
        "records plus clear routine/project false positives. Remaining ambiguous records are not forced. No stance labels, class targets "
        "or model outputs were used."
    ),
}
SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
