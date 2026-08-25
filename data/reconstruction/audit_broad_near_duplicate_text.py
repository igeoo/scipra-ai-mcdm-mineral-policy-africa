"""Targeted full-text evidence audit for broad near-duplicate candidates.

Only URLs appearing in broad_near_duplicate_candidates.csv are fetched. Article
text remains in runner memory; committed outputs contain metadata, fresh hashes,
word counts, extraction method, collision flags, and pairwise similarity only.

This stage is evidence-only and makes no duplicate decisions.
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
IN = RECON / "broad_near_duplicate_candidates.csv"
OUT = RECON / "broad_near_duplicate_text_evidence.csv"
SUMMARY = RECON / "broad_near_duplicate_text_evidence_summary.json"
UA = "Mozilla/5.0 (compatible; SCIPRA-Reproducibility-Audit/1.3; +https://github.com/Martin-do/scipra-ai-mcdm-mineral-policy-africa)"


def read_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\x00", " ")).strip()


def title_norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""


def tokens(text: str):
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def shingles(text: str, n=5):
    t = tokens(text)
    if len(t) < n:
        return {tuple(t)} if t else set()
    return {tuple(t[i:i+n]) for i in range(len(t)-n+1)}


def jaccard(a, b):
    if not a and not b:
        return 1.0
    u = a | b
    return len(a & b) / len(u) if u else 0.0


def extract(data: bytes, url: str):
    html = data.decode("utf-8", errors="replace")
    candidates = []
    try:
        text = trafilatura.extract(
            html, url=url, include_comments=False, include_tables=False,
            favor_precision=True, no_fallback=False
        )
        text = norm(text or "")
        if words(text) >= 80:
            candidates.append(("trafilatura", text))
    except Exception:
        pass

    soup = BeautifulSoup(html, "html.parser")
    # JSON-LD articleBody, when available, is a useful independent candidate.
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
                if isinstance(body, str):
                    body = norm(body)
                    if words(body) >= 80:
                        candidates.append(("jsonld_articleBody", body))
                for v in item.values():
                    if isinstance(v, (dict, list)):
                        stack.append(v)
            elif isinstance(item, list):
                stack.extend(item)

    # Prefer longest candidate; global collision detection below prevents boilerplate
    # from being trusted merely because it is long enough.
    unique = {}
    for method, text in candidates:
        unique.setdefault(sha(text), (method, text))
    vals = sorted(unique.values(), key=lambda x: (words(x[1]), len(x[1])), reverse=True)
    return vals


def fetch_one(url: str):
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-ZA,en;q=0.9"})
    last = ""
    for attempt in range(2):
        try:
            r = s.get(url, timeout=35, allow_redirects=True)
            if r.status_code == 200:
                candidates = extract(r.content, str(r.url))
                if candidates:
                    method, text = candidates[0]
                    return {
                        "url": url, "final_url": str(r.url), "fetch_status": "retrieved_extracted",
                        "fetch_error": "", "method": method, "text": text,
                        "words": words(text), "sha": sha(text), "candidate_extractions": len(candidates),
                    }
                return {
                    "url": url, "final_url": str(r.url), "fetch_status": "retrieved_no_text",
                    "fetch_error": "no_body_ge_80_words", "method": "", "text": "",
                    "words": 0, "sha": "", "candidate_extractions": 0,
                }
            last = f"HTTP {r.status_code}"
            if r.status_code in {401,403,404,410}:
                break
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(attempt + 1)
    return {
        "url": url, "final_url": url, "fetch_status": "fetch_failed", "fetch_error": last or "fetch_failed",
        "method": "", "text": "", "words": 0, "sha": "", "candidate_extractions": 0,
    }


pairs = read_rows(IN)
if len(pairs) != 49:
    raise RuntimeError(f"Expected 49 broad candidate pairs, found {len(pairs)}")

urls = sorted({r[k] for r in pairs for k in ("url_a","url_b") if r.get(k)})
results = {}
with ThreadPoolExecutor(max_workers=6) as pool:
    futs = {pool.submit(fetch_one, u): u for u in urls}
    for fut in as_completed(futs):
        res = fut.result()
        results[res["url"]] = res

# Global fresh-hash collision detection across distinct article titles.
hash_titles = defaultdict(set)
for r in pairs:
    for side in ("a","b"):
        u = r[f"url_{side}"]
        h = results.get(u, {}).get("sha", "")
        if h:
            hash_titles[h].add(title_norm(r[f"title_{side}"]))
collision_hashes = {h for h, ts in hash_titles.items() if len(ts) > 1}

out = []
for r in pairs:
    ra = results.get(r["url_a"], {})
    rb = results.get(r["url_b"], {})
    ta, tb = ra.get("text", ""), rb.get("text", "")
    collision_a = bool(ra.get("sha") and ra.get("sha") in collision_hashes)
    collision_b = bool(rb.get("sha") and rb.get("sha") in collision_hashes)

    if ta and tb and not collision_a and not collision_b:
        seq = SequenceMatcher(None, ta, tb, autojunk=False).ratio()
        tok = jaccard(set(tokens(ta)), set(tokens(tb)))
        sh = jaccard(shingles(ta, 5), shingles(tb, 5))
    else:
        seq = tok = sh = None

    if collision_a or collision_b:
        signal = "extraction_collision_blocks_text_similarity"
    elif not ta or not tb:
        signal = "insufficient_fresh_text"
    elif seq >= 0.98 and sh >= 0.90:
        signal = "very_high_text_similarity_republication_likely"
    elif seq >= 0.93 or sh >= 0.80:
        signal = "high_text_similarity_republication_review"
    elif seq >= 0.75 or sh >= 0.55:
        signal = "moderate_text_similarity_update_or_republication"
    else:
        signal = "low_text_similarity_distinct_supported"

    out.append({
        "record_id_a": r["record_id_a"], "record_id_b": r["record_id_b"],
        "title_a": r["title_a"], "title_b": r["title_b"],
        "url_a": r["url_a"], "url_b": r["url_b"],
        "candidate_signal": r["candidate_signal"],
        "fresh_status_a": ra.get("fetch_status", "not_fetched"), "fresh_status_b": rb.get("fetch_status", "not_fetched"),
        "fresh_words_a": ra.get("words", 0), "fresh_words_b": rb.get("words", 0),
        "fresh_sha256_a": ra.get("sha", ""), "fresh_sha256_b": rb.get("sha", ""),
        "extractor_a": ra.get("method", ""), "extractor_b": rb.get("method", ""),
        "fresh_hash_collision_a": str(collision_a).lower(), "fresh_hash_collision_b": str(collision_b).lower(),
        "sequence_similarity": "" if seq is None else f"{seq:.6f}",
        "token_set_jaccard": "" if tok is None else f"{tok:.6f}",
        "five_word_shingle_jaccard": "" if sh is None else f"{sh:.6f}",
        "text_evidence_signal": signal,
        "final_duplicate_decision": "",
        "final_duplicate_reason": "",
    })

fields = list(out[0].keys())
with OUT.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(out)

summary = {
    "scope": "targeted_full_text_evidence_for_49_broad_near_duplicate_candidates",
    "candidate_pairs": len(pairs),
    "unique_urls_targeted": len(urls),
    "fetch_status_counts": dict(Counter(res.get("fetch_status", "") for res in results.values())),
    "fresh_hash_collision_groups": len(collision_hashes),
    "fresh_hash_collision_hashes": sorted(collision_hashes),
    "text_evidence_signal_counts": dict(Counter(r["text_evidence_signal"] for r in out)),
    "final_duplicate_decisions_made": 0,
    "corpus_frozen": False,
    "important_note": (
        "Fresh article text is not committed. Repeated fresh hashes across distinct titles are treated as extraction collisions and block similarity-based decisions. "
        "All candidate pairs still require explicit review."
    ),
}
SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
