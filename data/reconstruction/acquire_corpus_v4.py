"""Acquisition v4: targeted OCR as a last-resort PDF text extractor.

This wrapper preserves v3 retrieval/collision handling. OCR is attempted only
when (a) the retrieved bytes are a real PDF, and (b) both pypdf and PyMuPDF
produce no substantive text. This is intended for image-only archival sources
such as the Christof Heyns Marikana Commission filing; it is not applied to
normal text PDFs or HTML hot-link stubs.
"""
from __future__ import annotations

import io

import fitz
import pytesseract
from PIL import Image

import acquire_corpus_v3 as v3

_base_extract = v3.base.extract_pdf


def extract_pdf_with_targeted_ocr(data: bytes):
    text, pages, method = _base_extract(data)
    if len((text or "").strip()) >= 500 or not data.startswith(b"%PDF"):
        return text, pages, method

    try:
        doc = fitz.open(stream=data, filetype="pdf")
        # OCR is deliberately last-resort and English-only. Render at ~200 dpi
        # (72 * 2.8) to balance archival legibility and CI runtime.
        ocr_pages: list[str] = []
        matrix = fitz.Matrix(2.8, 2.8)
        for page in doc:
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.open(io.BytesIO(pix.tobytes("png")))
            ocr_pages.append(pytesseract.image_to_string(image, lang="eng"))
        ocr_text = v3.base.normalise_space("\n\n".join(ocr_pages))
        if len(ocr_text.strip()) > len((text or "").strip()):
            return ocr_text, len(doc), "tesseract_ocr_last_resort"
    except Exception:
        pass
    return text, pages, method


v3.base.extract_pdf = extract_pdf_with_targeted_ocr

if __name__ == "__main__":
    raise SystemExit(v3.base.main())
