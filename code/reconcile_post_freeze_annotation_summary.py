from pathlib import Path
import csv, json
from collections import Counter

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / 'data' / 'post_freeze_analysis'
DRAFT = DATA / 'reconstructed_annotation_draft.csv'
RECOVERY = DATA / 'post_freeze_recovery_status.csv'
OUT = DATA / 'annotation_pass_summary.json'
RECON = DATA / 'annotation_count_reconciliation.json'
EXPECTED_MANIFEST_SHA = 'cb280e4cb138b2f6bba48b24f0dcd7521c4cb821871846ceb70523a05a7acad5'


def read_csv(path):
    with path.open('r', encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def main():
    rows = read_csv(DRAFT)
    recovery = read_csv(RECOVERY)
    assert len(rows) == 876, len(rows)
    assert len(recovery) == 876, len(recovery)

    recovered_ids = {
        r['record_id'] for r in recovery
        if r.get('execution_recovery_status') == 'retrieved_extracted'
    }
    unavailable_ids = {r['record_id'] for r in recovery} - recovered_ids

    labeled = [r for r in rows if r.get('draft_reconstructed_label', '') != '']
    review = [r for r in rows if r.get('needs_review') == 'true']
    labeled_review = [r for r in labeled if r.get('needs_review') == 'true']
    labeled_no_review = [r for r in labeled if r.get('needs_review') != 'true']
    unlabeled_recovered_review = [
        r for r in review
        if r['record_id'] in recovered_ids and r.get('draft_reconstructed_label', '') == ''
    ]
    unavailable_review = [r for r in review if r['record_id'] in unavailable_ids]
    recovered_review = [r for r in review if r['record_id'] in recovered_ids]
    usable_readings = [r for r in rows if r.get('stance_a_label', '') != '' and r.get('stance_b_label', '') != '']

    # Exhaustive/disjoint reconciliation.
    assert len(recovered_ids) == 873
    assert len(unavailable_ids) == 3
    assert len(labeled) == 735
    assert len(review) == 189
    assert len(labeled_review) == 48
    assert len(labeled_no_review) == 687
    assert len(unlabeled_recovered_review) == 138
    assert len(unavailable_review) == 3
    assert len(recovered_review) == 186
    assert len(usable_readings) == 873
    assert len(labeled_no_review) + len(labeled_review) + len(unlabeled_recovered_review) == 873
    assert len(labeled_no_review) + len(labeled_review) + len(unlabeled_recovered_review) + len(unavailable_review) == 876
    assert len(labeled_review) + len(unlabeled_recovered_review) + len(unavailable_review) == 189

    stakeholder_counts = Counter(
        r.get('stakeholder_group_proxy', '')
        for r in rows if r['record_id'] in recovered_ids
    )
    stakeholder_counts.pop('', None)
    assert sum(stakeholder_counts.values()) == 873

    label_counts = Counter(r['draft_reconstructed_label'] for r in labeled)
    agreement = sum(r['stance_a_label'] == r['stance_b_label'] for r in usable_readings) / len(usable_readings)

    summary = {
        'stage': 'post_freeze_computational_reannotation_pass_1_reconciled',
        'frozen_analysis_manifest_sha256': EXPECTED_MANIFEST_SHA,
        'frozen_analysis_ready_records': 876,
        'texts_recovered_for_execution': 873,
        'texts_unavailable_at_execution': 3,
        'computational_readings_agreement_rate_on_recovered_text': agreement,
        'draft_labels_assigned_total': 735,
        'draft_label_counts': dict(label_counts),
        'labeled_not_in_review_queue': 687,
        'labeled_but_in_stakeholder_review_queue': 48,
        'unlabeled_recovered_records_in_stance_review_queue': 138,
        'text_unavailable_records_in_review_queue': 3,
        'review_queue_records_total': 189,
        'review_queue_recovered_records': 186,
        'review_queue_overlap_with_labeled_records': 48,
        'reconciliation': {
            'recovered_text_partition': '687 labeled/no-review + 48 labeled/stakeholder-review + 138 unlabeled/stance-review = 873',
            'full_frozen_partition': '687 + 48 + 138 + 3 unavailable = 876',
            'review_queue_partition': '48 labeled/stakeholder-review + 138 unlabeled/stance-review + 3 unavailable = 189',
            'counts_are_disjoint_only_within_the_explicit_partition_above': True,
        },
        'stakeholder_proxy_counts_recovered': dict(stakeholder_counts),
        'historical_71_16_distribution_used_as_target': False,
        'legacy_svm_labels_used': False,
        'human_annotation_claim': False,
        'model_fitting_performed': False,
        'important_limitation': (
            'These are reconstructed computational annotations applying the documented B.4.2 criteria. '
            'They do not reproduce the unavailable historical two-human-annotator labels. The review queue '
            'overlaps the labeled set for 48 records whose stance was assigned but stakeholder attribution '
            'remains low-confidence.'
        ),
    }
    OUT.write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    RECON.write_text(json.dumps(summary['reconciliation'] | {
        'frozen_analysis_manifest_sha256': EXPECTED_MANIFEST_SHA,
        'computational_readings_agreement_rate_on_recovered_text': agreement,
        'labeled_not_in_review_queue': 687,
        'labeled_but_in_stakeholder_review_queue': 48,
        'unlabeled_recovered_records_in_stance_review_queue': 138,
        'text_unavailable_records_in_review_queue': 3,
        'total_frozen_records': 876,
        'total_recovered_records': 873,
        'total_review_queue_records': 189,
    }, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
