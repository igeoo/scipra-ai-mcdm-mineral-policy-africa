"""SCIPRA post-freeze computational re-annotation pass.

This is NOT a recreation of the manuscript's claimed two-human-annotator file;
that historical file is unavailable.  The script applies two deliberately
separate deterministic readings of the documented B.4.2 decision rules and
routes disagreements / low-confidence cases to review before any model fit.

Full source text is held only in runner memory.  Committed outputs contain
metadata, cue counts and decisions, never article/PDF body text.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlsplit

import requests
import trafilatura
from bs4 import BeautifulSoup
from pypdf import PdfReader

try:
    import fitz  # PyMuPDF fallback for PDFs pypdf cannot extract
except Exception:
    fitz = None

ROOT = Path(__file__).resolve().parents[1]
RECON = ROOT / "data" / "reconstruction"
OUT = ROOT / "data" / "post_freeze_analysis"
MANIFEST = RECON / "canonical_analysis_ready_manifest.csv"
FREEZE_HASHES = RECON / "corpus_freeze_hashes.json"
EXPECTED_MANIFEST_SHA = "cb280e4cb138b2f6bba48b24f0dcd7521c4cb821871846ceb70523a05a7acad5"
EXPECTED_N = 876
UA = "Mozilla/5.0 (compatible; SCIPRA-PostFreeze-Analysis/1.0; +https://github.com/Martin-do/scipra-ai-mcdm-mineral-policy-africa)"

RECOVERY_OUT = OUT / "post_freeze_recovery_status.csv"
DRAFT_OUT = OUT / "reconstructed_annotation_draft.csv"
REVIEW_OUT = OUT / "annotation_review_queue.csv"
SUMMARY_OUT = OUT / "annotation_pass_summary.json"

# B.4.2 concepts, encoded as phrase families rather than historical labels.
POS_RULE_A = [
    r"multi[- ]stakeholder", r"policy alignment", r"integrated governance", r"\bfpic\b",
    r"free prior informed consent", r"benefit[- ]sharing", r"community (?:engagement|consultation|participation)",
    r"stakeholder (?:engagement|consultation|dialogue)", r"social (?:and )?labou?r plan", r"social compact",
    r"compliance (?:improv|strengthen|progress)", r"improved compliance", r"reform", r"transparen(?:cy|t)",
    r"agreement", r"settlement", r"healing", r"renewal", r"remediation", r"compensation",
    r"partnership", r"collaborat", r"cooperat", r"constructive dialogue", r"community development",
]
NEG_RULE_A = [
    r"massacre", r"kill(?:ed|ing|ings)?", r"shoot(?:ing|ings)?", r"tortur", r"violence", r"death(?:s)?",
    r"strike", r"industrial action", r"protest", r"unrest", r"evict", r"displac", r"violation",
    r"non[- ]compliance", r"failed|failure", r"breach", r"rights? (?:denied|violat)", r"pollut",
    r"wage dispute", r"living wage crisis", r"retrench", r"job losses", r"conflict", r"opposition",
    r"neglect", r"inadequate", r"shortcoming", r"mistrust", r"accountability (?:failure|concern|gap)",
]

# Reading B emphasises explicit outcome/reform phrases versus documented conflict/failure event phrases.
POS_RULE_B = [
    r"(?:reached|signed|concluded|implemented|approved|launched|established|strengthened|improved|completed) .{0,60}(?:agreement|settlement|engagement|consultation|housing|community|compliance|reform|plan|programme)",
    r"(?:community|stakeholder).{0,35}(?:agreement|consent|engagement|participation|consultation|benefit|development)",
    r"(?:healing|renewal|reconciliation|remediation|redress|compensation|restorative)",
    r"(?:transparency|accountability|compliance).{0,35}(?:improved|strengthened|enhanced|reform|progress)",
    r"\bfpic\b|free prior informed consent|benefit[- ]sharing",
]
NEG_RULE_B = [
    r"(?:massacre|killings?|shootings?|deaths?|torture)", r"(?:strike|protest|unrest|industrial action)",
    r"(?:eviction|displacement|forced removal)", r"(?:rights?|environmental).{0,35}(?:violation|breach|denied)",
    r"(?:failed|failure|non[- ]compliance|breach|neglect|shortcoming)",
    r"(?:wage|pay).{0,30}(?:dispute|demand|strike)", r"(?:retrenchment|job losses|layoffs)",
    r"(?:conflict|opposition|violence).{0,35}(?:escalat|continue|persist|deadly|violent)",
]

POS_A = [re.compile(p, re.I) for p in POS_RULE_A]
NEG_A = [re.compile(p, re.I) for p in NEG_RULE_A]
POS_B = [re.compile(p, re.I) for p in POS_RULE_B]
NEG_B = [re.compile(p, re.I) for p in NEG_RULE_B]

GROUP_PATTERNS = {
    "government": [r"\bsaps\b", r"\bpolice\b", r"\bdmre\b", r"\bdmr\b", r"department of mineral", r"\bminister\b", r"\bgovernment\b", r"\bstate\b", r"\bregulator", r"\bcommission\b"],
    "investor": [r"\blonmin\b", r"\bsibanye(?:-stillwater)?\b", r"\bcompany\b", r"\bmanagement\b", r"\binvestor", r"\bshareholder", r"\bceo\b", r"mine operator", r"platinum producer"],
    "community": [r"\bnkaneng\b", r"\bwonderkop\b", r"\bcommunity\b", r"\bresidents?\b", r"\bfamil(?:y|ies)\b", r"\bwidows?\b", r"\bbapo\b", r"traditional council", r"local people"],
    "labour": [r"\bamcu\b", r"\bnum\b", r"\bunion\b", r"\bworkers?\b", r"\bmineworkers?\b", r"\bstrikers?\b", r"\bmathunjwa\b", r"collective bargaining", r"\bemployees?\b"],
    "NGO": [r"bench marks", r"\bseri\b", r"centre for environmental rights", r"\bcer\b", r"\bcasac\b", r"legal resources centre", r"civil society", r"human rights (?:group|organisation|organization)"],
}
GROUP_RE = {g: [re.compile(p, re.I) for p in pats] for g, pats in GROUP_PATTERNS.items()}
SPEECH = re.compile(r"\b(said|says|stated|argued|called|urged|demanded|announced|reported|maintained|contended|submitted|warned|welcomed|criticised|criticized|alleged|responded)\b", re.I)
MEDIA_PUBLISHERS = {"daily maverick", "mining weekly", "engineering news", "reuters", "news24", "business day"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\x00", " ")).strip()


def words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def text_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""


def pdf_extract(data: bytes) -> tuple[str, str]:
    # First pypdf for comparability with the freeze audit.
    try:
        reader = PdfReader(io.BytesIO(data))
        text = norm(" ".join((p.extract_text() or "") for p in reader.pages))
        if words(text) >= 80:
            return "pypdf", text
    except Exception:
        pass
    # Then PyMuPDF: substantially more robust on some annual reports.
    if fitz is not None:
        try:
            doc = fitz.open(stream=data, filetype="pdf")
            text = norm(" ".join(page.get_text("text") or "" for page in doc))
            doc.close()
            if words(text) >= 80:
                return "pymupdf", text
        except Exception:
            pass
    return "", ""


def html_extract(data: bytes, url: str) -> tuple[str, str]:
    html = data.decode("utf-8", errors="replace")
    candidates: list[tuple[str, str]] = []
    try:
        t = trafilatura.extract(html, url=url, include_comments=False, include_tables=False, favor_precision=True, no_fallback=False)
        t = norm(t or "")
        if words(t) >= 80:
            candidates.append(("trafilatura", t))
    except Exception:
        pass
    try:
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
            raw = script.string or script.get_text(" ", strip=True)
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except Exception:
                continue
            stack = obj if isinstance(obj, list) else [obj]
            while stack:
                item = stack.pop()
                if isinstance(item, dict):
                    body = item.get("articleBody")
                    if isinstance(body, str):
                        body = norm(body)
                        if words(body) >= 80:
                            candidates.append(("jsonld_articleBody", body))
                    for v in item.values():
                        if isinstance(v, (dict, list)):
                            stack.append(v)
                elif isinstance(item, list):
                    stack.extend(item)
    except Exception:
        pass
    if not candidates:
        return "", ""
    candidates.sort(key=lambda x: words(x[1]), reverse=True)
    return candidates[0]


def url_candidates(url: str) -> list[str]:
    out = [url]
    if "annualreports.co.uk/" in url:
        out.append(url.replace("annualreports.co.uk/", "annualreports.com/"))
    if url.startswith("http://"):
        out.append("https://" + url[len("http://"):])
    return list(dict.fromkeys(out))


def fetch_one(row: dict) -> dict:
    original = row["url"]
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "en-ZA,en;q=0.9"})
    last_error = ""
    for candidate in url_candidates(original):
        for attempt in range(2):
            try:
                r = session.get(candidate, timeout=60, allow_redirects=True)
                if r.status_code == 200:
                    ctype = (r.headers.get("content-type") or "").lower()
                    path = urlsplit(str(r.url)).path.lower()
                    if "application/pdf" in ctype or path.endswith(".pdf") or r.content[:5] == b"%PDF-":
                        method, text = pdf_extract(r.content)
                    else:
                        method, text = html_extract(r.content, str(r.url))
                    if text:
                        return {"id": row["canonical_record_id"], "status": "retrieved_extracted", "method": method, "text": text, "words": words(text), "sha": text_sha(text), "final_url": str(r.url), "error": ""}
                    last_error = "no_body_ge_80_words"
                else:
                    last_error = f"HTTP {r.status_code}"
                    if r.status_code in {401, 403, 404, 410}:
                        break
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(attempt + 1)
    return {"id": row["canonical_record_id"], "status": "unavailable_for_model_execution", "method": "", "text": "", "words": 0, "sha": "", "final_url": original, "error": last_error or "fetch_failed"}


def sentence_units(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if len(s.strip()) >= 25]


def hit_families(text: str, patterns: list[re.Pattern]) -> tuple[int, list[str]]:
    hits = []
    for p in patterns:
        if p.search(text):
            hits.append(p.pattern)
    return len(hits), hits


def stance_reading_a(title: str, text: str) -> dict:
    sents = sentence_units(text)
    pos_sent = sum(bool(any(p.search(s) for p in POS_A)) for s in sents)
    neg_sent = sum(bool(any(p.search(s) for p in NEG_A)) for s in sents)
    tp, tph = hit_families(title, POS_A)
    tn, tnh = hit_families(title, NEG_A)
    # log sentence counts reduce long-document length effects; title is a strong framing signal.
    score = math.log1p(pos_sent) - math.log1p(neg_sent) + 1.15 * (tp - tn)
    label = int(score >= 0)
    margin = abs(score)
    return {"label": label, "score": score, "pos_sent": pos_sent, "neg_sent": neg_sent, "title_pos": tp, "title_neg": tn, "cues": sorted(set(tph + tnh))[:12], "margin": margin}


def stance_reading_b(title: str, text: str) -> dict:
    # More outcome-specific reading, using only explicit reform/resolution and failure/conflict expressions.
    sents = sentence_units(text)
    pos = sum(bool(any(p.search(s) for p in POS_B)) for s in sents)
    neg = sum(bool(any(p.search(s) for p in NEG_B)) for s in sents)
    tp, tph = hit_families(title, POS_B)
    tn, tnh = hit_families(title, NEG_B)
    score = math.sqrt(pos) - math.sqrt(neg) + 1.5 * (tp - tn)
    label = int(score >= 0)
    return {"label": label, "score": score, "pos_sent": pos, "neg_sent": neg, "title_pos": tp, "title_neg": tn, "cues": sorted(set(tph + tnh))[:12], "margin": abs(score)}


def authored_group(row: dict) -> str | None:
    p = (row.get("publisher") or "").lower()
    t = (row.get("title") or "").lower()
    if any(x in p for x in ("lonmin", "sibanye")):
        return "investor"
    if re.search(r"\bamcu\b|\bnum\b|mathunjwa|trade union", p + " " + t):
        return "labour"
    if any(x in p for x in ("bench marks", "socio-economic rights institute", "centre for environmental rights", "legal resources centre", "casac")):
        return "NGO"
    if re.search(r"famil(?:y|ies)|bapo|ledingoane|injured and arrested", p + " " + t):
        return "community"
    if re.search(r"saps|department|minister|commission|mthethwa|ramaphosa|government|dmr|dmre|human rights commission", p + " " + t):
        return "government"
    return None


def stakeholder_voice(row: dict, text: str) -> dict:
    pub = (row.get("publisher") or "").strip().lower()
    source_authored = authored_group(row)
    # Non-news first-party/institutional documents are assigned to their authoring stakeholder.
    if source_authored and not any(x in pub for x in MEDIA_PUBLISHERS):
        return {"group": source_authored, "confidence": 1.0, "method": "document_author_group", "scores": {g: int(g == source_authored) * 10.0 for g in GROUP_RE}}

    scores = {g: 0.0 for g in GROUP_RE}
    title = row.get("title", "")
    for g, pats in GROUP_RE.items():
        scores[g] += 3.0 * sum(bool(p.search(title)) for p in pats)

    for sent in sentence_units(text):
        spoken = bool(SPEECH.search(sent))
        for g, pats in GROUP_RE.items():
            n = sum(bool(p.search(sent)) for p in pats)
            if n:
                scores[g] += n * (2.5 if spoken else 0.35)

    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    top_g, top = ordered[0]
    second = ordered[1][1]
    total = sum(scores.values())
    if total <= 0:
        # Last-resort author inference keeps the five-group design explicit but flags zero confidence.
        fallback = source_authored or "government"
        return {"group": fallback, "confidence": 0.0, "method": "fallback_no_actor_signal", "scores": scores}
    conf = max(0.0, min(1.0, (top - second) / max(top, 1.0)))
    return {"group": top_g, "confidence": conf, "method": "dominant_voice_proxy", "scores": scores}


def decision(a: dict, b: dict, stakeholder: dict) -> tuple[str, float, bool, str]:
    agree = a["label"] == b["label"]
    # Strong agreement: both readings point the same way and at least one has useful separation.
    confidence = min(1.0, (a["margin"] + b["margin"]) / 5.0)
    stakeholder_low = stakeholder["confidence"] < 0.12 and stakeholder["method"] == "dominant_voice_proxy"
    if agree and confidence >= 0.18:
        needs = stakeholder_low
        reason = "stakeholder_voice_low_confidence" if stakeholder_low else "computational_readings_agree"
        return str(a["label"]), confidence, needs, reason
    return "", confidence, True, "stance_readings_disagree_or_low_margin" if not agree or confidence < 0.18 else "stakeholder_voice_low_confidence"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    observed_sha = sha256_file(MANIFEST)
    if observed_sha != EXPECTED_MANIFEST_SHA:
        raise RuntimeError(f"Frozen analysis manifest hash drift: {observed_sha}")
    freeze_hashes = json.loads(FREEZE_HASHES.read_text(encoding="utf-8"))
    if freeze_hashes.get("canonical_analysis_ready_manifest.csv") != EXPECTED_MANIFEST_SHA:
        raise RuntimeError("Freeze hash registry disagrees with expected analysis manifest")
    rows = read_csv(MANIFEST)
    if len(rows) != EXPECTED_N:
        raise RuntimeError(f"Expected frozen N={EXPECTED_N}, got {len(rows)}")

    fetched: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(fetch_one, r): r["canonical_record_id"] for r in rows}
        for fut in as_completed(futs):
            res = fut.result()
            fetched[res["id"]] = res

    recovery_rows = []
    draft_rows = []
    for row in rows:
        rid = row["canonical_record_id"]
        res = fetched[rid]
        recovery_rows.append({
            "record_id": rid, "title": row["title"], "year": row["year"], "publisher": row["publisher"],
            "url": row["url"], "execution_recovery_status": res["status"], "execution_extraction_method": res["method"],
            "execution_words": res["words"], "execution_text_sha256": res["sha"], "final_url": res["final_url"], "error": res["error"],
            "frozen_provenance_text_sha256": row["text_sha256"], "frozen_provenance_text_words": row["text_words"],
        })
        if res["status"] != "retrieved_extracted":
            draft_rows.append({
                "record_id": rid, "title": row["title"], "year": row["year"], "publisher": row["publisher"], "url": row["url"],
                "stakeholder_group_proxy": authored_group(row) or "", "stakeholder_confidence": "", "stakeholder_method": "text_unavailable",
                "stance_a_label": "", "stance_a_score": "", "stance_b_label": "", "stance_b_score": "",
                "draft_reconstructed_label": "", "annotation_confidence": "", "needs_review": "true",
                "review_reason": "text_unavailable_at_execution", "positive_cue_families": "", "negative_cue_families": "",
            })
            continue

        a = stance_reading_a(row["title"], res["text"])
        b = stance_reading_b(row["title"], res["text"])
        sg = stakeholder_voice(row, res["text"])
        label, conf, needs, reason = decision(a, b, sg)
        pos_cues = sorted(set(a["cues"] + b["cues"]))
        # Separate by sign for audit readability without exposing source prose.
        positive = [x for x in pos_cues if any(x == p.pattern for p in POS_A + POS_B)]
        negative = [x for x in pos_cues if any(x == p.pattern for p in NEG_A + NEG_B)]
        draft_rows.append({
            "record_id": rid, "title": row["title"], "year": row["year"], "publisher": row["publisher"], "url": row["url"],
            "stakeholder_group_proxy": sg["group"], "stakeholder_confidence": f"{sg['confidence']:.4f}", "stakeholder_method": sg["method"],
            "stakeholder_score_government": f"{sg['scores']['government']:.3f}", "stakeholder_score_investor": f"{sg['scores']['investor']:.3f}",
            "stakeholder_score_community": f"{sg['scores']['community']:.3f}", "stakeholder_score_labour": f"{sg['scores']['labour']:.3f}",
            "stakeholder_score_NGO": f"{sg['scores']['NGO']:.3f}",
            "stance_a_label": a["label"], "stance_a_score": f"{a['score']:.5f}", "stance_a_positive_sentences": a["pos_sent"], "stance_a_negative_sentences": a["neg_sent"],
            "stance_b_label": b["label"], "stance_b_score": f"{b['score']:.5f}", "stance_b_positive_sentences": b["pos_sent"], "stance_b_negative_sentences": b["neg_sent"],
            "draft_reconstructed_label": label, "annotation_confidence": f"{conf:.4f}", "needs_review": str(needs).lower(), "review_reason": reason,
            "positive_cue_families": " | ".join(positive[:12]), "negative_cue_families": " | ".join(negative[:12]),
        })

    def write_csv(path: Path, data: list[dict]):
        fields = []
        for r in data:
            for k in r:
                if k not in fields:
                    fields.append(k)
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader(); w.writerows(data)

    write_csv(RECOVERY_OUT, recovery_rows)
    write_csv(DRAFT_OUT, draft_rows)
    review = [r for r in draft_rows if r.get("needs_review") == "true"]
    write_csv(REVIEW_OUT, review)

    usable = [r for r in draft_rows if r.get("stance_a_label") != ""]
    final = [r for r in draft_rows if r.get("draft_reconstructed_label") != ""]
    summary = {
        "stage": "post_freeze_computational_reannotation_pass_1",
        "frozen_analysis_manifest_sha256": observed_sha,
        "frozen_analysis_ready_records": len(rows),
        "texts_recovered_for_execution": sum(r["execution_recovery_status"] == "retrieved_extracted" for r in recovery_rows),
        "texts_unavailable_at_execution": sum(r["execution_recovery_status"] != "retrieved_extracted" for r in recovery_rows),
        "draft_labels_without_review": len(final),
        "review_queue_records": len(review),
        "computational_readings_agreement_rate_on_recovered_text": (sum(str(r.get("stance_a_label")) == str(r.get("stance_b_label")) for r in usable) / len(usable)) if usable else None,
        "draft_label_counts": dict(Counter(r["draft_reconstructed_label"] for r in final)),
        "stakeholder_proxy_counts_recovered": dict(Counter(r["stakeholder_group_proxy"] for r in usable)),
        "historical_71_16_distribution_used_as_target": False,
        "legacy_svm_labels_used": False,
        "human_annotation_claim": False,
        "model_fitting_performed": False,
        "important_limitation": "These are reconstructed computational annotations applying the documented B.4.2 criteria. They do not reproduce the unavailable historical two-human-annotator labels; disagreements and low-confidence cases are deliberately withheld for review before model fitting.",
    }
    SUMMARY_OUT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
