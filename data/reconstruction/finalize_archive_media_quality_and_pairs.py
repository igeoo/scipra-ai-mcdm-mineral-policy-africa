"""Finalize archive-media text-quality and same-title republication review.

This step does not change substantive eligibility. It converts the targeted
quality/similarity evidence into explicit pre-freeze data-quality decisions:

* repeated fresh hashes across unrelated titles remain extraction collisions;
* the 17 same-normalised-title/year Engineering News pairs are treated as
  republications, retaining the earliest publication as canonical; and
* quality exceptions remain in the eligibility/provenance manifest but are not
  analysis-ready until usable article text is recovered.

No stance labels, historical class targets or model outputs are used.
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "data" / "reconstruction"
INCLUDED = RECON / "archive_media_included_pre_dedup_manifest.csv"
PAIR_EVIDENCE = RECON / "archive_media_same_title_year_similarity_audit.csv"
PAIR_SOURCE = RECON / "archive_media_same_title_year_review.csv"
QUALITY_EVIDENCE = RECON / "archive_media_quality_recovery_audit.csv"
MISSING = RECON / "archive_media_text_hash_exceptions.csv"
COLLISIONS = RECON / "archive_media_extraction_hash_collisions.csv"
QUALITY_DECISIONS = RECON / "archive_media_quality_review_decisions.csv"
PAIR_DECISIONS = RECON / "archive_media_same_title_year_decisions.csv"
MANIFEST = RECON / "archive_media_post_titlepair_manifest.csv"
SUMMARY = RECON / "archive_media_post_titlepair_summary.json"

SPECIAL_EXTERNAL_CHECK = {
    "MEDIA-TITLEYEAR-0006": (
        "Later Engineering News extraction is a known boilerplate collision. Exact title/publisher/date-pattern review plus the "
        "independently recoverable 21 May 2019 Bloomberg version supports treating the 31 May page as a republication. "
        "External corroboration: https://www.miningweekly.com/article/lonmin-plans-to-cut-4-100-workers-as-it-closes-platinum-mines-2019-05-21"
    )
}


def read_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


included = read_rows(INCLUDED)
pair_evidence = read_rows(PAIR_EVIDENCE)
pair_source = read_rows(PAIR_SOURCE)
quality_evidence = read_rows(QUALITY_EVIDENCE)
missing_rows = read_rows(MISSING)
collision_rows = read_rows(COLLISIONS)

if len(included) != 678:
    raise RuntimeError(f"Expected 678 eligible archive-media rows, found {len(included)}")
if len(pair_evidence) != 17 or len(pair_source) != 34:
    raise RuntimeError(f"Expected 17 pair evidence rows / 34 source rows, found {len(pair_evidence)} / {len(pair_source)}")

# --- Correct/finalize quality evidence ---
fresh_hash_groups = defaultdict(list)
for r in quality_evidence:
    h = (r.get("fresh_text_sha256") or "").strip()
    if h:
        fresh_hash_groups[h].append(r)

quality_decisions = []
quality_status_by_id = {}
for r in quality_evidence:
    rid = r["record_id"]
    fresh_hash = (r.get("fresh_text_sha256") or "").strip()
    group = fresh_hash_groups.get(fresh_hash, []) if fresh_hash else []
    distinct_titles = {x.get("title", "") for x in group}
    if not fresh_hash:
        status = "unresolved_missing_text"
        note = "Targeted refetch still produced no usable article body."
    elif len(group) > 1 and len(distinct_titles) > 1:
        status = "persistent_extraction_hash_collision"
        note = (
            f"Fresh refetch still produced the identical payload/hash for {len(group)} unrelated titles; "
            "this is extractor boilerplate/collision, not recovered article text."
        )
    elif int(r.get("fresh_text_words") or 0) < 150:
        status = "recovered_text_too_short_requires_review"
        note = "Fresh extraction is too short for confident NLP use without source-level validation."
    else:
        status = "fresh_text_recovered_candidate"
        note = "Fresh extraction is distinct and long enough to be a recovery candidate, subject to source-level content validation."
    quality_status_by_id[rid] = status
    quality_decisions.append({
        "record_id": rid,
        "title": r.get("title", ""),
        "publisher": r.get("publisher", ""),
        "url": r.get("url", ""),
        "old_text_words": r.get("old_text_words", ""),
        "old_text_sha256": r.get("old_text_sha256", ""),
        "fresh_text_words": r.get("fresh_text_words", ""),
        "fresh_text_sha256": fresh_hash,
        "final_quality_status": status,
        "quality_review_note": note,
        "analysis_ready_from_quality_review": str(status == "fresh_text_recovered_candidate").lower(),
        "decision_provenance": "targeted_quality_review_2026-08-24",
    })

with QUALITY_DECISIONS.open("w", encoding="utf-8", newline="") as f:
    fields = list(quality_decisions[0].keys())
    w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(quality_decisions)

# All current exception rows should remain non-analysis-ready after corrected review.
if any(r["analysis_ready_from_quality_review"] == "true" for r in quality_decisions):
    raise RuntimeError("Unexpected quality recovery was promoted automatically; explicit content validation is required")

# --- Finalize same-title/year republication decisions ---
pair_source_by_cluster = defaultdict(list)
for r in pair_source:
    pair_source_by_cluster[r["cluster_id"]].append(r)

pair_decisions = []
duplicate_ids = set()
representative_by_duplicate = {}
for e in sorted(pair_evidence, key=lambda r: r["cluster_id"]):
    cid = e["cluster_id"]
    source_members = pair_source_by_cluster.get(cid, [])
    if len(source_members) != 2:
        raise RuntimeError(f"Expected two source members for {cid}, found {len(source_members)}")
    source_members = sorted(source_members, key=lambda r: (r.get("publication_date_from_url", ""), r["record_id"]))
    keep, drop = source_members
    similarity = float(e.get("sequence_similarity") or 0)
    if cid != "MEDIA-TITLEYEAR-0006" and similarity < 0.90:
        raise RuntimeError(f"Refusing republication decision for {cid}: sequence similarity {similarity:.6f} < 0.90")
    duplicate_ids.add(drop["record_id"])
    representative_by_duplicate[drop["record_id"]] = keep["record_id"]
    if cid in SPECIAL_EXTERNAL_CHECK:
        reason = "republication_same_title_publisher_close_date_external_original_corroborated"
        note = SPECIAL_EXTERNAL_CHECK[cid]
    else:
        reason = "republication_same_title_publisher_close_date_high_text_similarity"
        note = (
            f"Same normalized title and publisher; sequence similarity={e.get('sequence_similarity')}, "
            f"token Jaccard={e.get('token_set_jaccard')}, five-word shingle Jaccard={e.get('five_word_shingle_jaccard')}. "
            "Earliest publication retained to avoid overweighting republication in NLP analysis."
        )
    pair_decisions.append({
        "cluster_id": cid,
        "normalised_title_year": e.get("normalised_title_year", ""),
        "representative_record_id": keep["record_id"],
        "representative_date": keep.get("publication_date_from_url", ""),
        "redundant_republication_record_id": drop["record_id"],
        "redundant_date": drop.get("publication_date_from_url", ""),
        "sequence_similarity": e.get("sequence_similarity", ""),
        "token_set_jaccard": e.get("token_set_jaccard", ""),
        "five_word_shingle_jaccard": e.get("five_word_shingle_jaccard", ""),
        "final_duplicate_decision": "collapse_republication_keep_earliest",
        "final_duplicate_reason": reason,
        "review_note": note,
        "decision_provenance": "same_title_year_republication_review_2026-08-24",
    })

if len(pair_decisions) != 17 or len(duplicate_ids) != 17:
    raise RuntimeError(f"Expected 17 resolved republication pairs, got {len(pair_decisions)} / {len(duplicate_ids)} redundant IDs")

with PAIR_DECISIONS.open("w", encoding="utf-8", newline="") as f:
    fields = list(pair_decisions[0].keys())
    w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(pair_decisions)

# --- Build post-pair-review manifest ---
missing_ids = {r["record_id"] for r in missing_rows}
collision_ids = {r["record_id"] for r in collision_rows}
quality_exception_ids = missing_ids | collision_ids
out = []
for r in included:
    rid = r["record_id"]
    x = dict(r)
    if rid in duplicate_ids:
        pair_status = "redundant_republication"
        rep = representative_by_duplicate[rid]
    else:
        pair_status = "retained_after_titlepair_review"
        rep = rid

    if rid in missing_ids:
        quality_status = "unresolved_missing_text"
    elif rid in collision_ids:
        quality_status = "persistent_extraction_hash_collision"
    else:
        quality_status = "no_known_text_quality_exception"

    analysis_ready = pair_status == "retained_after_titlepair_review" and quality_status == "no_known_text_quality_exception"
    x.update({
        "titlepair_review_status": pair_status,
        "titlepair_representative_record_id": rep,
        "final_text_quality_status": quality_status,
        "analysis_ready_pre_cross_phase": str(analysis_ready).lower(),
    })
    out.append(x)

with MANIFEST.open("w", encoding="utf-8", newline="") as f:
    fields = list(out[0].keys())
    w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(out)

retained = [r for r in out if r["titlepair_review_status"] == "retained_after_titlepair_review"]
analysis_ready = [r for r in retained if r["analysis_ready_pre_cross_phase"] == "true"]
retained_quality_exceptions = [r for r in retained if r["final_text_quality_status"] != "no_known_text_quality_exception"]

summary = {
    "scope": "eligible_archive_media_after_same_title_republication_and_quality_review",
    "eligible_records_before_pair_review": len(out),
    "same_title_year_pairs_resolved": len(pair_decisions),
    "redundant_republication_records": len(duplicate_ids),
    "records_retained_after_republication_collapse": len(retained),
    "raw_quality_exception_records_before_pair_collapse": len(quality_exception_ids),
    "quality_exception_records_retained_after_pair_collapse": len(retained_quality_exceptions),
    "retained_missing_text_exceptions": sum(r["final_text_quality_status"] == "unresolved_missing_text" for r in retained),
    "retained_extraction_collision_exceptions": sum(r["final_text_quality_status"] == "persistent_extraction_hash_collision" for r in retained),
    "analysis_ready_archive_media_pre_cross_phase": len(analysis_ready),
    "same_title_year_review_complete": True,
    "corpus_frozen": False,
    "important_note": (
        "Substantive eligibility remains 678 pre-dedup records, but 17 later republications are collapsed for corpus analysis. "
        "Ten retained rows remain non-analysis-ready because article text is missing or extraction collisions persist. "
        "Cross-phase duplicate review against the prior screened reconstruction corpus and additional near-duplicate checks remain before freeze."
    ),
}
SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
