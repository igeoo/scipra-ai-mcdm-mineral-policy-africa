"""Derive transparent evidence for substantive review of archive media candidates.

This script does not make final corpus inclusion/exclusion decisions. It uses
acquired text to generate reproducible case/event, labour/community and routine
corporate-financial signals so the decision ledger can be reviewed efficiently.
No stance labels, historical class targets, model scores or downstream outcomes
are used.

Important boundary: a literal `Marikana` occurrence is not sufficient by itself.
Marikana is also a place/mine/project name, so event, labour, justice, community
or governance context is required before a case-term match is treated as strong
case evidence.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "data" / "reconstruction"
ACQ = ROOT / "acquisition_output"
TRIAGE = RECON / "media_substantive_screen_triage.csv"
TEXT_DIR = ACQ / "text"
OUT = RECON / "media_screening_evidence.csv"
SUMMARY = RECON / "media_screening_evidence_summary.json"

DATE_RX = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")

EVENT_PATTERNS = {
    "strike": re.compile(r"\bstrik(?:e|es|ing|er|ers)\b", re.I),
    "worker_miner": re.compile(r"\b(?:mine\s*)?workers?\b|\bminers?\b|\brock[- ]?drill(?: operators?)?\b|\brdos?\b", re.I),
    "police": re.compile(r"\bpolice\b|\bsaps\b", re.I),
    "shooting_death": re.compile(r"\bshoot(?:ing|ings|out)?\b|\bshot\b|\bkill(?:ed|ing|ings)?\b|\bdeaths?\b|\bdead\b|\bmassacre\b", re.I),
    "wage": re.compile(r"\bwages?\b|\bsalar(?:y|ies)\b|\bpay\b|\b12\s*[,.]?\s*500\b", re.I),
    "union": re.compile(r"\bamcu\b|\bnum\b|\bunion(?:s|ists?)?\b", re.I),
    "protest_unrest": re.compile(r"\bprotest(?:s|ers?|ing)?\b|\bunrest\b|\bviolence\b", re.I),
    "koppie": re.compile(r"\bkoppie\b", re.I),
}

CASE_PATTERNS = {
    "marikana": re.compile(r"\bmarikana\b", re.I),
    "farlam": re.compile(r"\bfarlam\b", re.I),
    "wonderkop": re.compile(r"\bwonderkop\b", re.I),
    "nkaneng": re.compile(r"\bnkaneng\b", re.I),
    "bapo": re.compile(r"\bbapo(?:-ba-mogale)?\b", re.I),
}

SOCIAL_PATTERNS = {
    "housing": re.compile(r"\bhous(?:e|es|ing)\b|\bhostels?\b", re.I),
    "community": re.compile(r"\bcommunit(?:y|ies)\b", re.I),
    "slp": re.compile(r"\bsocial and labour plan\b|\bslps?\b", re.I),
    "justice_accountability": re.compile(r"\bjustice\b|\baccountab(?:ility|le)\b|\bprosecut(?:e|ed|ion|ions)\b|\bcompensat(?:e|ed|ion)\b|\bdamages\b", re.I),
    "commission_inquiry": re.compile(r"\bcommission\b|\binquiry\b", re.I),
}

CORPORATE_PATTERNS = {
    "share_price": re.compile(r"\bshare price\b|\bshares?\b|\bstock\b", re.I),
    "earnings_results": re.compile(r"\bearnings\b|\bresults\b|\brevenue\b|\bprofit\b|\bloss\b|\bebitda\b", re.I),
    "production_output": re.compile(r"\bproduction\b|\boutput\b|\bounces?\b|\btonnes?\b", re.I),
    "funding_debt": re.compile(r"\bfunding\b|\bfinance\b|\bfinancing\b|\brefinanc(?:e|ed|ing)\b|\bdebt\b|\bloan\b|\bbond\b|\bcredit\b", re.I),
    "transaction": re.compile(r"\bacquisition\b|\bacquire[sd]?\b|\bdisposal\b|\bdispose[sd]?\b|\bstake\b|\bsell(?:s|ing)?\b|\bsold\b|\bbuy(?:s|ing)?\b|\bmerger\b|\btakeover\b", re.I),
    "dividend_rights": re.compile(r"\bdividend\b|\brights issue\b|\bcapital raising\b", re.I),
    "exploration_project": re.compile(r"\bexploration\b|\bproject\b|\btailings\b|\bsmelter\b|\bfurnace\b|\brefinery\b|\bshaft\b", re.I),
    "commodity_market": re.compile(r"\bplatinum price\b|\bmetal prices?\b|\bcommodity\b|\bmarket\b", re.I),
}

TITLE_CORPORATE_RX = re.compile(
    r"\b(?:funding|financing|refinancing|stake|share price|earnings|results|production|output|"
    r"acquisition|acquires?|disposal|sells?|sold|merger|takeover|dividend|rights issue|"
    r"tailings|petrozim|wallbridge|canadian junior|platinum price|furnace|smelter|project|"
    r"platinum group metals|pgm|guidance|capex)\b",
    re.I,
)

TITLE_CASE_PROCESS_RX = re.compile(
    r"\b(?:massacre|commission|farlam|famil(?:y|ies)|widows?|victims?|police|saps|"
    r"kill(?:ed|ing|ings)?|shoot(?:ing|ings)?|strike|workers?|miners?|justice|"
    r"prosecut(?:e|ed|ion|ions)|accountab(?:ility|le)|compensat(?:e|ed|ion)|"
    r"housing|community|social and labour plan|slp|memorial|anniversary|amcu|num)\b",
    re.I,
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def n(pattern: re.Pattern[str], text: str) -> int:
    return len(pattern.findall(text or ""))


def matched_names(patterns: dict[str, re.Pattern[str]], text: str) -> tuple[list[str], int]:
    names = []
    total = 0
    for name, rx in patterns.items():
        c = n(rx, text)
        if c:
            names.append(name)
            total += c
    return names, total


def parse_date(url: str) -> str:
    m = DATE_RX.search(url or "")
    if not m:
        return ""
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return ""


def early_event_window(pub_date: str) -> bool:
    if not pub_date:
        return False
    try:
        d = date.fromisoformat(pub_date)
    except ValueError:
        return False
    return date(2012, 8, 10) <= d <= date(2012, 10, 31)


rows = []
class_counts: Counter[str] = Counter()
triage_rows = read_csv(TRIAGE)

for r in triage_rows:
    cid = (r.get("candidate_id") or "").strip()
    text_path = TEXT_DIR / f"{cid}.txt"
    text = text_path.read_text(encoding="utf-8", errors="replace") if text_path.exists() else ""
    title = r.get("title", "")
    pub_date = parse_date(r.get("url", ""))

    event_names, event_total = matched_names(EVENT_PATTERNS, text)
    case_names, case_total = matched_names(CASE_PATTERNS, text)
    social_names, social_total = matched_names(SOCIAL_PATTERNS, text)
    corporate_names, corporate_total = matched_names(CORPORATE_PATTERNS, text)

    event_distinct = len(event_names)
    social_distinct = len(social_names)
    corporate_distinct = len(corporate_names)
    title_corporate = bool(TITLE_CORPORATE_RX.search(title or ""))
    title_case_process = bool(TITLE_CASE_PROCESS_RX.search(title or ""))
    early_2012 = early_event_window(pub_date)
    lonmin_mentions = int(r.get("lonmin_mentions") or 0)

    if (r.get("acquisition_status") or "") != "acquired_extracted":
        evidence_class = "acquisition_exception"
        evidence_note = "Usable extracted text is unavailable; no substantive decision should be made from title alone."
    elif early_2012 and lonmin_mentions >= 3 and event_distinct >= 3 and (
        "strike" in event_names or "worker_miner" in event_names
    ) and (
        "police" in event_names or "shooting_death" in event_names or "wage" in event_names or "union" in event_names
    ):
        evidence_class = "strong_early_2012_event_context"
        evidence_note = (
            "Contemporaneous Aug-Oct 2012 Lonmin coverage has multiple independent strike/worker/police/death/wage/union signals; "
            "the absence of the literal word Marikana is not treated as exclusion evidence."
        )
    elif case_total > 0 and (event_distinct >= 2 or social_distinct >= 1 or title_case_process):
        evidence_class = "strong_case_context_supported"
        evidence_note = (
            "A Marikana/Farlam/Wonderkop/Nkaneng/Bapo term is supported by event, labour, justice, community or governance context; "
            "the case term is not being treated as sufficient on its own."
        )
    elif case_total > 0 and title_corporate and corporate_distinct >= 1 and event_distinct <= 1 and social_distinct == 0:
        evidence_class = "case_name_only_routine_project_or_corporate_signal"
        evidence_note = (
            "The text/title contains a Marikana-related name but is dominated by project/production/corporate context without substantive "
            "event, labour, justice, community or governance evidence. This guards against place/mine/project-name false positives."
        )
    elif case_total > 0:
        evidence_class = "case_term_low_context_review"
        evidence_note = (
            "A high-specificity place/case term occurs, but contextual evidence is too weak to distinguish substantive Marikana-case treatment "
            "from a place/project name or incidental historical reference."
        )
    elif title_corporate and corporate_distinct >= 2 and event_distinct <= 1 and social_distinct == 0:
        evidence_class = "strong_routine_corporate_signal"
        evidence_note = (
            "Title and extracted text are dominated by routine corporate/financial/production signals with no high-specificity case term "
            "and minimal labour/community event signal."
        )
    elif corporate_distinct >= 3 and event_distinct <= 1 and social_distinct == 0:
        evidence_class = "likely_routine_corporate_signal"
        evidence_note = (
            "Extracted text has multiple routine corporate/financial signals with weak case-event/community evidence; manual confirmation remains required."
        )
    elif event_distinct >= 3 or social_distinct >= 2:
        evidence_class = "possible_substantive_case_context"
        evidence_note = (
            "Extracted text contains multiple labour/event or community/governance signals but lacks a high-specificity case term; direct substantive review is required."
        )
    else:
        evidence_class = "ambiguous_low_signal"
        evidence_note = "Automated evidence signals are insufficient for a defensible inclusion/exclusion decision."

    class_counts[evidence_class] += 1
    rows.append({
        "candidate_id": cid,
        "title": title,
        "year": r.get("year", ""),
        "publication_date_from_url": pub_date,
        "publisher": r.get("publisher", ""),
        "url": r.get("url", ""),
        "prescreen_bucket": r.get("prescreen_bucket", ""),
        "triage_status": r.get("triage_status", ""),
        "acquisition_status": r.get("acquisition_status", ""),
        "text_words": r.get("text_words", ""),
        "text_sha256": r.get("text_sha256", ""),
        "lonmin_mentions": lonmin_mentions,
        "case_terms": ";".join(case_names),
        "case_mentions_total": case_total,
        "event_terms": ";".join(event_names),
        "event_mentions_total": event_total,
        "event_distinct_terms": event_distinct,
        "social_terms": ";".join(social_names),
        "social_mentions_total": social_total,
        "social_distinct_terms": social_distinct,
        "corporate_terms": ";".join(corporate_names),
        "corporate_mentions_total": corporate_total,
        "corporate_distinct_terms": corporate_distinct,
        "early_aug_oct_2012_window": str(early_2012).lower(),
        "title_has_routine_corporate_signal": str(title_corporate).lower(),
        "title_has_case_process_signal": str(title_case_process).lower(),
        "evidence_class": evidence_class,
        "evidence_note": evidence_note,
        "final_decision": "",
        "final_reason_code": "",
        "final_evidence_note": "",
    })

if rows:
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

summary = {
    "screening_evidence_type": "non_decisional_transparent_acquired_text_signals",
    "records_processed": len(rows),
    "evidence_class_counts": dict(class_counts),
    "final_decisions_made": 0,
    "important_boundary": (
        "Literal Marikana/place/project-name matching is not sufficient. Strong case evidence requires event, labour, justice, community or governance context."
    ),
    "note": (
        "Evidence classes are decision support only. Final inclusion/exclusion requires the locked screening rubric and an explicit decision ledger entry."
    ),
}
SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
