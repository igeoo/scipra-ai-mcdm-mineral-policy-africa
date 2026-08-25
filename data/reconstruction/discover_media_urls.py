"""Discover Marikana-scope media URLs from documented publisher archives.

This is a discovery audit, not a corpus-inclusion script. It probes publisher
sitemaps and search/archive entry points, recursively enumerates sitemap URLs
where available, and writes candidate URLs for later protocol screening.
No stance labels or model outputs are used.
"""
from __future__ import annotations

import csv
import json
import re
import time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "reconstruction" / "discovery"
OUT.mkdir(parents=True, exist_ok=True)

UA = "Mozilla/5.0 (compatible; SCIPRA-Corpus-Discovery/1.0; +https://github.com/Martin-do/scipra-ai-mcdm-mineral-policy-africa)"
HEADERS = {"User-Agent": UA, "Accept-Language": "en-ZA,en;q=0.9"}

PUBLISHERS = {
    "Daily Maverick": {
        "host": "dailymaverick.co.za",
        "sitemaps": [
            "https://www.dailymaverick.co.za/sitemap_index.xml",
            "https://www.dailymaverick.co.za/wp-sitemap.xml",
            "https://www.dailymaverick.co.za/sitemap.xml",
        ],
        "searches": [
            "https://www.dailymaverick.co.za/?s=marikana",
            "https://www.dailymaverick.co.za/?s=lonmin",
        ],
    },
    "Mining Weekly": {
        "host": "miningweekly.com",
        "sitemaps": [
            "https://www.miningweekly.com/sitemap.xml",
            "https://www.miningweekly.com/sitemap_index.xml",
        ],
        "searches": [
            "https://www.miningweekly.com/search?query=marikana",
            "https://www.miningweekly.com/search?query=lonmin",
        ],
    },
    "Engineering News": {
        "host": "engineeringnews.co.za",
        "sitemaps": [
            "https://www.engineeringnews.co.za/sitemap.xml",
            "https://www.engineeringnews.co.za/sitemap_index.xml",
        ],
        "searches": [
            "https://www.engineeringnews.co.za/search?query=marikana",
            "https://www.engineeringnews.co.za/search?query=lonmin",
        ],
    },
}

KEYWORDS = (
    "marikana", "lonmin", "farlam", "sibanye", "amcu", "bapo", "wonderkop",
    "nkaneng", "platinum-strike", "platinum_strike",
)
YEAR_RE = re.compile(r"(?:^|[-_/])(201\d|202[0-3])(?:[-_/]|$)")


def same_host(url: str, expected_host: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == expected_host or host == "www." + expected_host


def candidate_url(url: str) -> bool:
    low = url.lower()
    if not any(k in low for k in KEYWORDS):
        return False
    m = YEAR_RE.search(low)
    if m and 2010 <= int(m.group(1)) <= 2023:
        return True
    # Some article URLs do not encode year in a consistently parseable segment;
    # keep keyword-bearing article paths for later metadata/date screening.
    return "/article/" in low


def fetch(session: requests.Session, url: str):
    try:
        r = session.get(url, timeout=25, allow_redirects=True, headers=HEADERS)
        return r, ""
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def parse_xml_urls(data: bytes) -> tuple[str, list[str]]:
    try:
        root = ET.fromstring(data)
    except Exception:
        return "not_xml", []
    tag = root.tag.rsplit("}", 1)[-1].lower()
    locs = []
    for el in root.iter():
        if el.tag.rsplit("}", 1)[-1].lower() == "loc" and el.text:
            locs.append(el.text.strip())
    if tag == "sitemapindex":
        return "sitemapindex", locs
    if tag == "urlset":
        return "urlset", locs
    return tag, locs


def discover_sitemaps(session, publisher, cfg, audit, found):
    queue = deque((u, 0) for u in cfg["sitemaps"])
    seen = set()
    sitemap_docs = 0
    # Safety ceiling prevents pathological sitemap trees; enough for publisher
    # archive enumeration while preserving a deterministic audit if hit.
    while queue and sitemap_docs < 500:
        url, depth = queue.popleft()
        if url in seen or depth > 3:
            continue
        seen.add(url)
        r, err = fetch(session, url)
        if r is None:
            audit.append([publisher, "sitemap", url, "error", "", err])
            continue
        ctype = r.headers.get("Content-Type", "")
        kind, locs = parse_xml_urls(r.content)
        audit.append([publisher, "sitemap", url, str(r.status_code), kind, f"locs={len(locs)} ctype={ctype}"])
        if r.status_code != 200:
            continue
        sitemap_docs += 1
        if kind == "sitemapindex":
            # Prioritise post/article/news sitemaps but retain other children if
            # the index is modest; this avoids downloading huge media/image maps.
            preferred = [x for x in locs if any(t in x.lower() for t in ("post", "article", "news", "page"))]
            children = preferred or locs
            for child in children[:300]:
                if child not in seen:
                    queue.append((child, depth + 1))
        elif kind == "urlset":
            for item in locs:
                if same_host(item, cfg["host"]) and candidate_url(item):
                    found.add(item)


def discover_search_pages(session, publisher, cfg, audit, found):
    for entry in cfg["searches"]:
        next_url = entry
        seen_pages = set()
        for _ in range(30):
            if not next_url or next_url in seen_pages:
                break
            seen_pages.add(next_url)
            r, err = fetch(session, next_url)
            if r is None:
                audit.append([publisher, "search", next_url, "error", "", err])
                break
            audit.append([publisher, "search", next_url, str(r.status_code), "html", f"bytes={len(r.content)}"])
            if r.status_code != 200:
                break
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                u = urljoin(str(r.url), a["href"])
                if same_host(u, cfg["host"]) and candidate_url(u):
                    found.add(u.split("#", 1)[0])
            # Generic pagination detection. Stop if no explicit next control.
            nxt = soup.find("a", attrs={"rel": lambda v: v and "next" in v})
            if not nxt:
                nxt = soup.find("a", string=re.compile(r"^(next|older|more)\b", re.I))
            next_url = urljoin(str(r.url), nxt["href"]) if nxt and nxt.get("href") else ""
            time.sleep(0.2)


def main() -> int:
    session = requests.Session()
    audit: list[list[str]] = []
    rows: list[dict[str, str]] = []
    summary = {}

    for publisher, cfg in PUBLISHERS.items():
        found: set[str] = set()
        discover_sitemaps(session, publisher, cfg, audit, found)
        discover_search_pages(session, publisher, cfg, audit, found)
        for url in sorted(found):
            rows.append({"publisher": publisher, "url": url, "discovery_status": "unscreened"})
        summary[publisher] = {"candidate_urls": len(found)}

    with (OUT / "media_discovery_urls.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["publisher", "url", "discovery_status"])
        w.writeheader(); w.writerows(rows)
    with (OUT / "media_discovery_endpoint_audit.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["publisher", "method", "endpoint", "http_status", "response_kind", "note"])
        w.writerows(audit)
    summary["total_candidate_urls"] = len(rows)
    (OUT / "media_discovery_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
