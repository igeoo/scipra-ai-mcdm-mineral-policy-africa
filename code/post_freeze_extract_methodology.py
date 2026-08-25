"""Extract only analysis-method paragraphs from the SCIPRA manuscript/SI DOCX files.

This helper does not alter corpus membership or create labels. It exists so the
post-freeze analysis can be checked against the manuscript's stated stance,
SVM, stakeholder, PCI and RPCI definitions before any new computation.
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "data" / "post_freeze_analysis"
OUT = OUTDIR / "methodology_keyword_extract.txt"
ANNOTATION_OUT = OUTDIR / "annotation_protocol_excerpt.txt"
SOURCES = [
    ROOT / "appendices" / "SCIPRA_Supplementary_Material.docx",
    ROOT / "SCIPRA_04052026.docx",
]
KEYWORDS = re.compile(
    r"\b(stance|pro[- ]?integration|resistan|support|oppose|label|annotat|"
    r"stakeholder group|svm|support vector|tf[- ]?idf|B\.3|B\.4|"
    r"policy convergence|acceptance|investment score|regulatory score|"
    r"stakeholder score|PCI|RPCI|salience|SIC)\b",
    re.I,
)

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def docx_paragraphs(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    out: list[str] = []
    for p in root.findall(".//w:p", NS):
        text = "".join(t.text or "" for t in p.findall(".//w:t", NS)).strip()
        if text:
            out.append(re.sub(r"\s+", " ", text))
    return out


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    blocks: list[str] = []
    si_paras: list[str] | None = None
    for src in SOURCES:
        paras = docx_paragraphs(src)
        if src.name == "SCIPRA_Supplementary_Material.docx":
            si_paras = paras
        hits = [(i, p) for i, p in enumerate(paras) if KEYWORDS.search(p)]
        wanted: set[int] = set()
        for i, _ in hits:
            wanted.update(j for j in (i - 1, i, i + 1) if 0 <= j < len(paras))
        blocks.append(f"===== {src.name} =====")
        for i in sorted(wanted):
            blocks.append(f"[{i:04d}] {paras[i]}")
        blocks.append("")
    OUT.write_text("\n".join(blocks), encoding="utf-8")

    if si_paras is None or len(si_paras) <= 730:
        raise RuntimeError("Supplementary appendix paragraph numbering drifted; cannot export B.4 safely")
    # Exact B.4 annotation-area excerpt, deliberately narrow to avoid redistributing the full SI.
    annotation = [f"[{i:04d}] {si_paras[i]}" for i in range(659, 731)]
    ANNOTATION_OUT.write_text("\n".join(annotation) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"wrote {ANNOTATION_OUT}")


if __name__ == "__main__":
    main()
