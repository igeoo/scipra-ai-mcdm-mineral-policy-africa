"""Lightweight acquired-text evidence pass for all 690 archive title-trigger media records.

The script re-fetches the public article URLs in the Actions runner, extracts text,
derives transparent relevance signals, and commits metadata/hashes only. It does
not redistribute article text and does not itself make final corpus decisions.

The classification deliberately distinguishes the Marikana case from the use of
`Marikana` as a mine/place/project name. Strong case evidence requires labour,
event, justice, community or governance context, or a clearly case-process title.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import requests
import trafilatura
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "data" / "reconstruction"
TRIAGE = RECON / "media_substantive_screen_triage.csv"
OUT = RECON / "media_targeted_substantive_evidence.csv"
SUMMARY = RECON / "media_targeted_substantive_evidence_summary.json"

UA = "Mozilla/5.0 (compatible; SCIPRA-Reproducibility-Screen/1.1; +https://github.com/Martin-do/scipra-ai-mcdm-mineral-policy-africa)"
DATE_RX = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")

CASE = {
    "marikana": re.compile(r"\bmarikana\b", re.I),
    "farlam": re.compile(r"\bfarlam\b", re.I),
    "wonderkop": re.compile(r"\bwonderkop\b", re.I),
    "nkaneng": re.compile(r"\bnkaneng\b", re.I),
    "bapo": re.compile(r"\bbapo(?:-ba-mogale)?\b", re.I),
}
EVENT = {
    "strike": re.compile(r"\bstrik(?:e|es|ing|er|ers)\b", re.I),
    "worker_miner": re.compile(r"\b(?:mine\s*)?workers?\b|\bminers?\b|\brock[- ]?drill(?: operators?)?\b|\brdos?\b", re.I),
    "police": re.compile(r"\bpolice\b|\bsaps\b", re.I),
    "shooting_death": re.compile(r"\bshoot(?:ing|ings|out)?\b|\bshot\b|\bkill(?:ed|ing|ings)?\b|\bdeaths?\b|\bdead\b|\bmassacre\b", re.I),
    "wage": re.compile(r"\bwages?\b|\bsalar(?:y|ies)\b|\bpay\b|\b12\s*[,.]?\s*500\b", re.I),
    "union": re.compile(r"\bamcu\b|\bnum\b|\bunion(?:s|ists?)?\b", re.I),
    "protest_unrest": re.compile(r"\bprotest(?:s|ers?|ing)?\b|\bunrest\b|\bviolence\b", re.I),
    "koppie": re.compile(r"\bkoppie\b", re.I),
}
SOCIAL = {
    "housing": re.compile(r"\bhous(?:e|es|ing)\b|\bhostels?\b", re.I),
    "community": re.compile(r"\bcommunit(?:y|ies)\b", re.I),
    "slp": re.compile(r"\bsocial and labour plan\b|\bslps?\b", re.I),
    "justice_accountability": re.compile(r"\bjustice\b|\baccountab(?:ility|le)\b|\bprosecut(?:e|ed|ion|ions)\b|\bcompensat(?:e|ed|ion)\b|\bdamages\b", re.I),
    "commission_inquiry": re.compile(r"\bcommission\b|\binquiry\b", re.I),
}
CORP = {
    "share_price": re.compile(r"\bshare price\b|\bshares?\b|\bstock\b", re.I),
    "earnings_results": re.compile(r"\bearnings\b|\bresults\b|\brevenue\b|\bprofit\b|\bloss\b|\bebitda\b", re.I),
    "production_output": re.compile(r"\bproduction\b|\boutput\b|\bounces?\b|\btonnes?\b", re.I),
    "funding_debt": re.compile(r"\bfunding\b|\bfinance\b|\bfinancing\b|\brefinanc(?:e|ed|ing)\b|\bdebt\b|\bloan\b|\bbond\b|\bcredit\b", re.I),
    "transaction": re.compile(r"\bacquisition\b|\bacquire[sd]?\b|\bdisposal\b|\bdispose[sd]?\b|\bstake\b|\bsell(?:s|ing)?\b|\bsold\b|\bbuy(?:s|ing)?\b|\bmerger\b|\btakeover\b", re.I),
    "dividend_rights": re.compile(r"\bdividend\b|\brights issue\b|\bcapital raising\b", re.I),
    "exploration_project": re.compile(r"\bexploration\b|\bproject\b|\btailings\b|\bsmelter\b|\bfurnace\b|\brefinery\b|\bshaft\b", re.I),
    "commodity_market": re.compile(r"\bplatinum price\b|\bmetal prices?\b|\bcommodity\b|\bmarket\b", re.I),
}
TITLE_CORP = re.compile(
    r"\b(?:funding|financing|refinancing|stake|share price|earnings|results|production|output|"
    r"acquisition|acquires?|disposal|sells?|sold|merger|takeover|dividend|rights issue|"
    r"tailings|petrozim|wallbridge|canadian junior|platinum price|furnace|smelter|project|"
    r"platinum group metals|pgm|guidance|capex|portfolio)\b", re.I
)
TITLE_CASE_PROCESS = re.compile(
    r"\b(?:massacre|commission|farlam|famil(?:y|ies)|widows?|victims?|police|saps|"
    r"kill(?:ed|ing|ings)?|shoot(?:ing|ings)?|strike|workers?|miners?|justice|"
    r"prosecut(?:e|ed|ion|ions)|accountab(?:ility|le)|compensat(?:e|ed|ion)|"
    r"housing|community|social and labour plan|slp|memorial|anniversary|amcu|num|"
    r"retrench(?:ment|ments)|job losses?)\b", re.I
)


def read_rows():
    with TRIAGE.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def normalise(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_html(data: bytes, url: str) -> str:
    html = data.decode("utf-8", errors="replace")
    try:
        text = trafilatura.extract(html, url=url, include_comments=False, include_tables=False, favor_precision=True, no_fallback=False)
        if text and len(text.strip()) >= 200:
            return normalise(text)
    except Exception:
        pass
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "form"]):
        tag.decompose()
    container = soup.find("article") or soup.find("main") or soup.body or soup
    paras = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    return normalise("\n\n".join(x for x in paras if x))


def fetch_one(row):
    url = row.get("url", "")
    s = requests.Session(); s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    last = ""
    for attempt in range(2):
        try:
            resp = s.get(url, timeout=30, allow_redirects=True)
            if resp.status_code == 200:
                return row, extract_html(resp.content, str(resp.url)), str(resp.url), ""
            last = f"HTTP {resp.status_code}"
            if resp.status_code in {401, 403, 404, 410}:
                break
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(attempt + 1)
    return row, "", url, last or "fetch_failed"


def hits(patterns, text):
    names, total = [], 0
    for name, rx in patterns.items():
        c = len(rx.findall(text))
        if c:
            names.append(name); total += c
    return names, total


def pub_date(url):
    m = DATE_RX.search(url or "")
    if not m:
        return ""
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return ""


def classify(row, text):
    title = row.get("title", "")
    d = pub_date(row.get("url", ""))
    case_names, case_total = hits(CASE, text)
    event_names, event_total = hits(EVENT, text)
    social_names, social_total = hits(SOCIAL, text)
    corp_names, corp_total = hits(CORP, text)
    event_d, social_d, corp_d = len(event_names), len(social_names), len(corp_names)
    lonmin_n = len(re.findall(r"\blonmin\b", text, re.I))
    try: dt = date.fromisoformat(d) if d else None
    except ValueError: dt = None
    early = bool(dt and date(2012, 8, 10) <= dt <= date(2012, 10, 31))
    title_corp = bool(TITLE_CORP.search(title or ""))
    title_case = bool(TITLE_CASE_PROCESS.search(title or ""))

    if len(text) < 500:
        klass = "acquisition_or_text_exception"
        note = "Less than 500 extracted characters; direct review/recovery required before a final decision."
    elif early and lonmin_n >= 3 and event_d >= 3 and ("strike" in event_names or "worker_miner" in event_names) and (
        "police" in event_names or "shooting_death" in event_names or "wage" in event_names or "union" in event_names
    ):
        klass = "strong_early_2012_event_context"
        note = "Contemporaneous Lonmin coverage has multiple independent strike/worker/police/death/wage/union signals."
    elif case_total > 0 and (event_d >= 2 or social_d >= 1 or title_case):
        klass = "strong_case_context_supported"
        note = "Case/place term is supported by event, labour, justice, community/governance context or a clearly case-process title."
    elif case_total > 0 and title_corp and corp_d >= 1 and event_d <= 1 and social_d == 0 and not title_case:
        klass = "case_name_only_routine_project_or_corporate_signal"
        note = "Marikana-related name is present but context is dominated by project/production/corporate material."
    elif case_total > 0:
        klass = "case_term_low_context_review"
        note = "Case/place term occurs but context is too weak to distinguish substantive case treatment from place/project/incidental use."
    elif title_corp and corp_d >= 2 and event_d <= 1 and social_d == 0 and not title_case:
        klass = "strong_routine_corporate_signal"
        note = "Routine corporate/financial/production title and text with minimal labour/community evidence and no case term."
    elif corp_d >= 3 and event_d <= 1 and social_d == 0 and not title_case:
        klass = "likely_routine_corporate_signal"
        note = "Multiple corporate/financial signals with weak case-event/community evidence."
    elif event_d >= 3 or social_d >= 2 or title_case:
        klass = "possible_substantive_case_context"
        note = "Labour/event/community/governance or case-process title signals require substantive review."
    else:
        klass = "ambiguous_low_signal"
        note = "Signals are insufficient for a defensible inclusion/exclusion decision."

    return {
        "publication_date_from_url": d,
        "retrieved_text_words": len(re.findall(r"\b\w+\b", text)),
        "retrieved_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest() if text else "",
        "retrieved_lonmin_mentions": lonmin_n,
        "case_terms": ";".join(case_names), "case_mentions_total": case_total,
        "event_terms": ";".join(event_names), "event_mentions_total": event_total, "event_distinct_terms": event_d,
        "social_terms": ";".join(social_names), "social_mentions_total": social_total, "social_distinct_terms": social_d,
        "corporate_terms": ";".join(corp_names), "corporate_mentions_total": corp_total, "corporate_distinct_terms": corp_d,
        "early_aug_oct_2012_window": str(early).lower(),
        "title_has_routine_corporate_signal": str(title_corp).lower(),
        "title_has_case_process_signal": str(title_case).lower(),
        "evidence_class": klass, "evidence_note": note,
    }


source = read_rows(); results = []; counts = Counter(); fetch_counts = Counter(); bucket_counts = Counter()
with ThreadPoolExecutor(max_workers=6) as pool:
    futures = [pool.submit(fetch_one, row) for row in source]
    for future in as_completed(futures):
        row, text, final_url, error = future.result()
        fetch_status = "retrieved_extracted" if text else "failed_or_no_text"
        fetch_counts[fetch_status] += 1
        evidence = classify(row, text); counts[evidence["evidence_class"]] += 1
        bucket_counts[row.get("prescreen_bucket", "missing")] += 1
        results.append({
            "candidate_id": row.get("candidate_id", ""), "title": row.get("title", ""), "year": row.get("year", ""),
            "publisher": row.get("publisher", ""), "url": row.get("url", ""), "final_url": final_url,
            "prescreen_bucket": row.get("prescreen_bucket", ""), "original_triage_status": row.get("triage_status", ""),
            "original_text_sha256": row.get("text_sha256", ""), "targeted_fetch_status": fetch_status,
            "targeted_fetch_error": error, **evidence,
            "final_decision": "", "final_reason_code": "", "final_evidence_note": "",
        })

results.sort(key=lambda r: r["candidate_id"])
if results:
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys())); w.writeheader(); w.writerows(results)
summary = {
    "target_group": "all_archive_title_trigger_media_candidates",
    "expected_records": 690,
    "records_processed": len(results),
    "prescreen_bucket_counts": dict(bucket_counts),
    "targeted_fetch_status_counts": dict(fetch_counts),
    "evidence_class_counts": dict(counts),
    "final_decisions_made": 0,
    "important_boundary": "Literal Marikana/place/project-name matching is not sufficient; case context is required.",
    "note": "Targeted evidence only; no article text is committed and no final membership decision is automated."
}
SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
