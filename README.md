# SCIPRA Computational Reproducibility Package

SCIPRA (Stakeholder-Centric Investment–Regulatory Policy Architecture) is an AI-enhanced multi-criteria decision framework for mineral-policy convergence. This repository is the **author-controlled computational project repository** and now contains the frozen technical reproducibility reconstruction of the original implementation.

## Repository status

The computational record is deliberately separated into three layers:

1. **Historical SCIPRA implementation and claims** — retained as the benchmark being audited.
2. **Technical reproducibility reconstruction** — a prospectively reconstructed and frozen corpus, reconstructed computational stance/stakeholder labels, leakage-safe model evaluation, and mathematical reproducibility audits.
3. **Proposed corrected SCIPRA revision** — a non-degenerate criterion-specific stakeholder-weight propagation mechanism, kept explicitly separate from historical replication.

The unpublished/revised manuscript and submission package are **not distributed in this repository** while manuscript revision and submission/archival approval remain pending.

See [`REPRODUCIBILITY_PROVENANCE.md`](REPRODUCIBILITY_PROVENANCE.md) for the development and authorship boundary.

## Frozen reconstruction

- Reconstructed replication corpus: **886 records**.
- Analysis-ready subset frozen before downstream annotation/model analysis: **876 records**.
- Historical reported corpus size **N=87** is a comparison benchmark only; it was not used as a quota, stopping rule, or class-balance target.
- Coverage: **2010-01-01 through 2023-12-31**.
- The reported set of 13 South Africa EITI documents cannot presently be independently recovered or validated as described in the original corpus documentation.

Primary corpus documentation:

- `data/reconstruction/RECONSTRUCTION_PROTOCOL.md`
- `data/reconstruction/canonical_reconstructed_replication_corpus.csv`
- `data/reconstruction/canonical_analysis_ready_manifest.csv`
- `data/reconstruction/corpus_freeze_summary.json`
- `data/reconstruction/corpus_freeze_hashes.json`
- `data/reconstruction/review_handoff/`

## Post-freeze reconstructed analysis

The final reconstructed computational stance ledger contains **807 labelled records**:

- **730 resistant**
- **77 pro-integration**
- **69 unresolved records excluded from model fitting**

The historical reported 71 pro-integration / 16 resistant split was never used as a target. These reconstructed labels are **not** the unavailable historical two-human-annotator ledger. Model metrics therefore quantify agreement with the transparent reconstructed computational target, not recovered human-label predictive validation.

Canonical post-freeze outputs include:

- `data/post_freeze_analysis/reconstructed_stance_labels_final.csv`
- `data/post_freeze_analysis/reconstructed_stance_summary.json`
- `data/post_freeze_analysis/svm_oof_predictions.csv`
- `data/post_freeze_analysis/svm_metrics.json`
- `data/post_freeze_analysis/POST_FREEZE_ANALYSIS_REPORT.md`
- `data/post_freeze_analysis/post_freeze_analysis_hashes.json`

## Mathematical reproducibility findings

The audit reproduces the documented SIC arithmetic and linear PCI formulation. Selected normalized RPCI scenario values do not exactly follow from the stated equation and inputs and are retained as discrepancies rather than reverse-engineered to match.

The historical SWDC implementation applies a common scalar salience adjustment to all criteria and then normalizes the vector. That scalar cancels, so it **cannot change relative criterion weights as coded**.

See:

- `data/post_freeze_analysis/mcdm_reproducibility_audit.json`
- `data/post_freeze_analysis/scenario_formula_validation.csv`

## Corrected SWDC revision layer

A proposed downstream revision introduces explicit stakeholder-by-criterion relevance before normalization. This is a **methodological revision, not a recovered historical implementation**.

The frozen revision analysis also records an important sensitivity result: the strong primary Local Employment upweighting is not robust to stricter employment semantics, while Community Infrastructure remains upweighted in the tested semantic variants. Substantive criterion-weight estimates should therefore be interpreted as measurement-sensitive rather than definitive policy weights.

See:

- `data/revision_analysis/REVISION_FREEZE_README.md`
- `data/revision_analysis/revision_freeze_summary.json`
- `data/revision_analysis/revision_freeze_hashes.json`
- `data/revision_analysis/CRITERION_RELEVANCE_PROTOCOL.md`
- `data/revision_analysis/NOVELTY_POSITIONING.md`

## Static reproducibility verification

The canonical repository uses a read-only verification workflow. It checks frozen SHA-256 manifests, corpus and annotation counts, reconciliation arithmetic, the recorded mathematical invariants, and manuscript exclusion. It does **not** reacquire live web sources or rewrite results.

Run locally with:

```bash
python code/verify_frozen_reproducibility.py
```

Live source availability can change over time, so the canonical integrity check is intentionally anchored to the frozen manifests and committed outputs. Acquisition/reconstruction scripts are retained for auditability and methodological inspection.

## Scientific and technical roles

Scientific authorship and interpretation remain with the study author(s) and the author-controlled `igeoo` project. Technical implementation and reproducibility engineering were performed in an isolated development fork after author review of the original repository, then curated for integration back into this canonical repository. See `REPRODUCIBILITY_PROVENANCE.md` for details.

## Citation

See `CITATION.cff` and the archived software metadata for project-author citation information. Cite the associated publication when an approved publication version is available.

## License

MIT License.
