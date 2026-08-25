"""Protocol-driven acquisition with collision-safe candidate identities.

The historical 87-record seed uses stable IDs. Expansion screening files were
created in several passes and some reuse local IDs such as EXP-MEDIA-001 for
different documents. This wrapper preserves every acquisition candidate by
qualifying colliding expansion IDs with the source-file stem. It does not
silently discard either record; duplicate-content resolution is deferred to the
pre-model corpus-QC stage using URLs and extracted-text hashes.

Archive-discovery records may be acquired while still awaiting substantive
screening. Acquisition is therefore not equivalent to corpus eligibility. For
external-review snapshots only, set SCIPRA_EXCLUDE_DISCOVERY_DIRECT=1 to exclude
the automatically pre-screened archive-discovery queue from acquisition. That
queue remains preserved separately and is never treated as fully screened corpus
membership merely because its text was retrieved.
"""
from __future__ import annotations

import csv
import os
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

import fitz  # PyMuPDF fallback for PDFs whose text layer pypdf cannot read

import acquire_corpus as base

RECON = Path(__file__).resolve().parent
OVERRIDES = RECON / "source_overrides.csv"
DISCOVERY_DIRECT_FILE = "expanded_media_candidates_discovery_direct.csv"

# Force the verified public Farlam mirror instead of the malformed repository PDF.
base.LOCAL_FALLBACKS.pop("INST-001", None)


def eligible(row: dict[str, str]) -> bool:
    """Return whether a row should be acquired, not whether it is in the corpus.

    `candidate_pending_substantive_screen` is intentionally acquisition-eligible
    because full text is needed to make the substantive decision. The status
    itself remains non-eligibility language so acquisition cannot be mistaken for
    an inclusion decision.
    """
    decision = (row.get("decision") or "").strip().lower()
    if decision in {"include", "included", "include_candidate", "eligible"}:
        return True
    status = (row.get("screening_status") or row.get("status") or "").strip().lower()
    return status.startswith("eligible") or status in {
        "candidate_pending_substantive_screen",
        "verified_candidate",
        "verified",
        "include",
        "included",
        "verified_archive",
        "verified_historical_citation",
    }


def expansion_records() -> list[tuple[Path, dict[str, str], str]]:
    records: list[tuple[Path, dict[str, str], str]] = []
    exclude_discovery_direct = os.getenv("SCIPRA_EXCLUDE_DISCOVERY_DIRECT") == "1"
    for path in base.expanded_candidate_files():
        if exclude_discovery_direct and path.name == DISCOVERY_DIRECT_FILE:
            continue
        for row in base.read_csv(path):
            if not eligible(row):
                continue
            raw_id = (row.get("candidate_id") or row.get("recovery_id") or "").strip()
            if raw_id:
                records.append((path, row, raw_id))
    return records


_EXPANSIONS = expansion_records()
_RAW_ID_COUNTS = Counter(raw_id for _, _, raw_id in _EXPANSIONS)


def acquisition_id(path: Path, raw_id: str) -> str:
    """Return stable unique ID; qualify only IDs reused across screening files."""
    if _RAW_ID_COUNTS[raw_id] > 1:
        return f"{path.stem}__{raw_id}"
    return raw_id


def candidate_ids_v3() -> tuple[list[str], int]:
    seed_rows = base.read_csv(RECON / "candidate_corpus_87.csv")
    seed_ids = [(r.get("candidate_doc_id") or "").strip() for r in seed_rows]
    seed_ids = [cid for cid in seed_ids if cid]
    if len(seed_ids) != 87:
        raise RuntimeError(
            "Historical seed file candidate_corpus_87.csv should contain 87 IDs; "
            f"found {len(seed_ids)}"
        )

    ids = list(seed_ids)
    ids.extend(acquisition_id(path, raw_id) for path, _, raw_id in _EXPANSIONS)

    if len(set(ids)) != len(ids):
        dupes = [cid for cid, n in Counter(ids).items() if n > 1]
        raise RuntimeError(f"Duplicate acquisition IDs remain after qualification: {dupes}")
    return ids, len(seed_ids)


def build_lookup_v3() -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}

    for row in base.read_csv(RECON / "retrieval_manifest.csv"):
        cid = (row.get("recovery_id") or "").strip()
        if cid:
            lookup[cid] = {
                "candidate_id": cid,
                "raw_candidate_id": cid,
                "title": row.get("title", ""),
                "year": row.get("year", ""),
                "publisher": row.get("publisher", ""),
                "url": row.get("url", ""),
                "source": "retrieval_manifest",
            }

    for row in base.read_csv(RECON / "institutional_replacement_candidates.csv"):
        cid = (row.get("candidate_id") or "").strip()
        if cid:
            lookup[cid] = {
                "candidate_id": cid,
                "raw_candidate_id": cid,
                "title": row.get("document_title", ""),
                "year": row.get("year", ""),
                "publisher": row.get("party_or_source", ""),
                "url": row.get("url", ""),
                "source": "institutional_replacement_candidates",
            }

    for path, row, raw_id in _EXPANSIONS:
        cid = acquisition_id(path, raw_id)
        lookup[cid] = {
            "candidate_id": cid,
            "raw_candidate_id": raw_id,
            "title": row.get("title", ""),
            "year": row.get("year", ""),
            "publisher": row.get("publisher", ""),
            "url": row.get("url", ""),
            "source": path.name,
        }

    # Transparent URL/source overrides. Qualified acquisition IDs may be used
    # directly when the same raw ID appears in more than one screening file.
    if OVERRIDES.exists():
        with OVERRIDES.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                raw_id = (row.get("candidate_id") or "").strip()
                title = (row.get("title") or "").strip()
                targets = []
                if raw_id in lookup:
                    targets.append(raw_id)
                targets.extend(
                    key for key, meta in lookup.items()
                    if key != raw_id
                    and meta.get("raw_candidate_id") == raw_id
                    and (not title or meta.get("title") == title)
                )
                if len(targets) == 1:
                    key = targets[0]
                    lookup[key].update({
                        "title": row.get("title", lookup[key].get("title", "")),
                        "year": row.get("year", lookup[key].get("year", "")),
                        "publisher": row.get("publisher", lookup[key].get("publisher", "")),
                        "url": row.get("url", lookup[key].get("url", "")),
                        "source": "source_overrides",
                    })

    return lookup


def bounded_fetch(session, url: str, attempts: int = 2):
    """Bound failure latency and handle Sibanye report-site hot-link controls."""
    last = ""
    parsed = urlsplit(url)
    is_sibanye_report_asset = (
        parsed.hostname == "reports.sibanyestillwater.com"
        and ("/download/" in parsed.path or "/downloads/" in parsed.path)
    )

    if is_sibanye_report_asset:
        match = re.search(r"/(20\d{2})/", parsed.path)
        if match:
            parent = f"https://reports.sibanyestillwater.com/{match.group(1)}/"
            try:
                session.get(parent, timeout=30, allow_redirects=True)
                response = session.get(
                    url,
                    timeout=30,
                    allow_redirects=True,
                    headers={
                        "Referer": parent,
                        "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.5",
                    },
                )
                ctype = response.headers.get("Content-Type", "").lower()
                # The host sometimes returns a ~212 byte HTML hot-link stub with
                # HTTP 200. Only accept a response that looks like the real asset.
                if response.status_code == 200 and (
                    response.content[:4] == b"%PDF" or
                    ("application/pdf" in ctype and len(response.content) > 1024)
                ):
                    return response, ""
                last = f"sibanye_hotlink_stub_or_http_{response.status_code}"
            except Exception as exc:
                last = f"sibanye_warmup_{type(exc).__name__}: {exc}"

    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, timeout=30, allow_redirects=True)
            if response.status_code == 200:
                return response, ""
            last = f"HTTP {response.status_code}"
            if response.status_code in {401, 403, 404, 410}:
                return response, last
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
        base.time.sleep(attempt * 2)
    return None, last


_pypdf_extract = base.extract_pdf


def extract_pdf_with_fallback(data: bytes):
    """Use PyMuPDF only when pypdf yields no useful text; no OCR is performed."""
    text, pages, method = _pypdf_extract(data)
    if len(text.strip()) >= 500:
        return text, pages, method
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        alt = base.normalise_space("\n\n".join(page.get_text("text") or "" for page in doc))
        if len(alt.strip()) > len(text.strip()):
            return alt, len(doc), "pymupdf_fallback"
    except Exception:
        pass
    return text, pages, method


base.row_is_eligible = eligible
base.candidate_ids = candidate_ids_v3
base.build_lookup = build_lookup_v3
base.fetch = bounded_fetch
base.extract_pdf = extract_pdf_with_fallback

if __name__ == "__main__":
    raise SystemExit(base.main())
