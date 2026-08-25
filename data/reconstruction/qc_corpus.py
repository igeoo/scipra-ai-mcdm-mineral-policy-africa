from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from sklearn.feature_extraction.text import HashingVectorizer

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "data" / "reconstruction"
OUT = ROOT / "acquisition_output"
QC = OUT / "qc"
STATUS = OUT / "acquisition_status.csv"
TEXT_DIR = OUT / "text"
MANUAL_DECISIONS = RECON / "manual_qc_decisions.csv"

NEAR_DUPLICATE_THRESHOLD = 0.95


def read_status() -> list[dict[str, str]]:
    with STATUS.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_manual_decisions() -> list[dict[str, str]]:
    if not MANUAL_DECISIONS.exists():
        return []
    with MANUAL_DECISIONS.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def canonical_priority(candidate_id: str) -> tuple[int, str]:
    if re.match(r"^(OFFICIAL|INST|MEDIA|CORP)-", candidate_id):
        return (0, candidate_id)
    if candidate_id.startswith("WEB-"):
        return (1, candidate_id)
    if candidate_id.startswith("EXP-"):
        return (2, candidate_id)
    if candidate_id.startswith("expanded_"):
        return (3, candidate_id)
    return (4, candidate_id)


def normalise_title(title: str) -> str:
    text = title.casefold().replace("’", "'").replace("–", "-").replace("—", "-")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def canonicalise_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        path = re.sub(r"/+", "/", parts.path).rstrip("/")
        return urlunsplit((parts.scheme.lower() or "https", host, path, "", ""))
    except Exception:
        return url


def metadata_review_clusters(unique_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in unique_rows:
        key = (normalise_title(row.get("title", "")), (row.get("year") or "").strip())
        if key[0]:
            groups[key].append(row)

    output: list[dict[str, object]] = []
    cluster_id = 0
    for (title_key, year), group in sorted(groups.items()):
        if len(group) < 2:
            continue
        cluster_id += 1
        for row in group:
            output.append({
                "cluster_id": cluster_id,
                "normalised_title": title_key,
                "year": year,
                "candidate_id": row["candidate_id"],
                "title": row.get("title", ""),
                "publisher": row.get("publisher", ""),
                "source_url": row.get("source_url", ""),
                "text_sha256": row.get("text_sha256", ""),
                "decision": "manual_review_same_title_year",
            })
    return output


def url_review_clusters(unique_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in unique_rows:
        key = canonicalise_url(row.get("source_url", ""))
        if key:
            groups[key].append(row)

    output: list[dict[str, object]] = []
    cluster_id = 0
    for url_key, group in sorted(groups.items()):
        if len(group) < 2:
            continue
        cluster_id += 1
        for row in group:
            output.append({
                "cluster_id": cluster_id,
                "canonicalised_url": url_key,
                "candidate_id": row["candidate_id"],
                "title": row.get("title", ""),
                "year": row.get("year", ""),
                "publisher": row.get("publisher", ""),
                "text_sha256": row.get("text_sha256", ""),
                "decision": "manual_review_same_url",
            })
    return output


def main() -> int:
    rows = read_status()
    extracted = [r for r in rows if r.get("status") == "acquired_extracted"]
    exceptions = [r for r in rows if r.get("status") != "acquired_extracted"]

    by_hash: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in extracted:
        text_hash = (row.get("text_sha256") or "").strip()
        if text_hash:
            by_hash[text_hash].append(row)

    duplicate_rows: list[dict[str, object]] = []
    noncanonical_ids: set[str] = set()
    duplicate_cluster_count = 0
    for text_hash, group in sorted(by_hash.items()):
        if len(group) < 2:
            continue
        duplicate_cluster_count += 1
        canonical = min((r["candidate_id"] for r in group), key=canonical_priority)
        for row in group:
            is_canonical = row["candidate_id"] == canonical
            if not is_canonical:
                noncanonical_ids.add(row["candidate_id"])
            duplicate_rows.append({
                "text_sha256": text_hash,
                "cluster_size": len(group),
                "canonical_id": canonical,
                "candidate_id": row["candidate_id"],
                "is_canonical": str(is_canonical).lower(),
                "title": row.get("title", ""),
                "year": row.get("year", ""),
                "publisher": row.get("publisher", ""),
                "source_url": row.get("source_url", ""),
                "metadata_source": row.get("metadata_source", ""),
            })

    unique_rows = [r for r in extracted if r["candidate_id"] not in noncanonical_ids]

    manual_decisions = read_manual_decisions()
    excluded_manual_ids = {
        (r.get("candidate_id") or "").strip()
        for r in manual_decisions
        if (r.get("decision") or "").strip().lower().startswith("exclude")
    }
    decision_by_id = {(r.get("candidate_id") or "").strip(): r for r in manual_decisions}
    manual_exclusion_rows: list[dict[str, object]] = []
    for row in unique_rows:
        cid = row["candidate_id"]
        if cid not in excluded_manual_ids:
            continue
        decision = decision_by_id[cid]
        manual_exclusion_rows.append({
            "candidate_id": cid,
            "title": row.get("title", ""),
            "year": row.get("year", ""),
            "publisher": row.get("publisher", ""),
            "decision": decision.get("decision", ""),
            "decision_stage": decision.get("decision_stage", ""),
            "reason": decision.get("reason", ""),
            "evidence_basis": decision.get("evidence_basis", ""),
            "model_results_seen": decision.get("model_results_seen", ""),
        })

    review_rows = [r for r in unique_rows if r["candidate_id"] not in excluded_manual_ids]
    title_review = metadata_review_clusters(review_rows)
    url_review = url_review_clusters(review_rows)

    texts: list[str] = []
    text_rows: list[dict[str, str]] = []
    for row in review_rows:
        path = TEXT_DIR / f"{row['candidate_id']}.txt"
        if not path.exists():
            continue
        texts.append(path.read_text(encoding="utf-8", errors="replace"))
        text_rows.append(row)

    near_rows: list[dict[str, object]] = []
    if texts:
        vectorizer = HashingVectorizer(
            n_features=2**17,
            alternate_sign=False,
            norm="l2",
            stop_words="english",
            ngram_range=(1, 2),
        )
        matrix = vectorizer.transform(texts)
        similarities = matrix @ matrix.T
        coo = similarities.tocoo()
        seen: set[tuple[int, int]] = set()
        for i, j, score in zip(coo.row, coo.col, coo.data):
            if i >= j or score < NEAR_DUPLICATE_THRESHOLD:
                continue
            pair = (int(i), int(j))
            if pair in seen:
                continue
            seen.add(pair)
            a = text_rows[i]
            b = text_rows[j]
            if (a.get("text_sha256") or "") == (b.get("text_sha256") or ""):
                continue
            near_rows.append({
                "similarity": f"{float(score):.6f}",
                "candidate_id_a": a["candidate_id"],
                "candidate_id_b": b["candidate_id"],
                "title_a": a.get("title", ""),
                "title_b": b.get("title", ""),
                "year_a": a.get("year", ""),
                "year_b": b.get("year", ""),
                "publisher_a": a.get("publisher", ""),
                "publisher_b": b.get("publisher", ""),
                "url_a": a.get("source_url", ""),
                "url_b": b.get("source_url", ""),
                "decision": "manual_review_near_duplicate",
            })

    exception_fields = [
        "candidate_id", "status", "title", "year", "publisher", "metadata_source",
        "source_url", "final_url", "http_status", "content_type", "retrieval_method",
        "raw_bytes", "extraction_method", "pages", "text_chars", "text_words", "error",
    ]
    exception_rows = [{key: row.get(key, "") for key in exception_fields} for row in exceptions]

    manifest_fields = [
        "candidate_id", "title", "year", "publisher", "metadata_source", "source_url",
        "final_url", "raw_sha256", "text_sha256", "text_words",
    ]
    manifest_rows = [{key: row.get(key, "") for key in manifest_fields} for row in review_rows]

    write_csv(QC / "exact_duplicate_clusters.csv",
              ["text_sha256", "cluster_size", "canonical_id", "candidate_id", "is_canonical",
               "title", "year", "publisher", "source_url", "metadata_source"], duplicate_rows)
    write_csv(QC / "manual_exclusions.csv",
              ["candidate_id", "title", "year", "publisher", "decision", "decision_stage",
               "reason", "evidence_basis", "model_results_seen"], manual_exclusion_rows)
    write_csv(QC / "same_title_year_review.csv",
              ["cluster_id", "normalised_title", "year", "candidate_id", "title", "publisher",
               "source_url", "text_sha256", "decision"], title_review)
    write_csv(QC / "same_url_review.csv",
              ["cluster_id", "canonicalised_url", "candidate_id", "title", "year", "publisher",
               "text_sha256", "decision"], url_review)
    write_csv(QC / "near_duplicate_review.csv",
              ["similarity", "candidate_id_a", "candidate_id_b", "title_a", "title_b", "year_a",
               "year_b", "publisher_a", "publisher_b", "url_a", "url_b", "decision"],
              sorted(near_rows, key=lambda r: float(r["similarity"]), reverse=True))
    write_csv(QC / "acquisition_exceptions.csv", exception_fields, exception_rows)
    write_csv(QC / "preliminary_unique_text_manifest.csv", manifest_fields, manifest_rows)

    status_counts = Counter(row.get("status", "") for row in rows)
    summary = {
        "candidate_records_processed": len(rows),
        "acquired_extracted_records": len(extracted),
        "acquisition_exception_records": len(exceptions),
        "exact_duplicate_clusters": duplicate_cluster_count,
        "exact_duplicate_redundant_records": len(noncanonical_ids),
        "unique_extracted_texts_after_exact_dedup_before_manual_exclusions": len(unique_rows),
        "prospective_manual_exclusions_applied": len(manual_exclusion_rows),
        "preliminary_corpus_records_after_exact_dedup_and_prospective_exclusions": len(review_rows),
        "same_title_year_clusters_requiring_review": len({r["cluster_id"] for r in title_review}),
        "same_url_clusters_requiring_review": len({r["cluster_id"] for r in url_review}),
        "near_duplicate_pairs_flagged_at_similarity_ge_0_95": len(near_rows),
        "status_counts": dict(status_counts),
        "near_duplicate_threshold": NEAR_DUPLICATE_THRESHOLD,
        "corpus_frozen": False,
        "note": (
            "Preliminary QC only. Corpus freeze requires resolution of acquisition exceptions, "
            "same-title/URL and near-duplicate reviews, substantive relevance/text-quality screening, "
            "and documented source-family saturation."
        ),
    }
    (QC / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
