import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

SOURCE = "nta"
BASE_URL = "https://www.nta.go.jp"
# トピックス一覧は日単位の日付があり件数も十分なため採用。報道発表(/information/release/index.htm)は
# 日付が「令和8年6月」のように月単位までしか無く精度が落ちる上、内容もトピックス一覧と重複するため省略。
INDEX_URL = f"{BASE_URL}/information/news/index.htm"

WAREKI_RE = re.compile(r"令和(\d+)年(\d+)月(\d+)日")
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
    # ページ側は charset=shift_jis 指定。resp.content(バイト列)を渡せばbs4がmetaタグから自動判定する。
    soup = BeautifulSoup(resp.content, "lxml")

    items = []
    for tr in soup.select("table.index_news tr"):
        th = tr.find("th")
        a = tr.find("a")
        if th is None or a is None or not a.get("href"):
            continue
        url = urljoin(BASE_URL, a["href"])
        items.append(
            {
                "id": url,
                "title": a.get_text(strip=True),
                "url": url,
                "date": _to_iso_date(th.get_text(strip=True)),
                "source": SOURCE,
            }
        )
    return items
