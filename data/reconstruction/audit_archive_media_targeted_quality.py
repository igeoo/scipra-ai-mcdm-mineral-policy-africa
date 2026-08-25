"""Targeted recovery/similarity audit for unresolved archive-media quality cases.

Only two small sets are re-fetched:
1. the 34 rows in 17 same-normalised-title/year review pairs; and
2. the 11 records currently withheld for missing text/hash or suspected extraction
   hash collisions.

The script stores no article text. It records fresh extraction hashes/word counts,
which extractor produced the selected body, and pairwise similarity metrics. It
makes no automatic corpus-membership or duplicate decisions.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from pathlib import Path

import requests
import trafilatura
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "data" / "reconstruction"
PAIR_IN = RECON / "archive_media_same_title_year_review.csv"
COLLISION_IN = RECON / "archive_media_extraction_hash_collisions.csv"
MISSING_IN = RECON / "archive_media_text_hash_exceptions.csv"
PAIR_OUT = RECON / "archive_media_same_title_year_similarity_audit.csv"
QUALITY_OUT = RECON / "archive_media_quality_recovery_audit.csv"
SUMMARY = RECON / "archive_media_targeted_quality_summary.json"

UA = "Mozilla/5.0 (compatible; SCIPRA-Reproducibility-Audit/1.2; +https://github.com/Martin-do/scipra-ai-mcdm-mineral-policy-africa)"


def read_rows(path: Path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def normalise(text: str) -> str:
    text = (text or "").replace("\x00", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""


def jsonld_bodies(soup: BeautifulSoup):
    out = []
    for script in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        stack = obj if isinstance(obj, list) else [obj]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                body = item.get("articleBody")
                if isinstance(body, str) and words(body) >= 80:
                    out.append(("jsonld_articleBody", normalise(body)))
                for value in item.values():
                    if isinstance(value, (dict, list)):
                        stack.append(value)
            elif isinstance(item, list):
                stack.extend(item)
    return out


def selector_candidates(soup: BeautifulSoup):
    selectors = [
        "[itemprop='articleBody']", ".article-body", ".article_body", ".article-content",
        ".article_content", ".story-body", ".story_body", ".entry-content", ".post-content",
        ".field-name-body", ".node__content", "article", "main",
    ]
    out = []
    seen = set()
    for selector in selectors:
        try:
            nodes = soup.select(selector)
        except Exception:
            continue
        for node in nodes[:3]:
            text = normalise("\n".join(p.get_text(" ", strip=True) for p in node.find_all("p")))
            if words(text) < 80:
                text = normalise(node.get_text(" ", strip=True))
            if words(text) >= 80:
                key = sha(text)
                if key not in seen:
                    seen.add(key)
                    out.append((f"css:{selector}", text))
    return out


def extract_candidates(data: bytes, url: str):
    html = data.decode("utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "form", "aside"]):
        if tag.name != "script" or not (tag.get("type") or "").lower().startswith("application/ld+json"):
            tag.decompose()
    candidates = []
    try:
        t = trafilatura.extract(html, url=url, include_comments=False, include_tables=False, favor_precision=True, no_fallback=False)
        if t and words(t) >= 80:
            candidates.append(("trafilatura", normalise(t)))
    except Exception:
        pass
    candidates.extend(jsonld_bodies(soup))
    candidates.extend(selector_candidates(soup))
    # Prefer the longest credible candidate. This audit then checks cross-page
    # hash collisions and pair similarity rather than trusting extraction alone.
    candidates.sort(key=lambda item: (words(item[1]), len(item[1])), reverse=True)
    return candidates


def fetch_one(url: str):
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "en-ZA,en;q=0.9"})
    last = ""
    for attempt in range(2):
        try:
            r = session.get(url, timeout=35, allow_redirects=True)
            if r.status_code == 200:
                candidates = extract_candidates(r.content, str(r.url))
                if candidates:
                    method, text = candidates[0]
                    return {
                        "url": url, "final_url": str(r.url), "fetch_status": "recovered_extracted",
                        "fetch_error": "", "extraction_method": method, "fresh_text": text,
                        "fresh_text_words": words(text), "fresh_text_sha256": sha(text),
                        "candidate_extractions": len(candidates),
                    }
                return {
                    "url": url, "final_url": str(r.url), "fetch_status": "recovered_no_text",
                    "fetch_error": "no_candidate_body_ge_80_words", "extraction_method": "", "fresh_text": "",
                    "fresh_text_words": 0, "fresh_text_sha256": "", "candidate_extractions": 0,
                }
            last = f"HTTP {r.status_code}"
            if r.status_code in {401, 403, 404, 410}:
                break
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(attempt + 1)
    return {
        "url": url, "final_url": url, "fetch_status": "recovery_failed", "fetch_error": last or "fetch_failed",
        "extraction_method": "", "fresh_text": "", "fresh_text_words": 0, "fresh_text_sha256": "",
        "candidate_extractions": 0,
    }


def tokens(text: str):
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def shingle_set(text: str, n=5):
    t = tokens(text)
    if len(t) < n:
        return set(t)
    return {tuple(t[i:i+n]) for i in range(len(t)-n+1)}


def jaccard(a, b):
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


pair_rows = read_rows(PAIR_IN)
collision_rows = read_rows(COLLISION_IN)
missing_rows = read_rows(MISSING_IN)
if len(pair_rows) != 34:
    raise RuntimeError(f"Expected 34 same-title/year review rows, found {len(pair_rows)}")

record_meta = {}
for r in pair_rows:
    record_meta[r["record_id"]] = r
for r in collision_rows:
    record_meta.setdefault(r["record_id"], r)
for r in missing_rows:
    record_meta.setdefault(r["record_id"], r)

urls = sorted({r.get("url", "") for r in record_meta.values() if r.get("url")})
results = {}
with ThreadPoolExecutor(max_workers=5) as pool:
    future_map = {pool.submit(fetch_one, url): url for url in urls}
    for future in as_completed(future_map):
        res = future.result()
        results[res["url"]] = res

# Quality recovery table for missing/collision records only.
quality_ids = {r["record_id"] for r in collision_rows} | {r["record_id"] for r in missing_rows}
collision_old_hashes = defaultdict(set)
for r in collision_rows:
    collision_old_hashes[r.get("text_sha256", "")].add(r["record_id"])

quality_out = []
for rid in sorted(quality_ids):
    meta = record_meta[rid]
    res = results.get(meta.get("url", ""), {})
    old_hash = meta.get("text_sha256") or meta.get("retrieved_text_sha256") or ""
    old_words = meta.get("retrieved_text_words", "")
    fresh_hash = res.get("fresh_text_sha256", "")
    fresh_words = int(res.get("fresh_text_words") or 0)
    if not fresh_hash:
        disposition = "still_unresolved_text_recovery"
    elif old_hash and fresh_hash == old_hash:
        disposition = "fresh_extraction_repeats_prior_suspect_payload"
    elif fresh_words < 150:
        disposition = "fresh_text_too_short_for_confident_recovery"
    else:
        disposition = "fresh_distinct_text_recovered_requires_content_qc"
    quality_out.append({
        "record_id": rid,
        "title": meta.get("title", ""),
        "publisher": meta.get("publisher", ""),
        "url": meta.get("url", ""),
        "old_text_words": old_words,
        "old_text_sha256": old_hash,
        "fetch_status": res.get("fetch_status", "not_fetched"),
        "fetch_error": res.get("fetch_error", ""),
        "extraction_method": res.get("extraction_method", ""),
        "candidate_extractions": res.get("candidate_extractions", 0),
        "fresh_text_words": fresh_words,
        "fresh_text_sha256": fresh_hash,
        "recovery_disposition": disposition,
    })

quality_fields = list(quality_out[0].keys()) if quality_out else ["record_id"]
with QUALITY_OUT.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=quality_fields); w.writeheader(); w.writerows(quality_out)

# Pairwise similarity table.
pairs = defaultdict(list)
for r in pair_rows:
    pairs[r["cluster_id"]].append(r)

pair_out = []
for cluster_id, members in sorted(pairs.items()):
    if len(members) != 2:
        raise RuntimeError(f"Expected pair cluster {cluster_id} to contain 2 rows, found {len(members)}")
    a, b = sorted(members, key=lambda r: (r.get("publication_date_from_url", ""), r["record_id"]))
    ra = results.get(a["url"], {})
    rb = results.get(b["url"], {})
    ta = ra.get("fresh_text", "")
    tb = rb.get("fresh_text", "")
    if ta and tb:
        char_ratio = SequenceMatcher(None, ta, tb, autojunk=False).ratio()
        token_j = jaccard(set(tokens(ta)), set(tokens(tb)))
        shingle_j = jaccard(shingle_set(ta, 5), shingle_set(tb, 5))
    else:
        char_ratio = token_j = shingle_j = None

    if char_ratio is None:
        signal = "insufficient_recovered_text"
    elif char_ratio >= 0.97 and shingle_j >= 0.92:
        signal = "very_high_similarity_possible_republication"
    elif char_ratio >= 0.90 or shingle_j >= 0.80:
        signal = "high_similarity_requires_republication_review"
    elif char_ratio >= 0.70 or shingle_j >= 0.55:
        signal = "moderate_similarity_distinct_update_possible"
    else:
        signal = "low_similarity_distinct_text_supported"

    pair_out.append({
        "cluster_id": cluster_id,
        "normalised_title_year": a.get("normalised_title_year", ""),
        "record_id_a": a["record_id"], "date_a": a.get("publication_date_from_url", ""), "url_a": a["url"],
        "fresh_words_a": ra.get("fresh_text_words", 0), "fresh_sha256_a": ra.get("fresh_text_sha256", ""),
        "extractor_a": ra.get("extraction_method", ""),
        "record_id_b": b["record_id"], "date_b": b.get("publication_date_from_url", ""), "url_b": b["url"],
        "fresh_words_b": rb.get("fresh_text_words", 0), "fresh_sha256_b": rb.get("fresh_text_sha256", ""),
        "extractor_b": rb.get("extraction_method", ""),
        "sequence_similarity": "" if char_ratio is None else f"{char_ratio:.6f}",
        "token_set_jaccard": "" if token_j is None else f"{token_j:.6f}",
        "five_word_shingle_jaccard": "" if shingle_j is None else f"{shingle_j:.6f}",
        "similarity_signal": signal,
        "final_duplicate_decision": "",
        "final_duplicate_reason": "",
    })

pair_fields = list(pair_out[0].keys()) if pair_out else ["cluster_id"]
with PAIR_OUT.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=pair_fields); w.writeheader(); w.writerows(pair_out)

summary = {
    "audit_scope": "targeted_archive_media_quality_recovery_and_same_title_year_similarity",
    "unique_urls_refetched": len(urls),
    "same_title_year_pairs": len(pair_out),
    "pair_similarity_signal_counts": dict(Counter(r["similarity_signal"] for r in pair_out)),
    "quality_exception_records_targeted": len(quality_out),
    "quality_recovery_disposition_counts": dict(Counter(r["recovery_disposition"] for r in quality_out)),
    "quality_records_with_fresh_text": sum(bool(r["fresh_text_sha256"]) for r in quality_out),
    "final_duplicate_decisions_made": 0,
    "important_note": (
        "This is evidence-only. Fresh text is held only in runner memory and is not committed. Similarity signals do not automatically collapse records; "
        "final pair decisions require explicit review. Suspected extraction-collision records remain non-analysis-ready until recovered text is judged credible."
    ),
}
SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
