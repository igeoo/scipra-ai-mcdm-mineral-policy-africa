"""Apply conservative Secondary Media Batch 02.

This batch resolves two defensible residual groups:

* low-context Marikana/Lonmin mentions in routine later corporate/project material
  are excluded as incidental/background;
* 2013-2014 labour/platinum-strike records are included only when Lonmin is
  actually present in the acquired article body, labour/event evidence is strong,
  and the generic title itself is labour/strike/wage/platinum-negotiation focused.

The 2014 platinum strike is prospectively declared in scope when Lonmin is
substantive. A lone historical Marikana reference without Lonmin is not enough.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "data" / "reconstruction"
EVIDENCE = RECON / "secondary_media_targeted_evidence.csv"
LEDGER = RECON / "secondary_media_substantive_decision_ledger.csv"
SUMMARY = RECON / "secondary_media_substantive_decision_summary.json"

LABOUR_TITLE = re.compile(
    r"\b(?:amcu|num|strike|strikers?|wage|wages|labour|labor|workers?|miners?|platinum|"
    r"collective bargaining|negotiat(?:e|es|ed|ing|ion|ions)|producers?|mining companies|"
    r"retrench(?:ment|ments)|job cuts?|job losses?|ccma|labour court)\b",
    re.I,
)


def read_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def i(v):
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


evidence = {r["candidate_id"]: r for r in read_rows(EVIDENCE)}
rows = read_rows(LEDGER)
if len(rows) != 1062 or len(evidence) != 1062:
    raise RuntimeError("Secondary evidence/ledger row count mismatch")

applied = Counter()
for d in rows:
    if d.get("decision_status") != "pending_substantive_review":
        continue
    e = evidence[d["candidate_id"]]
    klass = e.get("evidence_class", "")
    year = i(e.get("year"))
    lonmin_n = i(e.get("retrieved_lonmin_mentions"))
    event_d = i(e.get("event_distinct_terms"))
    title = e.get("title", "")

    if klass == "case_term_low_context_review":
        d.update({
            "decision_status": "final_secondary_batch_02",
            "final_decision": "exclude",
            "reason_code": "exclude_incidental_marikana_reference",
            "decision_note": (
                "Excluded after Batch-02 review: Marikana occurs only as low-context background/place/operation material in a routine "
                "corporate, project, management or market article, without substantive labour/justice/community case treatment."
            ),
            "decision_provenance": "secondary_batch_02_temporal_labour_review_2026-08-23",
        })
        applied[d["reason_code"]] += 1
        continue

    if klass == "lonmin_low_context_review":
        d.update({
            "decision_status": "final_secondary_batch_02",
            "final_decision": "exclude",
            "reason_code": "exclude_general_corporate_financial",
            "decision_note": (
                "Excluded after Batch-02 review: Lonmin is only low-context background in a routine finance, management, market, "
                "transaction or non-case operational article."
            ),
            "decision_provenance": "secondary_batch_02_temporal_labour_review_2026-08-23",
        })
        applied[d["reason_code"]] += 1
        continue

    # Prospective longitudinal inclusion: 2013-2014 labour/platinum-strike
    # coverage, but only with a real Lonmin body-text anchor and strong labour
    # evidence. This avoids admitting adjacent AMCU/other-producer stories that
    # mention Marikana only historically.
    if (
        klass in {"strong_case_context_supported", "possible_lonmin_substantive_context"}
        and year in {2013, 2014}
        and lonmin_n >= 1
        and event_d >= 4
        and LABOUR_TITLE.search(title or "")
    ):
        reason = "include_2014_platinum_strike_lonmin" if year == 2014 else "include_lonmin_marikana_labour_governance"
        d.update({
            "decision_status": "final_secondary_batch_02",
            "final_decision": "include",
            "reason_code": reason,
            "decision_note": (
                "Included under the predeclared longitudinal labour scope: acquired text confirms Lonmin is part of a substantive "
                "2013-2014 AMCU/NUM/wage/strike/platinum-labour story with at least four distinct labour/event signals."
            ),
            "decision_provenance": "secondary_batch_02_temporal_labour_review_2026-08-23",
        })
        applied[reason] += 1

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
    "batch_02_applied_counts": dict(applied),
    "pending_evidence_class_counts": dict(Counter(evidence[r["candidate_id"]]["evidence_class"] for r in pending)),
    "important_note": (
        "Batch 02 excludes low-context background references and admits only 2013-2014 labour/platinum-strike records with an actual "
        "Lonmin body-text anchor plus strong labour evidence. Other later or weakly anchored records remain pending."
    ),
}
SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
