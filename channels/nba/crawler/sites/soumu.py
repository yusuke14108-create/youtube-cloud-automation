import re
import warnings
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

SOURCE = "soumu"
INDEX_URL = "https://www.soumu.go.jp/menu_news/s-news/index.html"

DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")


def fetch_items(session: requests.Session) -> list[dict]:
    resp = session.get(INDEX_URL, timeout=30)
    resp.raise_for_status()
    # レスポンスヘッダにcharsetが無くresp.textはISO-8859-1化けするため、
    # ページ内のXML宣言(Shift_JIS)から自力デコードできるresp.contentを渡す
    soup = BeautifulSoup(resp.content, "lxml")

    items = []
    for tr in soup.select("table.tableList tr"):
        date_td = tr.find("td", class_="nw")
        a = tr.select_one("td a[href]")
        if date_td is None or a is None:
            continue

        m = DATE_RE.search(date_td.get_text(strip=True))
        date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""

        url = urljoin(INDEX_URL, a["href"])
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
