# SCIPRA Revision Analysis — Frozen Handoff

This folder is the frozen downstream revision layer. It does **not** alter the frozen reconstructed corpus or historical-replication outputs.

## Empirical robustness

- Frozen analysis-ready corpus: **876**
- Final reconstructed labels: **730 resistant / 77 pro-integration / 69 unresolved**
- Historical reported stance: **71 pro-integration / 16 resistant**
- The historical split was never used as a selection or annotation target.
- Across the adjudication sensitivity grid, the resistant-dominant result remains intact.

## Mathematical finding

The historical scalar-SIC SWDC implementation is structurally degenerate after normalization. The proposed revision introduces explicit stakeholder-by-criterion relevance before normalization and is kept clearly separate from historical replication.

## Evidence-derived revision

The primary criterion-relevance analysis recovered **774/776** resolved-stakeholder records. Its matrix estimates documentary issue prevalence, not expert preference strength.

## Semantic sensitivity

The post-hoc semantic audit recovered **773** records. It tests stricter employment semantics and broader financial semantics and is sensitivity-only; it does not replace the preregistered primary specification. The strong primary Local Employment upweighting is not semantically robust, while Community Infrastructure remains upweighted in the tested variants.

## Integrity

See `revision_freeze_hashes.json` for SHA-256 hashes of the required frozen revision files.
