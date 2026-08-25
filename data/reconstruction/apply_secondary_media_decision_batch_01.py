"""Apply conservative Batch 01 decisions to the 1,062 secondary media records.

The secondary queue was defined solely because URL titles contained neither a
high-specificity Marikana term nor Lonmin. The acquired-text pass has now read
all 1,062 source pages. This decision batch therefore uses body-text evidence:

1. Exclude records with *zero* Marikana-case mentions and zero Lonmin mentions.
   Sibanye-only coverage is not sufficient for the strict Sibanye-Marikana /
   Lonmin case corpus; relevant ownership-transition material should retain a
   Lonmin/Marikana anchor.
2. Exclude Marikana-name-only routine project/corporate records already isolated
   by the evidence classifier.
3. Include all `strong_lonmin_context_supported` records, which require repeated
   Lonmin mention plus strong labour/social/governance context.
4. Include only a guarded subset of `strong_case_context_supported` records when
   evidence is highly specific enough to avoid geographic homonym/analogy risk.
5. Leave every other Marikana/Lonmin-bearing record pending.

No stance labels, historical class targets or model outputs are used.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "data" / "reconstruction"
EVIDENCE = RECON / "secondary_media_targeted_evidence.csv"
LEDGER = RECON / "secondary_media_substantive_decision_ledger.csv"
SUMMARY = RECON / "secondary_media_substantive_decision_summary.json"

NO_ANCHOR_CLASSES = {
    "no_case_anchor",
    "strong_routine_no_case_anchor",
    "sibanye_context_without_case_anchor_review",
    "ambiguous_secondary_review",
}


def read_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def i(v) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def strong_case_guard(r: dict[str, str]) -> bool:
    terms = {x for x in (r.get("case_terms") or "").split(";") if x}
    events = {x for x in (r.get("event_terms") or "").split(";") if x}
    social = {x for x in (r.get("social_terms") or "").split(";") if x}
    high_specific = bool(terms & {"farlam", "wonderkop", "nkaneng", "bapo"})
    lonmin_n = i(r.get("retrieved_lonmin_mentions"))
    case_n = i(r.get("case_mentions_total"))
    event_d = i(r.get("event_distinct_terms"))

    # The guard deliberately does NOT use housing/community alone because a
    # different Cape Town informal settlement is also named Marikana.
    justice_process = bool(social & {"justice_accountability", "commission_inquiry"})
    return (
        high_specific
        or lonmin_n >= 2
        or (case_n >= 2 and event_d >= 4)
        or (case_n >= 2 and event_d >= 3 and justice_process)
    )


source = read_rows(EVIDENCE)
if len(source) != 1062:
    raise RuntimeError(f"Expected 1062 secondary evidence records, found {len(source)}")

rows = []
applied = Counter()
for r in source:
    klass = r.get("evidence_class", "")
    case_n = i(r.get("case_mentions_total"))
    lonmin_n = i(r.get("retrieved_lonmin_mentions"))

    decision_status = "pending_substantive_review"
    decision = ""
    reason = "review_ambiguous"
    note = "Marikana/Lonmin-bearing secondary record retained for further substantive review."

    if klass in NO_ANCHOR_CLASSES:
        # Verify the classifier invariant rather than relying on its label.
        if case_n != 0 or lonmin_n != 0:
            raise RuntimeError(
                f"No-anchor class invariant failed for {r.get('candidate_id')}: "
                f"class={klass} case_mentions={case_n} lonmin_mentions={lonmin_n}"
            )
        decision_status = "final_secondary_batch_01"
        decision = "exclude"
        reason = "exclude_no_marikana_lonmin_case_anchor"
        note = (
            "Excluded after acquired-text review: the article contains no Marikana/Farlam/Wonderkop/Nkaneng/Bapo case term and no "
            "Lonmin mention. Sibanye-only or unrelated coverage is insufficient for the strict Marikana/Lonmin case corpus."
        )
        applied[reason] += 1
    elif klass == "case_name_only_routine_project_or_corporate_signal":
        decision_status = "final_secondary_batch_01"
        decision = "exclude"
        reason = "exclude_general_corporate_financial"
        note = (
            "Excluded after acquired-text review: a Marikana-related name occurs, but substantive focus is routine project, production "
            "or corporate material without case-central labour/justice/community treatment."
        )
        applied[reason] += 1
    elif klass == "strong_lonmin_context_supported":
        decision_status = "final_secondary_batch_01"
        decision = "include"
        reason = "include_lonmin_marikana_labour_governance"
        note = (
            "Included under the prospectively declared longitudinal scope: repeated Lonmin mention is combined with strong labour, "
            "event, social or governance context despite a generic URL title."
        )
        applied[reason] += 1
    elif klass == "strong_case_context_supported" and strong_case_guard(r):
        decision_status = "final_secondary_batch_01"
        decision = "include"
        reason = "include_case_central"
        note = (
            "Included after guarded body-text review: the generic-title article contains high-specificity Marikana-case evidence "
            "reinforced by Lonmin, highly specific case terms, strong multi-dimensional event context, or justice/commission context."
        )
        applied[reason] += 1

    rows.append({
        "candidate_id": r.get("candidate_id", ""),
        "title": r.get("title", ""),
        "year": r.get("year", ""),
        "publication_date_from_url": r.get("publication_date_from_url", ""),
        "publisher": r.get("publisher", ""),
        "url": r.get("url", ""),
        "retrieved_text_words": r.get("retrieved_text_words", ""),
        "retrieved_text_sha256": r.get("retrieved_text_sha256", ""),
        "retrieved_lonmin_mentions": r.get("retrieved_lonmin_mentions", ""),
        "retrieved_sibanye_mentions": r.get("retrieved_sibanye_mentions", ""),
        "case_terms": r.get("case_terms", ""),
        "case_mentions_total": r.get("case_mentions_total", ""),
        "event_terms": r.get("event_terms", ""),
        "event_distinct_terms": r.get("event_distinct_terms", ""),
        "social_terms": r.get("social_terms", ""),
        "social_distinct_terms": r.get("social_distinct_terms", ""),
        "corporate_terms": r.get("corporate_terms", ""),
        "corporate_distinct_terms": r.get("corporate_distinct_terms", ""),
        "evidence_class": klass,
        "decision_status": decision_status,
        "final_decision": decision,
        "reason_code": reason,
        "decision_note": note,
        "decision_provenance": "secondary_batch_01_acquired_text_2026-08-23",
    })

rows.sort(key=lambda x: x["candidate_id"])
with LEDGER.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)

final_rows = [r for r in rows if r["decision_status"].startswith("final_")]
pending = [r for r in rows if r["decision_status"] == "pending_substantive_review"]
summary = {
    "ledger_scope": "1062_secondary_keyword_archive_media_candidates",
    "records_in_ledger": len(rows),
    "final_decisions_made": len(final_rows),
    "final_inclusions": sum(r["final_decision"] == "include" for r in final_rows),
    "final_exclusions": sum(r["final_decision"] == "exclude" for r in final_rows),
    "pending_substantive_review": len(pending),
    "decision_status_counts": dict(Counter(r["decision_status"] for r in rows)),
    "reason_code_counts": dict(Counter(r["reason_code"] for r in rows)),
    "batch_01_applied_counts": dict(applied),
    "pending_evidence_class_counts": dict(Counter(r["evidence_class"] for r in pending)),
    "important_note": (
        "Secondary Batch 01 excludes only acquired-text records lacking a Marikana/Lonmin anchor plus isolated routine project/corporate "
        "name matches, and includes only strong/guarded case evidence. All remaining Marikana/Lonmin-bearing records stay pending. "
        "No stance labels, class targets or model outputs were used."
    ),
}
SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
