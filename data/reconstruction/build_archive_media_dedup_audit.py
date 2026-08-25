"""Build a conservative pre-freeze dedup/text-quality audit for eligible archive media.

Exact text SHA equality is necessary but not sufficient for automatic deduplication:
web extraction can return identical boilerplate for unrelated pages. A SHA group is
automatically collapsible only when metadata corroborates identity through the same
normalised title or canonical URL. Same hashes across unrelated titles/URLs are
flagged as suspected extraction collisions and removed from the analysis-ready set
until text recovery/revalidation.

Same-title/year and same-URL clusters remain review flags. No stance labels or
model outputs are used and this script does not freeze the corpus.
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
TITLE_LEDGER = RECON / "media_substantive_decision_ledger.csv"
SECONDARY_LEDGER = RECON / "secondary_media_substantive_decision_ledger.csv"
PRE = RECON / "archive_media_included_pre_dedup_manifest.csv"
HASH_EXCEPTIONS = RECON / "archive_media_text_hash_exceptions.csv"
COLLISIONS = RECON / "archive_media_extraction_hash_collisions.csv"
EXACT = RECON / "archive_media_exact_duplicate_clusters.csv"
TITLE_REVIEW = RECON / "archive_media_same_title_year_review.csv"
URL_REVIEW = RECON / "archive_media_same_url_review.csv"
DEDUP = RECON / "archive_media_exact_dedup_preliminary_manifest.csv"
SUMMARY = RECON / "archive_media_dedup_summary.json"
SHA_RX = re.compile(r"[0-9a-f]{64}")


def read_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def canon_url(url: str) -> str:
    p = urlsplit((url or "").strip())
    host = p.netloc.lower().removeprefix("www.")
    path = re.sub(r"/+", "/", p.path).rstrip("/")
    return urlunsplit(("https", host, path, "", ""))


def norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()


def valid_sha(value: str) -> bool:
    return bool(SHA_RX.fullmatch((value or "").strip().lower()))


def sort_key(r):
    date = r.get("publication_date_from_url") or f"{r.get('year','9999')}-99-99"
    return (date, r.get("canonical_url", ""), r.get("record_id", ""))


title_rows = read_rows(TITLE_LEDGER)
secondary_rows = read_rows(SECONDARY_LEDGER)
if len(title_rows) != 690 or len(secondary_rows) != 1062:
    raise RuntimeError(f"Unexpected ledger sizes: title={len(title_rows)}, secondary={len(secondary_rows)}")

included = []
for source, rows in (("title_trigger", title_rows), ("secondary_keyword", secondary_rows)):
    for r in rows:
        if r.get("final_decision") != "include":
            continue
        sha = (r.get("retrieved_text_sha256") or "").strip().lower()
        included.append({
            "record_id": r.get("candidate_id", ""),
            "archive_queue": source,
            "title": r.get("title", ""),
            "normalised_title": norm_title(r.get("title", "")),
            "year": r.get("year", ""),
            "publication_date_from_url": r.get("publication_date_from_url", ""),
            "publisher": r.get("publisher", ""),
            "url": r.get("url", ""),
            "canonical_url": canon_url(r.get("url", "")),
            "retrieved_text_words": (r.get("retrieved_text_words") or "").strip(),
            "retrieved_text_sha256": sha if valid_sha(sha) else "",
            "text_hash_status": "valid_sha256" if valid_sha(sha) else "missing_or_invalid_sha256",
            "reason_code": r.get("reason_code", ""),
            "decision_status": r.get("decision_status", ""),
            "decision_provenance": r.get("decision_provenance", ""),
        })

expected_title = sum(r.get("final_decision") == "include" for r in title_rows)
expected_secondary = sum(r.get("final_decision") == "include" for r in secondary_rows)
if (expected_title, expected_secondary, len(included)) != (547, 131, 678):
    raise RuntimeError(f"Expected 547 + 131 = 678 included media rows; got {expected_title} + {expected_secondary} = {len(included)}")
if len({r["record_id"] for r in included}) != len(included):
    raise RuntimeError("Duplicate record IDs found across eligible archive media")
included.sort(key=sort_key)


def groups_by(rows, keyfn):
    d = defaultdict(list)
    for r in rows:
        key = keyfn(r)
        if key:
            d[key].append(r)
    return {k: sorted(v, key=sort_key) for k, v in d.items() if len(v) > 1}

raw_sha_groups = groups_by(included, lambda r: r["retrieved_text_sha256"] if valid_sha(r["retrieved_text_sha256"]) else "")
safe_exact_groups = {}
collision_groups = {}
for sha, members in raw_sha_groups.items():
    titles = {m["normalised_title"] for m in members if m["normalised_title"]}
    urls = {m["canonical_url"] for m in members if m["canonical_url"]}
    # Metadata corroboration is mandatory. All members sharing one title or one
    # canonical URL supports a true duplicate interpretation; otherwise the same
    # hash is treated as an extraction collision until recovered.
    if len(titles) == 1 or len(urls) == 1:
        safe_exact_groups[sha] = members
    else:
        collision_groups[sha] = members

collision_ids = {r["record_id"] for members in collision_groups.values() for r in members}
for r in included:
    if r["record_id"] in collision_ids:
        r["text_hash_status"] = "suspected_extraction_hash_collision"

fields = list(included[0].keys())
with PRE.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(included)

hash_exceptions = [r for r in included if r["text_hash_status"] == "missing_or_invalid_sha256"]
exception_fields = ["record_id","archive_queue","title","year","publication_date_from_url","publisher","url","retrieved_text_words","retrieved_text_sha256","text_hash_status","reason_code","decision_provenance"]
with HASH_EXCEPTIONS.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=exception_fields); w.writeheader()
    for r in hash_exceptions:
        w.writerow({k: r.get(k, "") for k in exception_fields})

collision_rows = []
for n, (sha, members) in enumerate(sorted(collision_groups.items()), 1):
    for r in members:
        collision_rows.append({
            "collision_id": f"MEDIA-HASH-COLLISION-{n:04d}",
            "text_sha256": sha,
            "cluster_size": len(members),
            "record_id": r["record_id"],
            "retrieved_text_words": r["retrieved_text_words"],
            "publisher": r["publisher"],
            "publication_date_from_url": r["publication_date_from_url"],
            "title": r["title"],
            "url": r["url"],
            "disposition": "text_recovery_required_not_auto_deduped",
        })
collision_fields = ["collision_id","text_sha256","cluster_size","record_id","retrieved_text_words","publisher","publication_date_from_url","title","url","disposition"]
with COLLISIONS.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=collision_fields); w.writeheader(); w.writerows(collision_rows)

exact_rows = []
redundant_ids = set()
for n, (sha, members) in enumerate(sorted(safe_exact_groups.items()), 1):
    keeper = members[0]["record_id"]
    for pos, r in enumerate(members, 1):
        is_keeper = r["record_id"] == keeper
        if not is_keeper:
            redundant_ids.add(r["record_id"])
        exact_rows.append({
            "cluster_id": f"MEDIA-EXACT-{n:04d}", "text_sha256": sha, "cluster_size": len(members),
            "member_order": pos, "record_id": r["record_id"], "canonical_representative": str(is_keeper).lower(),
            "representative_record_id": keeper, "archive_queue": r["archive_queue"], "publisher": r["publisher"],
            "publication_date_from_url": r["publication_date_from_url"], "title": r["title"], "url": r["url"],
        })
exact_fields = ["cluster_id","text_sha256","cluster_size","member_order","record_id","canonical_representative","representative_record_id","archive_queue","publisher","publication_date_from_url","title","url"]
with EXACT.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=exact_fields); w.writeheader(); w.writerows(exact_rows)

url_groups = groups_by(included, lambda r: r["canonical_url"])
title_year_groups = groups_by(included, lambda r: (r["normalised_title"], r["year"]) if r["normalised_title"] else None)

def write_review(path, groups, prefix, key_label):
    out = []
    for n, (key, members) in enumerate(sorted(groups.items(), key=lambda kv: str(kv[0])), 1):
        hashes = [m["retrieved_text_sha256"] for m in members]
        exact_same = all(valid_sha(h) for h in hashes) and len(set(hashes)) == 1
        for r in members:
            out.append({
                "cluster_id": f"{prefix}-{n:04d}", key_label: " | ".join(key) if isinstance(key, tuple) else str(key),
                "cluster_size": len(members), "all_text_sha256_equal": str(exact_same).lower(), "record_id": r["record_id"],
                "archive_queue": r["archive_queue"], "publisher": r["publisher"], "publication_date_from_url": r["publication_date_from_url"],
                "retrieved_text_sha256": r["retrieved_text_sha256"], "text_hash_status": r["text_hash_status"], "title": r["title"], "url": r["url"],
            })
    review_fields = ["cluster_id",key_label,"cluster_size","all_text_sha256_equal","record_id","archive_queue","publisher","publication_date_from_url","retrieved_text_sha256","text_hash_status","title","url"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=review_fields); w.writeheader(); w.writerows(out)
    return out

url_rows = write_review(URL_REVIEW, url_groups, "MEDIA-URL", "canonical_url")
title_rows_out = write_review(TITLE_REVIEW, title_year_groups, "MEDIA-TITLEYEAR", "normalised_title_year")

dedup = []
for r in included:
    if r["record_id"] in redundant_ids:
        continue
    x = dict(r)
    if r["record_id"] in collision_ids:
        x["exact_dedup_status"] = "retained_extraction_collision_requires_text_recovery"
        x["analysis_ready_after_exact_dedup"] = "false"
    elif r["text_hash_status"] != "valid_sha256":
        x["exact_dedup_status"] = "retained_hash_exception_requires_text_recovery"
        x["analysis_ready_after_exact_dedup"] = "false"
    else:
        x["exact_dedup_status"] = "retained_unique_or_safe_representative"
        x["analysis_ready_after_exact_dedup"] = "true"
    dedup.append(x)
with DEDUP.open("w", encoding="utf-8", newline="") as f:
    out_fields = fields + ["exact_dedup_status","analysis_ready_after_exact_dedup"]
    w = csv.DictWriter(f, fieldnames=out_fields); w.writeheader(); w.writerows(dedup)

valid_hash_records = sum(valid_sha(r["retrieved_text_sha256"]) for r in included)
analysis_ready = sum(r["analysis_ready_after_exact_dedup"] == "true" for r in dedup)
summary = {
    "scope": "eligible_archive_media_after_substantive_screening_before_corpus_freeze",
    "title_trigger_inclusions": expected_title,
    "secondary_keyword_inclusions": expected_secondary,
    "included_media_records_pre_dedup": len(included),
    "records_with_syntactically_valid_text_sha256": valid_hash_records,
    "missing_text_hash_analyzability_exceptions": len(hash_exceptions),
    "missing_text_hash_exception_record_ids": [r["record_id"] for r in hash_exceptions],
    "raw_repeated_sha256_groups": len(raw_sha_groups),
    "safe_exact_duplicate_clusters": len(safe_exact_groups),
    "safe_exact_duplicate_redundant_records": len(redundant_ids),
    "suspected_extraction_hash_collision_clusters": len(collision_groups),
    "suspected_extraction_hash_collision_records": len(collision_ids),
    "records_after_safe_exact_dedup_including_quality_exceptions": len(dedup),
    "analysis_ready_records_after_safe_exact_dedup": analysis_ready,
    "same_canonical_url_clusters_for_review": len(url_groups),
    "same_normalised_title_year_clusters_for_review": len(title_year_groups),
    "same_url_rows": len(url_rows),
    "same_title_year_rows": len(title_rows_out),
    "corpus_frozen": False,
    "dedup_rule": (
        "Identical SHA-256 is auto-collapsible only when metadata corroborates identity through the same normalised title or canonical URL. "
        "Repeated hashes across unrelated titles/URLs are treated as extraction collisions requiring text recovery. Same-title/year and same-URL clusters remain review-only unless safely resolved."
    ),
    "important_note": (
        "This audit covers the newly screened archive-media pool only. Cross-phase deduplication against the prior screened reconstruction corpus, "
        "same-title/near-duplicate resolution and text recovery for quality exceptions remain before corpus freeze."
    ),
}
SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
