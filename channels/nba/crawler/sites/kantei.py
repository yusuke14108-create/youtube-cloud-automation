from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

SOURCE = "kantei"
INDEX_URL = "https://www.kantei.go.jp/jp/news/index.html"


def fetch_items(session: requests.Session) -> list[dict]:
    resp = session.get(INDEX_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "lxml")

    items = []
    for li in soup.select("ul.list-new > li.list-new__item"):
        a = li.select_one("a.list-new__link")
        if a is None or not a.get("href"):
            continue
        url = urljoin(INDEX_URL, a["href"])

        title_el = li.select_one(".list-new__description")
        title = title_el.get_text(strip=True) if title_el else ""

        # datetime属性が既にISO8601形式（例: 2026-07-17）を持っているため和暦の手動変換は不要
        time_el = li.select_one("time.list-new__date")
        date = time_el["datetime"].strip() if time_el and time_el.get("datetime") else ""

        items.append(
            {
                "id": url,
                "title": title,
                "url": url,
                "date": date,
                "source": SOURCE,
            }
        )
    return items
