import hashlib
from datetime import datetime
from urllib.parse import quote_plus
from xml.etree import ElementTree

import requests

from generator.config import NBA_PLAYERS

SOURCE = "nba_news"
RSS_TEMPLATE = "https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"


def _text(node, name):
    child = node.find(name)
    return (child.text or "").strip() if child is not None else ""


def fetch_items(session: requests.Session) -> list[dict]:
    """Collect discovery links only. Script generation must open the linked
    article and cite it; RSS snippets are never treated as verified facts."""
    items = []
    for player in NBA_PLAYERS:
        query = quote_plus(f'"{player}" NBA when:2d')
        response = session.get(RSS_TEMPLATE.format(query=query), timeout=25)
        response.raise_for_status()
        root = ElementTree.fromstring(response.content)
        for entry in root.findall("./channel/item")[:15]:
            title = _text(entry, "title")
            url = _text(entry, "link")
            if not title or not url:
                continue
            raw_date = _text(entry, "pubDate")
            try:
                published = datetime.strptime(raw_date, "%a, %d %b %Y %H:%M:%S %Z").isoformat()
            except ValueError:
                published = raw_date
            item_id = hashlib.sha256(f"{player}|{title}|{url}".encode()).hexdigest()[:24]
            items.append({
                "id": item_id, "source": SOURCE, "player": player,
                "date": published, "title": title, "url": url,
            })
    # Japanese players remain the channel's anchor, while major league-wide
    # stories provide controlled topic diversity for performance learning.
    for topic in ("NBA 契約 移籍", "NBA プレーオフ", "NBA 記録 話題"):
        query = quote_plus(f'{topic} when:2d')
        response = session.get(RSS_TEMPLATE.format(query=query), timeout=25)
        response.raise_for_status()
        root = ElementTree.fromstring(response.content)
        for entry in root.findall("./channel/item")[:10]:
            title, url = _text(entry, "title"), _text(entry, "link")
            if not title or not url:
                continue
            raw_date = _text(entry, "pubDate")
            try:
                published = datetime.strptime(raw_date, "%a, %d %b %Y %H:%M:%S %Z").isoformat()
            except ValueError:
                published = raw_date
            item_id = hashlib.sha256(f"league|{title}|{url}".encode()).hexdigest()[:24]
            items.append({"id": item_id, "source": SOURCE, "player": None, "scope": "league", "date": published, "title": title, "url": url})
    return list({item["id"]: item for item in items}.values())
