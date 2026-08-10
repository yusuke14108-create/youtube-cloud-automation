import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

SOURCE = "pmda"
BASE_URL = "https://www.pmda.go.jp"
INDEX_URL = f"{BASE_URL}/0017.html"

DATE_RE = re.compile(r"(\d+)年(\d+)月(\d+)日")


def _to_iso_date(text: str) -> str:
    match = DATE_RE.search(text)
    if not match:
        return ""
    year, month, day = (int(v) for v in match.groups())
    return f"{year:04d}-{month:02d}-{day:02d}"


def fetch_items(session: requests.Session) -> list[dict]:
    resp = session.get(INDEX_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "lxml")

    items = []
    for li in soup.select("ul.list__news li"):
        a = li.find("a")
        title_p = li.find("p", class_="title")
        date_p = li.find("p", class_="date")
        if a is None or title_p is None or not a.get("href"):
            continue
        url = urljoin(BASE_URL, a["href"])
        items.append(
            {
                "id": url,
                "title": title_p.get_text(strip=True),
                "url": url,
                "date": _to_iso_date(date_p.get_text(strip=True)) if date_p else "",
                "source": SOURCE,
            }
        )
    return items
