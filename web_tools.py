"""Live web access: search, page fetch, news, weather (stdlib only)."""
import html
import ipaddress
import re
import socket
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UA = {"User-Agent": "Mozilla/5.0 (Jarvis assistant)"}
LIVE_KEYWORDS = ("news", "latest", "today", "score", "current", "search", "price", "who won",
                 "release date", "stock", "trending", "update on", "look up", "google")
URL_RE = re.compile(r"https?://[^\s<>\"')]+")


def needs_live_data(text):
    low = (text or "").lower()
    return any(k in low for k in LIVE_KEYWORDS)


def extract_urls(text):
    return URL_RE.findall(text or "")[:2]


def _get(url, timeout=6, limit=600_000):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        ctype = r.headers.get("Content-Type", "")
        return r.read(limit).decode("utf-8", errors="ignore"), ctype


def search_web(query, max_results=4):
    """DuckDuckGo HTML search -> list of {title, url, snippet}."""
    try:
        page, _ = _get("https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query))
    except Exception:
        return []
    out = []
    blocks = re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
                        r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', page, re.S)
    for href, title, snip in blocks[:max_results]:
        if "uddg=" in href:
            href = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
        strip = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s)).strip()
        out.append({"title": strip(title), "url": href, "snippet": strip(snip)})
    return out


def format_search_results(results):
    if not results:
        return "No live search results available."
    return "\n".join(f"- {r['title']} ({r['url']}): {r['snippet']}" for r in results)


def _is_public_host(host):
    try:
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        return True
    except Exception:
        return False


def fetch_page_text(url, max_chars=5000):
    """Readable text of a public web page. Blocks localhost/private networks."""
    p = urllib.parse.urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname or not _is_public_host(p.hostname):
        return "Blocked: only public http(s) pages can be fetched."
    try:
        page, ctype = _get(url, timeout=8)
    except Exception as e:
        return f"Could not fetch page: {e}"
    if "html" not in ctype and "text" not in ctype:
        return f"Unsupported content type: {ctype}"
    page = re.sub(r"(?is)<(script|style|noscript|svg|header|footer|nav)[^>]*>.*?</\1>", " ", page)
    title = re.search(r"(?is)<title[^>]*>(.*?)</title>", page)
    text = html.unescape(re.sub(r"<[^>]+>", " ", page))
    text = re.sub(r"\s+", " ", text).strip()
    head = f"Title: {html.unescape(title.group(1)).strip()}\n" if title else ""
    return head + text[:max_chars]


def get_news(topic="", count=5):
    """Headlines from Google News RSS (India edition)."""
    q = urllib.parse.quote(topic) if topic else ""
    url = (f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en" if topic
           else "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en")
    try:
        xml, _ = _get(url)
        items = ET.fromstring(xml).findall(".//item")[:count]
        return [{"title": i.findtext("title", ""), "url": i.findtext("link", ""),
                 "date": i.findtext("pubDate", "")} for i in items]
    except Exception:
        return []


def format_news(items):
    return "\n".join(f"- {n['title']} ({n['date'][:16]})" for n in items) or "No headlines available."


def get_weather(city="Bengaluru"):
    try:
        text, _ = _get(f"https://wttr.in/{urllib.parse.quote(city)}?format=3", timeout=3)
        return text.strip()
    except Exception:
        return f"{city}: weather unavailable"
