"""Conservative cross-phase duplicate audit for the SCIPRA reconstructed corpus.

Compare the earlier 300-record screened manifest with the 661 archive-media
records retained after republication review. A repeated text hash is never
sufficient on its own: automatic collapse requires the same canonical URL, or a
valid SHA-256 corroborated by the same normalized title. Same-title metadata
matches with differing URL/hash remain review candidates. Known text-quality
exceptions never participate in hash-only duplicate logic.

This script does not freeze the corpus and does not use stance/model outputs.
"""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "data" / "reconstruction"
PRIOR = RECON / "review_handoff" / "screened_qc_preliminary_unique_text_manifest.csv"
ARCHIVE = RECON / "archive_media_post_titlepair_manifest.csv"
MATCHES = RECON / "cross_phase_match_audit.csv"
SAFE = RECON / "cross_phase_safe_duplicate_decisions.csv"
TITLE_REVIEW = RECON / "cross_phase_same_title_review.csv"
HASH_COLLISIONS = RECON / "cross_phase_hash_collision_review.csv"
COMBINED = RECON / "cross_phase_preliminary_combined_manifest.csv"
SUMMARY = RECON / "cross_phase_dedup_summary.json"
SHA_RX = re.compile(r"^[0-9a-f]{64}$")


def read_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def norm_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def canon_url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    try:
        p = urlsplit(value)
    except Exception:
        return value.lower().rstrip("/")
    host = p.netloc.lower().removeprefix("www.")
    path = re.sub(r"/+", "/", p.path).rstrip("/")
    return urlunsplit(("https" if host else p.scheme.lower(), host, path, "", ""))


def valid_sha(value: str) -> str:
    value = (value or "").strip().lower()
    return value if SHA_RX.fullmatch(value) else ""


def write_csv(path: Path, rows: list[dict], fields: list[str]):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


prior_raw = read_rows(PRIOR)
archive_all = read_rows(ARCHIVE)
if len(prior_raw) != 300:
    raise RuntimeError(f"Expected 300 prior screened rows, found {len(prior_raw)}")
if len(archive_all) != 678:
    raise RuntimeError(f"Expected 678 auditable archive rows, found {len(archive_all)}")

archive_raw = [r for r in archive_all if r.get("titlepair_review_status") == "retained_after_titlepair_review"]
redundant_republications = [r for r in archive_all if r.get("titlepair_review_status") == "redundant_republication"]
if len(archive_raw) != 661 or len(redundant_republications) != 17:
    raise RuntimeError(
        f"Expected 661 retained + 17 republications; got retained={len(archive_raw)}, redundant={len(redundant_republications)}"
    )

prior = []
for r in prior_raw:
    urls = {canon_url(r.get("source_url")), canon_url(r.get("final_url"))} - {""}
    prior.append({
        "record_id": r.get("candidate_id", ""),
        "phase": "prior_screened_300",
        "title": r.get("title", ""),
        "normalised_title": norm_title(r.get("title", "")),
        "year": r.get("year", ""),
        "publisher": r.get("publisher", ""),
        "publisher_norm": (r.get("publisher") or "").strip().lower(),
        "url": r.get("final_url") or r.get("source_url") or "",
        "canonical_urls": urls,
        "text_sha256": valid_sha(r.get("text_sha256", "")),
        "text_words": r.get("text_words", ""),
        "analysis_ready": True,
    })

archive = []
for r in archive_raw:
    ready = str(r.get("analysis_ready_pre_cross_phase", "")).lower() == "true"
    archive.append({
        "record_id": r.get("record_id", ""),
        "phase": "archive_media_post_republication",
        "title": r.get("title", ""),
        "normalised_title": norm_title(r.get("title", "")),
        "year": r.get("year", ""),
        "publisher": r.get("publisher", ""),
        "publisher_norm": (r.get("publisher") or "").strip().lower(),
        "url": r.get("url", ""),
        "canonical_urls": {canon_url(r.get("url", ""))} - {""},
        "text_sha256": valid_sha(r.get("retrieved_text_sha256", "")),
        "text_words": r.get("retrieved_text_words", ""),
        "analysis_ready": ready,
        "final_text_quality_status": r.get("final_text_quality_status", ""),
    })

quality_exception_ids = {r["record_id"] for r in archive if not r["analysis_ready"]}
if len(quality_exception_ids) != 10:
    raise RuntimeError(f"Expected 10 retained archive text-quality exceptions, found {len(quality_exception_ids)}")

by_url = defaultdict(list)
by_hash = defaultdict(list)
by_title_year_pub = defaultdict(list)
for p in prior:
    for u in p["canonical_urls"]:
        by_url[u].append(p)
    if p["text_sha256"]:
        by_hash[p["text_sha256"]].append(p)
    by_title_year_pub[(p["normalised_title"], p["year"], p["publisher_norm"])].append(p)

match_rows = []
hash_collision_rows = []
title_review_rows = []
safe_candidates: dict[str, dict[str, dict]] = defaultdict(dict)


def add_safe(a, p, reason):
    entry = safe_candidates[a["record_id"]].setdefault(p["record_id"], {"prior": p, "reasons": set()})
    entry["reasons"].add(reason)


for a in archive:
    seen = set()

    # Same canonical URL is strong source identity, including when archive text is unavailable/corrupt.
    for u in sorted(a["canonical_urls"]):
        for p in by_url.get(u, []):
            pair = (p["record_id"], a["record_id"])
            if pair in seen:
                continue
            seen.add(pair)
            same_hash = bool(a["text_sha256"] and a["text_sha256"] == p["text_sha256"])
            same_title = a["normalised_title"] == p["normalised_title"]
            match_rows.append({
                "prior_record_id": p["record_id"], "archive_record_id": a["record_id"],
                "match_type": "same_canonical_url", "same_title": str(same_title).lower(),
                "same_valid_text_sha256": str(same_hash).lower(), "prior_title": p["title"],
                "archive_title": a["title"], "prior_publisher": p["publisher"], "archive_publisher": a["publisher"],
                "prior_year": p["year"], "archive_year": a["year"], "prior_url": p["url"], "archive_url": a["url"],
                "prior_text_sha256": p["text_sha256"], "archive_text_sha256": a["text_sha256"],
                "archive_analysis_ready_before_cross_phase": str(a["analysis_ready"]).lower(),
                "disposition": "safe_cross_phase_duplicate_candidate",
            })
            add_safe(a, p, "same_canonical_url")

    # Hash matches are safe only with title corroboration and only for archive rows with trustworthy text.
    if a["analysis_ready"] and a["text_sha256"]:
        for p in by_hash.get(a["text_sha256"], []):
            pair = (p["record_id"], a["record_id"])
            same_title = a["normalised_title"] == p["normalised_title"]
            same_url = bool(a["canonical_urls"] & p["canonical_urls"])
            if same_title or same_url:
                if pair not in seen:
                    seen.add(pair)
                    match_rows.append({
                        "prior_record_id": p["record_id"], "archive_record_id": a["record_id"],
                        "match_type": "same_sha256_with_metadata_corroboration", "same_title": str(same_title).lower(),
                        "same_valid_text_sha256": "true", "prior_title": p["title"], "archive_title": a["title"],
                        "prior_publisher": p["publisher"], "archive_publisher": a["publisher"],
                        "prior_year": p["year"], "archive_year": a["year"], "prior_url": p["url"], "archive_url": a["url"],
                        "prior_text_sha256": p["text_sha256"], "archive_text_sha256": a["text_sha256"],
                        "archive_analysis_ready_before_cross_phase": "true",
                        "disposition": "safe_cross_phase_duplicate_candidate",
                    })
                add_safe(a, p, "same_sha256_plus_same_title" if same_title else "same_sha256_plus_same_url")
            else:
                hash_collision_rows.append({
                    "prior_record_id": p["record_id"], "archive_record_id": a["record_id"],
                    "shared_text_sha256": a["text_sha256"], "prior_title": p["title"], "archive_title": a["title"],
                    "prior_url": p["url"], "archive_url": a["url"],
                    "review_status": "do_not_auto_collapse_hash_metadata_conflict",
                })

    # Same normalized title/year/publisher but differing URL/hash remains review-only.
    key = (a["normalised_title"], a["year"], a["publisher_norm"])
    already_safe_prior_ids = set(safe_candidates.get(a["record_id"], {}))
    for p in by_title_year_pub.get(key, []):
        if p["record_id"] in already_safe_prior_ids:
            continue
        title_review_rows.append({
            "prior_record_id": p["record_id"], "archive_record_id": a["record_id"],
            "normalised_title": a["normalised_title"], "year": a["year"], "publisher": a["publisher"],
            "prior_url": p["url"], "archive_url": a["url"],
            "prior_text_sha256": p["text_sha256"], "archive_text_sha256": a["text_sha256"],
            "archive_analysis_ready_before_cross_phase": str(a["analysis_ready"]).lower(),
            "review_status": "same_title_year_publisher_requires_explicit_review",
        })

safe_rows = []
redundant_archive_ids = set()
for aid, candidates in sorted(safe_candidates.items()):
    chosen_prior_id = sorted(candidates)[0]
    chosen = candidates[chosen_prior_id]
    all_reasons = sorted({reason for item in candidates.values() for reason in item["reasons"]})
    redundant_archive_ids.add(aid)
    safe_rows.append({
        "retained_prior_record_id": chosen_prior_id,
        "redundant_archive_record_id": aid,
        "duplicate_evidence": ";".join(all_reasons),
        "number_of_prior_candidates": len(candidates),
        "final_duplicate_decision": "collapse_cross_phase_duplicate_keep_prior_screened_record",
        "decision_reason": "same_source_identity_corroborated_by_canonical_url_or_hash_plus_title",
    })

combined = []
for p in prior:
    combined.append({
        "canonical_record_id": p["record_id"], "source_phase": p["phase"], "title": p["title"],
        "year": p["year"], "publisher": p["publisher"], "url": p["url"], "text_sha256": p["text_sha256"],
        "text_words": p["text_words"], "analysis_ready": "true", "cross_phase_status": "retained_prior_screened_record",
        "duplicate_representative_record_id": p["record_id"],
    })
for a in archive:
    if a["record_id"] in redundant_archive_ids:
        continue
    combined.append({
        "canonical_record_id": a["record_id"], "source_phase": a["phase"], "title": a["title"],
        "year": a["year"], "publisher": a["publisher"], "url": a["url"], "text_sha256": a["text_sha256"],
        "text_words": a["text_words"], "analysis_ready": str(a["analysis_ready"]).lower(),
        "cross_phase_status": "retained_archive_record_after_safe_cross_phase_audit",
        "duplicate_representative_record_id": a["record_id"],
    })

write_csv(MATCHES, match_rows, [
    "prior_record_id","archive_record_id","match_type","same_title","same_valid_text_sha256","prior_title","archive_title",
    "prior_publisher","archive_publisher","prior_year","archive_year","prior_url","archive_url","prior_text_sha256",
    "archive_text_sha256","archive_analysis_ready_before_cross_phase","disposition"
])
write_csv(SAFE, safe_rows, [
    "retained_prior_record_id","redundant_archive_record_id","duplicate_evidence","number_of_prior_candidates",
    "final_duplicate_decision","decision_reason"
])
write_csv(TITLE_REVIEW, title_review_rows, [
    "prior_record_id","archive_record_id","normalised_title","year","publisher","prior_url","archive_url",
    "prior_text_sha256","archive_text_sha256","archive_analysis_ready_before_cross_phase","review_status"
])
write_csv(HASH_COLLISIONS, hash_collision_rows, [
    "prior_record_id","archive_record_id","shared_text_sha256","prior_title","archive_title","prior_url","archive_url","review_status"
])
write_csv(COMBINED, combined, [
    "canonical_record_id","source_phase","title","year","publisher","url","text_sha256","text_words","analysis_ready",
    "cross_phase_status","duplicate_representative_record_id"
])

analysis_ready_count = sum(r["analysis_ready"] == "true" for r in combined)
summary = {
    "scope": "cross_phase_dedup_prior_screened_300_plus_post_republication_archive_661",
    "prior_screened_records": len(prior),
    "archive_records_post_republication": len(archive),
    "combined_pool_before_cross_phase_dedup": len(prior) + len(archive),
    "safe_cross_phase_duplicate_archive_records": len(redundant_archive_ids),
    "safe_cross_phase_duplicate_decision_rows": len(safe_rows),
    "same_title_year_publisher_review_pairs": len(title_review_rows),
    "hash_metadata_conflict_pairs": len(hash_collision_rows),
    "records_retained_after_safe_cross_phase_dedup": len(combined),
    "analysis_ready_records_after_safe_cross_phase_dedup": analysis_ready_count,
    "retained_non_analysis_ready_records": len(combined) - analysis_ready_count,
    "near_duplicate_review_complete": False,
    "corpus_frozen": False,
    "dedup_rule": (
        "Automatic cross-phase collapse requires the same canonical URL, or the same valid text SHA-256 corroborated by the same normalized title. "
        "Hash-only matches across conflicting metadata are never auto-collapsed. Same-title/year/publisher matches with differing URL/hash remain review candidates."
    ),
    "important_note": (
        "The 678-row archive manifest is deliberately auditable and retains the 17 republications as rows; this audit uses only its 661 final retained records. "
        "Broader near-duplicate review remains before corpus freeze."
    ),
}
SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
