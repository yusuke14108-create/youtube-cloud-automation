import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

SOURCE = "fsa"
BASE_URL = "https://www.fsa.go.jp"
INDEX_URL = f"{BASE_URL}/news/index.html"

WAREKI_RE = re.compile(r"令和(\d+)年(\d+)月(\d+)日")
# ページ内の日付は１桁が全角数字、２桁が半角数字と表記が揺れているため正規化する
FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")


def _to_iso_date(text: str) -> str:
    match = WAREKI_RE.search(text.translate(FULLWIDTH_DIGITS))
    if not match:
        return ""
    reiwa_year, month, day = (int(v) for v in match.groups())
    year = reiwa_year + 2018
    return f"{year:04d}-{month:02d}-{day:02d}"


def fetch_items(session: requests.Session) -> list[dict]:
    resp = session.get(INDEX_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "lxml")

    top_ul = soup.find("div", id="main").find("div", class_="inner").find("ul", recursive=False)

    items = []
    for date_li in top_ul.find_all("li", recursive=False):
        date_text = date_li.find(string=True, recursive=False) or ""
        date = _to_iso_date(date_text)
        nested_ul = date_li.find("ul")
        if not nested_ul:
            continue
        for a in nested_ul.find_all("a"):
            url = urljoin(BASE_URL, a["href"])
            items.append(
                {
                    "id": url,
                    "title": a.get_text(strip=True),
                    "url": url,
                    "date": date,
                    "source": SOURCE,
                }
            )
    return items
