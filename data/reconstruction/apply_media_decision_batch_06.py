"""Resolve the final 44 title-trigger archive-media records (Batch 06).

Every decision is an explicit candidate-ID decision following review of the
locked scope, targeted extracted-text evidence, and source-specific checks for
ambiguous cases. No stance labels, target class balance, or model outputs are
used. This closes substantive eligibility review for the 690 title-trigger
media queue; duplicate resolution remains a later step.
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

# Direct Marikana aftermath, accountability, reparation or political-effect
# records. These are about the case itself rather than merely a place name.
INCLUDE_CASE_IDS = {
    "DISC-MEDIA-0151",  # 2014 elections in the Marikana mining belt / political aftermath
    "DISC-MEDIA-0198",  # Marikana: The Fallout
    "DISC-MEDIA-0233",  # rejection of Ramaphosa's Marikana apology
    "DISC-MEDIA-0253",  # call for reparation over Marikana
    "DISC-MEDIA-0447",  # Lonmin tax-evasion allegations linked to wages/social obligations and commission context
}

# Longitudinal Lonmin labour/employment governance. Inclusion here requires
# substantive consultations, retrenchments/job security, union representation,
# or the social consequences of restructuring rather than incidental worker
# mentions in a production/earnings story.
INCLUDE_LABOUR_IDS = {
    "DISC-MEDIA-0449",  # union/employee consultations over labour-cost reduction and retrenchment
    "DISC-MEDIA-0476",  # 4,100 workers / shaft closures
    "DISC-MEDIA-0477",  # republication/edition of same 4,100-worker restructuring story
    "DISC-MEDIA-0531",  # Solidarity contesting planned dismissal of 1,139 workers
    "DISC-MEDIA-0466",  # job-cut revision immediately ahead of Sibanye takeover
}

# Community/social-development response around the Lonmin/Marikana operations.
INCLUDE_COMMUNITY_IDS = {
    "DISC-MEDIA-0502",  # local enterprise development and job creation in Lonmin host community
    "DISC-MEDIA-0574",  # Marikana education/technical-skills community development
}

# Ownership transition / public-interest governance. These records are retained
# because the declared scope includes the Lonmin-to-Sibanye transition and the
# selected reports materially address jobs, competition/public-interest review,
# community/SLP obligations, BEE ownership, or stakeholder governance. Pure
# offer-price/share-price/procedural records were excluded in earlier batches.
INCLUDE_TRANSITION_IDS = {
    "DISC-MEDIA-0649",  # post-acquisition restructuring of historical Lonmin/Marikana B-BBEE ownership
    "DISC-MEDIA-0383",  # UK competition review; job losses and SA competition/public-interest issues substantive
    "DISC-MEDIA-0634",  # takeover viability plus merger-related job cuts/Competition Commission scrutiny
    "DISC-MEDIA-0392",  # consolidation explicitly framed around saving ~20,000 Lonmin jobs
    "DISC-MEDIA-0650",  # core all-share acquisition/ownership-transition announcement
    "DISC-MEDIA-0651",  # substantive 'Lonmin rescue' transition analysis
    "DISC-MEDIA-0523",  # SA competition filing with worker/union/community dimensions
    "DISC-MEDIA-0601",  # PIC stakeholder-governance decision on the Lonmin transaction
    "DISC-MEDIA-0628",  # post-acquisition Marikana job cuts, SLPs and community-development commitments
    "DISC-MEDIA-0654",  # Marikana restructuring after acquisition, unions/jobs/community implications
}

# Corporate management/operations stories that contain Marikana labour history
# as background but whose substantive subject is management, plant operation,
# production, capex, earnings, commodity price or financing.
EXCLUDE_ROUTINE_IDS = {
    "DISC-MEDIA-0549",  # CEO appointment + furnace restart; 2012/union context is background
    "DISC-MEDIA-0550",  # republication/edition of the same management/furnace story
    "DISC-MEDIA-0611",  # Ramaphosa board exit following political-role change
    "DISC-MEDIA-0384",  # broad corporate/market 'turbulent period' discussion
    "DISC-MEDIA-0444",  # platinum-price/capex story; Marikana/strike context is background
    "DISC-MEDIA-0445",  # workforce/capex/unit-cost corporate restructuring report
    "DISC-MEDIA-0452",  # parallel workforce/capex/unit-cost report
    "DISC-MEDIA-0517",  # sales guidance/capex with job cuts as corporate-plan component
    "DISC-MEDIA-0545",  # platinum-price/producer economics
    "DISC-MEDIA-0395",  # Q1 production and FY guidance
    "DISC-MEDIA-0469",  # FY guidance and production numbers
    "DISC-MEDIA-0633",  # stock shorting/cash position/market story
    "DISC-MEDIA-0617",  # output/cash/tailings production story
    "DISC-MEDIA-0618",  # republication/edition of same production story
}

# Later independent fatal incidents are not the August 2012 killings or their
# justice/accountability process.
EXCLUDE_OTHER_EVENT_IDS = {
    "DISC-MEDIA-0629",  # 2015 contractor fatality at Marikana mine
    "DISC-MEDIA-0424",  # 2017 turnaround/production story with later fatalities
    "DISC-MEDIA-0425",  # parallel edition of 2017 turnaround/fatalities story
}

# Marikana is only a comparator for an unrelated road-safety statistic.
EXCLUDE_ANALOGICAL_IDS = {
    "DISC-MEDIA-0621",
}

# These concern the Marikana informal settlement in Philippi East, Cape Town,
# named after the North West events but geographically/substantively distinct.
EXCLUDE_OTHER_PLACE_IDS = {
    "DISC-MEDIA-0219",  # Noma documentary: Cape Town land occupation beside Philippi East Marikana settlement
    "DISC-MEDIA-0228",  # 60,000-person Philippi East land/housing court case
    "DISC-MEDIA-0229",  # same Philippi East land/housing litigation
}

# Local place-name use without substantive connection to the massacre/Lonmin
# policy case: a 2023 road-safety campaign by a transport SME based in Marikana.
EXCLUDE_PERIPHERAL_PLACE_IDS = {
    "DISC-MEDIA-0672",
}


def read_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


rows = read_rows(LEDGER)
by_id = {r["candidate_id"]: r for r in rows}
sets = [
    INCLUDE_CASE_IDS, INCLUDE_LABOUR_IDS, INCLUDE_COMMUNITY_IDS, INCLUDE_TRANSITION_IDS,
    EXCLUDE_ROUTINE_IDS, EXCLUDE_OTHER_EVENT_IDS, EXCLUDE_ANALOGICAL_IDS,
    EXCLUDE_OTHER_PLACE_IDS, EXCLUDE_PERIPHERAL_PLACE_IDS,
]
requested = set().union(*sets)
if len(requested) != 44:
    raise RuntimeError(f"Batch 06 must contain exactly 44 unique IDs; found {len(requested)}")
missing = sorted(requested - set(by_id))
if missing:
    raise RuntimeError(f"Batch 06 candidate IDs missing from ledger: {missing}")
conflicts = sorted(cid for cid in requested if by_id[cid].get("decision_status", "").startswith("final_"))
if conflicts:
    raise RuntimeError(f"Batch 06 expected the final 44 pending rows but found prior finals: {conflicts}")
pending_ids = {r["candidate_id"] for r in rows if r.get("decision_status") == "pending_substantive_review"}
if requested != pending_ids:
    raise RuntimeError(
        "Batch 06 explicit IDs do not exactly equal the current pending set. "
        f"missing_from_batch={sorted(pending_ids-requested)} extra={sorted(requested-pending_ids)}"
    )


def apply(ids, decision, reason, note):
    for cid in sorted(ids):
        by_id[cid].update({
            "decision_status": "final_batch_06",
            "final_decision": decision,
            "reason_code": reason,
            "decision_note": note,
            "decision_provenance": "review_batch_06_explicit_source_checked_2026-08-23",
        })

apply(INCLUDE_CASE_IDS, "include", "include_case_central",
      "Included after explicit source-specific Batch-06 review: substantive focus is Marikana aftermath, accountability, reparation, governance or political effect rather than incidental place-name use.")
apply(INCLUDE_LABOUR_IDS, "include", "include_lonmin_marikana_labour_governance",
      "Included under the locked longitudinal labour-governance scope: consultations, retrenchment/job security, union representation or employment consequences are substantive rather than incidental background.")
apply(INCLUDE_COMMUNITY_IDS, "include", "include_lonmin_community_housing_response",
      "Included under the locked host-community/social-development scope: substantive focus is education, enterprise development or community economic capacity around Lonmin/Marikana.")
apply(INCLUDE_TRANSITION_IDS, "include", "include_lonmin_ownership_transition_labour_governance",
      "Included under the prospectively declared Lonmin-to-Sibanye ownership-transition/public-interest scope: jobs, competition review, SLP/community commitments, BEE ownership or stakeholder governance are substantive.")
apply(EXCLUDE_ROUTINE_IDS, "exclude", "exclude_general_corporate_financial",
      "Excluded after explicit source-specific review: substantive focus is management, plant/production, capex, earnings, commodity prices, financing or market performance; Marikana/labour history is background only.")
apply(EXCLUDE_OTHER_EVENT_IDS, "exclude", "exclude_other_mine_or_event",
      "Excluded after explicit source-specific review: this concerns a later independent mine fatality/incident or production story with later fatalities, not the August 2012 killings or their accountability process.")
apply(EXCLUDE_ANALOGICAL_IDS, "exclude", "exclude_analogical_marikana_reference",
      "Excluded after source-specific review: Marikana is used as a comparator for an unrelated subject rather than being the substantive case.")
apply(EXCLUDE_OTHER_PLACE_IDS, "exclude", "exclude_other_place_named_marikana",
      "Excluded after external/source-specific verification: this concerns the Marikana informal settlement in Philippi East, Cape Town, not the North West Lonmin/Marikana case.")
apply(EXCLUDE_PERIPHERAL_PLACE_IDS, "exclude", "exclude_incidental_marikana_reference",
      "Excluded after source-specific review: Marikana is only the location of a peripheral local road-safety/business story with no substantive case, labour, justice, community-policy or ownership-transition treatment.")

with LEDGER.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)

status_counts = Counter(r["decision_status"] for r in rows)
reason_counts = Counter(r["reason_code"] for r in rows)
final_rows = [r for r in rows if r["decision_status"].startswith("final_")]
batch_rows = [r for r in rows if r["decision_status"] == "final_batch_06"]
pending = [r for r in rows if r["decision_status"] == "pending_substantive_review"]
if pending:
    raise RuntimeError(f"Batch 06 was intended to close the title-trigger queue but {len(pending)} rows remain")
summary = {
    "ledger_scope": "all_690_archive_title_trigger_media_candidates",
    "records_in_ledger": len(rows),
    "final_decisions_made": len(final_rows),
    "final_inclusions": sum(r["final_decision"] == "include" for r in final_rows),
    "final_exclusions": sum(r["final_decision"] == "exclude" for r in final_rows),
    "pending_substantive_review": 0,
    "title_trigger_substantive_screen_complete": True,
    "decision_status_counts": dict(status_counts),
    "reason_code_counts": dict(reason_counts),
    "batch_06_applied_counts": dict(Counter(r["reason_code"] for r in batch_rows)),
    "batch_06_inclusions": sum(r["final_decision"] == "include" for r in batch_rows),
    "batch_06_exclusions": sum(r["final_decision"] == "exclude" for r in batch_rows),
    "important_note": (
        "The 690-record title-trigger media queue now has an explicit substantive eligibility decision for every record. "
        "This does not freeze the corpus: the 1,062 secondary-keyword queue still requires screening, followed by duplicate resolution, "
        "canonical manifest construction and external pre-freeze review. No stance labels, historical class targets or model outputs were used."
    ),
}
SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
