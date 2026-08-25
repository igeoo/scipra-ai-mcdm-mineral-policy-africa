"""Deterministic post-freeze audit of SCIPRA's MCDM/PCI/RPCI mathematics.

This audit does not use stance labels and cannot alter the frozen corpus.  It
separates formulas that are fully specified from the SWDC criterion reweighting
step, whose present scalar-SIC implementation becomes invariant after
normalisation unless criterion/stakeholder-specific sensitivity is supplied.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "post_freeze_analysis"
OUT.mkdir(parents=True, exist_ok=True)

SCENARIO_CSV = OUT / "scenario_formula_validation.csv"
MCDM_JSON = OUT / "mcdm_reproducibility_audit.json"
HASHES_JSON = OUT / "mathematical_audit_hashes.json"

W = (0.30, 0.35, 0.35)
LAMBDA = 0.10
SCENARIOS = {
    "A_pre_intervention": (0.82, 0.48, 0.12),
    "B_regulatory_emphasis": (0.70, 0.75, 0.55),
    "C_scipra_optimised": (0.75, 0.80, 0.79),
}
# Values explicitly stated in the main text / SI narrative for cross-check only.
MANUSCRIPT_STATED = {
    "A_pre_intervention": {"pci": 0.456, "rpci_main_text": 0.427, "rpci_si_normalised": 0.407},
    "B_regulatory_emphasis": {"pci": 0.665, "rpci_main_text": 0.638, "rpci_si_normalised": 0.638},
    "C_scipra_optimised": {"pci": 0.781, "rpci_main_text": 0.752, "rpci_si_normalised": 0.752},
}

PLU = {
    "government": (0.82, 0.58, 0.75),
    "investor": (0.88, 0.65, 0.82),
    "community": (0.32, 0.92, 0.95),
    "NGO": (0.52, 0.80, 0.70),
    "labour": (0.75, 0.78, 0.90),
}
EXPECTED_SIC = {
    "government": 0.703,
    "investor": 0.770,
    "community": 0.749,
    "NGO": 0.686,
    "labour": 0.807,
}

INVESTMENT_BASE_WEIGHTS = {
    "NPV": 0.25,
    "IRR": 0.20,
    "Geological Feasibility": 0.15,
    "Market Stability": 0.15,
    "Local Employment": 0.15,
    "Community Infrastructure": 0.10,
}


def pci(vals):
    return sum(w * x for w, x in zip(W, vals))


def weighted_sigma(vals):
    mu = pci(vals)
    return math.sqrt(sum(w * (x - mu) ** 2 for w, x in zip(W, vals)))


def rpci_raw(vals):
    return max(0.0, pci(vals) - LAMBDA * weighted_sigma(vals))


def rpci_norm(vals):
    return rpci_raw(vals) / (1 + LAMBDA / 2)


def nonlinear_pci(vals, beta=0.5):
    lin = pci(vals)
    if any(v <= 0 for v in vals):
        hm = lin
    else:
        hm = 1 / sum(w / v for w, v in zip(W, vals))
    return beta * lin + (1 - beta) * hm


def sic(plu):
    p, l, u = plu
    return 0.30 * p + 0.40 * l + 0.30 * u


def normalised_scalar_swdc(base: dict[str, float], scalar_sic: float, delta=0.30):
    raw = {k: v * (1 + delta * scalar_sic) for k, v in base.items()}
    den = sum(raw.values())
    return raw, {k: v / den for k, v in raw.items()}


def sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    rows = []
    for name, vals in SCENARIOS.items():
        stated = MANUSCRIPT_STATED[name]
        calc = {
            "scenario": name,
            "investment": vals[0],
            "regulatory": vals[1],
            "stakeholder": vals[2],
            "pci_formula": pci(vals),
            "weighted_sigma_formula": weighted_sigma(vals),
            "rpci_raw_formula": rpci_raw(vals),
            "rpci_normalised_A10_formula": rpci_norm(vals),
            "nonlinear_pci_weighted_harmonic_blend": nonlinear_pci(vals),
            "manuscript_stated_pci": stated["pci"],
            "manuscript_stated_rpci_main_text": stated["rpci_main_text"],
            "manuscript_stated_rpci_si_normalised": stated["rpci_si_normalised"],
            "delta_pci_formula_minus_stated": pci(vals) - stated["pci"],
            "delta_rpci_norm_formula_minus_si_stated": rpci_norm(vals) - stated["rpci_si_normalised"],
        }
        rows.append(calc)

    with SCENARIO_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)

    sic_rows = {g: sic(v) for g, v in PLU.items()}
    sic_checks = {
        g: {
            "P": PLU[g][0], "L": PLU[g][1], "U": PLU[g][2],
            "calculated_sic": value,
            "manuscript_sic": EXPECTED_SIC[g],
            "absolute_difference": abs(value - EXPECTED_SIC[g]),
        }
        for g, value in sic_rows.items()
    }

    # Demonstrate the normalization cancellation using every documented scalar SIC.
    swdc_demo = {}
    for group, s in sic_rows.items():
        raw, normalised = normalised_scalar_swdc(INVESTMENT_BASE_WEIGHTS, s, 0.30)
        swdc_demo[group] = {
            "scalar_sic": s,
            "raw_adjusted_weights": raw,
            "renormalised_weights": normalised,
            "maximum_absolute_change_after_normalisation": max(
                abs(normalised[k] - INVESTMENT_BASE_WEIGHTS[k]) for k in INVESTMENT_BASE_WEIGHTS
            ),
        }

    # Specific published examples, checked against the written equation without inventing a mapping.
    community_raw_local_employment = 0.15 * (1 + 0.30 * EXPECTED_SIC["community"])
    labour_raw_local_employment = 0.15 * (1 + 0.30 * EXPECTED_SIC["labour"])
    community_raw_infrastructure_from_010 = 0.10 * (1 + 0.30 * EXPECTED_SIC["community"])
    community_raw_infrastructure_from_008 = 0.08 * (1 + 0.30 * EXPECTED_SIC["community"])

    audit = {
        "stage": "post_freeze_mcdm_and_index_formula_audit",
        "corpus_membership_used_or_modified": False,
        "fully_reproducible_components": [
            "SIC arithmetic from documented P/L/U and alpha=0.30 beta=0.40 gamma=0.30",
            "linear PCI with domain weights 0.30/0.35/0.35",
            "weighted cross-domain standard deviation",
            "RPCI raw = max(0, PCI - lambda*sigma)",
            "RPCI normalised per SI Eq A.10 = raw/(1+lambda/2)",
            "weighted-harmonic nonlinear PCI as currently implemented",
        ],
        "sic_verification": sic_checks,
        "swdc_equation_audit": {
            "documented_equation": "W_a = W_0 * (1 + delta * SIC)",
            "delta_used": 0.30,
            "finding": "Applying one scalar SIC to every criterion and then renormalising multiplies all criteria by the same constant, so relative weights return exactly to W_0. A criterion-specific stakeholder/sensitivity mapping is required for non-trivial reweighting, but that mapping is not encoded in the current adjust_weights implementation.",
            "scalar_normalisation_demonstration": swdc_demo,
            "published_example_cross_checks": {
                "local_employment_base_0_15_with_community_sic_raw": community_raw_local_employment,
                "local_employment_base_0_15_with_labour_sic_raw": labour_raw_local_employment,
                "published_local_employment_adjusted_claim": 0.184,
                "community_infrastructure_base_0_10_with_community_sic_raw": community_raw_infrastructure_from_010,
                "community_infrastructure_base_0_08_with_community_sic_raw": community_raw_infrastructure_from_008,
                "published_community_infrastructure_adjusted_claim": 0.099,
                "note": "The narrative gives Community Infrastructure base weight as 0.10 in the investment vector but later describes 0.08 -> 0.099. The latter is close to the unnormalised scalar equation using 0.08; it is not consistent with the stated 0.10 base vector. Local Employment 0.15 -> 0.184 is close to a single unnormalised community-SIC adjustment, not to a fully renormalised multi-criterion vector."
            },
            "reproducibility_status": "underdetermined_for_full_dynamic_criterion_vector",
        },
        "rpci_consistency_audit": {
            "finding": "Scenario A is explicitly acknowledged in the SI as 0.427 raw versus about 0.407 normalised. Applying the stated normalised A.10 equation to the documented B and C domain scores also yields values different from 0.638 and 0.752. The formula outputs are retained as authoritative computational results and manuscript-stated values are preserved separately for audit rather than forced to match.",
            "scenario_validation_file": SCENARIO_CSV.name,
        },
        "important_constraint": "No missing criterion-to-stakeholder mapping, sensitivity schedule, or manuscript value is back-filled by assumption. This audit marks under-specified components rather than manufacturing reproducibility.",
    }
    MCDM_JSON.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    hashes = {SCENARIO_CSV.name: sha(SCENARIO_CSV), MCDM_JSON.name: sha(MCDM_JSON)}
    HASHES_JSON.write_text(json.dumps({"algorithm": "sha256", **hashes}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
