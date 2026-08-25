# SCIPRA reconstructed replication corpus — frozen audit handoff

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

> The reported set of 13 South Africa EITI documents cannot presently be independently recovered or validated as described in the original corpus documentation.

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
