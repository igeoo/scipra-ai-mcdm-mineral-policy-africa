# Reproducibility provenance and role boundary

## Canonical scientific project

`igeoo/scipra-ai-mcdm-mineral-policy-africa` is the author-controlled canonical repository for SCIPRA. Scientific authorship, substantive interpretation, and approval of revisions remain with the study author(s).

## Technical implementation workflow

The original project repository was technically implemented under the `igeoo` account and reviewed by the study author. After that review, the repository was forked to `Martin-do/scipra-ai-mcdm-mineral-policy-africa` specifically to provide an isolated workspace for code repair, corpus reconstruction, reproducibility engineering, integrity checks, and audit work without disturbing the historical author-controlled repository state.

The `Martin-do` fork therefore served as a **technical development and reproducibility workspace**, not as a transfer of scientific ownership or authorship.

## Reconstruction discipline

The reconstruction was conducted prospectively:

- the historical reported N=87 was retained as a benchmark, not a corpus quota or stopping rule;
- the historical 71/16 stance split was not used as an annotation or class-balance target;
- corpus membership was frozen before stance annotation, classifier fitting, MCDM, PCI, or RPCI analysis;
- discrepancies between reconstructed outputs and historical reported values were retained rather than reverse-engineered away;
- unresolved records and provenance limitations were kept explicit;
- proposed methodological corrections were separated from historical replication results.

This allows the calculations to be evaluated independently of predetermined historical numerical targets while remaining within an author-supervised technical reconstruction workflow.

## Integration back into the canonical repository

The full exploratory development history remains preserved in the technical fork. For the canonical author-controlled repository, the validated outputs are curated into a concise computational package containing the reproducibility code, frozen manifests, hashes, analysis outputs, mathematical audits, sensitivity analyses, and reviewer-facing documentation.

This curation intentionally omits development-only trigger files, temporary diagnostic workflows, and branch-specific publishing machinery. The canonical verification workflow is read-only and checks the frozen package without mutating results.

## Manuscript and submission boundary

The unpublished/revised manuscript and submission-specific Word/PDF artifacts are intentionally excluded from the current computational repository while manuscript revision and submission/archival approval are pending.

The historical tracked files removed from the current canonical transfer tree include:

- `SCIPRA_04052026.docx`
- `appendices/SCIPRA_Supplementary_Material.docx`
- `appendices/SCIPRA_SI_References.docx`

Their removal affects the current repository tree only; existing Git history is not rewritten. Methodological facts needed for reproducibility are retained through transparent protocols, extracts, code, manifests, and audit outputs rather than by redistributing an unpublished submission package.

## Interpretation boundary

Repository evidence should distinguish clearly between:

1. historical SCIPRA claims and implementation;
2. reconstructed computational reproducibility results; and
3. proposed corrected/revised SCIPRA methods.

No reconstructed or revised output should be described as if it were an original historical result unless it is independently shown to reproduce that historical result.
