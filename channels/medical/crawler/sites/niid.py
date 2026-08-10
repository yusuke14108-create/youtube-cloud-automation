import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

SOURCE = "niid"
BASE_URL = "https://www.niid.jihs.go.jp/"
LIST_URL = "https://www.niid.jihs.go.jp/content11/20250328011613.html"
ITEM_LIMIT = 15

DATE_RE = re.compile(r"(\d{4})[年/](\d{1,2})[月/](\d{1,2})日?")


def _to_iso_date(text: str) -> str:
    match = DATE_RE.search(text)
    if not match:
        return ""
    year, month, day = (int(v) for v in match.groups())
    return f"{year:04d}-{month:02d}-{day:02d}"


def fetch_items(session: requests.Session) -> list[dict]:
    resp = session.get(BASE_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "lxml")

    items = []
    seen_urls = set()

    dl = soup.select_one("dl.kansenken-news-dl")
    for dt, dd in zip(dl.find_all("dt"), dl.find_all("dd")):
        a = dd.find("a")
        if a is None or not a.get("href"):
            continue
        url = urljoin(BASE_URL, a["href"])
        items.append(
            {
                "id": url,
                "title": a.get_text(strip=True),
                "url": url,
                "date": _to_iso_date(dt.get_text(strip=True)),
                "source": SOURCE,
            }
        )
        seen_urls.add(url)

    # トップページの更新情報は直近5件しか出ないため、「更新情報一覧」ページから追加分を補い、
    # 各記事ページのp.update-textを開いて日付を取得する（一覧ページ自体には日付が載っていない）
    resp = session.get(LIST_URL, timeout=30)
    resp.raise_for_status()
    list_soup = BeautifulSoup(resp.content, "lxml")

    for dd in list_soup.select("div.kansenken-list dd"):
        if len(items) >= ITEM_LIMIT:
            break
        a = dd.find("a")
        if a is None or not a.get("href"):
            continue
        url = urljoin(LIST_URL, a["href"])
        if url in seen_urls:
            continue
        seen_urls.add(url)

        detail_resp = session.get(url, timeout=30)
        detail_resp.raise_for_status()
        detail_soup = BeautifulSoup(detail_resp.content, "lxml")
        date_el = detail_soup.select_one("p.update-text")
        date = _to_iso_date(date_el.get_text(strip=True)) if date_el else ""

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
