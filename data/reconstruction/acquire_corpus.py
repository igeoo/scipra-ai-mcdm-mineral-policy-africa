from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import time
from pathlib import Path
from typing import Dict, Optional

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
import trafilatura

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "data" / "reconstruction"
OUT = ROOT / "acquisition_output"
RAW_OUT = OUT / "raw"
TEXT_OUT = OUT / "text"

USER_AGENT = (
    "Mozilla/5.0 (compatible; SCIPRA-Reproducibility-Acquisition/1.1; "
    "+https://github.com/Martin-do/scipra-ai-mcdm-mineral-policy-africa)"
)

LOCAL_FALLBACKS = {
    "INST-001": ROOT / "data" / "raw" / "Farlam_Commission_Report.pdf",
    "INST-002": ROOT / "data" / "raw" / "Bench_Marks_PG6.pdf",
    "INST-003": ROOT / "data" / "raw" / "CER_Zero_Hour.pdf",
    "INST-004": ROOT / "data" / "raw" / "Bench_Marks_PG10.pdf",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def expanded_candidate_files() -> list[Path]:
    """Return protocol-driven expansion files in deterministic name order."""
    return sorted(RECON.glob("expanded_*_candidates*.csv"))


def row_is_eligible(row: dict[str, str]) -> bool:
    status = (row.get("screening_status") or row.get("status") or "").strip().lower()
    return status.startswith("eligible") or status in {
        "verified_candidate",
        "verified",
        "include",
        "included",
    }


def normalise_space(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pdf(data: bytes) -> tuple[str, int, str]:
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                pages.append("")
        return normalise_space("\n\n".join(pages)), len(reader.pages), "pypdf"
    except Exception as exc:
        return "", 0, f"pypdf_error:{type(exc).__name__}"


def extract_html(data: bytes, url: str) -> tuple[str, str]:
    html = data.decode("utf-8", errors="replace")
    try:
        text = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
            no_fallback=False,
        )
        if text and len(text.strip()) >= 200:
            return normalise_space(text), "trafilatura"
    except Exception:
        pass

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "form"]):
        tag.decompose()
    container = soup.find("article") or soup.find("main") or soup.body or soup
    paras = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    text = normalise_space("\n\n".join(p for p in paras if p))
    return text, "beautifulsoup_fallback"


def build_lookup() -> Dict[str, dict[str, str]]:
    lookup: Dict[str, dict[str, str]] = {}

    for row in read_csv(RECON / "retrieval_manifest.csv"):
        rid = (row.get("recovery_id") or "").strip()
        if not rid:
            continue
        lookup[rid] = {
            "candidate_id": rid,
            "title": row.get("title", ""),
            "year": row.get("year", ""),
            "publisher": row.get("publisher", ""),
            "url": row.get("url", ""),
            "source": "retrieval_manifest",
        }

    for row in read_csv(RECON / "institutional_replacement_candidates.csv"):
        rid = (row.get("candidate_id") or "").strip()
        if not rid:
            continue
        lookup[rid] = {
            "candidate_id": rid,
            "title": row.get("document_title", ""),
            "year": row.get("year", ""),
            "publisher": row.get("party_or_source", ""),
            "url": row.get("url", ""),
            "source": "institutional_replacement_candidates",
        }

    # Expansion files are screened before acquisition. Only rows whose screening
    # status is explicitly eligible enter the acquisition set; excluded mirrors
    # and rejected records remain in the retrieval log but are not fetched as
    # independent corpus members.
    for path in expanded_candidate_files():
        for row in read_csv(path):
            if not row_is_eligible(row):
                continue
            cid = (row.get("candidate_id") or row.get("recovery_id") or "").strip()
            if not cid:
                continue
            lookup[cid] = {
                "candidate_id": cid,
                "title": row.get("title", ""),
                "year": row.get("year", ""),
                "publisher": row.get("publisher", ""),
                "url": row.get("url", ""),
                "source": path.name,
            }

    return lookup


def candidate_ids() -> tuple[list[str], int]:
    """Return seed + all screened eligible expansion IDs.

    The historical 87-record list is retained as a seed benchmark only. Final
    acquisition N is protocol-driven and may exceed 87.
    """
    seed_rows = read_csv(RECON / "candidate_corpus_87.csv")
    seed_ids = [(r.get("candidate_doc_id") or "").strip() for r in seed_rows]
    seed_ids = [x for x in seed_ids if x]
    if len(seed_ids) != 87:
        raise RuntimeError(
            "Historical seed file candidate_corpus_87.csv should contain 87 IDs; "
            f"found {len(seed_ids)}"
        )

    ids = list(seed_ids)
    for path in expanded_candidate_files():
        for row in read_csv(path):
            if not row_is_eligible(row):
                continue
            cid = (row.get("candidate_id") or row.get("recovery_id") or "").strip()
            if cid:
                ids.append(cid)

    if len(set(ids)) != len(ids):
        seen: set[str] = set()
        dupes: list[str] = []
        for cid in ids:
            if cid in seen and cid not in dupes:
                dupes.append(cid)
            seen.add(cid)
        raise RuntimeError(f"Duplicate acquisition candidate IDs: {dupes}")

    return ids, len(seed_ids)


def fetch(session: requests.Session, url: str, attempts: int = 3) -> tuple[Optional[requests.Response], str]:
    last = ""
    for attempt in range(1, attempts + 1):
        try:
            r = session.get(url, timeout=60, allow_redirects=True)
            if r.status_code == 200:
                return r, ""
            last = f"HTTP {r.status_code}"
            if r.status_code in {401, 403, 404, 410}:
                return r, last
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(attempt * 2)
    return None, last


def main() -> int:
    OUT.mkdir(exist_ok=True)
    RAW_OUT.mkdir(parents=True, exist_ok=True)
    TEXT_OUT.mkdir(parents=True, exist_ok=True)

    ids, seed_count = candidate_ids()
    lookup = build_lookup()
    total = len(ids)

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})

    status_rows: list[dict[str, object]] = []

    for idx, cid in enumerate(ids, 1):
        meta = lookup.get(cid, {})
        url = str(meta.get("url", "") or "").strip()
        title = str(meta.get("title", "") or "")
        publisher = str(meta.get("publisher", "") or "")
        year = str(meta.get("year", "") or "")

        print(f"[{idx:03d}/{total}] {cid} {publisher} {title[:70]}", flush=True)

        raw: bytes | None = None
        content_type = ""
        final_url = url
        http_status = ""
        retrieval_method = ""
        error = ""

        local_path = LOCAL_FALLBACKS.get(cid)
        if local_path and local_path.exists():
            raw = local_path.read_bytes()
            content_type = "application/pdf"
            final_url = url
            http_status = "local"
            retrieval_method = f"repo_fallback:{local_path.relative_to(ROOT)}"
        elif not url:
            error = "missing_url_and_no_local_fallback"
        else:
            response, fetch_error = fetch(session, url)
            if response is not None:
                http_status = str(response.status_code)
                final_url = str(response.url)
                content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
                if response.status_code == 200:
                    raw = response.content
                    retrieval_method = "http"
                else:
                    error = fetch_error
            else:
                error = fetch_error or "fetch_failed"

        text = ""
        extraction_method = ""
        pages = ""
        raw_sha = ""
        text_sha = ""
        raw_bytes = 0

        if raw is not None:
            raw_bytes = len(raw)
            raw_sha = sha256_bytes(raw)
            is_pdf = (
                content_type == "application/pdf"
                or final_url.lower().split("?")[0].endswith(".pdf")
                or raw[:4] == b"%PDF"
            )
            if is_pdf:
                raw_path = RAW_OUT / f"{cid}.pdf"
                raw_path.write_bytes(raw)
                text, page_count, extraction_method = extract_pdf(raw)
                pages = str(page_count)
            else:
                raw_path = RAW_OUT / f"{cid}.html"
                raw_path.write_bytes(raw)
                text, extraction_method = extract_html(raw, final_url)

            if text:
                text_path = TEXT_OUT / f"{cid}.txt"
                text_path.write_text(text, encoding="utf-8")
                text_sha = sha256_text(text)

        text_chars = len(text)
        text_words = len(re.findall(r"\b\w+\b", text)) if text else 0

        if raw is None:
            status = "failed"
        elif text_chars >= 500:
            status = "acquired_extracted"
        elif text_chars > 0:
            status = "acquired_low_text"
        else:
            status = "acquired_no_text"

        status_rows.append({
            "candidate_id": cid,
            "status": status,
            "title": title,
            "year": year,
            "publisher": publisher,
            "metadata_source": meta.get("source", ""),
            "source_url": url,
            "final_url": final_url,
            "http_status": http_status,
            "content_type": content_type,
            "retrieval_method": retrieval_method,
            "raw_bytes": raw_bytes,
            "raw_sha256": raw_sha,
            "extraction_method": extraction_method,
            "pages": pages,
            "text_chars": text_chars,
            "text_words": text_words,
            "text_sha256": text_sha,
            "error": error,
        })

    fieldnames = list(status_rows[0].keys())
    with (OUT / "acquisition_status.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(status_rows)

    counts: dict[str, int] = {}
    for row in status_rows:
        counts[str(row["status"])] = counts.get(str(row["status"]), 0) + 1

    summary = {
        "historical_seed_benchmark": seed_count,
        "eligible_expansion_candidates": total - seed_count,
        "processed_candidates": len(status_rows),
        "status_counts": counts,
        "total_raw_bytes": sum(int(r["raw_bytes"]) for r in status_rows),
        "total_text_words": sum(int(r["text_words"]) for r in status_rows),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))

    # Acquisition is an audit pass: partial failures do not fail the workflow.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
