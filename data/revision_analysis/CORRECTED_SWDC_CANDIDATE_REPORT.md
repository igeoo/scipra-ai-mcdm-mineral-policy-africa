# Corrected SCIPRA Stakeholder-Weighting Candidate — Mathematical Audit

## Boundary

This is a **proposed revision**, not a reconstruction of the historical SWDC implementation.

The original code multiplies every criterion by one common `(1 + delta*SIC)` scalar and then normalizes. The audit reconfirms a maximum post-normalization weight change of **5.551e-17** across all tested SIC/delta combinations: mathematically zero.

## Candidate

For stakeholder `s` and criterion `j`:

- `C_s = 1 - P_s(pro-integration)` — reconstructed contention signal
- `E_s = SIC_s * C_s` — salience-weighted policy pressure
- `G_j = sum_s(E_s A_sj) / sum_s(E_s)` — criterion-specific pressure
- `W*_j = W0_j(1 + delta G_j) / sum_k[W0_k(1 + delta G_k)]`

`A_sj` is the stakeholder-by-criterion relevance matrix. This is the missing structural object that the original scalar formulation did not contain.

## Why it is non-degenerate

For two criteria `j,k`:

`W*_j/W*_k = (W0_j/W0_k) * (1+delta G_j)/(1+delta G_k)`.

Therefore, when `delta > 0` and `G_j != G_k`, the relative weight ratio changes. If all `G_j` are equal, the common factor intentionally cancels and the model returns the base AHP vector.

## Verified properties

- positive normalized weights
- exact sum-to-one
- exact base recovery at `delta=0`
- exact base recovery under uniform criterion pressure
- non-trivial reweighting under unequal criterion pressure
- pairwise relative-ratio identity verified numerically
- 5000 random relevance-matrix stress tests preserved positivity and normalization; 5000/5000 were non-degenerate at delta=0.3

## Illustrative demonstration only

The included relevance matrix is **not empirical**. It merely reflects the manuscript's qualitative narrative sufficiently to demonstrate mathematical behavior. At delta=0.3, the illustrative adjusted investment weights are:

- NPV: base 0.2500 -> illustrative 0.2425
- IRR: base 0.2000 -> illustrative 0.1935
- Geological Feasibility: base 0.1500 -> illustrative 0.1479
- Market Stability: base 0.1500 -> illustrative 0.1507
- Local Employment: base 0.1500 -> illustrative 0.1594
- Community Infrastructure: base 0.1000 -> illustrative 0.1060

These values must not be reported as revised SCIPRA empirical findings.

## What is required next

A publishable revised model needs `A_sj` from either:

1. preregistered criterion-specific text coding / NLP relevance scoring on the frozen corpus, or
2. transparent expert elicitation with inter-rater/reliability reporting.

Only after that matrix is independently justified should corrected stakeholder-weighted policy results be computed.
