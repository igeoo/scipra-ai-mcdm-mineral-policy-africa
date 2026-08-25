"""Targeted acquired-text evidence pass for the 154 Lonmin-only low-case-signal rows.

This is a screening aid, not a final decision engine. It fetches only the rows
currently marked `manual_review_lonmin_only_low_case_signal`, extracts article
text in the Actions runner, derives transparent signals, writes metadata/hash
outputs, and does not commit or redistribute the full article text.
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
OUT = RECON / "low_signal_substantive_evidence.csv"
SUMMARY = RECON / "low_signal_substantive_evidence_summary.json"

UA = "Mozilla/5.0 (compatible; SCIPRA-Reproducibility-Screen/1.0; +https://github.com/Martin-do/scipra-ai-mcdm-mineral-policy-africa)"
DATE_RX = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")

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
CASE = {
    "marikana": re.compile(r"\bmarikana\b", re.I),
    "farlam": re.compile(r"\bfarlam\b", re.I),
    "wonderkop": re.compile(r"\bwonderkop\b", re.I),
    "nkaneng": re.compile(r"\bnkaneng\b", re.I),
    "bapo": re.compile(r"\bbapo(?:-ba-mogale)?\b", re.I),
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
    r"guidance|capex)\b", re.I
)


def read_rows():
    with TRIAGE.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if r.get("triage_status") == "manual_review_lonmin_only_low_case_signal"]


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
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    last = ""
    for attempt in range(2):
        try:
            resp = session.get(url, timeout=30, allow_redirects=True)
            if resp.status_code == 200:
                text = extract_html(resp.content, str(resp.url))
                return row, text, str(resp.url), ""
            last = f"HTTP {resp.status_code}"
            if resp.status_code in {401, 403, 404, 410}:
                break
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(attempt + 1)
    return row, "", url, last or "fetch_failed"


def hits(patterns, text):
    names = []
    total = 0
    for name, rx in patterns.items():
        c = len(rx.findall(text))
        if c:
            names.append(name)
            total += c
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
    event_names, event_total = hits(EVENT, text)
    social_names, social_total = hits(SOCIAL, text)
    case_names, case_total = hits(CASE, text)
    corp_names, corp_total = hits(CORP, text)
    event_d = len(event_names)
    social_d = len(social_names)
    corp_d = len(corp_names)
    lonmin_n = len(re.findall(r"\blonmin\b", text, re.I))
    try:
        dt = date.fromisoformat(d) if d else None
    except ValueError:
        dt = None
    early = bool(dt and date(2012, 8, 10) <= dt <= date(2012, 10, 31))
    title_corp = bool(TITLE_CORP.search(title or ""))

    if len(text) < 500:
        klass = "acquisition_or_text_exception"
        note = "Less than 500 extracted characters; no substantive decision should be made from title alone."
    elif early and lonmin_n >= 3 and event_d >= 3 and ("strike" in event_names or "worker_miner" in event_names) and (
        "police" in event_names or "shooting_death" in event_names or "wage" in event_names or "union" in event_names
    ):
        klass = "strong_early_2012_event_context"
        note = "Contemporaneous Lonmin coverage has multiple independent strike/worker/police/death/wage/union signals."
    elif case_total > 0 and (event_d >= 2 or social_d >= 1):
        klass = "case_context_supported"
        note = "A case/place term is supported by labour/event or social/governance context."
    elif title_corp and corp_d >= 2 and event_d <= 1 and social_d == 0 and case_total == 0:
        klass = "strong_routine_corporate_signal"
        note = "Routine corporate/financial/production title and text with minimal labour/community evidence and no case term."
    elif corp_d >= 3 and event_d <= 1 and social_d == 0 and case_total == 0:
        klass = "likely_routine_corporate_signal"
        note = "Multiple corporate/financial signals with weak case-event/community evidence."
    elif event_d >= 3 or social_d >= 2:
        klass = "possible_substantive_case_context"
        note = "Multiple labour/event or social/governance signals require direct substantive review."
    else:
        klass = "ambiguous_low_signal"
        note = "Signals are insufficient for a defensible decision."

    return {
        "publication_date_from_url": d,
        "retrieved_text_words": len(re.findall(r"\b\w+\b", text)),
        "retrieved_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest() if text else "",
        "retrieved_lonmin_mentions": lonmin_n,
        "case_terms": ";".join(case_names),
        "case_mentions_total": case_total,
        "event_terms": ";".join(event_names),
        "event_mentions_total": event_total,
        "event_distinct_terms": event_d,
        "social_terms": ";".join(social_names),
        "social_mentions_total": social_total,
        "social_distinct_terms": social_d,
        "corporate_terms": ";".join(corp_names),
        "corporate_mentions_total": corp_total,
        "corporate_distinct_terms": corp_d,
        "early_aug_oct_2012_window": str(early).lower(),
        "title_has_routine_corporate_signal": str(title_corp).lower(),
        "evidence_class": klass,
        "evidence_note": note,
    }


source = read_rows()
results = []
counts = Counter()
fetch_counts = Counter()
with ThreadPoolExecutor(max_workers=4) as pool:
    futures = [pool.submit(fetch_one, row) for row in source]
    for future in as_completed(futures):
        row, text, final_url, error = future.result()
        if text:
            fetch_status = "retrieved_extracted"
        else:
            fetch_status = "failed_or_no_text"
        fetch_counts[fetch_status] += 1
        evidence = classify(row, text)
        counts[evidence["evidence_class"]] += 1
        results.append({
            "candidate_id": row.get("candidate_id", ""),
            "title": row.get("title", ""),
            "year": row.get("year", ""),
            "publisher": row.get("publisher", ""),
            "url": row.get("url", ""),
            "final_url": final_url,
            "original_text_sha256": row.get("text_sha256", ""),
            "targeted_fetch_status": fetch_status,
            "targeted_fetch_error": error,
            **evidence,
            "final_decision": "",
            "final_reason_code": "",
            "final_evidence_note": "",
        })

results.sort(key=lambda r: r["candidate_id"])
if results:
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader(); w.writerows(results)

summary = {
    "target_group": "manual_review_lonmin_only_low_case_signal",
    "expected_records": 154,
    "records_processed": len(results),
    "targeted_fetch_status_counts": dict(fetch_counts),
    "evidence_class_counts": dict(counts),
    "final_decisions_made": 0,
    "note": "Targeted evidence only; no article text is committed and no final membership decision is automated."
}
SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
