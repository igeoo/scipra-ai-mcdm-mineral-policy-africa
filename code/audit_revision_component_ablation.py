"""Component ablation for the data-derived revised SCIPRA weighting rule.

Uses the already-derived primary A_sj matrix. No web retrieval. Separates the
contribution of criterion-specific relevance from SIC and reconstructed contention.
"""
from __future__ import annotations
import csv, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REV=ROOT/'data'/'revision_analysis'
PF=ROOT/'data'/'post_freeze_analysis'
MATRIX=REV/'criterion_relevance_matrix.csv'
GROUPS=PF/'stakeholder_acceptance_oof.csv'
OUT=REV/'revision_component_ablation.json'
CSVOUT=REV/'revision_component_ablation.csv'

STAKEHOLDERS=['government','investor','community','labour','NGO']
SIC={'government':0.703,'investor':0.770,'community':0.749,'labour':0.807,'NGO':0.686}
CRITERIA=['NPV','IRR','Geological Feasibility','Market Stability','Local Employment','Community Infrastructure']
W0={'NPV':0.25,'IRR':0.20,'Geological Feasibility':0.15,'Market Stability':0.15,'Local Employment':0.15,'Community Infrastructure':0.10}
DELTA=0.3

def rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def G(A,actor_weight):
    z=sum(actor_weight.values())
    return {c:sum(actor_weight[s]*A[(s,c)] for s in STAKEHOLDERS)/z for c in CRITERIA}

def adjust(g):
    raw={c:W0[c]*(1+DELTA*g[c]) for c in CRITERIA}; z=sum(raw.values())
    return {c:raw[c]/z for c in CRITERIA}

def main():
    A={(r['stakeholder_group'],r['criterion']):float(r['A_sj']) for r in rows(MATRIX)}
    prob={r['stakeholder_group']:float(r['mean_oof_pro_integration_probability']) for r in rows(GROUPS) if r['stakeholder_group'] in STAKEHOLDERS}
    n_by_group={}
    for r in rows(MATRIX): n_by_group[r['stakeholder_group']]=int(r['recovered_documents'])
    assert len(A)==len(STAKEHOLDERS)*len(CRITERIA)
    assert set(prob)==set(STAKEHOLDERS)

    modes={
      'base_no_revision': None,
      'criterion_relevance_equal_actor_groups': {s:1.0 for s in STAKEHOLDERS},
      'criterion_relevance_document_volume': {s:float(n_by_group[s]) for s in STAKEHOLDERS},
      'criterion_relevance_SIC_only': {s:SIC[s] for s in STAKEHOLDERS},
      'criterion_relevance_SIC_times_contention': {s:SIC[s]*(1-prob[s]) for s in STAKEHOLDERS},
    }
    weights={}
    pressures={}
    for name,aw in modes.items():
        if aw is None:
            weights[name]=dict(W0); pressures[name]={c:0.0 for c in CRITERIA}
        else:
            pressures[name]=G(A,aw); weights[name]=adjust(pressures[name])

    output_rows=[]
    for c in CRITERIA:
        for mode in modes:
            output_rows.append({'criterion':c,'mode':mode,'delta':DELTA,'weight':weights[mode][c],'change_from_base':weights[mode][c]-W0[c],'criterion_pressure':pressures[mode][c]})
    with CSVOUT.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(output_rows[0]));w.writeheader();w.writerows(output_rows)

    sic_mode=weights['criterion_relevance_SIC_only']
    full_mode=weights['criterion_relevance_SIC_times_contention']
    equal_mode=weights['criterion_relevance_equal_actor_groups']
    max_contention_increment=max(abs(full_mode[c]-sic_mode[c]) for c in CRITERIA)
    max_sic_increment=max(abs(sic_mode[c]-equal_mode[c]) for c in CRITERIA)
    max_total_change=max(abs(full_mode[c]-W0[c]) for c in CRITERIA)
    summary={
      'stage':'revised_SCIPRA_component_ablation',
      'delta':DELTA,
      'weights_by_mode':weights,
      'maximum_absolute_full_revision_change_from_base':max_total_change,
      'maximum_absolute_increment_from_SIC_over_equal_actor_groups':max_sic_increment,
      'maximum_absolute_increment_from_contention_over_SIC_only':max_contention_increment,
      'interpretation':(
        'In the reconstructed Marikana case, criterion-specific documentary relevance drives most of the weight shift. '
        'SIC produces only a small additional redistribution across stakeholder groups, and reconstructed contention adds '
        'very little beyond SIC because resistance/contention is high across most stakeholder groups. The contention term '
        'is therefore a valid dynamic component of the architecture but not the main empirical driver in this case.'
      ),
      'novelty_implication':(
        'Do not attribute the observed revised weights primarily to sentiment/contention. The demonstrated methodological '
        'advance is the non-degenerate criterion-specific propagation architecture; contention is an optional empirically '
        'weak modifier for this case and should be tested across additional cases before being promoted as a core contribution.'
      )
    }
    OUT.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=='__main__':main()
