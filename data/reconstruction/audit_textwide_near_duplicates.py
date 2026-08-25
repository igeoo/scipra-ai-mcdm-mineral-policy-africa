"""Final textwide near-duplicate evidence audit for the SCIPRA pre-freeze corpus.

Re-fetches the 883 currently analysis-ready retained records, extracts text in
runner memory, and computes TF-IDF cosine similarity across all successfully
recovered non-collision texts. No article/PDF text is committed.

The output is evidence-only. No corpus row is removed automatically. This audit
exists to catch near-duplicates with dissimilar titles that metadata blocking may
have missed.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlsplit

import requests
import trafilatura
from bs4 import BeautifulSoup
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "data" / "reconstruction"
MANIFEST = RECON / "prefreeze_manifest_after_broad_duplicate_review.csv"
STATUS_OUT = RECON / "textwide_recovery_status.csv"
PAIRS_OUT = RECON / "textwide_near_duplicate_candidates.csv"
SUMMARY = RECON / "textwide_near_duplicate_summary.json"
UA = "Mozilla/5.0 (compatible; SCIPRA-Reproducibility-Audit/1.4; +https://github.com/Martin-do/scipra-ai-mcdm-mineral-policy-africa)"


def read_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\x00", " ")).strip()


def title_norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def text_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""


def html_candidates(data: bytes, url: str):
    html = data.decode("utf-8", errors="replace")
    out = []
    try:
        t = trafilatura.extract(
            html, url=url, include_comments=False, include_tables=False,
            favor_precision=True, no_fallback=False
        )
        t = norm(t or "")
        if word_count(t) >= 80:
            out.append(("trafilatura", t))
    except Exception:
        pass

    soup = BeautifulSoup(html, "html.parser")
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
                    if word_count(body) >= 80:
                        out.append(("jsonld_articleBody", body))
                for v in item.values():
                    if isinstance(v, (dict, list)):
                        stack.append(v)
            elif isinstance(item, list):
                stack.extend(item)

    uniq = {}
    for method, text in out:
        uniq.setdefault(text_sha(text), (method, text))
    return sorted(uniq.values(), key=lambda x: (word_count(x[1]), len(x[1])), reverse=True)


def extract_pdf(data: bytes):
    try:
        reader = PdfReader(io.BytesIO(data))
        parts = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
        text = norm("\n".join(parts))
        if word_count(text) >= 80:
            return "pypdf", text
    except Exception:
        pass
    return "", ""


def fetch_one(row: dict):
    url = row.get("url", "")
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-ZA,en;q=0.9"})
    last = ""
    for attempt in range(2):
        try:
            r = s.get(url, timeout=45, allow_redirects=True)
            if r.status_code == 200:
                ctype = (r.headers.get("content-type") or "").lower()
                path = urlsplit(str(r.url)).path.lower()
                if "application/pdf" in ctype or path.endswith(".pdf") or r.content[:5] == b"%PDF-":
                    method, text = extract_pdf(r.content)
                    candidates = [(method, text)] if text else []
                else:
                    candidates = html_candidates(r.content, str(r.url))
                if candidates:
                    method, text = candidates[0]
                    return {
                        "record_id": row["canonical_record_id"], "url": url, "final_url": str(r.url),
                        "status": "retrieved_extracted", "error": "", "method": method,
                        "text": text, "words": word_count(text), "sha": text_sha(text),
                    }
                return {
                    "record_id": row["canonical_record_id"], "url": url, "final_url": str(r.url),
                    "status": "retrieved_no_text", "error": "no_body_ge_80_words", "method": "",
                    "text": "", "words": 0, "sha": "",
                }
            last = f"HTTP {r.status_code}"
            if r.status_code in {401,403,404,410}:
                break
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(attempt + 1)
    return {
        "record_id": row["canonical_record_id"], "url": url, "final_url": url,
        "status": "fetch_failed", "error": last or "fetch_failed", "method": "",
        "text": "", "words": 0, "sha": "",
    }


manifest_all = read_rows(MANIFEST)
if len(manifest_all) != 893:
    raise RuntimeError(f"Expected 893 retained records, found {len(manifest_all)}")
manifest = [r for r in manifest_all if str(r.get("analysis_ready", "")).lower() == "true"]
if len(manifest) != 883:
    raise RuntimeError(f"Expected 883 analysis-ready records, found {len(manifest)}")
by_id = {r["canonical_record_id"]: r for r in manifest}

results = {}
with ThreadPoolExecutor(max_workers=8) as pool:
    futs = {pool.submit(fetch_one, r): r["canonical_record_id"] for r in manifest}
    for fut in as_completed(futs):
        res = fut.result()
        results[res["record_id"]] = res

# Detect genuinely suspicious extractor hash reuse: the same fresh payload across
# >=3 records whose titles are not all near-identical. Pair-local same hashes are
# legitimate duplicate evidence and are not treated as global collisions.
hash_ids = defaultdict(list)
for rid, res in results.items():
    if res.get("sha"):
        hash_ids[res["sha"]].append(rid)
collision_hashes = set()
for h, ids in hash_ids.items():
    if len(ids) < 3:
        continue
    titles = [title_norm(by_id[rid].get("title", "")) for rid in ids]
    min_sim = 1.0
    for i in range(len(titles)):
        for j in range(i+1, len(titles)):
            min_sim = min(min_sim, SequenceMatcher(None, titles[i], titles[j], autojunk=False).ratio())
    if min_sim < 0.75:
        collision_hashes.add(h)

status_rows = []
good_ids = []
good_texts = []
for r in manifest:
    rid = r["canonical_record_id"]
    res = results[rid]
    collision = bool(res.get("sha") and res["sha"] in collision_hashes)
    usable = res.get("status") == "retrieved_extracted" and res.get("words", 0) >= 80 and not collision
    status_rows.append({
        "record_id": rid, "source_phase": r.get("source_phase", ""), "title": r.get("title", ""),
        "year": r.get("year", ""), "publisher": r.get("publisher", ""), "url": r.get("url", ""),
        "fetch_status": res.get("status", ""), "fetch_error": res.get("error", ""),
        "extraction_method": res.get("method", ""), "fresh_words": res.get("words", 0),
        "fresh_sha256": res.get("sha", ""), "global_extraction_collision": str(collision).lower(),
        "usable_for_textwide_similarity": str(usable).lower(),
    })
    if usable:
        good_ids.append(rid)
        good_texts.append(res["text"])

status_fields = list(status_rows[0].keys())
with STATUS_OUT.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=status_fields); w.writeheader(); w.writerows(status_rows)

pair_rows = []
if len(good_texts) >= 2:
    vectorizer = TfidfVectorizer(
        lowercase=True, strip_accents="unicode", stop_words="english",
        ngram_range=(1,2), min_df=1, max_df=1.0, sublinear_tf=True,
        max_features=100000, dtype="float32"
    )
    X = vectorizer.fit_transform(good_texts)
    S = cosine_similarity(X, dense_output=False).tocoo()
    for i, j, score in zip(S.row, S.col, S.data):
        if i >= j or score < 0.92:
            continue
        a_id, b_id = good_ids[i], good_ids[j]
        a, b = by_id[a_id], by_id[b_id]
        same_fresh_hash = results[a_id].get("sha") and results[a_id].get("sha") == results[b_id].get("sha")
        title_sim = SequenceMatcher(None, title_norm(a.get("title", "")), title_norm(b.get("title", "")), autojunk=False).ratio()
        signal = "near_duplicate_ge_0_95" if score >= 0.95 else "watch_0_92_to_0_95"
        pair_rows.append({
            "record_id_a": a_id, "record_id_b": b_id,
            "source_phase_a": a.get("source_phase", ""), "source_phase_b": b.get("source_phase", ""),
            "title_a": a.get("title", ""), "title_b": b.get("title", ""),
            "year_a": a.get("year", ""), "year_b": b.get("year", ""),
            "publisher_a": a.get("publisher", ""), "publisher_b": b.get("publisher", ""),
            "url_a": a.get("url", ""), "url_b": b.get("url", ""),
            "tfidf_cosine_similarity": f"{float(score):.6f}",
            "same_fresh_text_sha256": str(bool(same_fresh_hash)).lower(),
            "title_sequence_similarity": f"{title_sim:.6f}",
            "review_signal": signal,
            "final_duplicate_decision": "",
            "final_duplicate_reason": "",
        })

pair_rows.sort(key=lambda r: (-float(r["tfidf_cosine_similarity"]), r["record_id_a"], r["record_id_b"]))
pair_fields = [
    "record_id_a","record_id_b","source_phase_a","source_phase_b","title_a","title_b","year_a","year_b",
    "publisher_a","publisher_b","url_a","url_b","tfidf_cosine_similarity","same_fresh_text_sha256",
    "title_sequence_similarity","review_signal","final_duplicate_decision","final_duplicate_reason"
]
with PAIRS_OUT.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=pair_fields); w.writeheader(); w.writerows(pair_rows)

status_counts = Counter(r["fetch_status"] for r in status_rows)
method_counts = Counter(r["extraction_method"] for r in status_rows if r["extraction_method"])
summary = {
    "scope": "final_textwide_near_duplicate_evidence_audit_for_analysis_ready_prefreeze_corpus",
    "retained_manifest_records": len(manifest_all),
    "analysis_ready_records_targeted": len(manifest),
    "fresh_recovery_status_counts": dict(status_counts),
    "fresh_extraction_method_counts": dict(method_counts),
    "global_extraction_collision_groups": len(collision_hashes),
    "records_usable_for_textwide_similarity": len(good_ids),
    "records_not_usable_for_textwide_similarity": len(manifest) - len(good_ids),
    "candidate_pairs_ge_0_92": len(pair_rows),
    "near_duplicate_pairs_ge_0_95": sum(r["review_signal"] == "near_duplicate_ge_0_95" for r in pair_rows),
    "watch_pairs_0_92_to_0_95": sum(r["review_signal"] == "watch_0_92_to_0_95" for r in pair_rows),
    "final_duplicate_decisions_made": 0,
    "textwide_review_complete": False,
    "corpus_frozen": False,
    "important_note": (
        "This is an evidence audit only. It uses fresh extraction solely to identify near-duplicate candidates; no full text is committed. "
        "Any >=0.92 pair requires explicit source/content review. Failed or unusable fresh recoveries are reported and prevent claiming complete textwide coverage until reconciled against prior QC/provenance."
    ),
}
SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
