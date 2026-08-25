"""Build the final SCIPRA corpus-freeze audit handoff.

The handoff is a derived review package. It contains membership manifests,
hashes, screening summaries, duplicate/recovery decisions, and a reviewer-facing
protocol. It does not contain redistributed full media article text.
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "data" / "reconstruction"
HANDOFF = RECON / "review_handoff"
ZIP_OUT = RECON / "scipra_corpus_freeze_handoff.zip"
OLD_ZIP = RECON / "scipra_external_review_handoff.zip"

FREEZE = RECON / "corpus_freeze_summary.json"
HASHES = RECON / "corpus_freeze_hashes.json"
CANONICAL = RECON / "canonical_reconstructed_replication_corpus.csv"
ANALYSIS = RECON / "canonical_analysis_ready_manifest.csv"

COPY_FILES = [
    "corpus_freeze_summary.json",
    "corpus_freeze_hashes.json",
    "canonical_reconstructed_replication_corpus.csv",
    "canonical_analysis_ready_manifest.csv",
    "textwide_near_duplicate_final_decisions.csv",
    "textwide_recovery_reconciliation.csv",
    "textwide_near_duplicate_summary.json",
    "media_substantive_decision_summary.json",
    "secondary_media_substantive_decision_summary.json",
    "broad_near_duplicate_final_summary.json",
    "cross_phase_post_explicit_summary.json",
    "archive_media_post_titlepair_summary.json",
]

EITI_CAVEAT = (
    "The reported set of 13 South Africa EITI documents cannot presently be "
    "independently recovered or validated as described in the original corpus documentation."
)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def sha256(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


freeze = read_json(FREEZE)
hashes = read_json(HASHES)
if freeze.get("corpus_frozen") is not True:
    raise RuntimeError("Refusing to build freeze handoff before corpus_frozen=true")
if freeze.get("reconstructed_corpus_records") != 886 or freeze.get("analysis_ready_records") != 876:
    raise RuntimeError("Unexpected frozen corpus counts")
if freeze.get("retained_non_analysis_ready_quality_exceptions") != 10:
    raise RuntimeError("Expected 10 retained quality exceptions")
if freeze.get("eiti_provenance_caveat") != EITI_CAVEAT:
    raise RuntimeError("EITI provenance caveat drifted")

# Verify the two central manifests against the committed freeze hashes before packaging.
if sha256(CANONICAL) != hashes.get("canonical_reconstructed_replication_corpus.csv"):
    raise RuntimeError("Canonical frozen corpus hash mismatch")
if sha256(ANALYSIS) != hashes.get("canonical_analysis_ready_manifest.csv"):
    raise RuntimeError("Analysis-ready manifest hash mismatch")

canonical_rows = read_csv(CANONICAL)
analysis_rows = read_csv(ANALYSIS)
if len(canonical_rows) != 886 or len(analysis_rows) != 876:
    raise RuntimeError("Frozen manifest row counts do not match freeze summary")
quality = [r for r in canonical_rows if str(r.get("analysis_ready", "")).lower() != "true"]
if len(quality) != 10:
    raise RuntimeError("Quality-exception extraction did not yield 10 rows")

# The handoff is derived and may be replaced wholesale; the underlying provenance
# remains in data/reconstruction outside this directory.
if HANDOFF.exists():
    shutil.rmtree(HANDOFF)
HANDOFF.mkdir(parents=True)

for name in COPY_FILES:
    src = RECON / name
    if not src.exists():
        raise RuntimeError(f"Required freeze handoff source missing: {name}")
    shutil.copy2(src, HANDOFF / name)

quality_fields = list(canonical_rows[0].keys())
with (HANDOFF / "retained_quality_exceptions.csv").open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=quality_fields, extrasaction="ignore")
    w.writeheader(); w.writerows(quality)

handoff_summary = {
    "handoff_type": "SCIPRA frozen reconstructed replication corpus audit bundle",
    "corpus_frozen": True,
    "reconstructed_corpus_records": 886,
    "analysis_ready_records": 876,
    "retained_quality_exceptions": 10,
    "historical_reported_n_87_role": "benchmark_only_not_target_quota_or_stopping_rule",
    "period": "2010-01-01 to 2023-12-31",
    "title_trigger_media_screening": "690/690 complete; 547 included pre-dedup; 143 excluded",
    "secondary_media_screening": "1062/1062 complete; 131 included pre-dedup; 931 excluded",
    "final_textwide_review": "7/7 >=0.95 pairs explicitly resolved as duplicate/republication collapses",
    "current_live_recovery": "879/883 analysis-ready records freshly extracted; 4/883 reconciled to prior validated extractions",
    "unresolved_screening_or_duplicate_decisions": 0,
    "stance_annotation_performed": False,
    "classifier_or_mcdm_run": False,
    "eiti_provenance_caveat": EITI_CAVEAT,
    "canonical_corpus_sha256": hashes["canonical_reconstructed_replication_corpus.csv"],
    "analysis_ready_manifest_sha256": hashes["canonical_analysis_ready_manifest.csv"],
}
(HANDOFF / "HANDOFF_SUMMARY.json").write_text(json.dumps(handoff_summary, indent=2) + "\n", encoding="utf-8")

readme = f"""# SCIPRA reconstructed replication corpus — frozen audit handoff

This directory is the reviewer-facing audit package for the **frozen reconstructed replication corpus**. It replaces the earlier preliminary handoff that still described archive candidates as pending review.

## Frozen membership

- Frozen retained corpus: **886 records**
- Analysis-ready subset: **876 records**
- Retained non-analysis-ready quality exceptions: **10 records**
- Coverage period: **2010-01-01 through 2023-12-31**
- Historical reported corpus size **N=87**: benchmark only; it was **not** used as a target, quota, class-balancing device, or stopping rule.

The canonical membership file is `canonical_reconstructed_replication_corpus.csv`. The modeling-eligible pre-annotation subset is `canonical_analysis_ready_manifest.csv`. Their SHA-256 values are locked in `corpus_freeze_hashes.json`.

## Completed review chain

1. Title-trigger archive media: **690/690 explicitly screened** — 547 included pre-dedup, 143 excluded.
2. Secondary-keyword archive media: **1,062/1,062 explicitly screened** — 131 included pre-dedup, 931 excluded.
3. Cross-phase and prior-QC exact/same-source duplicate review completed.
4. Metadata-driven near-duplicate review completed.
5. Final textwide TF-IDF audit covered the full analysis-ready pre-freeze set and produced **7 pairs >=0.95**, all explicitly reviewed and collapsed as republication/syndication/update duplicates.
6. Latest live recovery extracted **879/883** analysis-ready records. The remaining four annual-report/official-PDF extraction gaps were reconciled to previously reviewed extractions with stored SHA-256 values and substantial text lengths.
7. Membership and the analysis-ready subset were hashed **before stance annotation or model fitting**.

## EITI provenance limitation

> {EITI_CAVEAT}

This is a provenance/documentation limitation. The reconstruction does not convert it into an allegation of fabrication.

## What the freeze does — and does not do

The freeze fixes corpus membership and identifies which retained records are presently analysis-ready. It does **not** assert that this is an exact recovery of the historical 87 documents. It also does not reproduce the historical 71/16 stance distribution.

No stance annotation, TF-IDF/SVM classifier fit, MCDM, PCI or RPCI calculation was used to select or balance the frozen corpus. Those are downstream analysis stages and must consume this frozen version without changing membership.

## Files to review first

- `HANDOFF_SUMMARY.json` — compact reviewer summary.
- `corpus_freeze_summary.json` — machine-readable freeze assertions.
- `corpus_freeze_hashes.json` — SHA-256 lock file.
- `canonical_reconstructed_replication_corpus.csv` — frozen membership, N=886.
- `canonical_analysis_ready_manifest.csv` — pre-annotation analysis-ready subset, N=876.
- `retained_quality_exceptions.csv` — the 10 retained records not currently analysis-ready.
- `textwide_near_duplicate_final_decisions.csv` — final seven textwide duplicate decisions.
- `textwide_recovery_reconciliation.csv` — four current extraction gaps reconciled to earlier validated text.
- `media_substantive_decision_summary.json` and `secondary_media_substantive_decision_summary.json` — completed media-screening ledgers.

Full copyrighted media article text is intentionally not redistributed in this handoff.
"""
(HANDOFF / "README.md").write_text(readme, encoding="utf-8")

protocol = f"""# Reconstruction and freeze protocol

## Inclusion frame

The reconstruction covers 2010-01-01 to 2023-12-31 and requires substantive Marikana/Lonmin/Sibanye-Marikana relevance. Acquisition, title matching and literal occurrence of the word *Marikana* are not sufficient for inclusion.

Substantive themes include the 2012 strike and killings, Farlam Commission processes, the 2014 platinum strike when Lonmin is substantively implicated, wages and labour relations, housing/community obligations, social and labour plans, justice/accountability, regulatory response, ownership transition and Marikana renewal.

Policy Gap 10 Kumba/Sishen material is prospectively excluded; the Lonmin-focused Policy Gap 7 material is retained. Deduplication occurs after substantive eligibility.

## Provenance controls

- Historical N=87 is comparison context only.
- Historical stance distribution is not a selection target.
- SHA-256 uniqueness alone is not treated as proof of authenticity.
- Hash-only matches with conflicting metadata are not automatically collapsed.
- Current acquisition failure does not erase a previously validated extraction when the prior text hash and provenance remain auditable.
- Full copyrighted media text is not committed as part of the review bundle.

## Freeze controls

The finalizer fails closed unless the two media queues are complete, the stable textwide candidate set is exactly the reviewed seven pairs, the current recovery gaps are fully reconciled, every retained year is within 2010–2023, and no stance/model-derived field is present in the selection manifest.

Frozen membership: **886**. Analysis-ready subset: **876**. Quality exceptions retained outside modeling subset: **10**.

EITI caveat: {EITI_CAVEAT}
"""
(HANDOFF / "RECONSTRUCTION_PROTOCOL.md").write_text(protocol, encoding="utf-8")

checklist = """# Reviewer checklist

- [ ] Confirm `corpus_freeze_hashes.json` matches the two canonical CSV files.
- [ ] Confirm corpus membership is N=886 and analysis-ready membership is N=876.
- [ ] Confirm the 10 quality exceptions are retained but excluded from the analysis-ready subset.
- [ ] Inspect the seven final textwide duplicate/republication decisions.
- [ ] Inspect the four recovery reconciliations and their prior validated SHA-256 values.
- [ ] Confirm title-trigger screening is 690/690 complete and secondary screening is 1,062/1,062 complete.
- [ ] Confirm historical N=87 is described only as a benchmark, not a reconstruction target.
- [ ] Confirm the EITI limitation is phrased as an unrecovered/unvalidated provenance claim, not as fabrication.
- [ ] Confirm no stance labels, SVM output, PCI/RPCI or MCDM result influenced membership.
"""
(HANDOFF / "REVIEWER_CHECKLIST.md").write_text(checklist, encoding="utf-8")

if OLD_ZIP.exists():
    OLD_ZIP.unlink()
if ZIP_OUT.exists():
    ZIP_OUT.unlink()
with zipfile.ZipFile(ZIP_OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for path in sorted(HANDOFF.rglob("*")):
        if path.is_file():
            z.write(path, path.relative_to(RECON))

print(json.dumps(handoff_summary, indent=2))
print(f"Built {ZIP_OUT.name} with {len(list(HANDOFF.iterdir()))} handoff files")
