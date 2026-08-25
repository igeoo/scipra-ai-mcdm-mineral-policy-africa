"""Post-hoc semantic sensitivity audit for revised SCIPRA criterion relevance.

The preregistered primary lexicon/result remains authoritative for that analysis.
This script does NOT replace it. It tests whether revised weight directions are
sensitive to reasonable alternative interpretations of the six investment criteria.

In particular:
- employment_strict removes generic labour/worker/wage mentions from Local Employment;
- finance_broad_employment_strict broadens NPV/IRR financial-language coverage while
  retaining the stricter employment definition.
"""
from __future__ import annotations
import csv, json, re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from post_freeze_annotation_pass import fetch_one, sentence_units
from derive_criterion_relevance_matrix import PATTERNS as PRIMARY_PATTERNS

ROOT=Path(__file__).resolve().parents[1]
PF=ROOT/'data'/'post_freeze_analysis'
OUT=ROOT/'data'/'revision_analysis'
LABELS=PF/'reconstructed_stance_labels_final.csv'
STAKE=PF/'reconstructed_stakeholder_attribution_final.csv'
GROUPS=PF/'stakeholder_acceptance_oof.csv'

STAKEHOLDERS=['government','investor','community','labour','NGO']
SIC={'government':0.703,'investor':0.770,'community':0.749,'labour':0.807,'NGO':0.686}
CRITERIA=['NPV','IRR','Geological Feasibility','Market Stability','Local Employment','Community Infrastructure']
W0={'NPV':.25,'IRR':.20,'Geological Feasibility':.15,'Market Stability':.15,'Local Employment':.15,'Community Infrastructure':.10}
DELTA=.3
RULE=(2,2)

EMPLOYMENT_STRICT=[
 r'local employment', r'local (?:jobs?|hiring)', r'job creation', r'employment (?:creation|opportunit)',
 r'jobs? (?:created|creation|lost|losses)', r'retrench(?:ment|ed|ing)?', r'lay[- ]?offs?', r'workforce reduction',
]
NPV_BROAD=list(PRIMARY_PATTERNS['NPV'])+[
 r'\binvestment\b', r'capital investment', r'financial value', r'project economics?', r'\brevenue\b',
 r'\bprofits?\b', r'operating cash', r'capital cost', r'operating cost',
]
IRR_BROAD=list(PRIMARY_PATTERNS['IRR'])+[
 r'financial performance', r'shareholder return', r'return on capital', r'profit margin', r'\bearnings\b',
]

VARIANTS={
 'primary_preregistered': {c:list(PRIMARY_PATTERNS[c]) for c in CRITERIA},
 'employment_strict': {**{c:list(PRIMARY_PATTERNS[c]) for c in CRITERIA}, 'Local Employment':EMPLOYMENT_STRICT},
 'finance_broad_employment_strict': {**{c:list(PRIMARY_PATTERNS[c]) for c in CRITERIA}, 'NPV':NPV_BROAD, 'IRR':IRR_BROAD, 'Local Employment':EMPLOYMENT_STRICT},
}
COMPILED={v:{c:[re.compile(p,re.I) for p in pats] for c,pats in d.items()} for v,d in VARIANTS.items()}

def rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def criterion_stats(text,pats):
    matched=0; fam=set()
    for sent in sentence_units(text):
        hit=False
        for i,p in enumerate(pats):
            if p.search(sent): fam.add(i); hit=True
        if hit: matched+=1
    return matched,len(fam)

def revised(A,prob):
    pressure={s:SIC[s]*(1-prob[s]) for s in STAKEHOLDERS}; z=sum(pressure.values())
    G={c:sum(pressure[s]*A[(s,c)] for s in STAKEHOLDERS)/z for c in CRITERIA}
    raw={c:W0[c]*(1+DELTA*G[c]) for c in CRITERIA}; rz=sum(raw.values())
    return G,{c:raw[c]/rz for c in CRITERIA}

def main():
    labels=rows(LABELS); stake=rows(STAKE); groups=rows(GROUPS)
    label_by={r['record_id']:r for r in labels}
    targets=[]
    for s in stake:
        if s.get('final_stakeholder_status')!='resolved' or s['record_id'] not in label_by: continue
        r=dict(label_by[s['record_id']]);r['canonical_record_id']=s['record_id'];r['final_stakeholder_group']=s['final_stakeholder_group'];targets.append(r)
    assert len(targets)==776
    prob={r['stakeholder_group']:float(r['mean_oof_pro_integration_probability']) for r in groups if r['stakeholder_group'] in STAKEHOLDERS}

    fetched=[]
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs={pool.submit(fetch_one,r):r for r in targets}
        for fut in as_completed(futs): fetched.append((futs[fut],fut.result()))

    recovered=Counter(); counts={v:defaultdict(Counter) for v in VARIANTS}; audit=[]
    for src,res in fetched:
        if res['status']!='retrieved_extracted': continue
        g=src['final_stakeholder_group'];recovered[g]+=1
        for v in VARIANTS:
            for c in CRITERIA:
                ms,df=criterion_stats(res['text'],COMPILED[v][c])
                rel=ms>=RULE[0] and df>=RULE[1]
                if rel:counts[v][g][c]+=1
                audit.append({'record_id':src['record_id'],'stakeholder_group':g,'variant':v,'criterion':c,'matched_sentences':ms,'distinct_families':df,'relevant':str(rel).lower()})
    assert sum(recovered.values())>=770

    matrix=[]; variant_summary={}
    for v in VARIANTS:
        A={}
        for g in STAKEHOLDERS:
            for c in CRITERIA:
                rel=counts[v][g][c]; n=recovered[g]; a=rel/n
                A[(g,c)]=a
                matrix.append({'variant':v,'stakeholder_group':g,'criterion':c,'recovered_documents':n,'relevant_documents':rel,'A_sj':a})
        G,w=revised(A,prob)
        variant_summary[v]={'criterion_pressure':G,'revised_weights':w,'changes_from_base':{c:w[c]-W0[c] for c in CRITERIA}}

    primary=variant_summary['primary_preregistered']['revised_weights']
    strict=variant_summary['employment_strict']['revised_weights']
    broad=variant_summary['finance_broad_employment_strict']['revised_weights']
    summary={
      'stage':'post_hoc_criterion_semantic_sensitivity',
      'status':'sensitivity_only_does_not_replace_preregistered_primary',
      'rule':{'min_matched_sentences':2,'min_distinct_families':2},
      'fresh_recovered_total':sum(recovered.values()),
      'recovered_by_stakeholder':dict(recovered),
      'variants':variant_summary,
      'employment_strict_local_employment_change_from_base':strict['Local Employment']-W0['Local Employment'],
      'finance_broad_strict_local_employment_change_from_base':broad['Local Employment']-W0['Local Employment'],
      'finance_broad_NPV_change_from_base':broad['NPV']-W0['NPV'],
      'finance_broad_IRR_change_from_base':broad['IRR']-W0['IRR'],
      'max_abs_weight_difference_primary_vs_employment_strict':max(abs(primary[c]-strict[c]) for c in CRITERIA),
      'max_abs_weight_difference_primary_vs_finance_broad_strict':max(abs(primary[c]-broad[c]) for c in CRITERIA),
      'interpretation_constraint':'These post-hoc variants test semantic dependence. They must be reported as sensitivity analyses, not substituted retroactively for the preregistered primary rule based on which result is preferred.'
    }
    def write(path,data):
        fields=[]
        for r in data:
            for k in r:
                if k not in fields:fields.append(k)
        with path.open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
    write(OUT/'criterion_semantic_sensitivity_matrix.csv',matrix)
    write(OUT/'criterion_semantic_sensitivity_document_audit.csv',audit)
    (OUT/'criterion_semantic_sensitivity_summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=='__main__':main()
