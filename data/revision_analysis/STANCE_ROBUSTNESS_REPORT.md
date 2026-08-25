# SCIPRA Stance-Reversal Robustness Audit

## Purpose

This is a **static** audit of the frozen reconstructed corpus. It does not reacquire source text, alter corpus membership, or tune labels toward the historical 71:16 distribution.

The historical human annotation ledger and exact historical N=87 corpus remain unavailable. Therefore the historical distribution is treated as **not independently reproduced**, not as proven false.

## Headline reconstructed result

- Historical reported pro-integration share: **81.6%** (71/87)
- Final reconstructed pro-integration share among finalized labels: **9.5%** (77/807)
- Final reconstructed resistant share: **90.5%** (730/807)

## Strongest conservative bound

Pass 1 alone fixed **672 resistant** and **63 pro-integration** labels. There are 141 non-pass1 records in the full frozen N=876 corpus.

Even if **every one** of those 141 records were assigned pro-integration, the full corpus would still be at least **76.7% resistant** and at most **23.3% pro-integration**.

To obtain a simple pro-integration majority under that maximally pro-favourable unresolved assignment, at least **235 of the 672 pass-1 resistant labels** would additionally have to be flipped. To reproduce the historical 81.6% pro-integration fraction, at least **511 pass-1 resistant labels (76.0%)** would have to flip after already assigning every non-pass1 record pro-integration.

## Independent computational readings

- Reading A: resistant **81.0%**, pro-integration **19.0%** across 873 recovered texts.
- Reading B: resistant **86.0%**, pro-integration **14.0%** across 873 recovered texts.

## Adjudication sensitivity

The audit evaluates 35 combinations of A/B weighting and adjudication margin. Across that grid:

- highest pro-integration fraction among labelled records: **13.0%**
- lowest resistant fraction among labelled records: **87.0%**
- highest possible pro-integration fraction after assigning every remaining unresolved record pro: **23.2%**

Detailed results are in `stance_adjudication_sensitivity_grid.csv`.

## Source-family check

Finalized labels are also broken down by frozen `source_phase` in `stance_source_phase_breakdown.csv`, and by publishers with at least five finalized records in `stance_publisher_breakdown_n_ge_5.csv`. This tests whether the aggregate result is driven by only one acquisition stream or publisher.

## Interpretation constraint

This result supports a claim of **empirical non-reproduction and strong sensitivity of the historical stance conclusion to corpus provenance**. It does not establish that the unavailable historical human labels were fabricated or necessarily incorrect on their exact historical corpus.
