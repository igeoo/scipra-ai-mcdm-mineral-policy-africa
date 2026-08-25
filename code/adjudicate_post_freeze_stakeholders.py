"""Conservatively adjudicate low-confidence stakeholder attribution after stance finalization.

This script does not alter corpus membership or reconstructed stance labels.
It only creates a separate final stakeholder-attribution ledger for downstream
stakeholder aggregation.  Pass-1 high-confidence/document-author assignments
are retained.  Low-confidence media proxies are re-read using strong title
subject evidence and attributed-voice dominance.  Cases without a clear margin
remain unresolved and are excluded from stakeholder-group aggregation rather
than receiving a forced group assignment.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from post_freeze_annotation_pass import fetch_one, GROUP_RE, SPEECH, sentence_units

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "post_freeze_analysis"
LABELS = OUT / "reconstructed_stance_labels_final.csv"
LABEL_SUMMARY = OUT / "reconstructed_stance_summary.json"
LEDGER = OUT / "reconstructed_stakeholder_attribution_final.csv"
UNRESOLVED = OUT / "reconstructed_stakeholder_attribution_unresolved.csv"
SUMMARY = OUT / "reconstructed_stakeholder_attribution_summary.json"
HASHES = OUT / "reconstructed_stakeholder_attribution_hashes.json"
EXPECTED_MANIFEST_SHA = "cb280e4cb138b2f6bba48b24f0dcd7521c4cb821871846ceb70523a05a7acad5"

STRONG_TITLE = {
    "government": [
        r"\bsaps\b", r"\bpolice\b", r"\bminister\b", r"\bgovernment\b", r"\bparliament\b",
        r"\bdepartment\b", r"\bcommission\b", r"\bramaphosa\b", r"\bcele\b", r"\bmthethwa\b",
    ],
    "investor": [
        r"\blonmin\b", r"\bsibanye(?:-stillwater)?\b", r"\bfroneman\b", r"\bmagara\b",
        r"\bshareholders?\b", r"\bmine operator\b", r"\bplatinum producer\b",
    ],
    "community": [
        r"\bcommunit(?:y|ies)\b", r"\bresidents?\b", r"\bfamil(?:y|ies)\b", r"\bwidows?\b",
        r"\bbapo\b", r"\bnkaneng\b", r"\bwonderkop\b", r"\blocal people\b",
    ],
    "labour": [
        r"\bamcu\b", r"\bnum\b", r"\bunion\b", r"\bworkers?\b", r"\bmineworkers?\b",
        r"\bminers?\b", r"\bstrikers?\b", r"\bmathunjwa\b",
    ],
    "NGO": [
        r"bench marks", r"\bseri\b", r"centre for environmental rights", r"\bcasac\b",
        r"legal resources centre", r"civil society", r"human rights (?:group|organisation|organization)",
    ],
}
STRONG_TITLE_RE = {g: [re.compile(p, re.I) for p in pats] for g, pats in STRONG_TITLE.items()}


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
    try:
        return float(v)
    except Exception:
        return default


def sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def low_confidence(row: dict) -> bool:
    method = row.get("stakeholder_method", "")
    return method == "fallback_no_actor_signal" or (
        method == "dominant_voice_proxy" and fnum(row.get("stakeholder_confidence")) < 0.12
    )


def unique_title_group(title: str):
    hits = {}
    for g, pats in STRONG_TITLE_RE.items():
        n = sum(bool(p.search(title or "")) for p in pats)
        if n:
            hits[g] = n
    if len(hits) == 1:
        g = next(iter(hits))
        return g, hits
    return None, hits


def attributed_voice_scores(title: str, text: str):
    scores = {g: 0.0 for g in GROUP_RE}
    title_hits = {g: sum(bool(p.search(title or "")) for p in STRONG_TITLE_RE[g]) for g in GROUP_RE}
    for g, n in title_hits.items():
        scores[g] += 4.0 * n

    sents = sentence_units(text)
    # Early article sentences strongly represent headline subject/context.
    for sent in sents[:12]:
        for g, pats in GROUP_RE.items():
            n = sum(bool(p.search(sent)) for p in pats)
            if n:
                scores[g] += 0.8 * n

    # Attributed speech/action is the primary body-level signal for dominant voice.
    for sent in sents:
        if not SPEECH.search(sent):
            continue
        for g, pats in GROUP_RE.items():
            n = sum(bool(p.search(sent)) for p in pats)
            if n:
                scores[g] += 3.0 * n

    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    top_g, top = ordered[0]
    second = ordered[1][1]
    margin = (top - second) / max(top, 1.0)
    return top_g, top, second, margin, scores, title_hits


def adjudicate(row: dict, text: str):
    title = row.get("title", "")
    unique, title_hits = unique_title_group(title)
    if unique is not None:
        return {
            "group": unique,
            "resolved": True,
            "method": "third_pass_unique_headline_subject",
            "confidence": 0.95,
            "scores": {g: float(title_hits.get(g, 0)) for g in GROUP_RE},
        }

    top_g, top, second, margin, scores, _ = attributed_voice_scores(title, text)
    if top >= 4.0 and margin >= 0.25:
        return {
            "group": top_g,
            "resolved": True,
            "method": "third_pass_attributed_voice_clear_margin",
            "confidence": min(0.94, 0.55 + 0.45 * margin),
            "scores": scores,
        }
    return {
        "group": "",
        "resolved": False,
        "method": "unresolved_stakeholder_voice_ambiguous",
        "confidence": max(0.0, min(0.49, margin)),
        "scores": scores,
    }


def main():
    if not LABELS.exists() or not LABEL_SUMMARY.exists():
        raise RuntimeError("Final stance ledger missing; stakeholder adjudication is blocked")
    labels = read_csv(LABELS)
    stance_summary = json.loads(LABEL_SUMMARY.read_text(encoding="utf-8"))
    if stance_summary.get("frozen_analysis_manifest_sha256") != EXPECTED_MANIFEST_SHA:
        raise RuntimeError("Stance ledger is not tied to frozen analysis manifest")
    if len(labels) != stance_summary.get("final_model_eligible_labelled_records"):
        raise RuntimeError("Stance ledger count does not match stance summary")

    targets = [r for r in labels if low_confidence(r)]
    fetched = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {}
        for r in targets:
            q = dict(r)
            q["canonical_record_id"] = r["record_id"]
            futs[pool.submit(fetch_one, q)] = r["record_id"]
        for fut in as_completed(futs):
            res = fut.result()
            fetched[res["id"]] = res

    ledger = []
    unresolved = []
    third_resolved = 0
    third_unavailable = 0
    for r in labels:
        out = dict(r)
        original_group = r.get("stakeholder_group_proxy", "")
        out["pass1_stakeholder_group_proxy"] = original_group
        out["pass1_stakeholder_confidence"] = r.get("stakeholder_confidence", "")
        out["pass1_stakeholder_method"] = r.get("stakeholder_method", "")

        if not low_confidence(r):
            out["final_stakeholder_group"] = original_group
            out["final_stakeholder_status"] = "resolved"
            out["final_stakeholder_method"] = "pass1_retained_sufficient_confidence"
            out["final_stakeholder_confidence"] = r.get("stakeholder_confidence", "") or "1.0000"
            ledger.append(out)
            continue

        res = fetched.get(r["record_id"])
        if not res or res["status"] != "retrieved_extracted":
            out["final_stakeholder_group"] = ""
            out["final_stakeholder_status"] = "unresolved"
            out["final_stakeholder_method"] = "unresolved_text_unavailable_for_third_pass"
            out["final_stakeholder_confidence"] = ""
            unresolved.append(out); ledger.append(out); third_unavailable += 1
            continue

        a = adjudicate(r, res["text"])
        out["final_stakeholder_group"] = a["group"]
        out["final_stakeholder_status"] = "resolved" if a["resolved"] else "unresolved"
        out["final_stakeholder_method"] = a["method"]
        out["final_stakeholder_confidence"] = f"{a['confidence']:.4f}"
        for g in GROUP_RE:
            out[f"third_pass_score_{g}"] = f"{a['scores'].get(g, 0.0):.3f}"
        if a["resolved"]:
            third_resolved += 1
        else:
            unresolved.append(out)
        ledger.append(out)

    if len(ledger) != len(labels):
        raise RuntimeError("Stakeholder ledger coverage mismatch")
    resolved = [r for r in ledger if r.get("final_stakeholder_status") == "resolved"]
    group_counts = Counter(r.get("final_stakeholder_group", "") for r in resolved)
    missing_groups = sorted(set(GROUP_RE) - set(group_counts))
    if missing_groups:
        raise RuntimeError(f"Resolved stakeholder ledger is missing required groups: {missing_groups}")

    write_csv(LEDGER, ledger)
    write_csv(UNRESOLVED, unresolved)
    summary = {
        "stage": "final_reconstructed_stakeholder_attribution",
        "frozen_analysis_manifest_sha256": EXPECTED_MANIFEST_SHA,
        "stance_labelled_records": len(labels),
        "pass1_low_confidence_or_fallback_targets": len(targets),
        "third_pass_resolved": third_resolved,
        "third_pass_text_unavailable": third_unavailable,
        "final_stakeholder_resolved_records": len(resolved),
        "final_stakeholder_unresolved_excluded_from_group_aggregation": len(unresolved),
        "final_group_counts": dict(sorted(group_counts.items())),
        "historical_human_stakeholder_ledger_recovered": False,
        "interpretation": "This is a conservative computational adjudication of dominant stakeholder voice. Unresolved cases remain eligible for stance-model evaluation but are excluded from stakeholder-group aggregation.",
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    HASHES.write_text(json.dumps({
        "algorithm": "sha256",
        LEDGER.name: sha(LEDGER),
        UNRESOLVED.name: sha(UNRESOLVED),
        SUMMARY.name: sha(SUMMARY),
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
