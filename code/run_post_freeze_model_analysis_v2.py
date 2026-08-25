"""Leakage-safe TF-IDF/RBF-SVM analysis using finalized stance labels and adjudicated stakeholder groups.

Stance-model evaluation uses every finalized reconstructed stance label whose
text can be freshly recovered. Stakeholder aggregation uses only records whose
separate stakeholder-attribution ledger is resolved. This prevents uncertain
stakeholder identity from contaminating group-level acceptance proxies.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, classification_report,
    cohen_kappa_score, confusion_matrix, f1_score, precision_score,
    recall_score, roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC

from post_freeze_annotation_pass import fetch_one

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "post_freeze_analysis"
LABELS = OUT / "reconstructed_stance_labels_final.csv"
LABEL_SUMMARY = OUT / "reconstructed_stance_summary.json"
STAKEHOLDER_LEDGER = OUT / "reconstructed_stakeholder_attribution_final.csv"
STAKEHOLDER_SUMMARY = OUT / "reconstructed_stakeholder_attribution_summary.json"
OOF_OUT = OUT / "svm_oof_predictions.csv"
METRICS_OUT = OUT / "svm_metrics.json"
GROUP_OUT = OUT / "stakeholder_acceptance_oof.csv"
INDEX_OUT = OUT / "corpus_derived_indices.json"
RECOVERY_OUT = OUT / "model_execution_recovery.csv"
HASHES_OUT = OUT / "post_freeze_model_hashes.json"
EXPECTED_MANIFEST_SHA = "cb280e4cb138b2f6bba48b24f0dcd7521c4cb821871846ceb70523a05a7acad5"
SIC = {"government": 0.703, "investor": 0.770, "community": 0.749, "labour": 0.807, "NGO": 0.686}
DOMAIN_WEIGHTS = (0.30, 0.35, 0.35)
LAMBDA = 0.10


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, data: list[dict]):
    fields = []
    for r in data:
        for k in r:
            if k not in fields:
                fields.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(data)


def sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pci(vals):
    return sum(w*x for w,x in zip(DOMAIN_WEIGHTS, vals))


def sigma(vals):
    mu = pci(vals)
    return math.sqrt(sum(w*(x-mu)**2 for w,x in zip(DOMAIN_WEIGHTS, vals)))


def rpci_raw(vals):
    return max(0.0, pci(vals) - LAMBDA*sigma(vals))


def rpci_norm(vals):
    return rpci_raw(vals)/(1+LAMBDA/2)


def nonlinear(vals, beta=0.5):
    lin = pci(vals)
    hm = lin if any(x <= 0 for x in vals) else 1/sum(w/x for w,x in zip(DOMAIN_WEIGHTS, vals))
    return beta*lin + (1-beta)*hm


def make_pipeline():
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            max_features=500,
            ngram_range=(1,2),
            min_df=2,
            max_df=0.90,
            sublinear_tf=True,
            stop_words="english",
            lowercase=True,
        )),
        ("svm", SVC(
            kernel="rbf", C=1.0, gamma="scale", class_weight="balanced",
            probability=True, random_state=42,
        )),
    ])


def main():
    for p in (LABELS, LABEL_SUMMARY, STAKEHOLDER_LEDGER, STAKEHOLDER_SUMMARY):
        if not p.exists():
            raise RuntimeError(f"Required finalized analysis input missing: {p.name}")

    stance_summary = json.loads(LABEL_SUMMARY.read_text(encoding="utf-8"))
    stakeholder_summary = json.loads(STAKEHOLDER_SUMMARY.read_text(encoding="utf-8"))
    if stance_summary.get("frozen_analysis_manifest_sha256") != EXPECTED_MANIFEST_SHA:
        raise RuntimeError("Final stance labels are not tied to frozen manifest")
    if stakeholder_summary.get("frozen_analysis_manifest_sha256") != EXPECTED_MANIFEST_SHA:
        raise RuntimeError("Stakeholder ledger is not tied to frozen manifest")
    if stance_summary.get("historical_reported_71_16_used_as_target") is not False or stance_summary.get("legacy_svm_labels_used") is not False:
        raise RuntimeError("Historical/legacy target leakage guard failed")

    labels = read_csv(LABELS)
    stakeholder_rows = read_csv(STAKEHOLDER_LEDGER)
    if len(stakeholder_rows) != len(labels):
        raise RuntimeError("Stakeholder ledger does not cover every finalized stance label")
    stakeholder_by_id = {r["record_id"]: r for r in stakeholder_rows}
    if len(stakeholder_by_id) != len(stakeholder_rows):
        raise RuntimeError("Duplicate record IDs in stakeholder ledger")

    recovered = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {}
        for r in labels:
            q = dict(r); q["canonical_record_id"] = r["record_id"]
            futs[pool.submit(fetch_one, q)] = r
        for fut in as_completed(futs):
            src = futs[fut]
            recovered.append((src, fut.result()))

    recovery_meta, usable = [], []
    for src, res in recovered:
        stake = stakeholder_by_id[src["record_id"]]
        recovery_meta.append({
            "record_id": src["record_id"],
            "label": src["final_reconstructed_label"],
            "final_stakeholder_group": stake.get("final_stakeholder_group", ""),
            "final_stakeholder_status": stake.get("final_stakeholder_status", ""),
            "status": res["status"], "method": res["method"], "words": res["words"],
            "text_sha256": res["sha"], "error": res["error"],
        })
        if res["status"] == "retrieved_extracted":
            usable.append((src, stake, res["text"]))
    write_csv(RECOVERY_OUT, sorted(recovery_meta, key=lambda r: r["record_id"]))

    usable.sort(key=lambda t: t[0]["record_id"])
    X = np.array([text for _,_,text in usable], dtype=object)
    y = np.array([int(r["final_reconstructed_label"]) for r,_,_ in usable], dtype=int)
    ids = [r["record_id"] for r,_,_ in usable]
    if len(set(y.tolist())) != 2:
        raise RuntimeError("Only one label class remains after fresh text recovery")
    min_class = int(np.bincount(y).min())
    n_splits = min(5, min_class)
    if n_splits < 2:
        raise RuntimeError("Minority class too small for stratified CV")

    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    oof_prob = np.full(len(y), np.nan)
    oof_pred = np.full(len(y), -1, dtype=int)
    fold_id = np.full(len(y), -1, dtype=int)
    for fold, (tr, te) in enumerate(cv.split(X, y), start=1):
        pipe = make_pipeline()
        pipe.fit(X[tr].tolist(), y[tr])
        classes = list(pipe.named_steps["svm"].classes_)
        oof_prob[te] = pipe.predict_proba(X[te].tolist())[:, classes.index(1)]
        oof_pred[te] = pipe.predict(X[te].tolist())
        fold_id[te] = fold
    if np.isnan(oof_prob).any() or (fold_id < 1).any():
        raise RuntimeError("OOF prediction coverage incomplete")

    metrics = {
        "stage": "post_freeze_tfidf_rbf_svm_oof_evaluation_v2",
        "target_type": "reconstructed_computational_B4_2_labels_not_historical_human_labels",
        "frozen_analysis_manifest_sha256": EXPECTED_MANIFEST_SHA,
        "final_reconstructed_label_records": len(labels),
        "model_evaluable_records_after_fresh_text_recovery": len(usable),
        "execution_text_unavailable_excluded": len(labels)-len(usable),
        "class_counts_model_evaluable": {str(k): int(v) for k,v in sorted(Counter(y.tolist()).items())},
        "cv": {"type":"StratifiedKFold","n_splits":n_splits,"shuffle":True,"random_state":42},
        "tfidf": {"max_features":500,"ngram_range":[1,2],"min_df":2,"max_df":0.90,"sublinear_tf":True,"stop_words":"english","fit_inside_each_fold":True},
        "svm": {"kernel":"rbf","C":1.0,"gamma":"scale","class_weight":"balanced","probability":True,"random_state":42},
        "accuracy": float(accuracy_score(y,oof_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y,oof_pred)),
        "precision_pro_integration": float(precision_score(y,oof_pred,pos_label=1,zero_division=0)),
        "recall_pro_integration": float(recall_score(y,oof_pred,pos_label=1,zero_division=0)),
        "f1_pro_integration": float(f1_score(y,oof_pred,pos_label=1,zero_division=0)),
        "roc_auc_pro_integration": float(roc_auc_score(y,oof_prob)),
        "cohen_kappa_oof_vs_reconstructed_target": float(cohen_kappa_score(y,oof_pred)),
        "confusion_matrix_labels_0_1": confusion_matrix(y,oof_pred,labels=[0,1]).tolist(),
        "classification_report": classification_report(y,oof_pred,labels=[0,1],target_names=["resistant","pro_integration"],output_dict=True,zero_division=0),
        "important_limitation": "Metrics quantify cross-validated agreement with computationally reconstructed B.4.2 labels, not unavailable historical human labels.",
    }
    METRICS_OUT.write_text(json.dumps(metrics, indent=2, sort_keys=True)+"\n", encoding="utf-8")

    by_id = {r["record_id"]:(r,stake) for r,stake,_ in usable}
    pred_rows=[]
    for i,rid in enumerate(ids):
        r, stake = by_id[rid]
        pred_rows.append({
            "record_id": rid, "year": r.get("year",""), "publisher": r.get("publisher",""),
            "final_stakeholder_group": stake.get("final_stakeholder_group",""),
            "final_stakeholder_status": stake.get("final_stakeholder_status",""),
            "final_stakeholder_method": stake.get("final_stakeholder_method",""),
            "final_stakeholder_confidence": stake.get("final_stakeholder_confidence",""),
            "reconstructed_target_label": int(y[i]), "oof_predicted_label": int(oof_pred[i]),
            "oof_pro_integration_probability": f"{oof_prob[i]:.8f}", "cv_fold": int(fold_id[i]),
            "final_label_method": r.get("final_label_method",""),
        })
    write_csv(OOF_OUT, pred_rows)

    group_rows=[]; group_prob={}
    for g in SIC:
        vals=[]
        for i,rid in enumerate(ids):
            _, stake = by_id[rid]
            if stake.get("final_stakeholder_status") == "resolved" and stake.get("final_stakeholder_group") == g:
                vals.append(float(oof_prob[i]))
        mean=float(np.mean(vals)) if vals else None
        group_prob[g]=mean
        group_rows.append({
            "stakeholder_group":g,"SIC":SIC[g],"n_resolved":len(vals),
            "mean_oof_pro_integration_probability":mean,
        })
    write_csv(GROUP_OUT, group_rows)
    missing=[g for g,v in group_prob.items() if v is None]
    if missing:
        raise RuntimeError(f"No resolved OOF observations for stakeholder groups: {missing}")

    I=group_prob["investor"]
    R=group_prob["government"]
    S=sum(SIC[g]*group_prob[g] for g in SIC)/sum(SIC.values())
    vals=(I,R,S)
    indices={
        "stage":"corpus_derived_operational_proxy_indices_from_oof_svm_v2",
        "investment_score_proxy":I,
        "regulatory_score_proxy":R,
        "stakeholder_score_sic_weighted":S,
        "linear_pci":pci(vals),
        "weighted_cross_domain_sigma":sigma(vals),
        "rpci_raw":rpci_raw(vals),
        "rpci_normalised_A10":rpci_norm(vals),
        "nonlinear_pci_weighted_harmonic_blend":nonlinear(vals),
        "domain_weights":[0.30,0.35,0.35],"rpc_lambda":LAMBDA,
        "stakeholder_group_probabilities":group_prob,
        "stakeholder_attribution_unresolved_excluded_from_group_aggregation": stakeholder_summary.get("final_stakeholder_unresolved_excluded_from_group_aggregation"),
        "interpretation_constraint":"I and R are reconstructed operational proxies from resolved investor/government OOF acceptance probabilities. They are not independently reproduced FAHP scenario performance scores.",
        "swdc_status":"original scalar-SIC normalized implementation is structurally degenerate; full corrected criterion-specific mapping is not inferred here",
    }
    INDEX_OUT.write_text(json.dumps(indices, indent=2, sort_keys=True)+"\n", encoding="utf-8")

    outputs=[OOF_OUT,METRICS_OUT,GROUP_OUT,INDEX_OUT,RECOVERY_OUT]
    HASHES_OUT.write_text(json.dumps({"algorithm":"sha256",**{p.name:sha(p) for p in outputs}},indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(metrics, indent=2, sort_keys=True))
    print(json.dumps(indices, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
