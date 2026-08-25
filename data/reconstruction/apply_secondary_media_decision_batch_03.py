"""Apply explicit source-specific Secondary Media Batch 03.

This final batch resolves the 69 records left after conservative acquired-text
screening. Decisions are explicit-ID based. They apply the locked reconstruction
scope without reference to stance labels, historical class proportions or model
outputs.

Inclusion is restricted to records where Lonmin/Marikana is substantively part
of labour/governance, 2014 platinum-strike negotiations, or the Sibanye-Lonmin
ownership-transition labour context. Historical Marikana references, unrelated
Sibanye/other-mine events, and routine corporate/financial stories are excluded.
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
SUMMARY = RECON / "secondary_media_substantive_decision_summary.json"


def ids(*suffixes: str) -> set[str]:
    return {f"SEC-MEDIA-{s}" for s in suffixes}


DECISION_GROUPS = {
    "include_2014_platinum_strike_lonmin": ids("0147", "0292", "0520"),
    "include_lonmin_marikana_labour_governance": ids("0230", "0239", "0196"),
    "include_lonmin_ownership_transition_labour_governance": ids(
        "0197", "0212", "0577", "0213", "0478", "0865"
    ),
    "exclude_incidental_marikana_reference": ids(
        "0002", "0006", "0408", "0043", "0045", "0046", "0048", "0050",
        "0054", "0057", "0070", "0076", "0096", "0113", "0114"
    ),
    "exclude_general_corporate_financial": ids(
        "0712", "0061", "0266", "0846", "0980", "0981", "0616", "0842",
        "0999", "0505", "0760", "0880", "0873"
    ),
    "exclude_other_mine_or_event": ids(
        "0805", "0806", "0038", "0912", "0428", "0633", "0448", "0769",
        "0935", "0954", "0249", "0039", "0231", "0232", "0442", "0443",
        "0459", "0460", "0047", "0143", "0174", "0208", "0225", "1015",
        "1032", "1040", "1058", "0451", "0112"
    ),
}

INCLUDE_REASONS = {
    "include_2014_platinum_strike_lonmin",
    "include_lonmin_marikana_labour_governance",
    "include_lonmin_ownership_transition_labour_governance",
}

NOTES = {
    "include_2014_platinum_strike_lonmin": (
        "Included after explicit Batch-03 review: the generic-title article is part of the 2014 platinum-strike/AMCU negotiation sequence and acquired text confirms Lonmin is a substantive participant, fitting the predeclared longitudinal labour scope."
    ),
    "include_lonmin_marikana_labour_governance": (
        "Included after explicit Batch-03 review: Lonmin is substantively tied to wages, labour relations, union conflict/violence or related governance rather than appearing only as historical background."
    ),
    "include_lonmin_ownership_transition_labour_governance": (
        "Included after explicit Batch-03 review: the article substantively concerns platinum labour/governance or PGM restructuring in the Sibanye-Lonmin transition context, which is prospectively within scope."
    ),
    "exclude_incidental_marikana_reference": (
        "Excluded after explicit Batch-03 review: Marikana appears as historical/background context in an AMCU, sector, political or labour story whose substantive subject is not the Marikana/Lonmin case."
    ),
    "exclude_general_corporate_financial": (
        "Excluded after explicit Batch-03 review: the substantive subject is earnings, dividends, expansion, financing, management or another routine corporate matter; Marikana/Lonmin references are operational or background only."
    ),
    "exclude_other_mine_or_event": (
        "Excluded after explicit Batch-03 review: the substantive subject is another mine, gold strike, Covid/safety event, unrelated transaction, or adjacent sector issue; Marikana/Lonmin is not case-central."
    ),
}


def read_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


evidence_rows = read_rows(EVIDENCE)
evidence = {r["candidate_id"]: r for r in evidence_rows}
rows = read_rows(LEDGER)
if len(rows) != 1062 or len(evidence_rows) != 1062:
    raise RuntimeError("Secondary evidence/ledger row count mismatch")

pending_before = {r["candidate_id"] for r in rows if r.get("decision_status") == "pending_substantive_review"}
assigned = set().union(*DECISION_GROUPS.values())
if len(assigned) != sum(len(v) for v in DECISION_GROUPS.values()):
    raise RuntimeError("Batch-03 decision groups contain duplicate candidate IDs")
if pending_before != assigned:
    missing = sorted(pending_before - assigned)
    extra = sorted(assigned - pending_before)
    raise RuntimeError(f"Batch-03 must exactly cover current pending set; missing={missing}, extra={extra}")
if len(pending_before) != 69:
    raise RuntimeError(f"Expected 69 pending secondary records before Batch 03, found {len(pending_before)}")

reason_by_id = {}
for reason, members in DECISION_GROUPS.items():
    for cid in members:
        reason_by_id[cid] = reason

applied = Counter()
for row in rows:
    cid = row["candidate_id"]
    if cid not in reason_by_id:
        continue
    if row.get("decision_status") != "pending_substantive_review":
        raise RuntimeError(f"Refusing to overwrite existing final decision for {cid}")
    reason = reason_by_id[cid]
    decision = "include" if reason in INCLUDE_REASONS else "exclude"
    row.update({
        "decision_status": "final_secondary_batch_03",
        "final_decision": decision,
        "reason_code": reason,
        "decision_note": NOTES[reason],
        "decision_provenance": "secondary_batch_03_explicit_source_review_2026-08-24",
    })
    applied[reason] += 1

with LEDGER.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)

final_rows = [r for r in rows if r["decision_status"].startswith("final_")]
pending = [r for r in rows if r["decision_status"] == "pending_substantive_review"]
if pending:
    raise RuntimeError(f"Secondary Batch 03 should close the queue; {len(pending)} records remain")

summary = {
    "ledger_scope": "1062_secondary_keyword_archive_media_candidates",
    "records_in_ledger": len(rows),
    "final_decisions_made": len(final_rows),
    "final_inclusions": sum(r["final_decision"] == "include" for r in final_rows),
    "final_exclusions": sum(r["final_decision"] == "exclude" for r in final_rows),
    "pending_substantive_review": 0,
    "secondary_keyword_substantive_screen_complete": True,
    "decision_status_counts": dict(Counter(r["decision_status"] for r in rows)),
    "reason_code_counts": dict(Counter(r["reason_code"] for r in rows)),
    "batch_03_applied_counts": dict(applied),
    "batch_03_inclusions": sum(v for k, v in applied.items() if k in INCLUDE_REASONS),
    "batch_03_exclusions": sum(v for k, v in applied.items() if k not in INCLUDE_REASONS),
    "important_note": (
        "All 1,062 secondary-keyword archive media candidates now have explicit substantive eligibility decisions. "
        "This completes media substantive screening but does not freeze the corpus: exact/near-duplicate resolution, "
        "canonical manifest construction and external pre-freeze review remain required. No stance labels, historical "
        "class targets or model outputs were used."
    ),
}
SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
