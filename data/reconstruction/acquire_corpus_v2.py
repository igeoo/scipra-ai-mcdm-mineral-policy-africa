"""Second-pass acquisition using transparent source overrides.

This wrapper leaves the first-pass acquisition tool unchanged for auditability.
It removes the malformed local Farlam fallback, applies the pre-label source
replacement decisions recorded in source_overrides.csv, and treats explicit
`include_candidate` screening decisions as eligible for acquisition.
"""
from __future__ import annotations

import csv
from pathlib import Path

import acquire_corpus as base

RECON = Path(__file__).resolve().parent
OVERRIDES = RECON / "source_overrides.csv"

# The repository's Farlam PDF is malformed for pypdf extraction. Force the
# verified public mirror recorded in source_overrides.csv instead.
base.LOCAL_FALLBACKS.pop("INST-001", None)

_original_build_lookup = base.build_lookup
_original_row_is_eligible = base.row_is_eligible


def row_is_eligible_with_decision(row: dict[str, str]) -> bool:
    """Accept prospective include decisions in addition to legacy status labels."""
    decision = (row.get("decision") or "").strip().lower()
    if decision in {"include", "included", "include_candidate", "eligible"}:
        return True
    return _original_row_is_eligible(row)


def build_lookup_with_overrides():
    lookup = _original_build_lookup()
    with OVERRIDES.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            cid = row["candidate_id"].strip()
            lookup[cid] = {
                "candidate_id": cid,
                "title": row.get("title", ""),
                "year": row.get("year", ""),
                "publisher": row.get("publisher", ""),
                "url": row.get("url", ""),
                "source": "source_overrides",
            }
    return lookup


base.row_is_eligible = row_is_eligible_with_decision
base.build_lookup = build_lookup_with_overrides

if __name__ == "__main__":
    raise SystemExit(base.main())
