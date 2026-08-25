"""Read-only verification of the frozen SCIPRA computational package.

This verifier uses only committed files. It does not access the network, change
corpus membership, relabel records, fit models, or rewrite outputs.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return sum(1 for _ in csv.reader(f)) - 1


def verify_flat_hash_manifest(manifest_path: Path, base_dir: Path) -> int:
    payload = load_json(manifest_path)
    assert payload.get("algorithm") == "sha256", manifest_path
    checked = 0
    for name, expected in payload.items():
        if name == "algorithm":
            continue
        path = base_dir / name
        assert path.is_file(), f"Missing frozen file: {path}"
        actual = sha256(path)
        assert actual == expected, f"SHA mismatch: {path}: {actual} != {expected}"
        checked += 1
    return checked


def verify_nested_hash_manifest(manifest_path: Path, base_dir: Path) -> int:
    payload = load_json(manifest_path)
    assert payload.get("algorithm") == "sha256", manifest_path
    files = payload.get("files")
    assert isinstance(files, dict) and files, manifest_path
    for name, expected in files.items():
        path = base_dir / name
        assert path.is_file(), f"Missing frozen file: {path}"
        actual = sha256(path)
        assert actual == expected, f"SHA mismatch: {path}: {actual} != {expected}"
    return len(files)


def main() -> None:
    recon_dir = ROOT / "data" / "reconstruction"
    post_dir = ROOT / "data" / "post_freeze_analysis"
    revision_dir = ROOT / "data" / "revision_analysis"

    checked_hashes = 0
    checked_hashes += verify_flat_hash_manifest(recon_dir / "corpus_freeze_hashes.json", recon_dir)
    checked_hashes += verify_flat_hash_manifest(post_dir / "post_freeze_analysis_hashes.json", post_dir)
    checked_hashes += verify_nested_hash_manifest(revision_dir / "revision_freeze_hashes.json", revision_dir)

    corpus = load_json(recon_dir / "corpus_freeze_summary.json")
    assert corpus["corpus_frozen"] is True
    assert corpus["reconstructed_corpus_records"] == 886
    assert corpus["analysis_ready_records"] == 876
    assert corpus["retained_non_analysis_ready_quality_exceptions"] == 10
    assert corpus["historical_reported_corpus_size_benchmark_only"] == 87
    assert corpus["historical_size_used_as_target_or_quota"] is False
    assert csv_rows(recon_dir / "canonical_reconstructed_replication_corpus.csv") == 886
    assert csv_rows(recon_dir / "canonical_analysis_ready_manifest.csv") == 876

    recon = load_json(post_dir / "annotation_count_reconciliation.json")
    assert recon["total_frozen_records"] == 876
    assert recon["total_recovered_records"] == 873
    assert recon["labeled_not_in_review_queue"] == 687
    assert recon["labeled_but_in_stakeholder_review_queue"] == 48
    assert recon["unlabeled_recovered_records_in_stance_review_queue"] == 138
    assert recon["text_unavailable_records_in_review_queue"] == 3
    assert recon["total_review_queue_records"] == 189
    assert 687 + 48 + 138 + 3 == 876
    assert 48 + 138 + 3 == 189

    stance = load_json(post_dir / "reconstructed_stance_summary.json")
    assert stance["final_model_eligible_labelled_records"] == 807
    assert stance["observed_reconstructed_class_counts"] == {"0": 730, "1": 77}
    assert stance["unresolved_records_excluded_from_model"] == 69
    assert stance["historical_reported_71_16_used_as_target"] is False
    assert stance["human_annotation_recreated"] is False
    assert csv_rows(post_dir / "reconstructed_stance_labels_final.csv") == 807
    assert csv_rows(post_dir / "reconstructed_stance_unresolved.csv") == 69

    post = load_json(post_dir / "post_freeze_analysis_summary.json")
    assert post["final_model_eligible_labelled_records"] == 807
    assert post["final_stakeholder_resolved_records"] == 776
    assert post["historical_71_16_used_as_target"] is False
    assert post["historical_labels_recovered"] is False

    mcdm = load_json(post_dir / "mcdm_reproducibility_audit.json")
    swdc = mcdm["swdc_equation_audit"]
    assert swdc["reproducibility_status"] == "underdetermined_for_full_dynamic_criterion_vector"
    max_changes = [
        v["maximum_absolute_change_after_normalisation"]
        for v in swdc["scalar_normalisation_demonstration"].values()
    ]
    assert max(max_changes) <= 1e-12

    revision = load_json(revision_dir / "revision_freeze_summary.json")
    assert revision["stage"] == "frozen_revision_analysis"
    assert revision["frozen_analysis_ready_records"] == 876
    assert revision["final_reconstructed_stance"]["resistant"] == 730
    assert revision["final_reconstructed_stance"]["pro_integration"] == 77
    assert revision["final_reconstructed_stance"]["unresolved"] == 69
    assert revision["historical_71_16_used_as_target"] is False
    assert revision["historical_corpus_exactly_recovered"] is False
    assert revision["historical_human_labels_recovered"] is False
    assert revision["original_swdc_status"] == "degenerate_common_scalar_cancels_exactly"
    assert revision["semantic_sensitivity"]["status"] == "sensitivity_only_does_not_replace_preregistered_primary"

    forbidden = [
        ROOT / "SCIPRA_04052026.docx",
        ROOT / "appendices" / "SCIPRA_Supplementary_Material.docx",
        ROOT / "appendices" / "SCIPRA_SI_References.docx",
    ]
    for path in forbidden:
        assert not path.exists(), f"Unpublished manuscript/submission artifact is tracked: {path}"

    print(
        json.dumps(
            {
                "status": "verified",
                "sha256_files_checked": checked_hashes,
                "reconstructed_corpus_records": 886,
                "analysis_ready_records": 876,
                "final_stance": {"resistant": 730, "pro_integration": 77, "unresolved": 69},
                "annotation_partition": "687 + 48 + 138 + 3 = 876",
                "manuscript_artifacts_present": False,
                "network_access_used": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
