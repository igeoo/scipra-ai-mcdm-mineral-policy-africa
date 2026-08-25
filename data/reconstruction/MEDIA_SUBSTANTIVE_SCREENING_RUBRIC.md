# SCIPRA media substantive screening rubric

## Purpose

This rubric governs final inclusion/exclusion review for archive-discovered media candidates before corpus freeze. It is prospective, source-content based, and independent of stance labels, historical class proportions, model scores, or downstream MCDM/PCI outcomes.

## Scope boundary

A media document is eligible only when the Marikana/Lonmin-at-Marikana case is substantively central to the document. Relevant dimensions include the August 2012 strike and killings; subsequent justice, accountability and Farlam Commission processes; wages and labour relations; unions; housing and community conditions; social and labour plans; regulatory/government responses; and later Marikana-specific corporate/community transition or renewal.

A document is not eligible merely because it mentions Lonmin, platinum mining, South African mining, labour unrest elsewhere, a Lonmin transaction, or a general corporate result.

## Decision states

- `include_case_central`: Marikana/Lonmin-at-Marikana is a substantive focus or necessary analytical context.
- `exclude_incidental_case_reference`: Marikana/Lonmin-at-Marikana appears only incidentally, comparatively, historically in passing, or as background to another topic.
- `exclude_general_corporate_financial`: the document is primarily about company finance, securities, production, acquisitions/disposals, commodity performance, routine project finance or other corporate matters without substantive Marikana-case treatment.
- `exclude_other_mine_or_event`: the document concerns another mine, strike, company or dispute and Marikana is not substantively central.
- `exclude_duplicate_or_republication`: duplicate/syndicated/republication content is represented by another retained record.
- `exclude_outside_period`: publication is outside 2010-01-01 through 2023-12-31.
- `exclude_insufficient_text`: substantive eligibility cannot be established because usable text could not be recovered.
- `review_ambiguous`: evidence is insufficient for a defensible final decision and the record requires direct reviewer inspection.

## Evidence requirements

Final decisions should use the acquired/extracted text wherever available, not title matching alone. The decision ledger must retain: candidate ID, title, year/date when recoverable, publisher, URL, acquisition/text hash, decision, reason code, concise evidence note and decision provenance.

For inclusion, at least one of the following should hold:

1. The article directly addresses Marikana, Wonderkop, Nkaneng, the Farlam process, or Bapo/Lonmin community issues in a Marikana-specific context.
2. The article is contemporaneous with the August 2012 Lonmin strike/killings and the extracted text clearly concerns that event even if the word `Marikana` is absent.
3. The article substantively analyses later consequences of the Marikana case: justice/accountability, labour relations, wages, housing/community obligations, social and labour plans, regulatory response, or Marikana-specific corporate/community transition.

For exclusion, strong evidence includes:

- routine Lonmin share-price, earnings, financing, production, acquisition/disposal, exploration or commodity stories with no substantive Marikana-case treatment;
- unrelated Lonmin operations or investments outside the Marikana case;
- another mine/strike/event where Marikana is only analogy/background;
- duplicate/republication content already represented.

## Special treatment of early August 2012 coverage

Articles published during the initial Lonmin strike/killings may be case-central even when `Marikana` does not appear in extracted text or the URL. Therefore `Lonmin-only low case signal` is never an automatic exclusion category. Contemporaneous event signals such as Lonmin + striking mineworkers + police/shooting/deaths/wage dispute/union conflict can establish case centrality.

## Automation boundary

Automated scripts may derive transparent evidence signals and propose review priority. They must not silently assign final corpus membership. Final decisions are written only to the decision ledger, with an explicit reason code and evidence note. Ambiguous records remain unresolved rather than being forced.

## Freeze condition

Corpus freeze is prohibited until every candidate admitted to the final screening universe has a recorded decision, acquisition/text exceptions are resolved or documented, duplicate review is complete, and a versioned/hash-locked final manifest has passed an external pre-freeze audit.
