import feedparser
import requests

SOURCE = "mhlw"
FEED_URL = "https://www.mhlw.go.jp/stf/news.rdf"


def fetch_items(session: requests.Session) -> list[dict]:
    resp = session.get(FEED_URL, timeout=30)
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)

    items = []
    for entry in feed.entries:
        url = entry.link
        items.append(
            {
                "id": url,
                "title": entry.title.strip(),
                "url": url,
                "date": entry.get("published", entry.get("updated", "")),
                "source": SOURCE,
            }
        )
    return items
