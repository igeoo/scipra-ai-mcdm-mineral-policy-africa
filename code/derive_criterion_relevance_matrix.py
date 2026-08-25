"""Derive stakeholder-by-criterion discourse relevance matrix for revised SCIPRA.

Revision layer only. This does not modify the frozen corpus or post-freeze
reconstruction. Text is reacquired from frozen URLs and held in memory only.
Committed outputs contain metadata, counts, hashes, and relevance decisions.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from post_freeze_annotation_pass import fetch_one, sentence_units

ROOT = Path(__file__).resolve().parents[1]
PF = ROOT / "data" / "post_freeze_analysis"
OUT = ROOT / "data" / "revision_analysis"
LABELS = PF / "reconstructed_stance_labels_final.csv"
STAKE = PF / "reconstructed_stakeholder_attribution_final.csv"
GROUPS = PF / "stakeholder_acceptance_oof.csv"

EXPECTED_LABELLED = 807
EXPECTED_RESOLVED_STAKE = 776
STAKEHOLDERS = ["government", "investor", "community", "labour", "NGO"]
SIC = {"government": 0.703, "investor": 0.770, "community": 0.749, "labour": 0.807, "NGO": 0.686}
CRITERIA = ["NPV", "IRR", "Geological Feasibility", "Market Stability", "Local Employment", "Community Infrastructure"]
W0 = {"NPV":0.25,"IRR":0.20,"Geological Feasibility":0.15,"Market Stability":0.15,"Local Employment":0.15,"Community Infrastructure":0.10}

# Fixed before execution; each regex is one phrase family.
PATTERNS = {
    "NPV": [
        r"\bnet present value\b", r"\bNPV\b", r"discounted cash flow", r"\bcash flow(?:s)?\b",
        r"capital expenditure|\bcapex\b", r"project (?:value|valuation)", r"investment value",
    ],
    "IRR": [
        r"internal rate of return", r"\bIRR\b", r"return on investment|\bROI\b", r"rate of return",
        r"profitabilit", r"financial return(?:s)?",
    ],
    "Geological Feasibility": [
        r"geolog(?:y|ical)", r"ore[- ]?body", r"mineral reserve(?:s)?", r"mineral resource(?:s)?",
        r"ore grade", r"resource base", r"mine life", r"(?:geological|mining) feasibility",
    ],
    "Market Stability": [
        r"platinum price(?:s)?", r"commodity price(?:s)?", r"market demand", r"market supply",
        r"market conditions?", r"price volatility", r"market stability", r"commodity market",
    ],
    "Local Employment": [
        r"\bemployment\b", r"\bjobs?\b", r"local hir(?:e|ing)", r"\bworkers?\b", r"\bemployees?\b",
        r"\bmineworkers?\b", r"retrench(?:ment|ed|ing)?", r"lay[- ]?offs?", r"\bwages?\b", r"\blabou?r\b",
    ],
    "Community Infrastructure": [
        r"\bhousing\b", r"accommodation", r"\bschools?\b", r"\bclinics?\b|healthcare|health care",
        r"\broads?\b", r"\bwater\b", r"sanitation", r"electricity", r"community infrastructure",
        r"community development", r"social and labou?r plan|\bSLP\b",
    ],
}
COMPILED = {c:[re.compile(p,re.I) for p in pats] for c,pats in PATTERNS.items()}
THRESHOLDS = [(1,1),(2,1),(2,2),(3,2)]
PRIMARY = (2,2)


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    fields=[]
    for r in rows:
        for k in r:
            if k not in fields: fields.append(k)
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def criterion_stats(text: str, criterion: str):
    sents = sentence_units(text)
    pats = COMPILED[criterion]
    matched_sentences = 0
    family_hits = set()
    for s in sents:
        hit_this = False
        for idx,p in enumerate(pats):
            if p.search(s):
                family_hits.add(idx); hit_this=True
        if hit_this: matched_sentences += 1
    return matched_sentences, len(family_hits), len(sents)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    labels=read_csv(LABELS); stake=read_csv(STAKE); groups=read_csv(GROUPS)
    assert len(labels)==EXPECTED_LABELLED
    resolved=[r for r in stake if r.get("final_stakeholder_status")=="resolved"]
    assert len(resolved)==EXPECTED_RESOLVED_STAKE
    label_by_id={r["record_id"]:r for r in labels}
    targets=[]
    for s in resolved:
        rid=s["record_id"]
        if rid not in label_by_id: continue
        r=dict(label_by_id[rid]); r["canonical_record_id"]=rid
        r["final_stakeholder_group"]=s["final_stakeholder_group"]
        targets.append(r)
    assert len(targets)==EXPECTED_RESOLVED_STAKE

    fetched=[]
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs={pool.submit(fetch_one,r):r for r in targets}
        for fut in as_completed(futs):
            fetched.append((futs[fut],fut.result()))

    recovery=[]; audit=[]
    recovered_by_group=Counter()
    matrix_counts={t:defaultdict(Counter) for t in THRESHOLDS}
    for src,res in fetched:
        g=src["final_stakeholder_group"]
        ok=res["status"]=="retrieved_extracted"
        recovery.append({"record_id":src["record_id"],"stakeholder_group":g,"status":res["status"],"method":res["method"],"words":res["words"],"text_sha256":res["sha"],"error":res["error"]})
        if not ok: continue
        recovered_by_group[g]+=1
        for c in CRITERIA:
            ms,df,ns=criterion_stats(res["text"],c)
            row={"record_id":src["record_id"],"stakeholder_group":g,"criterion":c,"matched_sentences":ms,"distinct_phrase_families":df,"sentence_units":ns}
            for t in THRESHOLDS:
                relevant=(ms>=t[0] and df>=t[1])
                row[f"relevant_s{t[0]}_f{t[1]}"]=str(relevant).lower()
                if relevant: matrix_counts[t][g][c]+=1
            audit.append(row)

    matrix_rows=[]; sensitivity_rows=[]
    for t in THRESHOLDS:
        for g in STAKEHOLDERS:
            n=recovered_by_group[g]
            if n==0: raise RuntimeError(f"No recovered texts for {g}")
            for c in CRITERIA:
                rel=matrix_counts[t][g][c]
                sensitivity_rows.append({"min_matched_sentences":t[0],"min_distinct_families":t[1],"stakeholder_group":g,"criterion":c,"recovered_documents":n,"relevant_documents":rel,"A_sj":rel/n})
                if t==PRIMARY:
                    matrix_rows.append({"stakeholder_group":g,"criterion":c,"recovered_documents":n,"relevant_documents":rel,"A_sj":rel/n})

    prob={r["stakeholder_group"]:float(r["mean_oof_pro_integration_probability"]) for r in groups if r["stakeholder_group"] in STAKEHOLDERS}
    if set(prob)!=set(STAKEHOLDERS): raise RuntimeError("Missing stakeholder OOF probabilities")

    # Compute revised weights for each threshold scheme under salience*contention and salience-only variants.
    revised_rows=[]
    for t in THRESHOLDS:
        A={(r["stakeholder_group"],r["criterion"]):r["A_sj"] for r in sensitivity_rows if r["min_matched_sentences"]==t[0] and r["min_distinct_families"]==t[1]}
        for mode in ["salience_times_contention","salience_only"]:
            pressure={s:SIC[s]*((1-prob[s]) if mode=="salience_times_contention" else 1.0) for s in STAKEHOLDERS}
            den=sum(pressure.values())
            G={c:sum(pressure[s]*A[(s,c)] for s in STAKEHOLDERS)/den for c in CRITERIA}
            for delta in [0.0,0.1,0.3,0.5,0.8]:
                raw={c:W0[c]*(1+delta*G[c]) for c in CRITERIA}; z=sum(raw.values()); w={c:raw[c]/z for c in CRITERIA}
                for c in CRITERIA:
                    revised_rows.append({"min_matched_sentences":t[0],"min_distinct_families":t[1],"mode":mode,"delta":delta,"criterion":c,"base_weight":W0[c],"A_weighted_pressure_G_j":G[c],"revised_weight":w[c],"change_from_base":w[c]-W0[c]})

    primary_weights=[r for r in revised_rows if r["min_matched_sentences"]==PRIMARY[0] and r["min_distinct_families"]==PRIMARY[1] and r["mode"]=="salience_times_contention" and r["delta"]==0.3]
    # Across threshold choices at delta=.3, measure range for each criterion.
    sensitivity_range={}
    for c in CRITERIA:
        vals=[r["revised_weight"] for r in revised_rows if r["criterion"]==c and r["mode"]=="salience_times_contention" and r["delta"]==0.3]
        sensitivity_range[c]={"min":min(vals),"max":max(vals),"range":max(vals)-min(vals)}

    summary={
        "stage":"data_derived_criterion_relevance_matrix_revision",
        "eligible_resolved_stakeholder_records":len(targets),
        "freshly_recovered_records":sum(recovered_by_group.values()),
        "fresh_recovery_unavailable":len(targets)-sum(recovered_by_group.values()),
        "recovered_by_stakeholder":dict(recovered_by_group),
        "primary_rule":{"min_matched_sentences":2,"min_distinct_families":2},
        "sensitivity_rules":[{"min_matched_sentences":a,"min_distinct_families":b} for a,b in THRESHOLDS],
        "matrix_interpretation":"A_sj is document-level criterion prevalence among freshly recovered, resolved-stakeholder records; it is a discourse-relevance proxy, not an expert preference matrix.",
        "primary_delta_0_3_salience_times_contention_weights":{r["criterion"]:r["revised_weight"] for r in primary_weights},
        "primary_delta_0_3_pressures":{r["criterion"]:r["A_weighted_pressure_G_j"] for r in primary_weights},
        "threshold_sensitivity_weight_ranges_delta_0_3":sensitivity_range,
        "historical_parameter_recovery_claim":False,
        "revision_claim":True,
        "important_limitation":"The matrix depends on preregistered phrase families and fresh source recovery; it estimates documentary issue prevalence, not normative stakeholder preference strength.",
    }

    write_csv(OUT/"criterion_relevance_recovery.csv",sorted(recovery,key=lambda r:r["record_id"]))
    write_csv(OUT/"criterion_relevance_document_audit.csv",sorted(audit,key=lambda r:(r["record_id"],r["criterion"])))
    write_csv(OUT/"criterion_relevance_matrix.csv",matrix_rows)
    write_csv(OUT/"criterion_relevance_matrix_sensitivity.csv",sensitivity_rows)
    write_csv(OUT/"data_derived_swdc_revision_grid.csv",revised_rows)
    (OUT/"criterion_relevance_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2,sort_keys=True))

if __name__=="__main__": main()
