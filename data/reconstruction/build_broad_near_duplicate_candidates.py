"""Generate broad metadata-based near-duplicate candidates for the retained SCIPRA corpus.

Input is the 942-row post-explicit duplicate-review manifest. This stage is
EVIDENCE ONLY: it never removes a record. Candidate generation uses normalized
titles, URL slugs, years, publishers and hashes so that only a small subset needs
targeted full-text recovery/similarity review.

Known non-analysis-ready extraction collisions are retained but never treated as
hash evidence for automatic duplication.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "data" / "reconstruction"
IN_MANIFEST = RECON / "cross_phase_post_explicit_manifest.csv"
OUT = RECON / "broad_near_duplicate_candidates.csv"
SUMMARY = RECON / "broad_near_duplicate_candidate_summary.json"
SHA_RX = re.compile(r"^[0-9a-f]{64}$")

CREAMER_HOSTS = {"miningweekly.com", "engineeringnews.co.za"}
STOP = {
    "the","a","an","and","or","of","to","for","in","on","at","as","by","from","with","s","sa","south","africa",
    "article","news","report","update"
}


def read_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def norm_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def tokens(value: str):
    return [t for t in norm_text(value).split() if t and t not in STOP]


def token_jaccard(a: str, b: str) -> float:
    x, y = set(tokens(a)), set(tokens(b))
    if not x or not y:
        return 0.0
    return len(x & y) / len(x | y)


def host(url: str) -> str:
    try:
        return urlsplit(url or "").netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def slug(url: str) -> str:
    try:
        path = urlsplit(url or "").path.strip("/").split("/")[-1]
    except Exception:
        path = ""
    # Strip common YYYY-MM-DD suffix and trailing duplicate suffix.
    path = re.sub(r"-20\d{2}-\d{2}-\d{2}(?:-\d+)?$", "", path)
    return norm_text(path)


def valid_sha(value: str) -> bool:
    return bool(SHA_RX.fullmatch((value or "").strip().lower()))


def sim(a: str, b: str) -> float:
    return SequenceMatcher(None, norm_text(a), norm_text(b), autojunk=False).ratio()


rows = read_rows(IN_MANIFEST)
if len(rows) != 942:
    raise RuntimeError(f"Expected 942 retained records, found {len(rows)}")

prepared = []
for r in rows:
    prepared.append({
        **r,
        "title_norm": norm_text(r.get("title", "")),
        "slug_norm": slug(r.get("url", "")),
        "host": host(r.get("url", "")),
        "ready": str(r.get("analysis_ready", "")).lower() == "true",
    })

# Candidate blocking: compare within same year, plus exact normalized titles across years.
by_year = defaultdict(list)
by_title = defaultdict(list)
for r in prepared:
    by_year[r.get("year", "")].append(r)
    if r["title_norm"]:
        by_title[r["title_norm"]].append(r)

pairs = {}


def consider(a, b, block_reason):
    if a["canonical_record_id"] == b["canonical_record_id"]:
        return
    key = tuple(sorted((a["canonical_record_id"], b["canonical_record_id"])))
    if key in pairs:
        pairs[key]["block_reasons"].add(block_reason)
        return

    title_sim = sim(a["title"], b["title"])
    title_j = token_jaccard(a["title"], b["title"])
    slug_sim = sim(a["slug_norm"], b["slug_norm"]) if a["slug_norm"] and b["slug_norm"] else 0.0
    same_title = a["title_norm"] == b["title_norm"] and bool(a["title_norm"])
    same_hash = (
        a["ready"] and b["ready"] and valid_sha(a.get("text_sha256", "")) and
        a.get("text_sha256") == b.get("text_sha256")
    )
    same_host = a["host"] == b["host"] and bool(a["host"])
    creamer_cross_site = a["host"] in CREAMER_HOSTS and b["host"] in CREAMER_HOSTS

    signal = None
    if same_hash:
        signal = "same_trusted_hash_requires_metadata_review"
    elif same_title:
        signal = "exact_normalised_title"
    elif title_sim >= 0.97 and title_j >= 0.85:
        signal = "very_high_title_similarity"
    elif title_sim >= 0.93 and title_j >= 0.78:
        signal = "high_title_similarity"
    elif slug_sim >= 0.97 and title_j >= 0.65:
        signal = "very_high_slug_similarity"
    elif creamer_cross_site and title_sim >= 0.90 and title_j >= 0.75:
        signal = "creamer_cross_site_high_title_similarity"
    else:
        return

    pairs[key] = {
        "record_id_a": a["canonical_record_id"],
        "record_id_b": b["canonical_record_id"],
        "title_a": a["title"], "title_b": b["title"],
        "year_a": a.get("year", ""), "year_b": b.get("year", ""),
        "publisher_a": a.get("publisher", ""), "publisher_b": b.get("publisher", ""),
        "url_a": a.get("url", ""), "url_b": b.get("url", ""),
        "host_a": a["host"], "host_b": b["host"],
        "analysis_ready_a": str(a["ready"]).lower(), "analysis_ready_b": str(b["ready"]).lower(),
        "text_sha256_a": a.get("text_sha256", ""), "text_sha256_b": b.get("text_sha256", ""),
        "same_trusted_hash": str(same_hash).lower(),
        "same_normalised_title": str(same_title).lower(),
        "title_sequence_similarity": title_sim,
        "title_token_jaccard": title_j,
        "slug_sequence_similarity": slug_sim,
        "same_host": str(same_host).lower(),
        "creamer_cross_site": str(creamer_cross_site).lower(),
        "candidate_signal": signal,
        "block_reasons": {block_reason},
    }

# Same-year comparison, O(n^2) within year blocks only.
for year, group in by_year.items():
    for i in range(len(group)):
        for j in range(i + 1, len(group)):
            consider(group[i], group[j], "same_year")

# Exact title across different years is unusual enough to inspect, but remains evidence-only.
for title, group in by_title.items():
    if len(group) < 2:
        continue
    for i in range(len(group)):
        for j in range(i + 1, len(group)):
            if group[i].get("year") != group[j].get("year"):
                consider(group[i], group[j], "exact_title_cross_year")

out = []
for key, r in pairs.items():
    x = dict(r)
    x["block_reasons"] = ";".join(sorted(x["block_reasons"]))
    x["title_sequence_similarity"] = f"{x['title_sequence_similarity']:.6f}"
    x["title_token_jaccard"] = f"{x['title_token_jaccard']:.6f}"
    x["slug_sequence_similarity"] = f"{x['slug_sequence_similarity']:.6f}"
    x["review_decision"] = "pending_targeted_near_duplicate_review"
    out.append(x)

# Strongest evidence first.
rank = {
    "same_trusted_hash_requires_metadata_review": 0,
    "exact_normalised_title": 1,
    "very_high_title_similarity": 2,
    "very_high_slug_similarity": 3,
    "creamer_cross_site_high_title_similarity": 4,
    "high_title_similarity": 5,
}
out.sort(key=lambda r: (rank.get(r["candidate_signal"], 99), -float(r["title_sequence_similarity"]), r["record_id_a"], r["record_id_b"]))

fields = list(out[0].keys()) if out else ["record_id_a","record_id_b","review_decision"]
with OUT.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader(); w.writerows(out)

summary = {
    "scope": "broad_metadata_near_duplicate_candidate_sweep_after_explicit_duplicate_review",
    "records_scanned": len(rows),
    "analysis_ready_records_scanned": sum(r["ready"] for r in prepared),
    "non_analysis_ready_records_scanned": sum(not r["ready"] for r in prepared),
    "candidate_pairs": len(out),
    "candidate_signal_counts": dict(Counter(r["candidate_signal"] for r in out)),
    "same_year_candidate_pairs": sum("same_year" in r["block_reasons"] for r in out),
    "cross_year_exact_title_candidate_pairs": sum("exact_title_cross_year" in r["block_reasons"] for r in out),
    "final_duplicate_decisions_made": 0,
    "near_duplicate_review_complete": len(out) == 0,
    "corpus_frozen": False,
    "important_note": (
        "This is candidate generation only. No row is removed by title or slug similarity. Candidate pairs require targeted full-text/source review before any additional collapse."
    ),
}
SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
