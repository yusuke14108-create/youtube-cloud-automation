import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

SOURCE = "mhlw"
BASE_URL = "https://www.mhlw.go.jp"
INDEX_URL = f"{BASE_URL}/stf/seisakunitsuite/bunya/kenkou_iryou/kenkou/kekkaku-kansenshou/oshirase.html"

FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
DATE_RE = re.compile(r"(\d+)年(\d+)月(\d+)日")


def _to_iso_date(text: str) -> str:
    match = DATE_RE.search(text.translate(FULLWIDTH_DIGITS))
    if not match:
        return ""
    year, month, day = (int(v) for v in match.groups())
    return f"{year:04d}-{month:02d}-{day:02d}"


def fetch_items(session: requests.Session) -> list[dict]:
    resp = session.get(INDEX_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "lxml")

    # 「重要なお知らせ」「報道発表資料」等が同一<ul>内に「■日付 [区分]」というテキストのみのli、
    # 続けてリンクを持つliが並ぶ構造（過去分は<details>内）。日付liを見つけたら次の日付liまでの
    # リンクをその日付として扱う。div.m-grid__col1に絞らないとパンくずや目次アンカーのaも拾ってしまう。
    container = soup.select_one("div.m-grid__col1")
    items = []
    current_date = ""
    for li in container.select("li"):
        text = li.get_text(strip=True)
        if text.startswith("■"):
            current_date = _to_iso_date(text)
            continue
        for a in li.find_all("a"):
            href = a.get("href")
            title = a.get_text(strip=True)
            if not href or not title:
                continue
            url = urljoin(BASE_URL, href)
            items.append(
                {
                    "id": url,
                    "title": title,
                    "url": url,
                    "date": current_date,
                    "source": SOURCE,
                }
            )
    return items
