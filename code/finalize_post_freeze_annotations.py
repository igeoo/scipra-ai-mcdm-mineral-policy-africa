"""Finalize reconstructed SCIPRA stance annotations after pass-1 review.

The historical human label ledger is unavailable.  This finalizer therefore
creates a distinctly named COMPUTATIONAL reconstruction.  It never targets the
reported 71:16 distribution.  Pass-1 agreements are retained; disagreements
are adjudicated only when the independent reading scores have a clear combined
margin.  Truly ambiguous or text-unavailable rows stay unresolved and are
excluded from model training/evaluation rather than receiving fabricated labels.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "post_freeze_analysis"
DRAFT = OUT / "reconstructed_annotation_draft.csv"
PASS_SUMMARY = OUT / "annotation_pass_summary.json"
FINAL = OUT / "reconstructed_stance_labels_final.csv"
UNRESOLVED = OUT / "reconstructed_stance_unresolved.csv"
SUMMARY = OUT / "reconstructed_stance_summary.json"
HASHES = OUT / "reconstructed_stance_hashes.json"
EXPECTED_FROZEN_N = 876
EXPECTED_MANIFEST_SHA = "cb280e4cb138b2f6bba48b24f0dcd7521c4cb821871846ceb70523a05a7acad5"


def rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def fnum(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def write(path: Path, data: list[dict]):
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


def main():
    if not DRAFT.exists() or not PASS_SUMMARY.exists():
        raise RuntimeError("Pass-1 annotation outputs are not available; refusing to finalize labels")
    src = rows(DRAFT)
    ps = json.loads(PASS_SUMMARY.read_text(encoding="utf-8"))
    if len(src) != EXPECTED_FROZEN_N:
        raise RuntimeError(f"Expected {EXPECTED_FROZEN_N} draft rows, found {len(src)}")
    if ps.get("frozen_analysis_manifest_sha256") != EXPECTED_MANIFEST_SHA:
        raise RuntimeError("Annotation pass was not tied to the frozen analysis manifest hash")
    if ps.get("historical_71_16_distribution_used_as_target") is not False:
        raise RuntimeError("Pass-1 does not explicitly reject the historical class target")

    final, unresolved = [], []
    adjudicated = 0
    for r in src:
        out = dict(r)
        existing = (r.get("draft_reconstructed_label") or "").strip()
        if existing in {"0", "1"}:
            out["final_reconstructed_label"] = existing
            out["final_label_method"] = "pass1_independent_readings_agree"
            out["adjudication_score"] = ""
            final.append(out)
            continue

        a_raw, b_raw = (r.get("stance_a_label") or "").strip(), (r.get("stance_b_label") or "").strip()
        if a_raw not in {"0", "1"} or b_raw not in {"0", "1"}:
            out["final_reconstructed_label"] = ""
            out["final_label_method"] = "unresolved_text_or_reading_unavailable"
            out["adjudication_score"] = ""
            unresolved.append(out)
            continue

        a = fnum(r.get("stance_a_score")); b = fnum(r.get("stance_b_score"))
        # A is the broader literal B.4.2 rule reading; B is the stricter outcome-specific reading.
        # The combination is fixed prospectively and is NOT calibrated to class counts.
        combined = 0.60 * a + 0.40 * b
        # Strong title evidence, if both readings encoded it into their scores, naturally widens margin.
        if abs(combined) >= 0.30:
            out["final_reconstructed_label"] = "1" if combined > 0 else "0"
            out["final_label_method"] = "third_computational_adjudication_clear_margin"
            out["adjudication_score"] = f"{combined:.6f}"
            out["annotation_confidence"] = f"{min(1.0, abs(combined)/3.0):.4f}"
            final.append(out); adjudicated += 1
        else:
            out["final_reconstructed_label"] = ""
            out["final_label_method"] = "unresolved_low_combined_margin"
            out["adjudication_score"] = f"{combined:.6f}"
            unresolved.append(out)

    if not final:
        raise RuntimeError("No reconstructed labels available")
    counts = Counter(r["final_reconstructed_label"] for r in final)
    if len(counts) < 2:
        raise RuntimeError("Reconstructed labels contain only one class; refusing downstream SVM")

    write(FINAL, final); write(UNRESOLVED, unresolved)
    group_counts = Counter(r.get("stakeholder_group_proxy", "") for r in final)
    low_group_conf = sum(
        (r.get("stakeholder_method") == "dominant_voice_proxy" and fnum(r.get("stakeholder_confidence")) < 0.12)
        or r.get("stakeholder_method") == "fallback_no_actor_signal"
        for r in final
    )
    summary = {
        "stage": "final_reconstructed_computational_stance_labels",
        "frozen_analysis_manifest_sha256": EXPECTED_MANIFEST_SHA,
        "frozen_analysis_ready_records": EXPECTED_FROZEN_N,
        "final_model_eligible_labelled_records": len(final),
        "unresolved_records_excluded_from_model": len(unresolved),
        "pass1_agreement_labels": len(final) - adjudicated,
        "third_computational_adjudications": adjudicated,
        "observed_reconstructed_class_counts": dict(sorted(counts.items())),
        "observed_reconstructed_pro_integration_fraction": counts.get("1", 0) / len(final),
        "observed_reconstructed_resistant_fraction": counts.get("0", 0) / len(final),
        "stakeholder_proxy_counts_model_eligible": dict(group_counts),
        "low_confidence_stakeholder_proxy_records_model_eligible": low_group_conf,
        "historical_reported_71_16_used_as_target": False,
        "legacy_svm_labels_used": False,
        "human_annotation_recreated": False,
        "interpretation": "This is a transparent computational reconstruction of the documented B.4.2 binary decision criteria. It is not the unavailable historical two-human-annotator ledger. Model metrics must therefore be described as agreement with reconstructed computational labels, not recovered human-label predictive validation.",
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    HASHES.write_text(json.dumps({
        "algorithm": "sha256",
        FINAL.name: sha(FINAL),
        UNRESOLVED.name: sha(UNRESOLVED),
        SUMMARY.name: sha(SUMMARY),
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
