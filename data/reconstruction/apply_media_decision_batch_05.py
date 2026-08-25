"""Apply explicit reviewed decisions for media batch 05.

This batch resolves residual records where the locked scope gives a defensible
source-specific answer. Decisions are explicit candidate IDs; no automatic title
eligibility rule is introduced.
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

# Direct case aftermath, interpretation, accountability or institutional effect.
INCLUDE_CASE_IDS = {
    "DISC-MEDIA-0043",  # contemporaneous analytical treatment of capitalism and Marikana
    "DISC-MEDIA-0059",  # political/electoral effect explicitly attributed to Marikana
    "DISC-MEDIA-0556",  # ANC admission of responsibility/context: events happened under our watch
    "DISC-MEDIA-0575",  # explicit analysis of how the Marikana tragedy changed the mining industry
    "DISC-MEDIA-0613",  # court judgment on alleged harmful conduct in Marikana
}

# Prospectively declared longitudinal labour-relations/governance records where
# Lonmin itself is substantive rather than incidental.
INCLUDE_LABOUR_IDS = {
    "DISC-MEDIA-0396",  # employees demand Solidarity recognition at Lonmin
    "DISC-MEDIA-0441",  # Lonmin consults unions in post-2012 labour environment
    "DISC-MEDIA-0595",  # NUM fights Lonmin job losses
    "DISC-MEDIA-0657",  # Solidarity recognition dispute at Lonmin
    "DISC-MEDIA-0660",  # Labour Court review of Lonmin withdrawal of union recognition
}

# Prospectively declared housing/community-response records.
INCLUDE_COMMUNITY_IDS = {
    "DISC-MEDIA-0455",  # Lonmin accommodation challenge
    "DISC-MEDIA-0463",  # Lonmin community grievance system
}

# Ownership-transition records retained only where labour, jobs, retrenchment,
# community or governance dimensions are substantive. Pure procedural deal
# mechanics are excluded separately below.
INCLUDE_TRANSITION_IDS = {
    "DISC-MEDIA-0368",  # AMCU moves to overturn Sibanye-Lonmin deal
    "DISC-MEDIA-0431",  # consolidation approval argued in terms of 20,000 jobs
    "DISC-MEDIA-0524",  # competition filing with worker/union/community dimensions
    "DISC-MEDIA-0533",  # biggest union seeks to stop deal over job cuts
    "DISC-MEDIA-0619",  # job retention following Sibanye-Lonmin deal
    "DISC-MEDIA-0636",  # competition finality with community/governance conditions
    "DISC-MEDIA-0648",  # same transition/governance issue in a second substantive report
    "DISC-MEDIA-0674",  # merger approval with retrenchment moratorium
}

# Geographic homonyms: Marikana informal settlement in Philippi East/Cape Town,
# not the North West Lonmin/Marikana case.
EXCLUDE_OTHER_PLACE_IDS = {
    "DISC-MEDIA-0118",
    "DISC-MEDIA-0141",
    "DISC-MEDIA-0246",
}

# Marikana used only as a comparator for a different event.
EXCLUDE_ANALOGICAL_IDS = {
    "DISC-MEDIA-0579",
}

# Later independent labour/accident events not part of the declared case themes.
EXCLUDE_OTHER_EVENT_IDS = {
    "DISC-MEDIA-0375",  # sympathy strike supporting Sibanye gold employees
    "DISC-MEDIA-0454",  # later mudslide fatality
}

# Routine corporate, plant, production, market, board, finance, contract or pure
# transaction/procedural deal records. These do not become case records merely
# because Lonmin/Marikana appears in the title or background text.
EXCLUDE_ROUTINE_IDS = {
    "DISC-MEDIA-0382", "DISC-MEDIA-0390", "DISC-MEDIA-0402",
    "DISC-MEDIA-0421", "DISC-MEDIA-0422", "DISC-MEDIA-0442", "DISC-MEDIA-0443",
    "DISC-MEDIA-0451", "DISC-MEDIA-0462", "DISC-MEDIA-0467", "DISC-MEDIA-0468",
    "DISC-MEDIA-0474", "DISC-MEDIA-0475", "DISC-MEDIA-0478", "DISC-MEDIA-0487",
    "DISC-MEDIA-0490", "DISC-MEDIA-0496", "DISC-MEDIA-0505", "DISC-MEDIA-0506",
    "DISC-MEDIA-0507", "DISC-MEDIA-0508", "DISC-MEDIA-0509", "DISC-MEDIA-0513",
    "DISC-MEDIA-0521", "DISC-MEDIA-0522", "DISC-MEDIA-0536", "DISC-MEDIA-0542",
    "DISC-MEDIA-0543", "DISC-MEDIA-0560", "DISC-MEDIA-0561", "DISC-MEDIA-0562",
    "DISC-MEDIA-0605", "DISC-MEDIA-0623", "DISC-MEDIA-0645", "DISC-MEDIA-0653",
    "DISC-MEDIA-0670", "DISC-MEDIA-0676",
}


def read_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


rows = read_rows(LEDGER)
by_id = {r["candidate_id"]: r for r in rows}
sets = [
    INCLUDE_CASE_IDS, INCLUDE_LABOUR_IDS, INCLUDE_COMMUNITY_IDS, INCLUDE_TRANSITION_IDS,
    EXCLUDE_OTHER_PLACE_IDS, EXCLUDE_ANALOGICAL_IDS, EXCLUDE_OTHER_EVENT_IDS, EXCLUDE_ROUTINE_IDS,
]
requested = set().union(*sets)
missing = sorted(requested - set(by_id))
if missing:
    raise RuntimeError(f"Batch 05 candidate IDs missing from ledger: {missing}")
conflicts = sorted(cid for cid in requested if by_id[cid].get("decision_status", "").startswith("final_"))
if conflicts:
    raise RuntimeError(f"Batch 05 expected pending rows but found prior final decisions: {conflicts}")


def apply(ids, decision, reason, note):
    for cid in sorted(ids):
        r = by_id[cid]
        r.update({
            "decision_status": "final_batch_05",
            "final_decision": decision,
            "reason_code": reason,
            "decision_note": note,
            "decision_provenance": "review_batch_05_explicit_residual_2026-08-23",
        })

apply(INCLUDE_CASE_IDS, "include", "include_case_central",
      "Included after explicit Batch-05 review: the substantive subject is the Marikana event, its aftermath, accountability, interpretation or institutional/political effect.")
apply(INCLUDE_LABOUR_IDS, "include", "include_lonmin_marikana_labour_governance",
      "Included under the prospectively declared longitudinal labour-relations scope: Lonmin worker/union representation, job-loss contestation or labour-court governance is substantive.")
apply(INCLUDE_COMMUNITY_IDS, "include", "include_lonmin_community_housing_response",
      "Included under the prospectively declared housing/community-response scope: Lonmin accommodation or community grievance governance is the substantive focus.")
apply(INCLUDE_TRANSITION_IDS, "include", "include_lonmin_ownership_transition_labour_governance",
      "Included under the prospectively declared ownership-transition scope because the Sibanye-Lonmin transition is substantively tied to jobs, retrenchment, union contestation, community conditions or competition governance.")
apply(EXCLUDE_OTHER_PLACE_IDS, "exclude", "exclude_other_place_named_marikana",
      "Excluded after source-specific review: this concerns a different place named Marikana (notably the Philippi East/Cape Town informal settlement), not the North West Lonmin/Marikana case.")
apply(EXCLUDE_ANALOGICAL_IDS, "exclude", "exclude_analogical_marikana_reference",
      "Excluded after source-specific review: Marikana is used mainly as an analogy or warning for a different event rather than treated as the substantive case.")
apply(EXCLUDE_OTHER_EVENT_IDS, "exclude", "exclude_other_mine_or_event",
      "Excluded after source-specific review: this is a later independent accident, shooting or labour event outside the declared Marikana/Lonmin case themes.")
apply(EXCLUDE_ROUTINE_IDS, "exclude", "exclude_general_corporate_financial",
      "Excluded after explicit Batch-05 review: substantive focus is routine production, plant/project activity, management, finance, market performance, or pure transaction/procedural deal mechanics rather than the Marikana/Lonmin policy case.")

with LEDGER.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)

status_counts = Counter(r["decision_status"] for r in rows)
reason_counts = Counter(r["reason_code"] for r in rows)
final_rows = [r for r in rows if r["decision_status"].startswith("final_")]
batch_rows = [r for r in rows if r["decision_status"] == "final_batch_05"]
summary = {
    "ledger_scope": "all_690_archive_title_trigger_media_candidates",
    "records_in_ledger": len(rows),
    "final_decisions_made": len(final_rows),
    "final_inclusions": sum(r["final_decision"] == "include" for r in final_rows),
    "final_exclusions": sum(r["final_decision"] == "exclude" for r in final_rows),
    "pending_substantive_review": sum(r["decision_status"] == "pending_substantive_review" for r in rows),
    "decision_status_counts": dict(status_counts),
    "reason_code_counts": dict(reason_counts),
    "batch_05_applied_counts": dict(Counter(r["reason_code"] for r in batch_rows)),
    "important_note": (
        "Batch 05 is explicit-ID based and applies the locked scope consistently to residual labour/community/ownership-transition records, "
        "geographic homonyms, analogical references, unrelated later events and routine corporate/procedural material. Remaining records "
        "stay pending. No stance labels, class targets or model outputs were used."
    ),
}
SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
