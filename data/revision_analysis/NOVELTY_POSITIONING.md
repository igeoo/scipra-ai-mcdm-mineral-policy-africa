# SCIPRA Revision — Novelty Positioning

## Status

This is a targeted positioning note, **not a systematic literature review** and not evidence for an absolute `first-ever` claim.

The revised SCIPRA contribution should be framed narrowly because several neighboring ideas already exist independently.

## What is not novel by itself

### Stakeholder-specific MCDA weights

Stakeholder-specific or multi-actor criterion weighting is established in MCDA/MAMCA practice. For example:

- Putro, Pradono & Setiawan (2021), *Development of Multi-Actor Multi-Criteria Analysis Based on the Weight of Stakeholder Involvement in the Assessment of Natural–Cultural Tourism Area Transportation Policies*, **Algorithms 14(7), 217**, DOI: `10.3390/a14070217`.
- Weber & Köppel (2022), *Can MCDA Serve Ex-Post to Indicate ‘Winners and Losers’ in Sustainability Dilemmas? A Case Study of Marine Spatial Planning in Germany*, **Energies 15(20), 7654**, DOI: `10.3390/en15207654`.

Therefore revised SCIPRA should not claim novelty simply for allowing different stakeholders to affect criterion weights.

### Text analytics combined with MCDM

Text-driven MCDM is established. For example:

- Pérez Rave, Jaramillo Álvarez & Correa Morales (2022), *Multi-criteria decision-making leveraged by text analytics and interviews with strategists*, **Journal of Marketing Analytics 10(1), 30–49**, DOI: `10.1057/s41270-021-00125-8`.

Therefore revised SCIPRA should not claim novelty simply for combining NLP/text mining with MCDM.

### Sentiment analysis combined with MCDM

Prior decision frameworks combine aspect-level sentiment/text mining with MCDM ranking methods. Therefore an NLP-derived positive/negative signal alone is not a sufficient novelty claim.

### Stakeholder salience theory

Power–Legitimacy–Urgency stakeholder salience is established. Dynamic/context-sensitive stakeholder salience mapping also predates SCIPRA. The revision must therefore not claim novelty for SIC/PLU alone.

## Structural problem revealed by reconstruction

The historical SCIPRA code attempted to propagate stakeholder salience into criterion weights using one common scalar multiplier:

`W_a = W_0 * (1 + delta*SIC)`

followed by vector normalization. The reconstruction proves that this common multiplier cancels, leaving relative criterion weights unchanged.

The principal methodological requirement exposed by the audit is therefore **criterion specificity before normalization**.

## Proposed non-degenerate architecture

The revision makes the missing stakeholder-by-criterion object explicit:

- structural stakeholder salience: `SIC_s`
- stakeholder-by-criterion documentary relevance: `A_sj`
- optional observed contention modifier: `C_s = 1 - P_s(pro-integration)`
- optional salience/contention pressure: `E_s = SIC_s*C_s`
- criterion-specific pressure: `G_j = sum_s(E_s*A_sj)/sum_s(E_s)`
- normalized update: `W*_j = W0_j(1+delta*G_j)/sum_k W0_k(1+delta*G_k)`

The pairwise weight ratio changes whenever criterion pressures differ, so the revised rule is non-degenerate by construction.

## What the ablation shows

In the reconstructed Marikana case, most of the numerical change comes from **criterion-specific relevance itself**, not from the contention modifier. SIC and contention contribute only small incremental redistribution beyond the relevance layer.

Therefore contention should be described as an optional dynamic modifier, not as the principal demonstrated empirical innovation in this case.

## What the semantic sensitivity audit adds

The preregistered primary criterion lexicon produced a strong Local Employment upweighting. A post-hoc semantic audit then removed generic `labour`, `workers`, and `wages` language from Local Employment and separately broadened financial terminology.

That audit found:

- the strong Local Employment upweighting is **not semantically robust**; under strict employment semantics it returns approximately to the base weight;
- Community Infrastructure remains upweighted under the tested semantic variants;
- broadening financial semantics can restore NPV approximately to or slightly above its base weight.

This means the empirical contribution should **not** be framed as a definitive new set of Marikana investment weights. The architecture is mathematically sound, but documentary criterion-weight estimates depend on how criterion relevance is operationalized and require stronger measurement validation.

## Defensible candidate contribution

A cautious contribution statement is:

> The revised framework introduces an auditable criterion-specific propagation layer that prevents stakeholder salience from cancelling during normalization and permits documentary criterion relevance, structural salience, and optional contention signals to influence relative mineral-policy criterion weights transparently.

The current evidence supports novelty primarily in the **specific non-degenerate propagation architecture plus reproducibility/sensitivity discipline**, not in any single numerical revised weight.

The targeted literature search conducted during reconstruction identified prior work on neighboring components but did not establish that this exact architecture is absent from all prior literature. This is a **candidate methodological gap**, not an absolute priority claim.

## Language recommended for a manuscript

Prefer:

> "Building on stakeholder-salience, text-analytics and multi-actor MCDA literatures, this study introduces a criterion-specific propagation mechanism that avoids scalar-normalization cancellation and evaluates documentary issue relevance under explicit sensitivity analysis."

If a later structured literature search supports it, cautiously consider:

> "To our knowledge, prior mineral-policy MCDA frameworks have not combined criterion-specific documentary relevance with stakeholder salience in a normalized weighting rule designed explicitly to avoid common-scalar cancellation."

Avoid:

- "the first stakeholder-aware MCDM framework"
- "the first NLP-MCDM framework"
- "the first dynamic stakeholder weighting model"
- "the first use of text mining to derive MCDA weights"
- claims that contention is the main empirical driver in the Marikana case
- claims that the primary Local Employment weight is semantically stable

## Separate empirical contribution

The stance result is independent of the corrected-model novelty. On the independently reconstructed frozen corpus, the historical pro-integration-dominant conclusion does not reproduce under either computational reading, the final adjudicated ledger, or 35 alternative adjudication settings. This remains the strongest empirical reproducibility finding.

## Remaining literature task before submission

Before using `to our knowledge` language, conduct a structured search across at least Scopus/Web of Science/Google Scholar using combinations of stakeholder salience, stakeholder-specific/dynamic weights, mining/mineral policy, criterion relevance, stakeholder documents/statements, issue salience/contention, text mining, and multi-actor MCDA. Record search strings, dates, databases, inclusion criteria and nearest methodological comparators.
