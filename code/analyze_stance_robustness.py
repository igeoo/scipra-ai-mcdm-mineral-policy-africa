"""Static robustness audit for the reconstructed SCIPRA stance reversal.

This script does not reacquire web text and does not modify corpus membership.
It tests whether the resistant-dominant result depends on the chosen third-pass
adjudication threshold/weighting and reports conservative unresolved-case bounds.

It does NOT claim the historical N=87 labels are false: the exact historical
corpus and human annotation ledger are unavailable. The result is framed as
non-reproduction / lack of robustness under the independently reconstructed,
frozen corpus and documented B.4.2 decision rules.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PF = ROOT / "data" / "post_freeze_analysis"
RECON = ROOT / "data" / "reconstruction"
OUT = ROOT / "data" / "revision_analysis"

DRAFT = PF / "reconstructed_annotation_draft.csv"
FINAL = PF / "reconstructed_stance_labels_final.csv"
UNRESOLVED = PF / "reconstructed_stance_unresolved.csv"
MANIFEST = RECON / "canonical_analysis_ready_manifest.csv"

EXPECTED_N = 876
EXPECTED_MANIFEST_SHA = "cb280e4cb138b2f6bba48b24f0dcd7521c4cb821871846ceb70523a05a7acad5"
HISTORICAL_PRO = 71
HISTORICAL_RES = 16
HISTORICAL_PRO_FRACTION = HISTORICAL_PRO / (HISTORICAL_PRO + HISTORICAL_RES)


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fnum(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def write_csv(path: Path, rows: list[dict]):
    fields = []
    for row in rows:
        for k in row:
            if k not in fields:
                fields.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(rows)


def count_labels(rows: list[dict], field: str) -> Counter:
    return Counter((r.get(field) or "").strip() for r in rows if (r.get(field) or "").strip() in {"0", "1"})


def fraction(counts: Counter, label: str) -> float:
    n = counts.get("0", 0) + counts.get("1", 0)
    return counts.get(label, 0) / n if n else float("nan")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    draft = read_csv(DRAFT)
    final = read_csv(FINAL)
    unresolved = read_csv(UNRESOLVED)
    manifest = read_csv(MANIFEST)

    assert len(draft) == EXPECTED_N
    assert len(manifest) == EXPECTED_N
    assert len(final) == 807
    assert len(unresolved) == 69
    assert len(final) + len(unresolved) == EXPECTED_N
    assert sha(MANIFEST) == EXPECTED_MANIFEST_SHA

    pass1 = count_labels(draft, "draft_reconstructed_label")
    reading_a = count_labels(draft, "stance_a_label")
    reading_b = count_labels(draft, "stance_b_label")
    final_counts = count_labels(final, "final_reconstructed_label")

    assert pass1 == Counter({"0": 672, "1": 63}), pass1
    assert final_counts == Counter({"0": 730, "1": 77}), final_counts

    # Recovered text rows have computational readings; the three unavailable rows do not.
    recovered = [r for r in draft if (r.get("stance_a_label") or "").strip() in {"0", "1"}]
    assert len(recovered) == 873
    assert sum(reading_a.values()) == 873
    assert sum(reading_b.values()) == 873

    # Adjudication grid: pass-1 labels remain fixed; only previously unlabeled recovered
    # rows are adjudicated under alternate prospective A/B score weights and margins.
    grid = []
    a_weights = [0.40, 0.50, 0.60, 0.70, 0.80]
    thresholds = [0.00, 0.10, 0.20, 0.30, 0.50, 0.75, 1.00]
    for aw in a_weights:
        bw = 1.0 - aw
        for threshold in thresholds:
            counts = Counter(pass1)
            adjudicated = 0
            for r in draft:
                if (r.get("draft_reconstructed_label") or "").strip() in {"0", "1"}:
                    continue
                a_label = (r.get("stance_a_label") or "").strip()
                b_label = (r.get("stance_b_label") or "").strip()
                if a_label not in {"0", "1"} or b_label not in {"0", "1"}:
                    continue
                score = aw * fnum(r.get("stance_a_score")) + bw * fnum(r.get("stance_b_score"))
                if abs(score) >= threshold:
                    counts["1" if score > 0 else "0"] += 1
                    adjudicated += 1
            labelled = counts["0"] + counts["1"]
            unresolved_n = EXPECTED_N - labelled
            # Conservative upper bound: every unresolved record is pro-integration.
            max_possible_pro_fraction_all_unresolved_pro = (counts["1"] + unresolved_n) / EXPECTED_N
            min_possible_resistant_fraction_all_unresolved_pro = counts["0"] / EXPECTED_N
            grid.append({
                "reading_a_weight": aw,
                "reading_b_weight": bw,
                "adjudication_threshold": threshold,
                "adjudicated_from_pass1_unlabelled": adjudicated,
                "labelled_total": labelled,
                "resistant_count": counts["0"],
                "pro_integration_count": counts["1"],
                "unresolved_count": unresolved_n,
                "pro_fraction_among_labelled": counts["1"] / labelled,
                "resistant_fraction_among_labelled": counts["0"] / labelled,
                "max_possible_pro_fraction_if_all_unresolved_pro": max_possible_pro_fraction_all_unresolved_pro,
                "min_possible_resistant_fraction_if_all_unresolved_pro": min_possible_resistant_fraction_all_unresolved_pro,
            })

    # Fixed-pass1 lower bound: regardless of how all 141 non-pass1 records are labelled,
    # 672 resistant pass-1 labels already occupy 76.7% of the frozen corpus.
    pass1_unassigned = EXPECTED_N - sum(pass1.values())
    pass1_max_pro_if_all_unassigned_pro = (pass1["1"] + pass1_unassigned) / EXPECTED_N
    pass1_min_resistant_fraction = pass1["0"] / EXPECTED_N

    # Stress: how many fixed pass-1 resistant labels must be flipped after giving every
    # non-pass1 record the most pro-integration-favourable assignment?
    majority_required = EXPECTED_N // 2 + 1
    pro_before_flips = pass1["1"] + pass1_unassigned
    resistant_flips_for_majority = max(0, majority_required - pro_before_flips)
    historical_equivalent_pro_count = math.ceil(HISTORICAL_PRO_FRACTION * EXPECTED_N)
    resistant_flips_for_historical_share = max(0, historical_equivalent_pro_count - pro_before_flips)

    # Final-ledger unresolved-case bound.
    final_max_pro_if_all_69_unresolved_pro = (final_counts["1"] + len(unresolved)) / EXPECTED_N
    final_min_resistant_if_all_69_unresolved_pro = final_counts["0"] / EXPECTED_N

    # Source-phase breakdown uses only finalized labels and the frozen manifest.
    phase_by_id = {r["canonical_record_id"]: r["source_phase"] for r in manifest}
    phase_counts = defaultdict(Counter)
    for r in final:
        phase_counts[phase_by_id[r["record_id"]]][r["final_reconstructed_label"]] += 1
    phase_rows = []
    for phase, counts in sorted(phase_counts.items()):
        n = counts["0"] + counts["1"]
        phase_rows.append({
            "source_phase": phase,
            "n_final_labelled": n,
            "resistant": counts["0"],
            "pro_integration": counts["1"],
            "resistant_fraction": counts["0"] / n,
            "pro_integration_fraction": counts["1"] / n,
        })

    publisher_counts = defaultdict(Counter)
    for r in final:
        publisher_counts[r.get("publisher", "")][r["final_reconstructed_label"]] += 1
    publisher_rows = []
    for publisher, counts in publisher_counts.items():
        n = counts["0"] + counts["1"]
        if n >= 5:
            publisher_rows.append({
                "publisher": publisher,
                "n_final_labelled": n,
                "resistant": counts["0"],
                "pro_integration": counts["1"],
                "resistant_fraction": counts["0"] / n,
                "pro_integration_fraction": counts["1"] / n,
            })
    publisher_rows.sort(key=lambda r: (-r["n_final_labelled"], r["publisher"]))

    grid_max_upper_pro = max(r["max_possible_pro_fraction_if_all_unresolved_pro"] for r in grid)
    grid_min_resistant_among_labelled = min(r["resistant_fraction_among_labelled"] for r in grid)
    grid_max_pro_among_labelled = max(r["pro_fraction_among_labelled"] for r in grid)

    summary = {
        "stage": "static_stance_reversal_robustness_audit",
        "frozen_analysis_manifest_sha256": EXPECTED_MANIFEST_SHA,
        "frozen_analysis_ready_records": EXPECTED_N,
        "historical_reported_distribution": {
            "pro_integration": HISTORICAL_PRO,
            "resistant": HISTORICAL_RES,
            "pro_integration_fraction": HISTORICAL_PRO_FRACTION,
        },
        "pass1": {
            "labelled": sum(pass1.values()),
            "resistant": pass1["0"],
            "pro_integration": pass1["1"],
            "resistant_fraction_among_labelled": fraction(pass1, "0"),
            "pro_integration_fraction_among_labelled": fraction(pass1, "1"),
        },
        "independent_reading_a": {
            "n": sum(reading_a.values()), "resistant": reading_a["0"], "pro_integration": reading_a["1"],
            "resistant_fraction": fraction(reading_a, "0"), "pro_integration_fraction": fraction(reading_a, "1"),
        },
        "independent_reading_b": {
            "n": sum(reading_b.values()), "resistant": reading_b["0"], "pro_integration": reading_b["1"],
            "resistant_fraction": fraction(reading_b, "0"), "pro_integration_fraction": fraction(reading_b, "1"),
        },
        "final_reconstructed_ledger": {
            "labelled": sum(final_counts.values()),
            "resistant": final_counts["0"],
            "pro_integration": final_counts["1"],
            "resistant_fraction": fraction(final_counts, "0"),
            "pro_integration_fraction": fraction(final_counts, "1"),
            "unresolved": len(unresolved),
        },
        "conservative_bounds": {
            "pass1_nonpass1_records": pass1_unassigned,
            "pass1_minimum_resistant_fraction_even_if_all_nonpass1_records_are_pro": pass1_min_resistant_fraction,
            "pass1_maximum_pro_fraction_even_if_all_nonpass1_records_are_pro": pass1_max_pro_if_all_unassigned_pro,
            "final_minimum_resistant_fraction_even_if_all_69_unresolved_are_pro": final_min_resistant_if_all_69_unresolved_pro,
            "final_maximum_pro_fraction_even_if_all_69_unresolved_are_pro": final_max_pro_if_all_69_unresolved_pro,
            "pass1_resistant_labels_that_must_flip_to_reach_simple_pro_majority_after_all_nonpass1_assigned_pro": resistant_flips_for_majority,
            "pass1_resistant_labels_that_must_flip_to_match_historical_pro_fraction_after_all_nonpass1_assigned_pro": resistant_flips_for_historical_share,
            "fraction_of_pass1_resistant_labels_that_must_flip_to_match_historical_pro_fraction": resistant_flips_for_historical_share / pass1["0"],
        },
        "adjudication_grid": {
            "reading_a_weights": a_weights,
            "thresholds": thresholds,
            "scenarios": len(grid),
            "maximum_pro_fraction_among_labelled_across_grid": grid_max_pro_among_labelled,
            "minimum_resistant_fraction_among_labelled_across_grid": grid_min_resistant_among_labelled,
            "maximum_possible_pro_fraction_across_grid_even_if_every_unresolved_record_is_pro": grid_max_upper_pro,
        },
        "source_phase_breakdown_rows": len(phase_rows),
        "interpretation": (
            "The historical 71/16 distribution is not treated as falsified because the exact historical corpus and human label ledger are unavailable. "
            "This audit tests whether the resistant-dominant result of the independently reconstructed frozen corpus is an artifact of third-pass adjudication choices."
        ),
    }

    write_csv(OUT / "stance_adjudication_sensitivity_grid.csv", grid)
    write_csv(OUT / "stance_source_phase_breakdown.csv", phase_rows)
    write_csv(OUT / "stance_publisher_breakdown_n_ge_5.csv", publisher_rows)
    (OUT / "stance_robustness_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = f"""# SCIPRA Stance-Reversal Robustness Audit

## Purpose

This is a **static** audit of the frozen reconstructed corpus. It does not reacquire source text, alter corpus membership, or tune labels toward the historical 71:16 distribution.

The historical human annotation ledger and exact historical N=87 corpus remain unavailable. Therefore the historical distribution is treated as **not independently reproduced**, not as proven false.

## Headline reconstructed result

- Historical reported pro-integration share: **{HISTORICAL_PRO_FRACTION:.1%}** (71/87)
- Final reconstructed pro-integration share among finalized labels: **{fraction(final_counts,'1'):.1%}** ({final_counts['1']}/{sum(final_counts.values())})
- Final reconstructed resistant share: **{fraction(final_counts,'0'):.1%}** ({final_counts['0']}/{sum(final_counts.values())})

## Strongest conservative bound

Pass 1 alone fixed **{pass1['0']} resistant** and **{pass1['1']} pro-integration** labels. There are {pass1_unassigned} non-pass1 records in the full frozen N={EXPECTED_N} corpus.

Even if **every one** of those {pass1_unassigned} records were assigned pro-integration, the full corpus would still be at least **{pass1_min_resistant_fraction:.1%} resistant** and at most **{pass1_max_pro_if_all_unassigned_pro:.1%} pro-integration**.

To obtain a simple pro-integration majority under that maximally pro-favourable unresolved assignment, at least **{resistant_flips_for_majority} of the {pass1['0']} pass-1 resistant labels** would additionally have to be flipped. To reproduce the historical 81.6% pro-integration fraction, at least **{resistant_flips_for_historical_share} pass-1 resistant labels ({resistant_flips_for_historical_share/pass1['0']:.1%})** would have to flip after already assigning every non-pass1 record pro-integration.

## Independent computational readings

- Reading A: resistant **{fraction(reading_a,'0'):.1%}**, pro-integration **{fraction(reading_a,'1'):.1%}** across {sum(reading_a.values())} recovered texts.
- Reading B: resistant **{fraction(reading_b,'0'):.1%}**, pro-integration **{fraction(reading_b,'1'):.1%}** across {sum(reading_b.values())} recovered texts.

## Adjudication sensitivity

The audit evaluates {len(grid)} combinations of A/B weighting and adjudication margin. Across that grid:

- highest pro-integration fraction among labelled records: **{grid_max_pro_among_labelled:.1%}**
- lowest resistant fraction among labelled records: **{grid_min_resistant_among_labelled:.1%}**
- highest possible pro-integration fraction after assigning every remaining unresolved record pro: **{grid_max_upper_pro:.1%}**

Detailed results are in `stance_adjudication_sensitivity_grid.csv`.

## Source-family check

Finalized labels are also broken down by frozen `source_phase` in `stance_source_phase_breakdown.csv`, and by publishers with at least five finalized records in `stance_publisher_breakdown_n_ge_5.csv`. This tests whether the aggregate result is driven by only one acquisition stream or publisher.

## Interpretation constraint

This result supports a claim of **empirical non-reproduction and strong sensitivity of the historical stance conclusion to corpus provenance**. It does not establish that the unavailable historical human labels were fabricated or necessarily incorrect on their exact historical corpus.
"""
    (OUT / "STANCE_ROBUSTNESS_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
