# SCIPRA Source-Family Retrieval Rules

These rules operationalise `RECONSTRUCTION_PROTOCOL.md` before the expanded candidate set is frozen or labelled. They are designed to preserve document-genre comparability and prevent arbitrary corpus inflation.

## General unit of analysis

The unit of analysis is a substantive textual document or article that can reasonably be treated as an independent authored/published communication for the SCIPRA NLP task.

A separate URL does not automatically constitute a separate document. Mirrors, reprints, alternate formats, index pages, and trivial updates are logged but collapsed to one canonical document when they contain the same substantive text.

## Media: Mining Weekly, Engineering News, Daily Maverick

Include:
- distinct news reports, analyses, interviews, features, and clearly identified opinion/analysis articles that satisfy the date and Marikana-scope criteria;
- follow-up stories on the same event when the article contains independently authored substantive text.

Deduplicate:
- Mining Weekly and Engineering News frequently mirror the same Creamer Media story. If title/byline/date/body indicate the same story, keep one canonical text and preserve the alternate URL as a mirror in the retrieval log;
- print/online republications of the same story are one document;
- URL variants of the same article are one document.

Exclude:
- short round-ups where Marikana is only one small item unless the Marikana item itself provides sufficient substantive text;
- articles where Marikana/Lonmin is merely an incidental example with no material case discussion.

## Marikana Commission / official Justice records

Include:
- the final Commission report;
- substantive Heads of Argument;
- formal stakeholder submissions or analytical memoranda that present an identifiable party/institutional position;
- formal Commission/government reports or policy records with substantive Marikana analysis.

Exclude from the primary NLP corpus:
- photographs, video/audio artefacts, crime-scene packs, maps, raw police logs, post-mortem material, and other non-text evidentiary artefacts;
- raw witness statements and isolated evidentiary exhibits whose function is factual evidence rather than an authored analytical/stakeholder communication;
- routine scheduling notices, accreditation documents, and administrative media advisories.

These excluded records remain discoverable in the retrieval log where relevant but are not treated as comparable NLP documents.

## Government / Parliament / regulator

Include formal reports, committee records, policy/briefing documents, findings, and substantive official statements where Marikana/Lonmin is a central subject.

Exclude records with only incidental mention of Marikana or generic mining-sector material without direct case relevance.

## NGO / civil society

Include published reports, formal submissions, analytical briefs, and substantive advocacy documents directly addressing Marikana, Lonmin, affected communities/workers, accountability, living conditions, or directly linked mining-governance obligations.

General mining-governance reports require substantive Marikana/Lonmin discussion to qualify for the strict corpus.

## Corporate: Lonmin / Sibanye-Stillwater

Include distinct annual, integrated, sustainability, social-and-labour-plan, stakeholder, Marikana-renewal, housing/community, employment, and socioeconomic reports or substantive corporate communications with direct Marikana relevance.

HTML and PDF editions of the same annual/integrated report are one document. Annual reports from different years are distinct documents.

Routine production notices qualify only when they materially address labour relations, community/stakeholder obligations, Marikana restructuring, or another SCIPRA-relevant dimension rather than ordinary production statistics alone.

## Duplicate resolution

Duplicate checks use, in order where available:
1. exact extracted-text SHA-256;
2. normalized-text hash;
3. title + byline + publication date + publisher;
4. high textual similarity/manual review for syndicated or mirrored stories.

All excluded mirrors remain in the retrieval log with `exclude_duplicate_mirror` and a canonical document identifier.

## Freeze rule

These source-family rules are fixed before stance annotation and model fitting. They may not be changed because of class balance, classifier metrics, or agreement with historical SCIPRA results.
