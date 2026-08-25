# SCIPRA Corpus Reconstruction Protocol

## Purpose

This branch reconstructs a traceable Marikana document corpus before any NLP/SVM code, labels, or reported model metrics are altered. The objective is to prevent outcome-driven corpus selection and to ensure that the computational pipeline is tailored to a frozen, auditable dataset.

## Historical manuscript benchmark

The supplementary material describes an 87-document corpus with the following source composition:

- 13 EITI documents
- 1 Farlam Commission report
- 2 Bench Marks Foundation reports
- 1 SERI document
- 1 Centre for Environmental Rights document
- 58 news/media documents
- 11 corporate engagement reports

Total: 87 documents.

This historical count is retained for comparison only. **It is not a stopping rule for the reconstruction.** The reconstructed corpus size must be determined by the retrieval protocol below.

## Provenance problem identified

South Africa is not an EITI implementing country. Therefore the claimed block of 13 South Africa EITI documents cannot presently be recovered as described. It must not be recreated synthetically or silently treated as genuine historical evidence.

The reconstruction preserves two distinct concepts:

1. **Recovered/original-category records**: independently verified documents matching a source family described in the manuscript.
2. **Reconstruction records**: independently verified Marikana-scope documents admitted under the prospective inclusion criteria below when the original historical record cannot be recovered exactly.

Replacement/reconstruction status must remain explicit in metadata and in any revised manuscript.

## Retrieval principle: no fixed target N

The reconstruction must **not stop when N = 87**. All verifiable documents satisfying the prospective inclusion criteria within the defined scope, period, and source universe must be logged and evaluated.

The final corpus size is the number of unique documents that remain after:

1. systematic retrieval is completed;
2. inclusion/exclusion criteria are applied;
3. duplicate and mirror records are removed;
4. acquisition and text-quality checks are passed;
5. corpus membership is frozen before annotation/model fitting.

A final corpus larger or smaller than 87 is acceptable. No document may be added, removed, or replaced because of its stance label or its effect on classifier performance.

## Scope

### Time window

- Publication/document date: **1 January 2010 through 31 December 2023**.
- Documents outside this interval are excluded from the primary reconstructed corpus.

### Geographic/case scope

A document must have substantive relevance to at least one of the following:

- Marikana;
- Lonmin operations at Marikana or directly connected platinum operations/events;
- Sibanye-Stillwater's Marikana operations after acquisition;
- the 2012 Marikana strike and killings and their direct aftermath;
- the 2014 platinum strike where Marikana/Lonmin is substantively implicated;
- Marikana Commission/Farlam proceedings and implementation;
- Marikana worker/community living conditions, housing, wages, health, labour relations, social and labour plans, stakeholder conflict, justice/accountability, regulatory response, ownership transition, or Marikana renewal.

General South African mining documents are included only when Marikana/Lonmin/Sibanye-Marikana is substantively discussed rather than merely mentioned incidentally.

## Eligible source families

The retrieval process searches the source families documented or directly implied by the manuscript/SI and reconstruction record:

- South African government, Parliament, Department of Justice/Marikana Commission, DMRE and other official public records;
- Bench Marks Foundation, SERI, Centre for Environmental Rights, SAHRC and other directly relevant civil-society/NGO records tied to the Marikana case;
- Lonmin and Sibanye-Stillwater annual, integrated, sustainability, social-and-labour-plan, stakeholder, renewal and related corporate reports;
- Mining Weekly;
- Engineering News;
- Daily Maverick;
- other source records already explicitly documented in the historical manifest, provided they satisfy the same date/scope requirements and their provenance is verifiable.

Any new source family not documented above must be marked `expanded_source_universe` and reported separately so that sensitivity analyses can compare the strict documented-source corpus with any broader corpus.

## Inclusion criteria

A record is eligible for the primary reconstructed corpus only if all of the following hold:

1. publication/document date falls within 2010-01-01 to 2023-12-31;
2. substantive Marikana-scope relevance is demonstrated from title, abstract/lead, body text, official description, or document metadata;
3. the source is independently verifiable through an article-specific/document-specific URL, DOI, official archive record, or recoverable archived copy;
4. enough substantive text can be obtained for reproducible NLP analysis;
5. the record is a unique document, not a duplicate, mirror, reprint, or trivial update of another included record;
6. inclusion is decided before stance annotation and without reference to previous or current model performance.

## Exclusion criteria

Exclude records when any of the following apply:

- outside the 2010-2023 period;
- only incidental mention of Marikana/Lonmin with no substantive case relevance;
- duplicate/mirror/republication of an already included document;
- broken or unverifiable provenance with no recoverable archive/document identity;
- insufficient substantive text for the planned NLP task;
- administrative/index/navigation pages that do not themselves constitute the document being analysed;
- documents selected solely because they improve class balance, reproduce the historical 71/16 split, or improve agreement with historical SVM metrics.

## Systematic retrieval and stopping rule

Retrieval is performed source-family by source-family and year-by-year where practical. For each source family, search terms include combinations of:

- Marikana
- Lonmin
- Sibanye Marikana
- Marikana Commission / Farlam
- AMCU + Lonmin/Marikana
- platinum strike + Lonmin/Marikana
- Marikana housing / community / wages / labour / social labour plan / renewal / accountability

The retrieval log must record every candidate considered, including excluded candidates and the reason for exclusion.

Retrieval for a source family is considered saturated only after the documented search variants/date windows yield no additional eligible unique records after duplicate resolution. The exact searches, dates, source/domain, and result decisions must be preserved in the retrieval log.

## Current 87-record list

`candidate_corpus_87.csv` is retained only as a **historical reconstruction seed set**. It must not be treated as the final corpus manifest and must not constrain final N.

The 13 official Marikana Commission filings previously selected as substitutes for the invalid EITI block remain eligible candidates, but they are no longer a quota. Additional official Commission/government documents satisfying the same inclusion criteria must also be considered.

Similarly, the previously identified 58 media records and 11 corporate records are seed candidates, not maximum counts.

## Acquisition and text-quality requirements

For each included record preserve, where available:

- stable document/article identifier;
- title;
- author/publisher;
- publication/document date;
- source family and source URL/DOI/archive URL;
- retrieval date;
- acquisition method;
- HTTP/fetch status;
- raw file hash (SHA-256) where legally stored;
- extracted-text hash (SHA-256);
- extraction method;
- text length/word count;
- duplicate-group identifier where relevant;
- inclusion/exclusion decision and reason;
- redistribution status.

Acquisition failures must remain in the log; they must not disappear from the record.

## Corpus freeze

Before any stance labeling, stakeholder-group assignment used by the model, TF-IDF construction, P/L/U scoring, or SVM fitting:

1. retrieval must be declared complete under the stopping rule;
2. inclusion/exclusion decisions must be finalized;
3. duplicates/mirrors must be resolved;
4. text extraction and minimum quality checks must be completed;
5. the final manifest must be versioned and cryptographically hashed;
6. a frozen corpus version/tag/commit must be recorded.

After the freeze, corpus membership cannot be changed in response to model performance. Any later correction requires a new corpus version and a documented reason independent of model results.

## Annotation and class distribution

The historical 71 pro-integration / 16 resistant class split is **not a target**.

After corpus freeze:

- annotation is performed independently of historical labels/metrics;
- raw annotator labels are preserved;
- disagreements and adjudication are preserved;
- Cohen's kappa and disagreement counts are computed from the actual annotation record;
- the final class distribution is reported exactly as observed;
- stakeholder-group distribution and source-family distribution are also reported.

## Model rerun

Only after corpus freeze and annotation freeze may the NLP/SVM pipeline be adapted and rerun. Reported accuracy, precision, recall, F1, ROC-AUC, confusion matrix, stakeholder acceptance scores, P/L/U outputs, S-score, PCI/RPCI values, and sensitivity results must be regenerated from the frozen corpus.

Historical manuscript metrics are comparison values only and must not constrain the new analysis.

## Reproducibility principle

If the reconstructed, auditable corpus produces a different sample size, class distribution, stakeholder distribution, salience scores, or classifier metrics from the original manuscript, the empirical claims must be revised to the regenerated results. The corpus or code must not be modified solely to recover predetermined numerical outputs.
