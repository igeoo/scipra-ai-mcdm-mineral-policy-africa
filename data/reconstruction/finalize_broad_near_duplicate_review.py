"""Finalize the 49-pair broad near-duplicate review from committed evidence.

The raw targeted-text audit used an intentionally conservative first-pass hash
collision rule. Four candidate pairs were flagged because identical fresh text
had slightly different normalized titles. Here we distinguish genuine global
boilerplate collisions from pair-local identity: a fresh hash occurring only in
the two members of one strongly corroborated candidate pair is duplicate
evidence, not an extraction collision.

All decisions remain explicit and auditable. No stance/model output is used and
the corpus is not frozen here.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "data" / "reconstruction"
MANIFEST_IN = RECON / "cross_phase_post_explicit_manifest.csv"
CANDIDATES = RECON / "broad_near_duplicate_candidates.csv"
EVIDENCE = RECON / "broad_near_duplicate_text_evidence.csv"
DECISIONS = RECON / "broad_near_duplicate_final_decisions.csv"
MANIFEST_OUT = RECON / "prefreeze_manifest_after_broad_duplicate_review.csv"
SUMMARY = RECON / "broad_near_duplicate_final_summary.json"


def read_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


manifest = read_rows(MANIFEST_IN)
candidates = read_rows(CANDIDATES)
evidence = read_rows(EVIDENCE)
if len(manifest) != 942:
    raise RuntimeError(f"Expected 942 pre-review manifest rows, found {len(manifest)}")
if len(candidates) != 49 or len(evidence) != 49:
    raise RuntimeError(f"Expected 49 candidate/evidence pairs, found candidates={len(candidates)}, evidence={len(evidence)}")

cand_by_pair = {(r["record_id_a"], r["record_id_b"]): r for r in candidates}
ev_by_pair = {(r["record_id_a"], r["record_id_b"]): r for r in evidence}
if set(cand_by_pair) != set(ev_by_pair):
    raise RuntimeError("Candidate and evidence pair sets differ")

# Count how many distinct records each fresh hash touches. Pair-local identical
# hashes (2 records) are not global boilerplate collisions.
hash_records = defaultdict(set)
for r in evidence:
    for side in ("a", "b"):
        h = (r.get(f"fresh_sha256_{side}") or "").strip()
        if h:
            hash_records[h].add(r[f"record_id_{side}"])

decisions = []
redundant_ids = set()
representatives = set()
corrected_pair_local_collision_flags = 0

for pair in sorted(cand_by_pair):
    c = cand_by_pair[pair]
    e = ev_by_pair[pair]
    a, b = pair
    sha_a = (e.get("fresh_sha256_a") or "").strip()
    sha_b = (e.get("fresh_sha256_b") or "").strip()
    same_fresh_hash = bool(sha_a and sha_a == sha_b)
    hash_scope = len(hash_records.get(sha_a, set())) if same_fresh_hash else 0
    seq = float(e["sequence_similarity"]) if e.get("sequence_similarity") else None
    shingle = float(e["five_word_shingle_jaccard"]) if e.get("five_word_shingle_jaccard") else None
    title_seq = float(c.get("title_sequence_similarity") or 0)
    slug_seq = float(c.get("slug_sequence_similarity") or 0)
    creamer = c.get("creamer_cross_site") == "true"
    same_title = c.get("same_normalised_title") == "true"

    raw_collision = e.get("text_evidence_signal") == "extraction_collision_blocks_text_similarity"
    pair_local_hash_identity = raw_collision and same_fresh_hash and hash_scope == 2

    if pair_local_hash_identity:
        # Require strong metadata corroboration before correcting the raw flag.
        if not (slug_seq >= 0.97 or title_seq >= 0.90 or same_title):
            raise RuntimeError(f"Pair-local hash identity lacks metadata corroboration: {pair}")
        corrected_pair_local_collision_flags += 1
        qualifies = True
        decision_basis = "pair_local_identical_fresh_body_hash_plus_metadata_corroboration"
        text_similarity = "1.000000_exact_fresh_hash_identity"
    elif e.get("text_evidence_signal") == "very_high_text_similarity_republication_likely":
        qualifies = True
        decision_basis = "very_high_fresh_text_similarity_plus_metadata_corroboration"
        text_similarity = e.get("sequence_similarity", "")
    elif e.get("text_evidence_signal") == "high_text_similarity_republication_review":
        # High-similarity cases are collapsed only with strong metadata evidence.
        metadata_ok = same_title or slug_seq >= 0.92 or (creamer and title_seq >= 0.90)
        text_ok = seq is not None and seq >= 0.93 and (shingle is None or shingle >= 0.70)
        if not (metadata_ok and text_ok):
            raise RuntimeError(f"High-similarity candidate not strong enough for explicit collapse: {pair}")
        qualifies = True
        decision_basis = "high_fresh_text_similarity_plus_title_slug_date_source_corroboration"
        text_similarity = e.get("sequence_similarity", "")
    else:
        qualifies = False
        decision_basis = "insufficient_duplicate_evidence"
        text_similarity = e.get("sequence_similarity", "")

    if not qualifies:
        raise RuntimeError(f"Unresolved broad candidate remains after review: {pair}: {e.get('text_evidence_signal')}")

    # Candidate generation orders each pair deterministically. In this queue A is
    # the preferred earlier/prior representative except for same-source update
    # pairs, where A is still the earlier publication.
    representative = a
    redundant = b
    if redundant in redundant_ids:
        raise RuntimeError(f"Record marked redundant in more than one decision: {redundant}")
    redundant_ids.add(redundant)
    representatives.add(representative)
    decisions.append({
        "representative_record_id": representative,
        "redundant_record_id": redundant,
        "candidate_signal": c.get("candidate_signal", ""),
        "raw_text_evidence_signal": e.get("text_evidence_signal", ""),
        "final_duplicate_decision": "collapse_near_duplicate_or_republication_keep_representative",
        "decision_basis": decision_basis,
        "fresh_text_similarity": text_similarity,
        "fresh_hash_identity": str(same_fresh_hash).lower(),
        "fresh_hash_record_scope": hash_scope,
        "title_sequence_similarity": c.get("title_sequence_similarity", ""),
        "slug_sequence_similarity": c.get("slug_sequence_similarity", ""),
        "source_context": "creamer_media_cross_site_or_same_publisher_update" if creamer or c.get("same_host") == "true" else "other",
        "decision_provenance": "broad_targeted_text_near_duplicate_review_2026-08-24",
    })

if len(decisions) != 49 or len(redundant_ids) != 49:
    raise RuntimeError(f"Expected 49 explicit broad duplicate decisions, got {len(decisions)} decisions/{len(redundant_ids)} redundant IDs")
# No representative may be removed in this pass.
if representatives & redundant_ids:
    overlap = sorted(representatives & redundant_ids)
    raise RuntimeError(f"Transitive/overlapping broad duplicate decisions require flattening: {overlap}")

by_id = {r["canonical_record_id"]: r for r in manifest}
for d in decisions:
    if d["representative_record_id"] not in by_id or d["redundant_record_id"] not in by_id:
        raise RuntimeError(f"Decision references record absent from manifest: {d}")

retained = []
for r in manifest:
    if r["canonical_record_id"] in redundant_ids:
        continue
    x = dict(r)
    x["broad_near_duplicate_review_status"] = "retained_after_broad_near_duplicate_review"
    retained.append(x)

if len(retained) != 893:
    raise RuntimeError(f"Expected 893 retained rows after 49 collapses, found {len(retained)}")
analysis_ready = sum(str(r.get("analysis_ready", "")).lower() == "true" for r in retained)
if analysis_ready != 883:
    raise RuntimeError(f"Expected 883 analysis-ready rows after broad review, found {analysis_ready}")
non_ready = len(retained) - analysis_ready
if non_ready != 10:
    raise RuntimeError(f"Expected 10 retained quality exceptions, found {non_ready}")

fields = list(decisions[0].keys())
with DECISIONS.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(decisions)

manifest_fields = list(manifest[0].keys()) + ["broad_near_duplicate_review_status"]
with MANIFEST_OUT.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=manifest_fields); w.writeheader(); w.writerows(retained)

summary = {
    "scope": "broad_near_duplicate_review_after_safe_cross_phase_and_explicit_review",
    "records_before_broad_review": len(manifest),
    "candidate_pairs_reviewed": len(candidates),
    "duplicate_or_republication_pairs_collapsed": len(decisions),
    "pair_local_hash_collision_flags_corrected": corrected_pair_local_collision_flags,
    "records_retained_after_broad_review": len(retained),
    "analysis_ready_records_after_broad_review": analysis_ready,
    "retained_non_analysis_ready_records": non_ready,
    "metadata_candidate_queue_fully_resolved": True,
    "full_corpus_textwide_near_duplicate_audit_complete": False,
    "corpus_frozen": False,
    "important_note": (
        "All 49 metadata-generated near-duplicate candidates were explicitly resolved using fresh text and source metadata. "
        "A final textwide audit of the retained analysis-ready corpus is still required to detect near duplicates with dissimilar titles before freeze."
    ),
}
SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
