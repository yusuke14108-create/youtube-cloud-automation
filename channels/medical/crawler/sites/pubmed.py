from datetime import datetime

import requests

SOURCE = "pubmed"
BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
SEARCH_URL = f"{BASE}/esearch.fcgi"
SUMMARY_URL = f"{BASE}/esummary.fcgi"
QUERY = (
    '(clinical trial[ptyp] OR meta-analysis[ptyp] OR systematic review[ptyp] '
    'OR practice guideline[ptyp]) AND humans[mesh]'
)


def _iso_date(value: str) -> str:
    value = value.split(" ")[0] if "/" in value else value
    for fmt in ("%Y/%m/%d", "%Y %b %d", "%Y %b", "%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return value


def fetch_items(session: requests.Session) -> list[dict]:
    search = session.get(
        SEARCH_URL,
        params={
            "db": "pubmed", "term": QUERY, "datetype": "edat", "reldate": 3,
            "retmax": 30, "sort": "pub date", "retmode": "json",
            "tool": "medical_news_channel",
        },
        timeout=30,
    )
    search.raise_for_status()
    ids = search.json()["esearchresult"].get("idlist", [])
    if not ids:
        return []

    summary = session.get(
        SUMMARY_URL,
        params={
            "db": "pubmed", "id": ",".join(ids), "retmode": "json",
            "tool": "medical_news_channel",
        },
        timeout=30,
    )
    summary.raise_for_status()
    result = summary.json()["result"]
    items = []
    for pmid in ids:
        record = result.get(pmid, {})
        title = record.get("title", "").strip()
        if not title:
            continue
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        history = {h.get("pubstatus"): h.get("date", "") for h in record.get("history", [])}
        date_value = record.get("epubdate") or history.get("pubmed") or record.get("pubdate", "")
        items.append({
            "id": url, "title": title, "url": url,
            "date": _iso_date(date_value), "source": SOURCE,
        })
    return items
