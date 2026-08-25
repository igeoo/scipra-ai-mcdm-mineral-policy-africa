"""Freeze the completed SCIPRA revision-analysis outputs with SHA-256 integrity metadata.

This is a static post-analysis step. It must not reacquire sources, alter corpus
membership, relabel records, or recompute the substantive revision results.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "revision_analysis"

REQUIRED = [
    "stance_robustness_summary.json",
    "STANCE_ROBUSTNESS_REPORT.md",
    "stance_adjudication_sensitivity_grid.csv",
    "stance_source_phase_breakdown.csv",
    "stance_publisher_breakdown_n_ge_5.csv",
    "corrected_swdc_candidate_summary.json",
    "CORRECTED_SWDC_CANDIDATE_REPORT.md",
    "criterion_relevance_summary.json",
    "criterion_relevance_matrix.csv",
    "criterion_relevance_document_audit.csv",
    "criterion_relevance_matrix_sensitivity.csv",
    "revision_component_ablation.json",
    "criterion_semantic_sensitivity_summary.json",
    "criterion_semantic_sensitivity_matrix.csv",
    "criterion_semantic_sensitivity_document_audit.csv",
    "CRITERION_RELEVANCE_PROTOCOL.md",
    "NOVELTY_POSITIONING.md",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    missing = [x for x in REQUIRED if not (OUT / x).exists()]
    if missing:
        raise SystemExit(f"Cannot freeze revision analysis; missing: {missing}")

    stance = json.loads((OUT / "stance_robustness_summary.json").read_text(encoding="utf-8"))
    rel = json.loads((OUT / "criterion_relevance_summary.json").read_text(encoding="utf-8"))
    sem = json.loads((OUT / "criterion_semantic_sensitivity_summary.json").read_text(encoding="utf-8"))
    swdc = json.loads((OUT / "corrected_swdc_candidate_summary.json").read_text(encoding="utf-8"))

    assert stance["frozen_analysis_ready_records"] == 876
    assert stance["final_reconstructed_ledger"]["resistant"] == 730
    assert stance["final_reconstructed_ledger"]["pro_integration"] == 77
    assert stance["final_reconstructed_ledger"]["unresolved"] == 69
    assert swdc["original_structural_result"] == "degenerate_common_scalar_cancels_exactly"
    assert rel["eligible_resolved_stakeholder_records"] == 776
    assert rel["historical_parameter_recovery_claim"] is False
    assert sem["status"] == "sensitivity_only_does_not_replace_preregistered_primary"
    assert sem["fresh_recovered_total"] >= 770

    hashes = {name: sha256(OUT / name) for name in REQUIRED}
    hash_payload = {
        "algorithm": "sha256",
        "stage": "frozen_revision_analysis",
        "files": hashes,
    }
    (OUT / "revision_freeze_hashes.json").write_text(
        json.dumps(hash_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    summary = {
        "stage": "frozen_revision_analysis",
        "replication_revision_boundary": "Revision outputs are downstream of and separate from the frozen reconstruction/post-freeze replication outputs.",
        "frozen_analysis_ready_records": 876,
        "final_reconstructed_stance": stance["final_reconstructed_ledger"],
        "historical_reported_distribution": stance["historical_reported_distribution"],
        "maximum_pro_fraction_across_adjudication_grid": stance["adjudication_grid"]["maximum_pro_fraction_among_labelled_across_grid"],
        "maximum_possible_pro_fraction_with_all_grid_unresolved_pro": stance["adjudication_grid"]["maximum_possible_pro_fraction_across_grid_even_if_every_unresolved_record_is_pro"],
        "original_swdc_status": swdc["original_structural_result"],
        "criterion_relevance_recovered_records": rel["freshly_recovered_records"],
        "criterion_relevance_primary_delta_0_3_weights": rel["primary_delta_0_3_salience_times_contention_weights"],
        "semantic_sensitivity": {
            "status": sem["status"],
            "fresh_recovered_total": sem["fresh_recovered_total"],
            "employment_strict_local_employment_change_from_base": sem["employment_strict_local_employment_change_from_base"],
            "finance_broad_employment_strict_local_employment_change_from_base": sem["finance_broad_strict_local_employment_change_from_base"],
            "finance_broad_NPV_change_from_base": sem["finance_broad_NPV_change_from_base"],
            "finance_broad_IRR_change_from_base": sem["finance_broad_IRR_change_from_base"],
            "max_abs_weight_difference_primary_vs_employment_strict": sem["max_abs_weight_difference_primary_vs_employment_strict"],
            "max_abs_weight_difference_primary_vs_finance_broad_strict": sem["max_abs_weight_difference_primary_vs_finance_broad_strict"],
        },
        "historical_corpus_exactly_recovered": False,
        "historical_human_labels_recovered": False,
        "historical_71_16_used_as_target": False,
        "revised_swdc_claim": "proposed corrected architecture, not recovered historical implementation",
        "hash_manifest": "revision_freeze_hashes.json",
    }
    (OUT / "revision_freeze_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    readme = f"""# SCIPRA Revision Analysis — Frozen Handoff\n\nThis folder is the frozen downstream revision layer. It does **not** alter the frozen reconstructed corpus or historical-replication outputs.\n\n## Empirical robustness\n\n- Frozen analysis-ready corpus: **876**\n- Final reconstructed labels: **730 resistant / 77 pro-integration / 69 unresolved**\n- Historical reported stance: **71 pro-integration / 16 resistant**\n- The historical split was never used as a selection or annotation target.\n- Across the adjudication sensitivity grid, the resistant-dominant result remains intact.\n\n## Mathematical finding\n\nThe historical scalar-SIC SWDC implementation is structurally degenerate after normalization. The proposed revision introduces explicit stakeholder-by-criterion relevance before normalization and is kept clearly separate from historical replication.\n\n## Evidence-derived revision\n\nThe primary criterion-relevance analysis recovered **{rel['freshly_recovered_records']}/776** resolved-stakeholder records. Its matrix estimates documentary issue prevalence, not expert preference strength.\n\n## Semantic sensitivity\n\nThe post-hoc semantic audit recovered **{sem['fresh_recovered_total']}** records. It tests stricter employment semantics and broader financial semantics and is sensitivity-only; it does not replace the preregistered primary specification. The strong primary Local Employment upweighting is not semantically robust, while Community Infrastructure remains upweighted in the tested variants.\n\n## Integrity\n\nSee `revision_freeze_hashes.json` for SHA-256 hashes of the required frozen revision files.\n"""
    (OUT / "REVISION_FREEZE_README.md").write_text(readme, encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
