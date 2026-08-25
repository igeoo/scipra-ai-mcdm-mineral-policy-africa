from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "data" / "reconstruction"
DISC = RECON / "discovery"
INFILE = DISC / "media_discovery_urls.csv"
AUDIT = DISC / "media_discovery_prescreen.csv"
DIRECT = RECON / "expanded_media_candidates_discovery_direct.csv"
SUMMARY = DISC / "media_discovery_prescreen_summary.json"

# Title/URL matching is only a discovery triage. It must never imply substantive
# corpus eligibility. High-specificity Marikana terms are separated from
# Lonmin-only matches because a company-name hit can be a generic corporate or
# financial story with no substantive Marikana relevance.
CASE_SPECIFIC = re.compile(r"(?:marikana|farlam|nkaneng|wonderkop|bapo(?:-ba-mogale)?)", re.I)
LONMIN = re.compile(r"lonmin", re.I)
DATE_DM = re.compile(r"/(?:article|opinionista)/(20\d{2})-(\d{2})-(\d{2})-")
DATE_SUFFIX = re.compile(r"-(20\d{2})-(\d{2})-(\d{2})(?:-|/?$)")


def read_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def canon(url: str) -> str:
    p = urlsplit((url or "").strip())
    host = p.netloc.lower().removeprefix("www.")
    path = re.sub(r"/+", "/", p.path).rstrip("/")
    return urlunsplit(("https", host, path, "", ""))


def known_urls() -> set[str]:
    urls: set[str] = set()
    for path in [RECON / "retrieval_manifest.csv", RECON / "institutional_replacement_candidates.csv"]:
        if not path.exists():
            continue
        for r in read_rows(path):
            u = r.get("url") or ""
            if u:
                urls.add(canon(u))
    for path in RECON.glob("expanded_*_candidates*.csv"):
        if path.name == DIRECT.name:
            continue
        for r in read_rows(path):
            u = r.get("url") or ""
            if u:
                urls.add(canon(u))
    return urls


def year_from_url(url: str) -> str:
    m = DATE_DM.search(url) or DATE_SUFFIX.search(url)
    return m.group(1) if m else ""


def slug_title(url: str) -> str:
    slug = urlsplit(url).path.rstrip("/").split("/")[-1]
    slug = re.sub(r"^20\d{2}-\d{2}-\d{2}-", "", slug)
    slug = re.sub(r"-20\d{2}-\d{2}-\d{2}(?:-\d+)?$", "", slug)
    return re.sub(r"[-_]+", " ", slug).strip().title()


known = known_urls()
audit = []
direct = []
counts = Counter()
pub_counts = Counter()
seen_new = set()

for idx, row in enumerate(read_rows(INFILE), 1):
    publisher = row.get("publisher", "")
    url = row.get("url", "")
    cu = canon(url)
    year = year_from_url(url)
    path_text = urlsplit(url).path.lower()

    if cu in known:
        status = "already_screened"
    elif cu in seen_new:
        status = "duplicate_discovery_url"
    elif year and not (2010 <= int(year) <= 2023):
        status = "exclude_outside_period"
    elif not year:
        status = "review_year_unresolved"
    elif CASE_SPECIFIC.search(path_text):
        status = "explicit_case_title_review"
    elif LONMIN.search(path_text):
        status = "lonmin_only_title_review"
    else:
        status = "secondary_keyword_only_review"

    seen_new.add(cu)
    counts[status] += 1
    pub_counts[(publisher, status)] += 1
    audit.append({
        "publisher": publisher,
        "url": url,
        "canonical_url": cu,
        "year": year,
        "prescreen_status": status,
    })

    if status in {"explicit_case_title_review", "lonmin_only_title_review"}:
        cid = f"DISC-MEDIA-{len(direct)+1:04d}"
        if status == "explicit_case_title_review":
            reason = (
                "Discovered from a documented publisher archive/sitemap and the URL title contains a "
                "high-specificity case term (Marikana/Farlam/Nkaneng/Wonderkop/Bapo). This is a review "
                "trigger only; substantive corpus eligibility still requires acquired-text case-centrality, "
                "text-quality and duplicate review."
            )
        else:
            reason = (
                "Discovered from a documented publisher archive/sitemap and the URL title contains Lonmin "
                "without a high-specificity Marikana case term. Lonmin-only matches can be unrelated corporate "
                "or financial stories, so this record is not provisionally eligible and requires acquired-text "
                "substantive screening before any inclusion decision."
            )
        direct.append({
            "candidate_id": cid,
            "source_family": "media",
            "title": slug_title(url),
            "year": year,
            "publisher": publisher,
            "url": url,
            "screening_status": "candidate_pending_substantive_screen",
            "prescreen_bucket": status,
            "decision_reason": reason,
            "search_id": "SEARCH-MEDIA-ARCHIVE-PRESCREEN",
            "source_universe": "strict_documented",
        })

AUDIT.parent.mkdir(parents=True, exist_ok=True)
with AUDIT.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=audit[0].keys())
    w.writeheader()
    w.writerows(audit)

with DIRECT.open("w", encoding="utf-8", newline="") as f:
    fields = [
        "candidate_id",
        "source_family",
        "title",
        "year",
        "publisher",
        "url",
        "screening_status",
        "prescreen_bucket",
        "decision_reason",
        "search_id",
        "source_universe",
    ]
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(direct)

summary = {
    "discovered_urls": len(audit),
    "status_counts": dict(counts),
    # Backward-compatible count name for existing handoff builders. This now
    # means title-trigger review candidates, not substantively eligible records.
    "direct_case_new_candidates": len(direct),
    "title_trigger_review_candidates": len(direct),
    "explicit_case_title_review_candidates": counts.get("explicit_case_title_review", 0),
    "lonmin_only_title_review_candidates": counts.get("lonmin_only_title_review", 0),
    "publisher_status_counts": {f"{p}::{s}": n for (p, s), n in sorted(pub_counts.items())},
    "note": (
        "Automated title/URL pre-screen only. No title match confers corpus eligibility. "
        "High-specificity case-title and Lonmin-only matches are preserved for acquired-text substantive "
        "screening; secondary-keyword URLs are preserved for reviewer screening and are not silently excluded."
    ),
}
SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
