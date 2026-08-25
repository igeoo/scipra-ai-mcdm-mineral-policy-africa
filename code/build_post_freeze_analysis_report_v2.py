"""Build the final compact SCIPRA post-freeze reproducibility report (v2)."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "post_freeze_analysis"
REPORT = OUT / "POST_FREEZE_ANALYSIS_REPORT.md"
SUMMARY = OUT / "post_freeze_analysis_summary.json"
HASHES = OUT / "post_freeze_analysis_hashes.json"


def j(name):
    return json.loads((OUT/name).read_text(encoding="utf-8"))


def csvrows(name):
    with (OUT/name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ann = j("annotation_pass_summary.json")
    stance = j("reconstructed_stance_summary.json")
    stake = j("reconstructed_stakeholder_attribution_summary.json")
    svm = j("svm_metrics.json")
    idx = j("corpus_derived_indices.json")
    mcdm = j("mcdm_reproducibility_audit.json")
    groups = csvrows("stakeholder_acceptance_oof.csv")
    scenarios = csvrows("scenario_formula_validation.csv")
    classes = stance["observed_reconstructed_class_counts"]

    group_lines = [
        f"| {r['stakeholder_group']} | {int(r['n_resolved'])} | {float(r['mean_oof_pro_integration_probability']):.4f} | {float(r['SIC']):.3f} |"
        for r in groups
    ]
    scenario_lines = [
        f"| {r['scenario']} | {float(r['pci_formula']):.4f} | {float(r['rpci_raw_formula']):.4f} | {float(r['rpci_normalised_A10_formula']):.4f} | {float(r['manuscript_stated_rpci_si_normalised']):.3f} |"
        for r in scenarios
    ]

    text = f"""# SCIPRA Post-Freeze Reproducibility Analysis

## Scope

This analysis is downstream of the frozen reconstructed replication corpus and does **not** modify corpus membership. The frozen analysis-ready manifest SHA-256 is `{stance['frozen_analysis_manifest_sha256']}`.

The historical two-human-annotator label ledger is unavailable. All labels below are explicitly reconstructed computational annotations applying the documented Appendix B.4.2 decision criteria. The historical 71:16 class distribution was never used as a target.

## Annotation accounting

- Frozen analysis-ready records: **{stance['frozen_analysis_ready_records']}**
- Text recovered at pass 1: **{ann['texts_recovered_for_execution']}**
- Computational-reading agreement: **{ann['computational_readings_agreement_rate_on_recovered_text']:.3%}**
- Pass-1 labels assigned: **{ann['draft_labels_assigned_total']}**
- Final model-eligible stance labels: **{stance['final_model_eligible_labelled_records']}**
- Unresolved stance records excluded from SVM: **{stance['unresolved_records_excluded_from_model']}**
- Pass-1 agreement labels retained: **{stance['pass1_agreement_labels']}**
- Third computational stance adjudications: **{stance['third_computational_adjudications']}**
- Resistant (0): **{classes.get('0',0)}**
- Pro-integration (1): **{classes.get('1',0)}**

The 189-record pass-1 review queue overlapped the labeled set; its reconciled accounting is retained in `annotation_count_reconciliation.json` and should not be interpreted as a disjoint 735+189 total.

## Stakeholder attribution adjudication

- Low-confidence/fallback pass-1 stakeholder targets: **{stake['pass1_low_confidence_or_fallback_targets']}**
- Resolved in third pass: **{stake['third_pass_resolved']}**
- Final resolved stakeholder attributions: **{stake['final_stakeholder_resolved_records']}**
- Unresolved stakeholder attributions excluded from group aggregation: **{stake['final_stakeholder_unresolved_excluded_from_group_aggregation']}**

Unresolved stakeholder identity does not invalidate a record's finalized stance label. Such records remain eligible for stance-model evaluation but are excluded from stakeholder-group means and downstream group-derived proxy indices.

## Leakage-safe TF-IDF / SVM

TF-IDF is fitted inside every training fold. The evaluation target is the reconstructed computational stance ledger, not unavailable historical human labels.

- Freshly model-evaluable records: **{svm['model_evaluable_records_after_fresh_text_recovery']}**
- CV folds: **{svm['cv']['n_splits']}**
- Accuracy: **{svm['accuracy']:.4f}**
- Balanced accuracy: **{svm['balanced_accuracy']:.4f}**
- Precision, pro-integration: **{svm['precision_pro_integration']:.4f}**
- Recall, pro-integration: **{svm['recall_pro_integration']:.4f}**
- F1, pro-integration: **{svm['f1_pro_integration']:.4f}**
- ROC AUC: **{svm['roc_auc_pro_integration']:.4f}**
- Cohen's kappa: **{svm['cohen_kappa_oof_vs_reconstructed_target']:.4f}**
- Confusion matrix `[0,1]`: `{svm['confusion_matrix_labels_0_1']}`

## Resolved stakeholder acceptance proxies

| Group | resolved n | Mean OOF P(pro-integration) | SIC |
|---|---:|---:|---:|
{chr(10).join(group_lines)}

## Corpus-derived operational proxy indices

- Investment proxy: **{idx['investment_score_proxy']:.4f}**
- Regulatory proxy: **{idx['regulatory_score_proxy']:.4f}**
- SIC-weighted stakeholder proxy: **{idx['stakeholder_score_sic_weighted']:.4f}**
- Linear PCI proxy: **{idx['linear_pci']:.4f}**
- Weighted cross-domain sigma: **{idx['weighted_cross_domain_sigma']:.4f}**
- RPCI raw proxy: **{idx['rpci_raw']:.4f}**
- RPCI normalized A.10 proxy: **{idx['rpci_normalised_A10']:.4f}**
- Nonlinear PCI proxy: **{idx['nonlinear_pci_weighted_harmonic_blend']:.4f}**

These are operational proxies derived from OOF group acceptance probabilities. They are **not** independent reconstructions of the manuscript's FAHP investment/regulatory scenario scores.

## Mathematical scenario audit

| Scenario | PCI | RPCI raw | RPCI normalized A.10 | SI-stated normalized RPCI |
|---|---:|---:|---:|---:|
{chr(10).join(scenario_lines)}

Scenario A is essentially consistent after raw versus normalized RPCI is distinguished. Scenarios B and C do not reproduce the stated normalized values from the documented A.10 formula and domain scores.

## SWDC finding

All five SIC values reproduce exactly. However, the original historical `dynamic_weighting.py` applies the same scalar multiplier `(1 + delta*SIC)` to every criterion and then normalizes the vector. That common multiplier cancels exactly, so the implemented mechanism cannot change relative criterion weights for any SIC or delta. This is a structural property of the original implementation, not a reconstruction regression.

Status: **{mcdm['swdc_equation_audit']['reproducibility_status']}**.

A revised SCIPRA formulation would require an explicitly criterion-specific stakeholder influence map or another mathematically non-degenerate formulation. No such missing mapping is invented in this replication analysis.

## Interpretation

This stage establishes an auditable reconstructed stance-model pipeline downstream of a hash-frozen corpus. It does not claim recovery of the historical human annotation ledger or historical SVM validation. Discrepancies are retained as reproducibility findings rather than tuned away.
"""
    REPORT.write_text(text, encoding="utf-8")

    summary = {
        "stage": "completed_post_freeze_reconstructed_analysis_v2",
        "frozen_analysis_manifest_sha256": stance["frozen_analysis_manifest_sha256"],
        "final_model_eligible_labelled_records": stance["final_model_eligible_labelled_records"],
        "unresolved_stance_records_excluded_from_model": stance["unresolved_records_excluded_from_model"],
        "final_stakeholder_resolved_records": stake["final_stakeholder_resolved_records"],
        "unresolved_stakeholder_records_excluded_from_group_aggregation": stake["final_stakeholder_unresolved_excluded_from_group_aggregation"],
        "observed_reconstructed_class_counts": classes,
        "svm_accuracy": svm["accuracy"],
        "svm_balanced_accuracy": svm["balanced_accuracy"],
        "svm_roc_auc": svm["roc_auc_pro_integration"],
        "corpus_derived_operational_indices": idx,
        "swdc_reproducibility_status": mcdm["swdc_equation_audit"]["reproducibility_status"],
        "historical_labels_recovered": False,
        "historical_71_16_used_as_target": False,
        "report": REPORT.name,
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True)+"\n", encoding="utf-8")

    candidates = [
        "annotation_pass_summary.json", "annotation_count_reconciliation.json",
        "reconstructed_stance_labels_final.csv", "reconstructed_stance_unresolved.csv", "reconstructed_stance_summary.json", "reconstructed_stance_hashes.json",
        "reconstructed_stakeholder_attribution_final.csv", "reconstructed_stakeholder_attribution_unresolved.csv", "reconstructed_stakeholder_attribution_summary.json", "reconstructed_stakeholder_attribution_hashes.json",
        "svm_oof_predictions.csv", "svm_metrics.json", "stakeholder_acceptance_oof.csv", "corpus_derived_indices.json", "model_execution_recovery.csv", "post_freeze_model_hashes.json",
        "scenario_formula_validation.csv", "mcdm_reproducibility_audit.json", REPORT.name, SUMMARY.name,
    ]
    existing = [OUT/x for x in candidates if (OUT/x).exists()]
    HASHES.write_text(json.dumps({"algorithm":"sha256", **{p.name:sha(p) for p in existing}}, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
