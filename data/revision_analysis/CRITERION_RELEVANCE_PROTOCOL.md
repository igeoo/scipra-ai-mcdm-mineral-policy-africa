# SCIPRA Revision — Criterion-Relevance Matrix Protocol

## Status

This protocol belongs to the **revision** layer. It does not alter the frozen reconstructed corpus or historical replication findings.

The objective is to estimate the missing stakeholder-by-criterion relevance matrix `A_sj` from the frozen corpus in a transparent, reproducible way. The resulting matrix is a **discourse-relevance proxy**, not an expert preference matrix and not a recovered historical parameter.

## Unit of analysis

Only records with:

1. a finalized reconstructed stance label, and
2. a resolved final stakeholder attribution

are eligible for stakeholder-by-criterion aggregation.

Source text is reacquired at execution time from the frozen canonical URL. Full text is used in memory only and is not committed. Recovery status, extraction method, word count and text SHA-256 are retained for audit.

## Investment criteria

The six criteria are taken directly from the manuscript's stated Step-2 AHP vector:

- NPV — base 0.25
- IRR — base 0.20
- Geological Feasibility — base 0.15
- Market Stability — base 0.15
- Local Employment — base 0.15
- Community Infrastructure — base 0.10

The manuscript later refers to Community Infrastructure as `0.08 -> 0.099`; that conflicts with the stated normalized AHP base vector and is retained as a source inconsistency rather than silently resolved.

## Criterion phrase families

Phrase families are fixed before execution and encoded in `code/derive_criterion_relevance_matrix.py`.

They are designed to capture the semantic scope of each named criterion rather than the stance labels:

- **NPV:** net present value, discounted cash flow, cash flow, capital expenditure/CAPEX, project value/valuation, investment value.
- **IRR:** internal rate of return, IRR, return on investment/ROI, rate of return, profitability, financial return(s).
- **Geological Feasibility:** geology/geological, ore body/orebody, mineral reserves/resources, ore grade, resource base, mine life, geological/mining feasibility.
- **Market Stability:** platinum/commodity prices, market demand/supply, market conditions, price volatility, market stability, commodity market.
- **Local Employment:** employment/jobs/local hiring, workers/employees/mineworkers, retrenchment/layoffs, wages, labour/labor.
- **Community Infrastructure:** housing/accommodation, schools, clinics/healthcare, roads, water, sanitation, electricity, community infrastructure/development, Social and Labour Plan/SLP.

## Primary document-relevance rule

A document is relevant to criterion `j` when:

- at least **2 sentence units** contain criterion-family matches, **and**
- at least **2 distinct phrase families** for that criterion are present.

No stance outcome, historical 71:16 balance, SVM metric, PCI/RPCI value or desired criterion weight is used in this rule.

## Sensitivity rules

The same matrix is also computed under the following alternative thresholds without changing phrase families:

- 1 matched sentence / 1 distinct family
- 2 matched sentences / 1 distinct family
- 2 matched sentences / 2 distinct families — primary
- 3 matched sentences / 2 distinct families

This allows revised weight sensitivity to criterion-coding strictness to be measured.

## Matrix definition

For stakeholder group `s` and criterion `j`:

`A_sj = number of freshly recovered resolved-s documents relevant to j / number of freshly recovered resolved-s documents`

Therefore `A_sj` is a prevalence in `[0,1]`. Rows are **not forced to sum to one** because a policy document may substantively address multiple criteria.

## Revised salience/contention propagation

Let:

- `p_s` = committed OOF probability of pro-integration for stakeholder group `s`
- `C_s = 1 - p_s` = observed contention proxy
- `SIC_s` = structural stakeholder salience coefficient
- `E_s = SIC_s * C_s` = salience-weighted policy pressure
- `G_j = sum_s(E_s * A_sj) / sum_s(E_s)` = criterion-specific policy pressure

Then the proposed revised normalized criterion weight is:

`W*_j = W0_j(1 + delta*G_j) / sum_k W0_k(1 + delta*G_k)`

This is a **proposed SCIPRA revision**. It is not attributed to the historical implementation.

## Interpretation limitations

- `A_sj` measures documentary issue prevalence, not normative preference strength.
- `p_s` derives from reconstructed computational stance labels, not recovered historical human labels.
- Fresh text retrieval may vary over time; execution hashes must accompany every matrix.
- Revised numerical weights are exploratory until criterion coding is independently reviewed/validated.
- The principal contribution at this stage is a transparent non-degenerate mechanism and its robustness, not a claim that the resulting weights are the uniquely correct policy weights.
