# SCIPRA Post-Freeze Reproducibility Analysis

## Scope

This analysis is downstream of the frozen reconstructed replication corpus and does **not** modify corpus membership. The frozen analysis-ready manifest SHA-256 is `cb280e4cb138b2f6bba48b24f0dcd7521c4cb821871846ceb70523a05a7acad5`.

The historical two-human-annotator label ledger is unavailable. All labels below are explicitly reconstructed computational annotations applying the documented Appendix B.4.2 decision criteria. The historical 71:16 class distribution was never used as a target.

## Annotation accounting

- Frozen analysis-ready records: **876**
- Text recovered at pass 1: **873**
- Computational-reading agreement: **89.003%**
- Pass-1 labels assigned: **735**
- Final model-eligible stance labels: **807**
- Unresolved stance records excluded from SVM: **69**
- Pass-1 agreement labels retained: **735**
- Third computational stance adjudications: **72**
- Resistant (0): **730**
- Pro-integration (1): **77**

The 189-record pass-1 review queue overlapped the labeled set; its reconciled accounting is retained in `annotation_count_reconciliation.json` and should not be interpreted as a disjoint 735+189 total.

## Stakeholder attribution adjudication

- Low-confidence/fallback pass-1 stakeholder targets: **51**
- Resolved in third pass: **20**
- Final resolved stakeholder attributions: **776**
- Unresolved stakeholder attributions excluded from group aggregation: **31**

Unresolved stakeholder identity does not invalidate a record's finalized stance label. Such records remain eligible for stance-model evaluation but are excluded from stakeholder-group means and downstream group-derived proxy indices.

## Leakage-safe TF-IDF / SVM

TF-IDF is fitted inside every training fold. The evaluation target is the reconstructed computational stance ledger, not unavailable historical human labels.

- Freshly model-evaluable records: **806**
- CV folds: **5**
- Accuracy: **0.9305**
- Balanced accuracy: **0.7554**
- Precision, pro-integration: **0.6613**
- Recall, pro-integration: **0.5395**
- F1, pro-integration: **0.5942**
- ROC AUC: **0.9395**
- Cohen's kappa: **0.5566**
- Confusion matrix `[0,1]`: `[[709, 21], [35, 41]]`

## Resolved stakeholder acceptance proxies

| Group | resolved n | Mean OOF P(pro-integration) | SIC |
|---|---:|---:|---:|
| government | 319 | 0.0537 | 0.703 |
| investor | 147 | 0.2739 | 0.770 |
| community | 33 | 0.1846 | 0.749 |
| labour | 244 | 0.0443 | 0.807 |
| NGO | 32 | 0.0537 | 0.686 |

## Corpus-derived operational proxy indices

- Investment proxy: **0.2739**
- Regulatory proxy: **0.0537**
- SIC-weighted stakeholder proxy: **0.1237**
- Linear PCI proxy: **0.1443**
- Weighted cross-domain sigma: **0.0898**
- RPCI raw proxy: **0.1353**
- RPCI normalized A.10 proxy: **0.1288**
- Nonlinear PCI proxy: **0.1200**

These are operational proxies derived from OOF group acceptance probabilities. They are **not** independent reconstructions of the manuscript's FAHP investment/regulatory scenario scores.

## Mathematical scenario audit

| Scenario | PCI | RPCI raw | RPCI normalized A.10 | SI-stated normalized RPCI |
|---|---:|---:|---:|---:|
| A_pre_intervention | 0.4560 | 0.4278 | 0.4074 | 0.407 |
| B_regulatory_emphasis | 0.6650 | 0.6563 | 0.6251 | 0.638 |
| C_scipra_optimised | 0.7815 | 0.7794 | 0.7423 | 0.752 |

Scenario A is essentially consistent after raw versus normalized RPCI is distinguished. Scenarios B and C do not reproduce the stated normalized values from the documented A.10 formula and domain scores.

## SWDC finding

All five SIC values reproduce exactly. However, the original historical `dynamic_weighting.py` applies the same scalar multiplier `(1 + delta*SIC)` to every criterion and then normalizes the vector. That common multiplier cancels exactly, so the implemented mechanism cannot change relative criterion weights for any SIC or delta. This is a structural property of the original implementation, not a reconstruction regression.

Status: **underdetermined_for_full_dynamic_criterion_vector**.

A revised SCIPRA formulation would require an explicitly criterion-specific stakeholder influence map or another mathematically non-degenerate formulation. No such missing mapping is invented in this replication analysis.

## Interpretation

This stage establishes an auditable reconstructed stance-model pipeline downstream of a hash-frozen corpus. It does not claim recovery of the historical human annotation ledger or historical SVM validation. Discrepancies are retained as reproducibility findings rather than tuned away.
