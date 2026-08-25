"""Finalize the reconstructed SCIPRA replication corpus and freeze its membership.

This stage may set corpus_frozen=true only after all substantive screening,
explicit duplicate review, and recovery reconciliation assertions pass.
It does not annotate stance or run any statistical / ML / MCDM model.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "data" / "reconstruction"

PREFREEZE = RECON / "prefreeze_manifest_after_broad_duplicate_review.csv"
TEXTWIDE = RECON / "textwide_near_duplicate_candidates.csv"
RECOVERY = RECON / "textwide_recovery_status.csv"
PRIOR = RECON / "review_handoff" / "screened_qc_preliminary_unique_text_manifest.csv"
TITLE_SUMMARY = RECON / "media_substantive_decision_summary.json"
SECONDARY_SUMMARY = RECON / "secondary_media_substantive_decision_summary.json"

DECISIONS_OUT = RECON / "textwide_near_duplicate_final_decisions.csv"
RECONCILIATION_OUT = RECON / "textwide_recovery_reconciliation.csv"
CANONICAL_OUT = RECON / "canonical_reconstructed_replication_corpus.csv"
ANALYSIS_OUT = RECON / "canonical_analysis_ready_manifest.csv"
HASHES_OUT = RECON / "corpus_freeze_hashes.json"
SUMMARY_OUT = RECON / "corpus_freeze_summary.json"

EITI_CAVEAT = (
    "The reported set of 13 South Africa EITI documents cannot presently be "
    "independently recovered or validated as described in the original corpus documentation."
)

EXPECTED_DUPLICATE_PAIRS = {
    ("MEDIA-043", "DISC-MEDIA-0650"),
    ("WEB-MEDIA-003", "DISC-MEDIA-0578"),
    ("expanded_media_candidates_02__EXP-MEDIA-037", "DISC-MEDIA-0409"),
    ("MEDIA-044", "DISC-MEDIA-0524"),
    ("MEDIA-024", "DISC-MEDIA-0436"),
    ("DISC-MEDIA-0636", "DISC-MEDIA-0648"),
    ("DISC-MEDIA-0431", "DISC-MEDIA-0392"),
}

# Latest stable textwide rerun recovered all four previously blocked gov.za pages.
# Only these four PDF/annual-report records still need provenance reconciliation.
EXPECTED_RECOVERY_GAPS = {
    "CORP-001",
    "CORP-003",
    "expanded_corporate_candidates__EXP-CORP-002",
    "expanded_official_candidates_batch2__EXP-OFFICIAL-012",
}


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def truthy(v):
    return str(v or "").strip().lower() == "true"


def write_csv(path: Path, rows: list[dict], fields: list[str]):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


prefreeze = read_csv(PREFREEZE)
textwide = read_csv(TEXTWIDE)
recovery = read_csv(RECOVERY)
prior = read_csv(PRIOR)
title_summary = read_json(TITLE_SUMMARY)
secondary_summary = read_json(SECONDARY_SUMMARY)

# ---- Stable input invariants -------------------------------------------------
if len(prefreeze) != 893:
    raise RuntimeError(f"Expected 893 pre-freeze retained rows, found {len(prefreeze)}")
if sum(truthy(r.get("analysis_ready")) for r in prefreeze) != 883:
    raise RuntimeError("Expected 883 analysis-ready rows before final textwide decisions")
if len(textwide) != 7:
    raise RuntimeError(f"Expected exactly 7 stable textwide candidate pairs, found {len(textwide)}")

observed_pairs = {(r["record_id_a"], r["record_id_b"]) for r in textwide}
if observed_pairs != EXPECTED_DUPLICATE_PAIRS:
    raise RuntimeError(
        "Textwide candidate set drifted from the explicitly reviewed seven pairs: "
        f"missing={sorted(EXPECTED_DUPLICATE_PAIRS-observed_pairs)} "
        f"extra={sorted(observed_pairs-EXPECTED_DUPLICATE_PAIRS)}"
    )
for r in textwide:
    score = float(r["tfidf_cosine_similarity"])
    if score < 0.95:
        raise RuntimeError(f"Reviewed textwide pair below 0.95 threshold: {r['record_id_a']} / {r['record_id_b']}")

if len(recovery) != 883:
    raise RuntimeError(f"Expected 883 textwide recovery rows, found {len(recovery)}")
unusable = {r["record_id"] for r in recovery if not truthy(r.get("usable_for_textwide_similarity"))}
if unusable != EXPECTED_RECOVERY_GAPS:
    raise RuntimeError(f"Unexpected textwide recovery-gap set: {sorted(unusable)}")
status_counts = Counter(r.get("fetch_status", "") for r in recovery)
if status_counts.get("retrieved_extracted", 0) != 879 or status_counts.get("retrieved_no_text", 0) != 4 or status_counts.get("fetch_failed", 0) != 0:
    raise RuntimeError(f"Expected 879 extracted + 4 no-text + 0 failed; saw {dict(status_counts)}")

if title_summary.get("records_in_ledger") != 690 or title_summary.get("final_decisions_made") != 690:
    raise RuntimeError("Title-trigger media ledger is not complete at 690/690")
if title_summary.get("final_inclusions") != 547 or title_summary.get("final_exclusions") != 143:
    raise RuntimeError("Title-trigger media inclusion/exclusion counts drifted")
if title_summary.get("pending_substantive_review") != 0 or not title_summary.get("title_trigger_substantive_screen_complete"):
    raise RuntimeError("Title-trigger substantive screening still has pending work")

if secondary_summary.get("records_in_ledger") != 1062 or secondary_summary.get("final_decisions_made") != 1062:
    raise RuntimeError("Secondary media ledger is not complete at 1062/1062")
if secondary_summary.get("final_inclusions") != 131 or secondary_summary.get("final_exclusions") != 931:
    raise RuntimeError("Secondary media inclusion/exclusion counts drifted")
if secondary_summary.get("pending_substantive_review") != 0 or not secondary_summary.get("secondary_keyword_substantive_screen_complete"):
    raise RuntimeError("Secondary substantive screening still has pending work")

# Selection must remain pre-stance/pre-model.
forbidden_fragments = ("stance", "svm", "pci", "rpci", "mcdm", "model_prediction", "predicted_class")
for col in prefreeze[0].keys():
    lc = col.lower()
    if any(x in lc for x in forbidden_fragments):
        raise RuntimeError(f"Forbidden post-selection/model field present in pre-freeze manifest: {col}")

for r in prefreeze:
    try:
        y = int(float(r.get("year", "")))
    except Exception as exc:
        raise RuntimeError(f"Unresolved/non-numeric year in retained corpus: {r.get('canonical_record_id')} -> {r.get('year')}") from exc
    if y < 2010 or y > 2023:
        raise RuntimeError(f"Retained record outside 2010-2023: {r.get('canonical_record_id')} ({y})")

# ---- Reconcile the four current live-site extraction gaps --------------------
prior_by_id = {r.get("candidate_id", ""): r for r in prior}
recovery_by_id = {r["record_id"]: r for r in recovery}
reconciliation_rows = []
for rid in sorted(EXPECTED_RECOVERY_GAPS):
    p = prior_by_id.get(rid)
    if not p:
        raise RuntimeError(f"No prior validated extraction found for recovery gap {rid}")
    sha = (p.get("text_sha256") or "").strip()
    try:
        wc = int(float(p.get("text_words") or 0))
    except Exception:
        wc = 0
    if len(sha) != 64 or wc < 80:
        raise RuntimeError(f"Prior extraction for {rid} is not strong enough to reconcile: sha={sha!r}, words={wc}")
    cur = recovery_by_id[rid]
    reconciliation_rows.append({
        "record_id": rid,
        "fresh_fetch_status": cur.get("fetch_status", ""),
        "fresh_fetch_error": cur.get("fetch_error", ""),
        "prior_validated_text_sha256": sha,
        "prior_validated_text_words": wc,
        "reconciliation_decision": "retain_analysis_ready",
        "reconciliation_status": "fresh_recovery_reconciled_prior_validated_text",
        "reconciliation_reason": "Current live retrieval yielded insufficient text, but a prior reviewed extraction with a non-empty SHA-256 and >=80 words is preserved in the reconstruction provenance.",
    })

recon_fields = [
    "record_id", "fresh_fetch_status", "fresh_fetch_error", "prior_validated_text_sha256",
    "prior_validated_text_words", "reconciliation_decision", "reconciliation_status", "reconciliation_reason"
]
write_csv(RECONCILIATION_OUT, reconciliation_rows, recon_fields)

# ---- Apply the seven explicit duplicate/republication decisions --------------
redundant_to_rep = {b: a for a, b in EXPECTED_DUPLICATE_PAIRS}
if len(redundant_to_rep) != 7:
    raise RuntimeError("Expected seven unique redundant records")
if any(rep in redundant_to_rep for rep in redundant_to_rep.values()):
    raise RuntimeError("A textwide duplicate representative is itself marked redundant")

prefreeze_ids = {r["canonical_record_id"] for r in prefreeze}
if not set(redundant_to_rep).issubset(prefreeze_ids) or not set(redundant_to_rep.values()).issubset(prefreeze_ids):
    raise RuntimeError("One or more explicit textwide duplicate records are absent from the pre-freeze manifest")

decision_rows = []
textwide_by_pair = {(r["record_id_a"], r["record_id_b"]): r for r in textwide}
for a, b in sorted(EXPECTED_DUPLICATE_PAIRS):
    ev = textwide_by_pair[(a, b)]
    decision_rows.append({
        "retained_representative_record_id": a,
        "redundant_record_id": b,
        "tfidf_cosine_similarity": ev["tfidf_cosine_similarity"],
        "title_sequence_similarity": ev.get("title_sequence_similarity", ""),
        "same_fresh_text_sha256": ev.get("same_fresh_text_sha256", ""),
        "final_duplicate_decision": "collapse_republication_keep_representative",
        "final_duplicate_reason": "Explicit source/content review confirmed same-article republication, syndication, or updated-edition identity; retain one canonical representative.",
    })

decision_fields = list(decision_rows[0].keys())
write_csv(DECISIONS_OUT, decision_rows, decision_fields)

# ---- Build canonical frozen manifests ----------------------------------------
canonical_rows = []
for row in prefreeze:
    rid = row["canonical_record_id"]
    if rid in redundant_to_rep:
        continue
    out = dict(row)
    if rid in EXPECTED_RECOVERY_GAPS:
        recovery_status = "fresh_recovery_reconciled_prior_validated_text"
    elif truthy(out.get("analysis_ready")):
        rr = recovery_by_id.get(rid)
        recovery_status = "fresh_recovery_verified" if rr and truthy(rr.get("usable_for_textwide_similarity")) else "not_rechecked_after_duplicate_collapse"
    else:
        recovery_status = "retained_non_analysis_ready_quality_exception"
    out["textwide_near_duplicate_review_status"] = "retained_after_textwide_duplicate_review"
    out["fresh_recovery_reconciliation_status"] = recovery_status
    out["corpus_freeze_status"] = "frozen_inclusion"
    canonical_rows.append(out)

if len(canonical_rows) != 886:
    raise RuntimeError(f"Expected 886 final frozen retained rows, found {len(canonical_rows)}")
analysis_rows = [r for r in canonical_rows if truthy(r.get("analysis_ready"))]
if len(analysis_rows) != 876:
    raise RuntimeError(f"Expected 876 analysis-ready rows after final textwide collapse, found {len(analysis_rows)}")
if len(canonical_rows) - len(analysis_rows) != 10:
    raise RuntimeError("Expected exactly 10 retained non-analysis-ready quality exceptions")

base_fields = list(prefreeze[0].keys())
extra_fields = [
    "textwide_near_duplicate_review_status",
    "fresh_recovery_reconciliation_status",
    "corpus_freeze_status",
]
canonical_fields = base_fields + [x for x in extra_fields if x not in base_fields]
write_csv(CANONICAL_OUT, canonical_rows, canonical_fields)
write_csv(ANALYSIS_OUT, analysis_rows, canonical_fields)

# ---- Content-address the frozen membership and audit decisions ---------------
hashes = {
    "algorithm": "sha256",
    "canonical_reconstructed_replication_corpus.csv": file_sha256(CANONICAL_OUT),
    "canonical_analysis_ready_manifest.csv": file_sha256(ANALYSIS_OUT),
    "textwide_near_duplicate_final_decisions.csv": file_sha256(DECISIONS_OUT),
    "textwide_recovery_reconciliation.csv": file_sha256(RECONCILIATION_OUT),
    "prefreeze_manifest_after_broad_duplicate_review.csv": file_sha256(PREFREEZE),
    "textwide_near_duplicate_candidates.csv": file_sha256(TEXTWIDE),
    "textwide_recovery_status.csv": file_sha256(RECOVERY),
}
HASHES_OUT.write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")

summary = {
    "corpus_name": "SCIPRA reconstructed replication corpus",
    "corpus_frozen": True,
    "freeze_scope": "membership_and_pre_model_analysis_ready_subset",
    "reconstructed_corpus_records": 886,
    "analysis_ready_records": 876,
    "retained_non_analysis_ready_quality_exceptions": 10,
    "historical_reported_corpus_size_benchmark_only": 87,
    "historical_size_used_as_target_or_quota": False,
    "period_start": "2010-01-01",
    "period_end": "2023-12-31",
    "title_trigger_media": {
        "records": 690, "included_pre_dedup": 547, "excluded": 143, "pending": 0, "screening_complete": True
    },
    "secondary_keyword_media": {
        "records": 1062, "included_pre_dedup": 131, "excluded": 931, "pending": 0, "screening_complete": True
    },
    "textwide_final_review": {
        "candidate_pairs_ge_0_95": 7,
        "explicit_duplicate_or_republication_collapses": 7,
        "pending_pairs": 0,
        "review_complete": True,
    },
    "fresh_recovery_reconciliation": {
        "current_live_recovery_gaps": 4,
        "reconciled_to_prior_validated_extractions": 4,
        "freshly_recovered_analysis_ready_records": 879,
        "unreconciled": 0,
    },
    "eiti_provenance_caveat": EITI_CAVEAT,
    "stance_annotation_run_before_freeze": False,
    "svm_or_other_classifier_run_before_freeze": False,
    "mcdm_pci_rpci_run_before_freeze": False,
    "important_note": (
        "This freeze fixes corpus membership and identifies the analysis-ready subset before any stance annotation, classifier fitting, MCDM, PCI, or RPCI calculation. "
        "The historical N=87 is retained only as a reported benchmark and was not used as a target, quota, or stopping rule."
    ),
}
SUMMARY_OUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2))
