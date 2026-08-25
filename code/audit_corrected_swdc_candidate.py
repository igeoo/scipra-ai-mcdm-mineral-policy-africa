"""Audit a corrected, criterion-specific SCIPRA stakeholder-weighting candidate.

This file belongs to the REVISION layer, not the historical replication layer.
It does not overwrite or reinterpret the original dynamic_weighting.py.

Original implemented form:
    Wa_j = W0_j * (1 + delta*SIC)
followed by normalization. Because the multiplier is common across j, it cancels.

Candidate revised form:
    contention_s = 1 - p_s
    pressure_s   = SIC_s * contention_s
    G_j          = sum_s pressure_s * A_sj / sum_s pressure_s
    W*_j         = W0_j * (1 + delta*G_j) / sum_k W0_k*(1 + delta*G_k)

A_sj is an explicit stakeholder-by-criterion relevance matrix in [0,1]. It is
NOT recovered from the historical manuscript. A numerical matrix in this script
is illustrative only, to test mathematical behavior. A publishable empirical
SCIPRA revision must estimate/pre-register A_sj via transparent expert elicitation
or criterion-specific text coding.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PF = ROOT / "data" / "post_freeze_analysis"
OUT = ROOT / "data" / "revision_analysis"
GROUPS = PF / "stakeholder_acceptance_oof.csv"

STAKEHOLDERS = ["government", "investor", "community", "labour", "NGO"]
SIC = {"government": 0.703, "investor": 0.770, "community": 0.749, "labour": 0.807, "NGO": 0.686}

# Main-text Step 2 states these conventional AHP investment criteria/weights.
# The same narrative later says Community Infrastructure rises from 0.08 to 0.099,
# which conflicts with the stated 0.10 base weight. The normalized 0.10 vector is
# used here; the 0.08 narrative is retained as a documented source inconsistency.
CRITERIA = ["NPV", "IRR", "Geological Feasibility", "Market Stability", "Local Employment", "Community Infrastructure"]
W0 = [0.25, 0.20, 0.15, 0.15, 0.15, 0.10]

# ILLUSTRATIVE ONLY. Chosen to express the manuscript's qualitative narrative:
# investor relevance is strongest for financial/market criteria; labour/community
# relevance is strongest for employment/community infrastructure. These values are
# not empirical estimates and must not be reported as recovered SCIPRA parameters.
ILLUSTRATIVE_A = {
    "government": [0.55, 0.50, 0.65, 0.75, 0.80, 0.80],
    "investor":   [1.00, 1.00, 0.90, 0.95, 0.45, 0.35],
    "community":  [0.20, 0.20, 0.30, 0.35, 0.90, 1.00],
    "labour":     [0.20, 0.20, 0.20, 0.30, 1.00, 0.70],
    "NGO":        [0.20, 0.20, 0.40, 0.45, 0.60, 0.90],
}


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(values):
    total = sum(values)
    if total <= 0:
        raise ValueError("Cannot normalize non-positive vector")
    return [v / total for v in values]


def original_adjusted(W0, sic, delta):
    return normalize([w * (1 + delta * sic) for w in W0])


def criterion_pressure(prob_pro: dict[str, float], matrix: dict[str, list[float]], use_contention=True):
    pressure = {}
    for s in STAKEHOLDERS:
        contention = 1.0 - prob_pro[s] if use_contention else 1.0
        pressure[s] = SIC[s] * contention
    denom = sum(pressure.values())
    G = []
    for j in range(len(CRITERIA)):
        G.append(sum(pressure[s] * matrix[s][j] for s in STAKEHOLDERS) / denom)
    return pressure, G


def revised_adjusted(W0, G, delta):
    if delta < 0:
        raise ValueError("delta must be non-negative in this candidate")
    if len(W0) != len(G):
        raise ValueError("W0/G dimension mismatch")
    raw = [w * (1 + delta * g) for w, g in zip(W0, G)]
    return normalize(raw)


def max_abs_change(a, b):
    return max(abs(x-y) for x,y in zip(a,b))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    group_rows = read_csv(GROUPS)
    prob_pro = {}
    for r in group_rows:
        g = r["stakeholder_group"]
        if g in STAKEHOLDERS:
            prob_pro[g] = float(r["mean_oof_pro_integration_probability"])
    missing = [s for s in STAKEHOLDERS if s not in prob_pro]
    if missing:
        raise RuntimeError(f"Missing stakeholder OOF probabilities: {missing}")

    # Base vector invariants.
    assert abs(sum(W0) - 1.0) < 1e-12
    assert all(w > 0 for w in W0)

    # Original implementation degeneracy for every stakeholder and delta tested.
    original_grid = []
    original_max_change = 0.0
    for delta in [0.0, 0.1, 0.3, 0.5, 0.8, 1.0]:
        for s in STAKEHOLDERS:
            wa = original_adjusted(W0, SIC[s], delta)
            change = max_abs_change(wa, W0)
            original_max_change = max(original_max_change, change)
            original_grid.append({
                "delta": delta, "stakeholder": s, "SIC": SIC[s],
                "max_abs_change_from_base_after_normalization": change,
                **{f"weight_{CRITERIA[j]}": wa[j] for j in range(len(CRITERIA))},
            })
    assert original_max_change < 1e-12

    pressure, G = criterion_pressure(prob_pro, ILLUSTRATIVE_A, use_contention=True)
    assert all(0 <= g <= 1 for g in G)

    revised_grid = []
    for delta in [0.0, 0.1, 0.3, 0.5, 0.8, 1.0]:
        w = revised_adjusted(W0, G, delta)
        assert abs(sum(w)-1.0) < 1e-12
        assert all(x > 0 for x in w)
        revised_grid.append({
            "delta": delta,
            "max_abs_change_from_base": max_abs_change(w, W0),
            **{f"pressure_{CRITERIA[j]}": G[j] for j in range(len(CRITERIA))},
            **{f"weight_{CRITERIA[j]}": w[j] for j in range(len(CRITERIA))},
        })

    # A uniform criterion relevance matrix should intentionally collapse to baseline.
    uniform_A = {s: [1.0]*len(CRITERIA) for s in STAKEHOLDERS}
    _, uniform_G = criterion_pressure(prob_pro, uniform_A, use_contention=True)
    uniform_w = revised_adjusted(W0, uniform_G, 0.3)
    assert max_abs_change(uniform_w, W0) < 1e-12

    # Non-degeneracy: illustrative criterion pressures differ, so delta>0 must change weights.
    revised_at_03 = revised_adjusted(W0, G, 0.3)
    assert max_abs_change(revised_at_03, W0) > 1e-6

    # Relative-ratio theorem numerical verification:
    # W*j/W*k = (W0j/W0k)*(1+dGj)/(1+dGk)
    ratio_checks = []
    delta = 0.3
    for j in range(len(CRITERIA)):
        for k in range(j+1, len(CRITERIA)):
            lhs = revised_at_03[j] / revised_at_03[k]
            rhs = (W0[j]/W0[k]) * ((1+delta*G[j])/(1+delta*G[k]))
            err = abs(lhs-rhs)
            assert err < 1e-12
            ratio_checks.append({"criterion_j":CRITERIA[j],"criterion_k":CRITERIA[k],"lhs":lhs,"rhs":rhs,"abs_error":err})

    # Monte Carlo formal stress test over arbitrary relevance matrices in [0,1].
    rng = random.Random(42)
    mc_n = 5000
    nondegenerate = 0
    max_sum_error = 0.0
    min_weight_seen = 1.0
    max_change_seen = 0.0
    for _ in range(mc_n):
        A = {s: [rng.random() for _ in CRITERIA] for s in STAKEHOLDERS}
        _, Gm = criterion_pressure(prob_pro, A, use_contention=True)
        wm = revised_adjusted(W0, Gm, 0.3)
        max_sum_error = max(max_sum_error, abs(sum(wm)-1.0))
        min_weight_seen = min(min_weight_seen, min(wm))
        c = max_abs_change(wm, W0)
        max_change_seen = max(max_change_seen, c)
        if c > 1e-10:
            nondegenerate += 1
    assert max_sum_error < 1e-12
    assert min_weight_seen > 0

    summary = {
        "stage": "candidate_corrected_swdc_mathematical_audit",
        "replication_revision_boundary": "This is a proposed SCIPRA revision, not a recovered historical implementation.",
        "original_implemented_formula": "W0_j*(1+delta*SIC), then vector normalization",
        "original_max_abs_weight_change_after_normalization_across_test_grid": original_max_change,
        "original_structural_result": "degenerate_common_scalar_cancels_exactly",
        "candidate_formula": {
            "contention_s": "1 - P_s(pro-integration)",
            "pressure_s": "SIC_s * contention_s",
            "criterion_pressure_G_j": "sum_s pressure_s*A_sj / sum_s pressure_s",
            "adjusted_weight": "W0_j*(1+delta*G_j) / sum_k W0_k*(1+delta*G_k)",
        },
        "candidate_properties_verified": {
            "positive_weights_for_delta_ge_0": True,
            "weights_sum_to_one": True,
            "returns_base_weights_at_delta_0": True,
            "returns_base_weights_if_all_criterion_pressures_equal": True,
            "nontrivial_relative_reweighting_if_criterion_pressures_differ": True,
            "relative_ratio_identity_verified": True,
        },
        "canonical_committed_group_probabilities_used_for_demonstration": prob_pro,
        "stakeholder_contention": {s: 1-prob_pro[s] for s in STAKEHOLDERS},
        "effective_pressure_SIC_times_contention": pressure,
        "illustrative_criterion_pressures": {CRITERIA[j]: G[j] for j in range(len(CRITERIA))},
        "illustrative_delta_0_3_adjusted_weights": {CRITERIA[j]: revised_at_03[j] for j in range(len(CRITERIA))},
        "illustrative_matrix_status": "illustrative_not_empirical_not_for_substantive_policy_claims",
        "base_weight_source_note": "Main text states Community Infrastructure base weight 0.10 but later narrative says 0.08->0.099; this candidate uses the normalized stated AHP vector with 0.10 and preserves the discrepancy as a source inconsistency.",
        "monte_carlo_formal_stress": {
            "random_relevance_matrices": mc_n,
            "delta": 0.3,
            "nondegenerate_runs": nondegenerate,
            "max_sum_to_one_error": max_sum_error,
            "minimum_positive_weight_seen": min_weight_seen,
            "maximum_abs_change_from_base_seen": max_change_seen,
        },
        "empirical_requirement_before_claiming_revised_SCIPRA_results": "Estimate A_sj transparently via preregistered criterion-specific text coding or expert elicitation; do not use the illustrative matrix as empirical evidence.",
    }

    def write_csv(path, rows):
        fields=[]
        for r in rows:
            for k in r:
                if k not in fields: fields.append(k)
        with path.open("w", encoding="utf-8", newline="") as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

    write_csv(OUT / "original_swdc_degeneracy_grid.csv", original_grid)
    write_csv(OUT / "corrected_swdc_illustrative_delta_grid.csv", revised_grid)
    write_csv(OUT / "corrected_swdc_ratio_checks.csv", ratio_checks)
    (OUT / "corrected_swdc_candidate_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True)+"\n", encoding="utf-8")

    report = f"""# Corrected SCIPRA Stakeholder-Weighting Candidate — Mathematical Audit

## Boundary

This is a **proposed revision**, not a reconstruction of the historical SWDC implementation.

The original code multiplies every criterion by one common `(1 + delta*SIC)` scalar and then normalizes. The audit reconfirms a maximum post-normalization weight change of **{original_max_change:.3e}** across all tested SIC/delta combinations: mathematically zero.

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
- {mc_n} random relevance-matrix stress tests preserved positivity and normalization; {nondegenerate}/{mc_n} were non-degenerate at delta=0.3

## Illustrative demonstration only

The included relevance matrix is **not empirical**. It merely reflects the manuscript's qualitative narrative sufficiently to demonstrate mathematical behavior. At delta=0.3, the illustrative adjusted investment weights are:

""" + "\n".join(f"- {c}: base {W0[j]:.4f} -> illustrative {revised_at_03[j]:.4f}" for j,c in enumerate(CRITERIA)) + """

These values must not be reported as revised SCIPRA empirical findings.

## What is required next

A publishable revised model needs `A_sj` from either:

1. preregistered criterion-specific text coding / NLP relevance scoring on the frozen corpus, or
2. transparent expert elicitation with inter-rater/reliability reporting.

Only after that matrix is independently justified should corrected stakeholder-weighted policy results be computed.
"""
    (OUT / "CORRECTED_SWDC_CANDIDATE_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
