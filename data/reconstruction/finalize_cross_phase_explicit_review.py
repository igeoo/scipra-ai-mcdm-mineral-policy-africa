"""Finalize explicit duplicate decisions before broad near-duplicate review.

Inputs:
- cross_phase_preliminary_combined_manifest.csv (953 rows after 8 safe cross-phase collapses)
- prior screened QC evidence and the explicit cross-phase review files

This script applies only source-specific duplicate decisions already reviewed:
1. four residual cross-phase republication/syndication cases; and
2. seven unresolved duplicate rows already flagged by the prior 300-record QC.

It does not freeze the corpus and does not use stance/model outputs.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "data" / "reconstruction"
IN_MANIFEST = RECON / "cross_phase_preliminary_combined_manifest.csv"
DECISIONS = RECON / "cross_phase_explicit_review_decisions.csv"
OUT_MANIFEST = RECON / "cross_phase_post_explicit_manifest.csv"
SUMMARY = RECON / "cross_phase_post_explicit_summary.json"


def read_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


rows = read_rows(IN_MANIFEST)
if len(rows) != 953:
    raise RuntimeError(f"Expected 953 rows after safe cross-phase pass, found {len(rows)}")
by_id = {r["canonical_record_id"]: r for r in rows}
if len(by_id) != len(rows):
    raise RuntimeError("Duplicate canonical_record_id values in cross-phase input manifest")

# Explicit decisions. Representatives are chosen from the already-screened prior
# corpus where possible. The MEDIA-051 chain is resolved transitively so both
# EXP-MEDIA-060 and DISC-MEDIA-0646 point directly to MEDIA-051.
decisions = [
    # Residual cross-phase cases.
    {
        "redundant_record_id": "DISC-MEDIA-0646",
        "representative_record_id": "MEDIA-051",
        "decision_family": "cross_phase_republication",
        "reason": "Same Sibanye Marikana retrenchment story; 4 Oct 2019 item republishes/updates the 25 Sep 2019 Creamer Media report. Representative follows transitive prior-QC collapse MEDIA-051 <- EXP-MEDIA-060.",
        "evidence": "same_title_same_publisher_close_date_plus_external_creamer_media_verification",
    },
    {
        "redundant_record_id": "SEC-MEDIA-0190",
        "representative_record_id": "expanded_media_candidates__EXP-MEDIA-006",
        "decision_family": "cross_site_syndication",
        "reason": "Same-date Creamer Media article on Engineering News/Mining Weekly with identical acquired-text SHA and matching article slug; headline wording differs only by Lonmin qualifier.",
        "evidence": "same_date_matching_slug_identical_sha_sibling_creamer_media_sites",
    },
    {
        "redundant_record_id": "SEC-MEDIA-0253",
        "representative_record_id": "expanded_media_candidates_batch1__EXP-MEDIA-032",
        "decision_family": "cross_site_syndication",
        "reason": "Same-date Creamer Media article on Engineering News/Mining Weekly with identical acquired-text SHA and identical URL slug despite alternate metadata title.",
        "evidence": "same_date_identical_slug_identical_sha_sibling_creamer_media_sites",
    },
    {
        "redundant_record_id": "SEC-MEDIA-0779",
        "representative_record_id": "SAT-MEDIA-014",
        "decision_family": "cross_site_syndication",
        "reason": "Same-date Engineering News/Mining Weekly Creamer Media item with same normalized title, matching slug and identical acquired-text SHA.",
        "evidence": "same_date_same_title_matching_slug_identical_sha_sibling_creamer_media_sites",
    },

    # Prior 300-record unresolved duplicate review.
    {
        "redundant_record_id": "EXP-MEDIA-063",
        "representative_record_id": "MEDIA-054",
        "decision_family": "prior_qc_cross_site_republication",
        "reason": "Same-day Mining Weekly/Engineering News Creamer Media article; prior QC text similarity 0.999097.",
        "evidence": "prior_qc_similarity_0.999097_same_title_date_creamer_media",
    },
    {
        "redundant_record_id": "WEB-MEDIA-005",
        "representative_record_id": "SAT5-MEDIA-003",
        "decision_family": "prior_qc_cross_site_republication",
        "reason": "Same-day Engineering News/Mining Weekly Creamer Media article on Marikana housing accountability; prior QC similarity 0.998947.",
        "evidence": "prior_qc_similarity_0.998947_same_case_article_date_creamer_media",
    },
    {
        "redundant_record_id": "SAT6-MEDIA-001",
        "representative_record_id": "MEDIA-008",
        "decision_family": "prior_qc_cross_site_republication",
        "reason": "Same-day Mining Weekly/Engineering News Creamer Media article; prior QC similarity 0.998915.",
        "evidence": "prior_qc_similarity_0.998915_same_title_date_creamer_media",
    },
    {
        "redundant_record_id": "EXP-MEDIA-060",
        "representative_record_id": "MEDIA-051",
        "decision_family": "prior_qc_cross_site_republication",
        "reason": "Same-day Mining Weekly/Engineering News Creamer Media article; prior QC similarity 0.998719.",
        "evidence": "prior_qc_similarity_0.998719_same_title_date_creamer_media",
    },
    {
        "redundant_record_id": "SAT5-MEDIA-002",
        "representative_record_id": "MEDIA-014",
        "decision_family": "prior_qc_cross_site_republication",
        "reason": "Same-day Mining Weekly/Engineering News Creamer Media article; prior QC similarity 0.998651.",
        "evidence": "prior_qc_similarity_0.998651_same_title_date_creamer_media",
    },
    {
        "redundant_record_id": "EXP-MEDIA-061",
        "representative_record_id": "MEDIA-053",
        "decision_family": "prior_qc_cross_site_republication",
        "reason": "Same-day Mining Weekly/Engineering News Creamer Media article; prior QC similarity 0.997893.",
        "evidence": "prior_qc_similarity_0.997893_same_title_date_creamer_media",
    },
    {
        "redundant_record_id": "SAT5-MEDIA-001",
        "representative_record_id": "MEDIA-040",
        "decision_family": "prior_qc_cross_site_republication",
        "reason": "Same 25 June 2015 Farlam/Lonmin housing article on sibling Engineering News and Mining Weekly Creamer Media sites; externally verified same author/date/body subject.",
        "evidence": "same_title_date_creamer_media_cross_site_external_verification",
    },
]

redundant_ids = {d["redundant_record_id"] for d in decisions}
if len(redundant_ids) != 11:
    raise RuntimeError(f"Expected 11 unique explicit redundant IDs, found {len(redundant_ids)}")

for d in decisions:
    rid = d["redundant_record_id"]
    rep = d["representative_record_id"]
    if rid not in by_id:
        raise RuntimeError(f"Redundant record missing from input manifest: {rid}")
    if rep not in by_id:
        raise RuntimeError(f"Representative record missing from input manifest: {rep}")
    if rid == rep:
        raise RuntimeError(f"Self duplicate decision: {rid}")

# Representatives must themselves survive this explicit pass.
if redundant_ids & {d["representative_record_id"] for d in decisions}:
    # Only allow if transitive mapping was intentionally flattened. Current list
    # is expected to contain no redundant representative after flattening.
    overlap = sorted(redundant_ids & {d["representative_record_id"] for d in decisions})
    raise RuntimeError(f"Representative also marked redundant; flatten mapping first: {overlap}")

out = []
for r in rows:
    rid = r["canonical_record_id"]
    if rid in redundant_ids:
        continue
    x = dict(r)
    x["explicit_duplicate_review_status"] = "retained_after_explicit_duplicate_review"
    out.append(x)

if len(out) != 942:
    raise RuntimeError(f"Expected 942 retained rows after 11 explicit collapses, found {len(out)}")
analysis_ready = sum(str(r.get("analysis_ready", "")).lower() == "true" for r in out)
if analysis_ready != 932:
    raise RuntimeError(f"Expected 932 analysis-ready retained rows, found {analysis_ready}")
non_ready = len(out) - analysis_ready
if non_ready != 10:
    raise RuntimeError(f"Expected 10 retained non-analysis-ready quality exceptions, found {non_ready}")

# Write decision ledger.
decision_fields = [
    "redundant_record_id", "representative_record_id", "decision_family", "reason", "evidence"
]
with DECISIONS.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=decision_fields)
    w.writeheader(); w.writerows(decisions)

fields = list(rows[0].keys()) + ["explicit_duplicate_review_status"]
with OUT_MANIFEST.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader(); w.writerows(out)

summary = {
    "scope": "post_safe_cross_phase_plus_explicit_prior_qc_and_cross_phase_duplicate_review",
    "records_before_explicit_review": len(rows),
    "safe_cross_phase_duplicates_already_removed": 8,
    "explicit_duplicate_decisions_applied": len(decisions),
    "explicit_cross_phase_duplicates": 4,
    "explicit_prior_qc_duplicates": 7,
    "records_retained_after_explicit_review": len(out),
    "analysis_ready_records_after_explicit_review": analysis_ready,
    "retained_non_analysis_ready_records": non_ready,
    "near_duplicate_review_complete": False,
    "corpus_frozen": False,
    "important_note": (
        "This stage resolves all previously identified same-title and >=0.95 prior-QC near-duplicate cases plus the four residual cross-phase cases. "
        "A broader metadata/text near-duplicate candidate sweep still remains before canonical corpus freeze."
    ),
}
SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
