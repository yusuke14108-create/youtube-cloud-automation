"""Fetch source documents before API-only LLM calls (which cannot use WebFetch)."""
from io import BytesIO
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader


def _pdf_text(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def fetch_source_text(url: str, timeout: int = 60, max_chars: int = 80000) -> str:
    response = requests.get(url, timeout=timeout, headers={"User-Agent": "medical-news-channel/1.0"})
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    if "pdf" in content_type or url.lower().endswith(".pdf"):
        text = _pdf_text(response.content)
    else:
        soup = BeautifulSoup(response.content, "lxml")
        pdf_urls = []
        for link in soup.select("a[href]"):
            href = link.get("href", "")
            if ".pdf" in href.lower():
                absolute = urljoin(url, href)
                if absolute not in pdf_urls:
                    pdf_urls.append(absolute)
        for node in soup(["script", "style", "nav", "footer"]):
            node.decompose()
        text = soup.get_text("\n", strip=True)
        # PMDA index pages often keep the medically relevant detail in linked
        # PDFs. Include links in page order, bounded to control prompt size.
        for pdf_url in pdf_urls[:15]:
            if len(text) >= max_chars:
                break
            pdf = requests.get(pdf_url, timeout=timeout, headers={"User-Agent": "medical-news-channel/1.0"})
            pdf.raise_for_status()
            text += f"\n\n### Linked PDF: {pdf_url}\n" + _pdf_text(pdf.content)
    if len(text.strip()) < 100:
        raise RuntimeError("source extraction returned too little readable text")
    return text[:max_chars]


def build_source_context(items: list) -> str:
    sections = []
    for item in items:
        try:
            text = fetch_source_text(item["url"])
        except Exception as exc:
            raise RuntimeError(f"failed to fetch required medical source {item['url']}: {exc}") from exc
        sections.append(f"## {item['title']}\nURL: {item['url']}\n{text}")
    return "\n\n".join(sections)
