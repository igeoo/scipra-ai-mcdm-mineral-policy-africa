"""Run leakage-safe TF-IDF/SVM analysis on finalized reconstructed labels.

Important: the labels consumed here are computational reconstructions of the
published B.4.2 criteria, NOT recovered historical human annotations.  Metrics
therefore measure out-of-fold agreement with that reconstructed target.

The frozen corpus manifest is never modified. Text is recovered in runner
memory and not committed. TF-IDF is fitted inside each training fold via a
Pipeline to avoid vocabulary/IDF leakage.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, classification_report,
    cohen_kappa_score, confusion_matrix, f1_score, precision_score,
    recall_score, roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC

from post_freeze_annotation_pass import fetch_one

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "post_freeze_analysis"
LABELS = OUT / "reconstructed_stance_labels_final.csv"
LABEL_SUMMARY = OUT / "reconstructed_stance_summary.json"
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


def fnum(v, default=0.0):
    try: return float(v)
    except Exception: return default


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
            kernel="rbf",
            C=1.0,
            gamma="scale",
            class_weight="balanced",
            probability=True,
            random_state=42,
        )),
    ])


def main():
    if not LABELS.exists() or not LABEL_SUMMARY.exists():
        raise RuntimeError("Final reconstructed label ledger missing; model fitting is blocked")
    label_summary = json.loads(LABEL_SUMMARY.read_text(encoding="utf-8"))
    if label_summary.get("frozen_analysis_manifest_sha256") != EXPECTED_MANIFEST_SHA:
        raise RuntimeError("Labels are not tied to frozen analysis manifest")
    if label_summary.get("historical_reported_71_16_used_as_target") is not False or label_summary.get("legacy_svm_labels_used") is not False:
        raise RuntimeError("Label finalizer does not explicitly reject legacy/class-target leakage")

    labels = read_csv(LABELS)
    if len(labels) < 20:
        raise RuntimeError("Too few finalized reconstructed labels for SVM")

    # Recover model texts independently at execution time; preserve only hashes/counts.
    recovered = []
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {}
        for r in labels:
            row = dict(r)
            row["canonical_record_id"] = r["record_id"]
            futures[pool.submit(fetch_one, row)] = r
        for fut in as_completed(futures):
            src = futures[fut]
            res = fut.result()
            recovered.append((src, res))

    recovery_meta = []
    usable = []
    for src, res in recovered:
        ok = res["status"] == "retrieved_extracted"
        recovery_meta.append({
            "record_id": src["record_id"], "label": src["final_reconstructed_label"],
            "stakeholder_group_proxy": src.get("stakeholder_group_proxy", ""),
            "status": res["status"], "method": res["method"], "words": res["words"],
            "text_sha256": res["sha"], "error": res["error"],
        })
        if ok:
            usable.append((src, res["text"]))
    write_csv(RECOVERY_OUT, sorted(recovery_meta, key=lambda r:r["record_id"]))

    usable.sort(key=lambda t: t[0]["record_id"])
    X = np.array([text for _, text in usable], dtype=object)
    y = np.array([int(r["final_reconstructed_label"]) for r,_ in usable], dtype=int)
    ids = [r["record_id"] for r,_ in usable]
    if len(set(y.tolist())) != 2:
        raise RuntimeError("Only one label class remains after execution-time text recovery")
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
        oof_prob[te] = pipe.predict_proba(X[te].tolist())[:, list(pipe.named_steps["svm"].classes_).index(1)]
        oof_pred[te] = pipe.predict(X[te].tolist())
        fold_id[te] = fold
    if np.isnan(oof_prob).any() or (fold_id < 1).any():
        raise RuntimeError("OOF prediction coverage incomplete")

    metrics = {
        "stage": "post_freeze_tfidf_rbf_svm_oof_evaluation",
        "target_type": "reconstructed_computational_B4_2_labels_not_historical_human_labels",
        "frozen_analysis_manifest_sha256": EXPECTED_MANIFEST_SHA,
        "final_reconstructed_label_records": len(labels),
        "model_evaluable_records_after_fresh_text_recovery": len(usable),
        "execution_text_unavailable_excluded": len(labels)-len(usable),
        "class_counts_model_evaluable": {str(k): int(v) for k,v in sorted(Counter(y.tolist()).items())},
        "cv": {"type":"StratifiedKFold", "n_splits":n_splits, "shuffle":True, "random_state":42},
        "tfidf": {"max_features":500, "ngram_range":[1,2], "min_df":2, "max_df":0.90, "sublinear_tf":True, "stop_words":"english", "fit_inside_each_fold":True},
        "svm": {"kernel":"rbf", "C":1.0, "gamma":"scale", "class_weight":"balanced", "probability":True, "random_state":42},
        "accuracy": float(accuracy_score(y,oof_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y,oof_pred)),
        "precision_pro_integration": float(precision_score(y,oof_pred,pos_label=1,zero_division=0)),
        "recall_pro_integration": float(recall_score(y,oof_pred,pos_label=1,zero_division=0)),
        "f1_pro_integration": float(f1_score(y,oof_pred,pos_label=1,zero_division=0)),
        "roc_auc_pro_integration": float(roc_auc_score(y,oof_prob)),
        "cohen_kappa_oof_vs_reconstructed_target": float(cohen_kappa_score(y,oof_pred)),
        "confusion_matrix_labels_0_1": confusion_matrix(y,oof_pred,labels=[0,1]).tolist(),
        "classification_report": classification_report(y,oof_pred,labels=[0,1],target_names=["resistant","pro_integration"],output_dict=True,zero_division=0),
        "important_limitation": "These metrics quantify cross-validated model agreement with computationally reconstructed B.4.2 labels. They are not validation against the unavailable historical two-human-annotator labels and must not be presented as recovery of the manuscript's reported SVM performance.",
    }
    METRICS_OUT.write_text(json.dumps(metrics,indent=2,sort_keys=True)+"\n",encoding="utf-8")

    by_id = {r["record_id"]:r for r,_ in usable}
    pred_rows=[]
    for i,rid in enumerate(ids):
        r=by_id[rid]
        pred_rows.append({
            "record_id":rid, "year":r.get("year",""), "publisher":r.get("publisher",""),
            "stakeholder_group_proxy":r.get("stakeholder_group_proxy",""),
            "stakeholder_confidence":r.get("stakeholder_confidence",""), "stakeholder_method":r.get("stakeholder_method",""),
            "reconstructed_target_label":int(y[i]), "oof_predicted_label":int(oof_pred[i]),
            "oof_pro_integration_probability":f"{oof_prob[i]:.8f}", "cv_fold":int(fold_id[i]),
            "final_label_method":r.get("final_label_method",""),
        })
    write_csv(OOF_OUT,pred_rows)

    group_rows=[]
    group_prob={}
    for g in SIC:
        vals=[oof_prob[i] for i,rid in enumerate(ids) if by_id[rid].get("stakeholder_group_proxy")==g]
        high=[oof_prob[i] for i,rid in enumerate(ids) if by_id[rid].get("stakeholder_group_proxy")==g and not (
            by_id[rid].get("stakeholder_method")=="fallback_no_actor_signal" or
            (by_id[rid].get("stakeholder_method")=="dominant_voice_proxy" and fnum(by_id[rid].get("stakeholder_confidence"))<0.12)
        )]
        mean=float(np.mean(vals)) if vals else None
        high_mean=float(np.mean(high)) if high else None
        group_prob[g]=mean
        group_rows.append({"stakeholder_group":g,"SIC":SIC[g],"n":len(vals),"mean_oof_pro_integration_probability":mean,"n_excluding_low_confidence_proxy":len(high),"mean_oof_probability_excluding_low_confidence_proxy":high_mean})
    write_csv(GROUP_OUT,group_rows)

    if group_prob.get("investor") is None or group_prob.get("government") is None or any(group_prob.get(g) is None for g in SIC):
        raise RuntimeError("One or more required stakeholder groups have no OOF observations")
    I=group_prob["investor"]
    R=group_prob["government"]
    S=sum(SIC[g]*group_prob[g] for g in SIC)/sum(SIC.values())
    vals=(I,R,S)
    indices={
        "stage":"corpus_derived_operational_proxy_indices_from_oof_svm",
        "investment_score_proxy":I,
        "regulatory_score_proxy":R,
        "stakeholder_score_sic_weighted":S,
        "linear_pci":pci(vals),
        "weighted_cross_domain_sigma":sigma(vals),
        "rpci_raw":rpci_raw(vals),
        "rpci_normalised_A10":rpci_norm(vals),
        "nonlinear_pci_weighted_harmonic_blend":nonlinear(vals),
        "domain_weights":[0.30,0.35,0.35], "rpc_lambda":LAMBDA,
        "stakeholder_group_probabilities":group_prob,
        "interpretation_constraint":"I and R here are reconstructed operational proxies inherited from the repository's documented group-aggregation pipeline (investor and government OOF acceptance probabilities). They are not independently re-estimated FAHP investment/regulatory scenario performance scores and must not be substituted for manuscript scenario scores without qualification.",
        "swdc_status":"full dynamic criterion reweighting remains underdetermined; see mcdm_reproducibility_audit.json",
    }
    INDEX_OUT.write_text(json.dumps(indices,indent=2,sort_keys=True)+"\n",encoding="utf-8")

    outputs=[OOF_OUT,METRICS_OUT,GROUP_OUT,INDEX_OUT,RECOVERY_OUT]
    HASHES_OUT.write_text(json.dumps({"algorithm":"sha256",**{p.name:sha(p) for p in outputs}},indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(metrics,indent=2,sort_keys=True))
    print(json.dumps(indices,indent=2,sort_keys=True))


if __name__ == "__main__":
    main()
