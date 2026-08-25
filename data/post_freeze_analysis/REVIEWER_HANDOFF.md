# SCIPRA Reproducibility Reconstruction — Reviewer Handoff

## Purpose

This handoff separates the reconstruction into two auditable stages:

1. **Corpus reconstruction and freeze** — PR #1 (`dataset-reconstruction`)
2. **Post-freeze annotation and mathematical/model audit** — PR #2 (`post-freeze-analysis`)

The historical manuscript reported a corpus of 87 documents. That historical `N=87` was treated only as a benchmark. It was **not** used as a target, quota, stopping rule, stance-balance target, or duplicate-resolution criterion.

The current output should therefore be described as a **reconstructed replication corpus**, not as an exact recovery of the historical 87-document corpus.

---

## 1. Current status at a glance

### Corpus stage — COMPLETE AND FROZEN

- Reconstructed replication corpus: **886 retained records**
- Analysis-ready pre-annotation subset: **876 records**
- Retained non-analysis-ready quality exceptions: **10 records**
- Coverage: **2010-01-01 to 2023-12-31**
- Corpus frozen **before** stance annotation, SVM fitting, MCDM, PCI or RPCI calculation
- Historical stance distribution was not used during selection

Freeze hashes:

- Canonical reconstructed corpus SHA-256: `f6f0652617fd0bedd94154e7b2b187ee5ff15ca0a3be19aadde8fbf93a2b91b0`
- Analysis-ready manifest SHA-256: `cb280e4cb138b2f6bba48b24f0dcd7521c4cb821871846ceb70523a05a7acad5`

### Post-freeze annotation stage — FIRST PASS COMPLETE

- Frozen analysis-ready records targeted: **876**
- Texts recovered for execution: **873**
- Texts unavailable at this execution: **3**
- Agreement between two independent computational readings: **89.0%** on recovered texts
- **735 records received a draft stance label**
  - Resistant (`0`): **672**
  - Pro-integration (`1`): **63**
- **189 records appear in the review queue**, but the review queue is **not disjoint** from the labeled set.

Exact reconciliation:

- **687** = labeled and **not** in review queue
- **48** = labeled but **also** in review queue because dominant-stakeholder attribution is low-confidence
- **138** = recovered-text records with no draft stance label, queued for stance adjudication
- **3** = text-unavailable records, queued because stance cannot be assigned at this execution

Therefore:

- Recovered-text partition: `687 + 48 + 138 = 873`
- Full frozen analysis partition: `687 + 48 + 138 + 3 = 876`
- Review-queue partition: `48 + 138 + 3 = 189`

The earlier field name `draft_labels_without_review = 735` was misleading. The correct interpretation is **735 draft labels assigned**, of which **48 remain queued for stakeholder-attribution review**. This presentation/schema issue has been corrected explicitly rather than treating the queue and labeled set as mutually exclusive.

The historical **71 pro-integration / 16 resistant** distribution was **not used** as a target. The first-pass reconstructed direction differs substantially from it, which is itself a reproducibility finding.

### SVM/model stage — NOT YET CLAIMED COMPLETE

The final adjudication and leakage-safe TF-IDF/SVM scripts have been prepared, but final model metrics are **not yet being presented as completed results** in this handoff. No reviewer should infer that the historical model performance has been recovered.

---

## 2. Annotation protocol used

The post-freeze reconstruction follows the manuscript's Appendix B.4.2 decision rules:

- **1 — Pro-integration:** support for multi-stakeholder policy alignment, FPIC implementation, community benefit sharing, integrated governance reform, compliance improvement, or positive stakeholder-engagement outcomes.
- **0 — Resistant:** opposition to integrated governance; conflict events; community/labour resistance; regulatory non-compliance; governance failure; strikes; protests; evictions; or policy rollbacks.

For mixed-source documents, stakeholder attribution follows the manuscript's **dominant stakeholder voice** principle.

Important limitation: the historical manuscript states that two human annotators and a third adjudicator were used. Those historical human labels are unavailable. The present labels are therefore explicitly described as **reconstructed computational annotations applying the documented rules**, not as recovery of the historical human annotations.

Legacy/toy label files in the original repository were not accepted as ground truth because internally inconsistent label assignments were found across old analysis files.

---

## 3. Mathematical reproducibility audit

### Reproduced exactly

All five stakeholder influence coefficients reproduce from the documented P/L/U values using:

`SIC = 0.30P + 0.40L + 0.30U`

| Stakeholder | Reproduced SIC |
| --- | ---: |
| Government | 0.703 |
| Investor | 0.770 |
| Community | 0.749 |
| NGO | 0.686 |
| Labour | 0.807 |

Linear PCI, weighted cross-domain standard deviation, raw RPCI and the normalized Appendix A.10 RPCI formula are also directly reproducible.

### RPCI discrepancy found

Using the documented domain scores and Appendix A.10:

| Scenario | PCI | RPCI raw | RPCI normalized (formula) | Manuscript/SI stated normalized |
| --- | ---: | ---: | ---: | ---: |
| A — Pre-intervention | 0.4560 | 0.4278 | 0.4074 | 0.407 |
| B — Regulatory emphasis | 0.6650 | 0.6563 | 0.6251 | 0.638 |
| C — SCIPRA-optimised | 0.7815 | 0.7794 | 0.7423 | 0.752 |

Scenario A is consistent after distinguishing raw from normalized RPCI. Scenarios B and C do **not** reproduce the stated normalized values from the documented formula and domain scores.

### SWDC/dynamic-weighting structural degeneracy

The current executable equation applies a scalar factor:

`W_a = W_0 × (1 + δ × SIC)`

If the same scalar SIC is applied to every criterion and the vector is then normalized, all relative criterion weights return exactly to `W_0`. This is not merely an implementation detail: a common scalar multiplier necessarily cancels under normalization.

Therefore the reported non-trivial changes (for example Local Employment 0.15 → approximately 0.184) require a **criterion-specific stakeholder/sensitivity mapping**, criterion-specific multipliers, or a different normalization rule. That mapping is not encoded in the current implementation. As currently coded, the stakeholder-salience mechanism is mathematically inert with respect to **relative criterion weights**.

This should be treated as a structural reproducibility finding, not patched by reverse-engineering unpublished parameters.

---

## 4. Provenance caveat — EITI

The reported set of **13 South Africa EITI documents cannot presently be independently recovered or validated as described in the original corpus documentation**.

This is recorded as a provenance/documentation limitation. It should **not** be interpreted as proof that the historical claim was fabricated.

---

## 5. Recommended reviewer reading order

### A. Corpus/freeze evidence — PR #1

1. `data/reconstruction/review_handoff/README.md`
2. `data/reconstruction/review_handoff/REVIEWER_CHECKLIST.md`
3. `data/reconstruction/review_handoff/corpus_freeze_summary.json`
4. `data/reconstruction/review_handoff/corpus_freeze_hashes.json`
5. `data/reconstruction/review_handoff/canonical_reconstructed_replication_corpus.csv`
6. `data/reconstruction/review_handoff/canonical_analysis_ready_manifest.csv`
7. `data/reconstruction/RECONSTRUCTION_PROTOCOL.md`
8. `data/reconstruction/MEDIA_SUBSTANTIVE_SCREENING_RUBRIC.md`

Packaged freeze bundle:

`data/reconstruction/scipra_corpus_freeze_handoff.zip`

### B. Post-freeze annotation and math audit — PR #2

1. `data/post_freeze_analysis/REVIEWER_HANDOFF.md` — this file
2. `data/post_freeze_analysis/annotation_pass_summary.json`
3. `data/post_freeze_analysis/annotation_count_reconciliation.json`
4. `data/post_freeze_analysis/reconstructed_annotation_draft.csv`
5. `data/post_freeze_analysis/annotation_review_queue.csv`
6. `data/post_freeze_analysis/post_freeze_recovery_status.csv`
7. `data/post_freeze_analysis/mcdm_reproducibility_audit.json`
8. `data/post_freeze_analysis/scenario_formula_validation.csv`
9. `data/post_freeze_analysis/mathematical_audit_hashes.json`
10. `data/post_freeze_analysis/annotation_protocol_excerpt.txt`

Relevant executable code:

- `code/post_freeze_annotation_pass.py`
- `code/reconcile_post_freeze_annotation_summary.py`
- `code/finalize_post_freeze_annotations.py`
- `code/run_post_freeze_model_analysis.py`
- `code/audit_post_freeze_mcdm_formulas.py`
- `code/build_post_freeze_analysis_report.py`

---

## 6. What I am asking the reviewer to assess

1. **Corpus validity:** Are the prospective inclusion/exclusion rules and duplicate-resolution procedures defensible for a reconstructed Marikana/Lonmin replication corpus?
2. **Freeze integrity:** Is the separation between corpus selection and downstream annotation/model fitting sufficiently clear to prevent outcome-driven dataset construction?
3. **Annotation reconstruction:** Is the computational implementation of Appendix B.4.2 an acceptable reproducibility substitute given that the historical human labels are unavailable, provided it is explicitly labelled as reconstruction rather than recovery?
4. **Ambiguous cases:** Are the fail-closed review rules appropriate, particularly the explicit separation of stance ambiguity from stakeholder-attribution ambiguity?
5. **SWDC mathematics:** Do you agree that the normalized common-scalar SIC transformation is structurally degenerate for relative criterion weighting and requires an additional criterion-specific mapping or reformulation?
6. **RPCI reporting:** Should the reconstructed paper use the direct Appendix A.10 formula outputs (B ≈ 0.625, C ≈ 0.742) and identify the published 0.638/0.752 figures as unreproduced, rather than force agreement?
7. **EITI wording:** Is the provenance caveat appropriately conservative?

---

## 7. Current interpretation

The reconstruction has succeeded in producing an independently auditable dataset and in separating pre-freeze corpus decisions from post-freeze outcomes. It has **not** demonstrated exact recovery of the historical N=87 corpus, historical labels, or all manuscript outputs.

Several manuscript claims reproduce cleanly (notably SIC arithmetic and PCI arithmetic), while other elements show material reproducibility gaps: historical corpus provenance, historical stance distribution, parts of RPCI reporting, and—most importantly—the current SWDC dynamic-weight implementation, whose common scalar multiplier cancels under normalization.

These discrepancies are retained as findings rather than corrected by reverse-engineering outputs to match the manuscript.
