"""Build a compact audit report for the completed SCIPRA post-freeze analysis."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data"/"post_freeze_analysis"
REPORT=OUT/"POST_FREEZE_ANALYSIS_REPORT.md"
SUMMARY=OUT/"post_freeze_analysis_summary.json"
HASHES=OUT/"post_freeze_analysis_hashes.json"


def j(name): return json.loads((OUT/name).read_text(encoding="utf-8"))
def csvrows(name):
    with (OUT/name).open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ann=j("annotation_pass_summary.json")
    stance=j("reconstructed_stance_summary.json")
    svm=j("svm_metrics.json")
    idx=j("corpus_derived_indices.json")
    mcdm=j("mcdm_reproducibility_audit.json")
    groups=csvrows("stakeholder_acceptance_oof.csv")
    scenarios=csvrows("scenario_formula_validation.csv")
    class_counts=stance["observed_reconstructed_class_counts"]
    group_lines=[]
    for r in groups:
        group_lines.append(f"| {r['stakeholder_group']} | {r['n']} | {float(r['mean_oof_pro_integration_probability']):.4f} | {float(r['SIC']):.3f} |")
    scenario_lines=[]
    for r in scenarios:
        scenario_lines.append(
            f"| {r['scenario']} | {float(r['pci_formula']):.4f} | {float(r['rpci_raw_formula']):.4f} | {float(r['rpci_normalised_A10_formula']):.4f} | {float(r['manuscript_stated_rpci_si_normalised']):.3f} |"
        )

    text=f"""# SCIPRA Post-Freeze Reproducibility Analysis

## Scope and provenance

This analysis is downstream of the frozen reconstructed replication corpus and does **not** modify corpus membership. The frozen analysis-ready manifest is identified by SHA-256 `{stance['frozen_analysis_manifest_sha256']}`.

The historical two-human-annotator stance ledger was not recoverable. Consequently, the labels used below are explicitly **reconstructed computational annotations** implementing the documented Appendix B.4.2 criteria. The historical reported 71:16 class split was not used as a target, quota, calibration condition, or stopping rule.

## Reconstructed annotation

- Frozen analysis-ready records: **{stance['frozen_analysis_ready_records']}**
- Texts recovered during first annotation pass: **{ann['texts_recovered_for_execution']}**
- Direct agreement between the two computational readings: **{ann['computational_readings_agreement_rate_on_recovered_text']:.3%}**
- Final model-eligible reconstructed labels: **{stance['final_model_eligible_labelled_records']}**
- Unresolved records excluded from model fitting: **{stance['unresolved_records_excluded_from_model']}**
- Pass-1 agreement labels: **{stance['pass1_agreement_labels']}**
- Third computational adjudications: **{stance['third_computational_adjudications']}**
- Observed reconstructed resistant labels (0): **{class_counts.get('0',0)}**
- Observed reconstructed pro-integration labels (1): **{class_counts.get('1',0)}**

This distribution is an observed consequence of applying the reconstructed rule system to the expanded frozen corpus; it is not forced to resemble the historical N=87 distribution.

## Leakage-safe TF-IDF / SVM evaluation

TF-IDF is fitted **inside each cross-validation training fold**. The model uses the intended 500-feature TF-IDF representation and a class-balanced RBF SVM. Metrics are out-of-fold and describe agreement with the reconstructed computational target—not recovered historical human-label performance.

- Model-evaluable records: **{svm['model_evaluable_records_after_fresh_text_recovery']}**
- CV folds: **{svm['cv']['n_splits']}**
- Accuracy: **{svm['accuracy']:.4f}**
- Balanced accuracy: **{svm['balanced_accuracy']:.4f}**
- Precision, pro-integration: **{svm['precision_pro_integration']:.4f}**
- Recall, pro-integration: **{svm['recall_pro_integration']:.4f}**
- F1, pro-integration: **{svm['f1_pro_integration']:.4f}**
- ROC AUC: **{svm['roc_auc_pro_integration']:.4f}**
- Cohen's kappa, OOF prediction vs reconstructed target: **{svm['cohen_kappa_oof_vs_reconstructed_target']:.4f}**
- Confusion matrix `[0,1]`: `{svm['confusion_matrix_labels_0_1']}`

## Stakeholder acceptance proxies from OOF probabilities

| Group | n | Mean OOF P(pro-integration) | SIC |
|---|---:|---:|---:|
{chr(10).join(group_lines)}

These are dominant-voice **proxies** for the reconstructed analysis; they do not recreate the unavailable historical human stakeholder attribution ledger.

## Corpus-derived operational index proxies

- Investment proxy (investor-group OOF acceptance): **{idx['investment_score_proxy']:.4f}**
- Regulatory proxy (government-group OOF acceptance): **{idx['regulatory_score_proxy']:.4f}**
- SIC-weighted stakeholder score: **{idx['stakeholder_score_sic_weighted']:.4f}**
- Linear PCI: **{idx['linear_pci']:.4f}**
- Weighted cross-domain sigma: **{idx['weighted_cross_domain_sigma']:.4f}**
- RPCI raw: **{idx['rpci_raw']:.4f}**
- RPCI normalized, SI Eq. A.10: **{idx['rpci_normalised_A10']:.4f}**
- Nonlinear PCI: **{idx['nonlinear_pci_weighted_harmonic_blend']:.4f}**

These I/R values are operational proxies inherited from the repository's group-aggregation logic; they are **not** independently reproduced FAHP scenario-domain performance scores.

## Mathematical scenario audit

| Scenario | PCI formula | RPCI raw | RPCI normalized A.10 | SI-stated RPCI |
|---|---:|---:|---:|---:|
{chr(10).join(scenario_lines)}

The Appendix A.10 normalized formula is internally reproducible, but the stated normalized values for Scenarios B and C do not equal the result of applying that formula to the documented domain scores. Both formula outputs and manuscript-stated values are retained rather than forcing agreement.

## MCDM / SWDC reproducibility status

All five documented SIC values reproduce from P/L/U. Full dynamic criterion reweighting does **not** currently reproduce from the implemented scalar formula after normalization: multiplying every base criterion by the same `(1 + delta*SIC)` factor and renormalizing returns the original relative weights exactly. The manuscript examples imply criterion/stakeholder-specific influence, but that mapping/sensitivity schedule is not fully specified in the current executable implementation.

Status: **{mcdm['swdc_equation_audit']['reproducibility_status']}**.

Accordingly, this reconstruction does not invent missing criterion mappings and does not claim the full FAHP/SWDC transformation has been independently reproduced.

## Scientific interpretation

The downstream reconstruction is substantially more reproducible than the original repository because corpus membership is hash-locked before labels or models, historical class balance is not imposed, annotation uncertainty is explicit, TF-IDF is trained within CV folds, OOF probabilities drive group summaries, and equation inconsistencies are reported rather than patched to match expected results.

It does **not** recover the unavailable historical human annotation process or validate the manuscript's historical SVM metrics. Any revised paper should distinguish the frozen reconstructed replication corpus and reconstructed computational analysis from the originally reported N=87 experiment.
"""
    REPORT.write_text(text,encoding="utf-8")
    summary={
        "stage":"completed_post_freeze_reconstructed_analysis",
        "frozen_analysis_manifest_sha256":stance["frozen_analysis_manifest_sha256"],
        "final_model_eligible_labelled_records":stance["final_model_eligible_labelled_records"],
        "unresolved_records_excluded_from_model":stance["unresolved_records_excluded_from_model"],
        "observed_reconstructed_class_counts":class_counts,
        "svm_accuracy":svm["accuracy"],"svm_balanced_accuracy":svm["balanced_accuracy"],"svm_roc_auc":svm["roc_auc_pro_integration"],
        "corpus_derived_operational_indices":idx,
        "swdc_reproducibility_status":mcdm["swdc_equation_audit"]["reproducibility_status"],
        "historical_labels_recovered":False,"historical_71_16_used_as_target":False,
        "report":REPORT.name,
    }
    SUMMARY.write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    candidates=[
        "reconstructed_stance_labels_final.csv","reconstructed_stance_unresolved.csv","reconstructed_stance_summary.json",
        "svm_oof_predictions.csv","svm_metrics.json","stakeholder_acceptance_oof.csv","corpus_derived_indices.json","model_execution_recovery.csv",
        "scenario_formula_validation.csv","mcdm_reproducibility_audit.json",REPORT.name,SUMMARY.name,
    ]
    existing=[OUT/x for x in candidates if (OUT/x).exists()]
    HASHES.write_text(json.dumps({"algorithm":"sha256",**{p.name:sha(p) for p in existing}},indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(text)

if __name__=="__main__":main()
