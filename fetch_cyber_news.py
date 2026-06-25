#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# made by: Xdim
# v5: no BeautifulSoup required, richer Details, quick 3-line summary

import json
import re
import sys
import hashlib
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape, escape
from pathlib import Path
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from difflib import SequenceMatcher
from urllib.parse import urljoin, urlparse

OUT_HTML = Path("index.html")
HISTORY_JSON = Path("cyber_news_history.json")

MAX_PER_SOURCE = 25
MAX_DAYS_BACK = 60
SIMILARITY_THRESHOLD = 0.85
MAX_FETCH_BYTES = 6_000_000

# Article fetching:
# True = for RSS items, also try to open the article page and extract more text for Details.
# This is slower but gives better Details / Quick Summary.
FETCH_ARTICLE_SUMMARY = True
MAX_ARTICLE_FETCH_PER_RUN = 35
MAX_ARTICLE_CHARS = 4500

SOURCES = [
    {
        "name": "The Hacker News",
        "type": "rss",
        "url": "https://feeds.feedburner.com/TheHackersNews",
        "quality": "High",
        "scope": "General",
    },
    {
        "name": "BleepingComputer",
        "type": "rss",
        "url": "https://www.bleepingcomputer.com/feed/",
        "quality": "High",
        "scope": "General",
    },
    {
        "name": "Dark Reading",
        "type": "rss",
        "url": "https://www.darkreading.com/rss.xml",
        "quality": "High",
        "scope": "General",
    },
    {
        "name": "SecurityWeek",
        "type": "rss",
        "url": "https://www.securityweek.com/feed/",
        "quality": "High",
        "scope": "General",
    },
    {
        "name": "KrebsOnSecurity",
        "type": "rss",
        "url": "https://krebsonsecurity.com/feed/",
        "quality": "High",
        "scope": "General",
    },
    {
        "name": "The Record",
        "type": "rss",
        "url": "https://therecord.media/feed",
        "quality": "High",
        "scope": "General",
    },
    {
        "name": "Recorded Future Research",
        "type": "rss",
        "url": "https://www.recordedfuture.com/feed",
        "quality": "High",
        "scope": "Research",
    },
    {
        "name": "Check Point Research",
        "type": "rss",
        "url": "https://research.checkpoint.com/feed/",
        "quality": "High",
        "scope": "Research",
    },
    {
        "name": "Palo Alto Unit 42",
        "type": "rss",
        "url": "https://unit42.paloaltonetworks.com/feed/",
        "quality": "High",
        "scope": "Research",
    },
    {
        "name": "Microsoft Security Blog",
        "type": "rss",
        "url": "https://www.microsoft.com/en-us/security/blog/feed/",
        "quality": "High",
        "scope": "Research",
    },
    {
        "name": "CrowdStrike Blog",
        "type": "rss",
        "url": "https://www.crowdstrike.com/blog/feed/",
        "quality": "High",
        "scope": "Research",
    },
    {
        "name": "Cisco Talos",
        "type": "rss",
        "url": "https://blog.talosintelligence.com/rss/",
        "quality": "High",
        "scope": "Research",
    },
    {
        "name": "Mandiant",
        "type": "rss",
        "url": "https://cloud.google.com/blog/topics/threat-intelligence/rss",
        "quality": "High",
        "scope": "Research",
    },
    {
        "name": "SANS ISC",
        "type": "rss",
        "url": "https://isc.sans.edu/rssfeed.xml",
        "quality": "High",
        "scope": "Research",
    },
    {
        "name": "Zero Day Initiative",
        "type": "rss",
        "url": "https://www.zerodayinitiative.com/rss/published/",
        "quality": "High",
        "scope": "Vulnerability",
    },
    {
        "name": "HackRead",
        "type": "rss",
        "url": "https://www.hackread.com/feed/",
        "quality": "Medium",
        "scope": "General",
    },
    {
        "name": "Cyber Security News",
        "type": "rss",
        "url": "https://cybersecuritynews.com/feed/",
        "quality": "Medium",
        "scope": "General",
    },
    {
        "name": "Reddit r/netsec",
        "type": "rss",
        "url": "https://www.reddit.com/r/netsec/.rss",
        "quality": "Medium",
        "scope": "Community",
    },
    {
        "name": "TechNadu",
        "type": "html",
        "url": "https://www.technadu.com/",
        "base": "https://www.technadu.com",
        "quality": "Medium",
        "scope": "General",
    },
    {
        "name": "CyberNews Security",
        "type": "html",
        "url": "https://cybernews.com/security/",
        "base": "https://cybernews.com",
        "quality": "Medium",
        "scope": "General",
    },
    {
        "name": "Hudson Rock Press",
        "type": "hudson_press",
        "url": "https://www.hudsonrock.com/press",
        "base": "https://www.hudsonrock.com",
        "quality": "Medium",
        "scope": "Press",
    },
    {
        "name": "Hudson Rock Blog",
        "type": "html",
        "url": "https://www.hudsonrock.com/blog",
        "base": "https://www.hudsonrock.com",
        "quality": "High",
        "scope": "Research",
    },
    {
        "name": "InfoStealers Weekly Reports",
        "type": "weekly",
        "url": "https://www.infostealers.com/info-stealers-reports/",
        "base": "https://www.infostealers.com",
        "quality": "High",
        "scope": "Weekly",
    },
    {
        "name": "DeafNews",
        "type": "html",
        "url": "https://deafnews.it/en/",
        "base": "https://deafnews.it",
        "quality": "Medium",
        "scope": "Research",
    },
]

STOP = set("""
a an the and or of for to in on at from with by about after before over under via into
as is are was were be been new latest update updates says warns report reports cyber
security cybersecurity hackers hacker hacking attack attacks flaw flaws bug bugs using use
used how what why when today
""".split())

BLOCK = ["nude", "nudes", "porn", "sexual", "explicit", "onlyfans", "escort"]

RELEVANT = [
    "breach",
    "leak",
    "ransom",
    "hack",
    "vulnerability",
    "malware",
    "infostealer",
    "stealer",
    "stolen",
    "exposed",
    "cve",
    "compromised",
    "exploit",
    "phishing",
    "credential",
    "zero-day",
    "0-day",
    "edr",
    "xdr",
    "microsoft",
    "fortinet",
    "fortigate",
    "veeam",
    "acronis",
    "watchguard",
    "truenas",
    "vpn",
    "firewall",
    "ransomware",
    "patch",
    "critical",
    "rce",
    "ai",
    "llm",
    "supply chain",
]

article_fetch_count = 0


def safe_url(u: str) -> bool:
    try:
        p = urlparse(str(u).strip())
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


def http_get(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 LocalCyberDashboard/5.2",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, application/json, text/html, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=28) as resp:
        return resp.read(MAX_FETCH_BYTES)


def clean(s) -> str:
    s = unescape(str(s or ""))
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def strip_html_for_article(html: str) -> str:
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.I | re.S)
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.I | re.S)
    html = re.sub(r"<nav.*?</nav>", " ", html, flags=re.I | re.S)
    html = re.sub(r"<footer.*?</footer>", " ", html, flags=re.I | re.S)
    html = re.sub(r"<header.*?</header>", " ", html, flags=re.I | re.S)
    html = re.sub(r"\s+", " ", html)
    return html


def extract_article_text(url: str) -> str:
    global article_fetch_count
    if not FETCH_ARTICLE_SUMMARY or article_fetch_count >= MAX_ARTICLE_FETCH_PER_RUN:
        return ""
    if not safe_url(url):
        return ""
    try:
        article_fetch_count += 1
        raw = http_get(url).decode("utf-8", "ignore")
        raw = strip_html_for_article(raw)
        paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", raw, flags=re.I | re.S)
        parts = []
        for p in paragraphs:
            txt = clean(p)
            if len(txt) >= 60:
                # Avoid cookie/footer/newsletter junk
                low = txt.lower()
                if any(
                    j in low
                    for j in [
                        "subscribe",
                        "cookie",
                        "newsletter",
                        "advertisement",
                        "all rights reserved",
                    ]
                ):
                    continue
                parts.append(txt)
            if len(" ".join(parts)) > MAX_ARTICLE_CHARS:
                break
        return " ".join(parts)[:MAX_ARTICLE_CHARS]
    except Exception:
        return ""


def split_sentences(text: str):
    text = clean(text)
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if len(p.strip()) > 30]


def quick_summary(title: str, summary: str, article_text: str) -> list:
    text = f"{summary} {article_text}".strip()
    sentences = split_sentences(text)
    lines = []

    # Line 1: what happened
    if sentences:
        lines.append(sentences[0][:220])
    else:
        lines.append(title[:220])

    # Line 2: risk/type
    combined = f"{title} {summary} {article_text}".lower()
    risk = []
    if "ransomware" in combined:
        risk.append("ransomware/extortion")
    if any(
        x in combined
        for x in [
            "credential",
            "password",
            "cookie",
            "session",
            "infostealer",
            "stealer",
        ]
    ):
        risk.append("credentials/infostealer risk")
    if any(
        x in combined for x in ["cve-", "vulnerability", "zero-day", "rce", "exploit"]
    ):
        risk.append("vulnerability/exploitation risk")
    if any(
        x in combined
        for x in ["microsoft", "fortinet", "veeam", "acronis", "watchguard", "truenas"]
    ):
        risk.append("ISNET vendor relevance")
    lines.append(
        "Risk: " + (", ".join(risk[:3]) if risk else "general cybersecurity update")
    )

    # Line 3: suggested action
    if any(
        x in combined for x in ["cve-", "vulnerability", "patch", "zero-day", "rce"]
    ):
        action = "Action: check affected products, patch status, and exposed services."
    elif any(
        x in combined
        for x in ["credential", "password", "cookie", "infostealer", "stealer"]
    ):
        action = "Action: review compromised credentials, MFA/session controls, and endpoint detections."
    elif "ransomware" in combined:
        action = "Action: monitor indicators, backups, remote access, and related vendor exposure."
    else:
        action = (
            "Action: read full article if the vendor/customer/environment is relevant."
        )
    lines.append(action)
    return lines[:3]


def parse_date(value) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        dt = parsedate_to_datetime(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(str(value)[:30], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return datetime.now(timezone.utc)


def canonical_title(title: str) -> str:
    s = re.sub(r"[^a-z0-9\-\. ]+", " ", str(title).lower())
    words = [w for w in s.split() if len(w) > 2 and w not in STOP]
    return " ".join(words[:20])


def stable_id(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()[:16]


def item_type(text: str) -> str:
    l = text.lower()
    if "weekly report" in l or "infostealer report" in l:
        return "Weekly Threat Intel"
    if any(x in l for x in ["ransomware", "extortion", "leak site"]):
        return "Ransomware"
    if any(
        x in l
        for x in ["breach", "leak", "stolen", "exposed", "exfiltrat", "compromised"]
    ):
        return "Data Leak / Breach"
    if any(
        x in l
        for x in [
            "cve-",
            "vulnerability",
            "zero-day",
            "0-day",
            "rce",
            "patch",
            "exploit",
        ]
    ):
        return "Vulnerability"
    if any(
        x in l
        for x in ["malware", "trojan", "backdoor", "infostealer", "stealer", "botnet"]
    ):
        return "Malware"
    if any(x in l for x in ["phishing", "scam", "fraud", "smishing"]):
        return "Phishing / Scam"
    return "General Cybersecurity"


def severity(text: str) -> str:
    l = text.lower()
    if any(
        x in l
        for x in [
            "zero-day",
            "0-day",
            "actively exploited",
            "rce",
            "critical",
            "emergency patch",
            "supply chain",
            "oauth token",
        ]
    ):
        return "Critical"
    if any(
        x in l
        for x in [
            "ransomware",
            "data breach",
            "data leak",
            "leaked",
            "stolen",
            "extortion",
            "malware",
            "credential",
            "phishing",
            "breach",
            "hack",
            "compromised",
        ]
    ):
        return "High"
    if any(
        x in l
        for x in [
            "vulnerability",
            "patched",
            "patch",
            "exploit",
            "bug",
            "cve-",
            "weekly report",
        ]
    ):
        return "Medium"
    return "Low"


def extract_target(title: str) -> str:
    out = []
    raw = re.sub(r"[:|–—].*", "", str(title)).strip()
    for word in raw.split()[:9]:
        w = re.sub(r"[^A-Za-z0-9\.\-]+", "", word)
        if (
            len(w) > 2
            and (w[:1].isupper() or w.isupper() or re.search(r"\d", w))
            and w.lower() not in STOP
        ):
            out.append(w)
    return " ".join(out[:4]) or "Unknown"


def make_item(
    src, title, link, summary="", dt=None, target=None, category="", article_text=""
):
    title = clean(title)
    link = clean(link)
    summary = clean(summary)
    category = clean(category)
    article_text = clean(article_text)

    if not title:
        return None
    if link and not safe_url(link):
        return None
    if any(bad in (title + " " + summary).lower() for bad in BLOCK):
        return None

    if not article_text and link and src.get("type") == "rss":
        article_text = extract_article_text(link)

    full = f"{title} {summary} {article_text} {category}"
    qs = quick_summary(title, summary, article_text)

    return {
        "id": stable_id(src["name"] + " " + canonical_title(title)),
        "date": (dt or datetime.now(timezone.utc)).isoformat(),
        "source": src["name"],
        "quality": src.get("quality", "Medium"),
        "scope": src.get("scope", "General"),
        "category": category,
        "title": title,
        "summary": summary[:1600],
        "article_text": article_text[:MAX_ARTICLE_CHARS],
        "quick_summary": qs,
        "link": link,
        "target": target or extract_target(title),
        "type": item_type(full),
        "severity": severity(full),
        "sources": [src["name"]],
        "links": [{"source": src["name"], "url": link}] if link else [],
    }


def parse_rss(src):
    out = []
    try:
        root = ET.fromstring(http_get(src["url"]))
        nodes = root.findall(".//item") or root.findall(
            ".//{http://www.w3.org/2005/Atom}entry"
        )
        for node in nodes[:MAX_PER_SOURCE]:
            title = clean(
                node.findtext("title")
                or node.findtext("{http://www.w3.org/2005/Atom}title")
                or ""
            )
            link = clean(node.findtext("link") or "")
            if not link:
                atom_link = node.find("{http://www.w3.org/2005/Atom}link")
                link = atom_link.attrib.get("href", "") if atom_link is not None else ""
            summary = clean(
                node.findtext("description")
                or node.findtext("summary")
                or node.findtext("{http://www.w3.org/2005/Atom}summary")
                or ""
            )
            pub = (
                node.findtext("pubDate")
                or node.findtext("published")
                or node.findtext("updated")
                or node.findtext("{http://www.w3.org/2005/Atom}updated")
            )
            it = make_item(src, title, link, summary, parse_date(pub))
            if it:
                out.append(it)
    except Exception as e:
        print(f"[WARN] {src['name']} failed: {e}", file=sys.stderr)
    return out


def parse_html_links(src, only_relevant=True, limit=MAX_PER_SOURCE):
    out = []
    try:
        html = http_get(src["url"]).decode("utf-8", "ignore")
        pairs = re.findall(
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, flags=re.I | re.S
        )
        seen = set()
        for href, text in pairs:
            title = clean(text)
            key = canonical_title(title)
            if len(title) < 25 or len(title) > 180:
                continue
            if key in seen:
                continue
            seen.add(key)
            if only_relevant and not any(k in title.lower() for k in RELEVANT):
                continue
            link = urljoin(src.get("base", src["url"]), href)
            summary = f"Discovered from {src['name']} page. Open full article for more details."
            it = make_item(src, title, link, summary)
            if it:
                out.append(it)
            if len(out) >= limit:
                break
    except Exception as e:
        print(f"[WARN] {src['name']} failed: {e}", file=sys.stderr)
    return out


def parse_weekly(src):
    out = []
    try:
        html = http_get(src["url"]).decode("utf-8", "ignore")
        pairs = re.findall(
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, flags=re.I | re.S
        )
        seen = set()
        for href, text in pairs:
            title = clean(text)
            if "infostealers weekly report" not in title.lower():
                continue
            key = canonical_title(title)
            if key in seen:
                continue
            seen.add(key)
            link = urljoin(src.get("base", src["url"]), href)
            summary = "Weekly intelligence briefing tracking infostealer activity, compromised domains and breached organizations."
            article_text = extract_article_text(link)
            it = make_item(
                src,
                title,
                link,
                summary,
                datetime.now(timezone.utc),
                category="Weekly Infostealer Report",
                article_text=article_text,
            )
            if it:
                out.append(it)
            if len(out) >= 6:
                break
    except Exception as e:
        print(f"[WARN] {src['name']} failed: {e}", file=sys.stderr)
    return out


def parse_hudson_press(src):
    out = parse_html_links(src, only_relevant=True, limit=MAX_PER_SOURCE)
    for it in out:
        it["type"] = "Hudson Rock Press"
        it["summary"] = (
            "Company in the press item discovered from Hudson Rock press page."
        )
        if not it.get("quick_summary"):
            it["quick_summary"] = quick_summary(
                it["title"], it["summary"], it.get("article_text", "")
            )
    return out


def is_recent(item):
    try:
        dt = datetime.fromisoformat(item["date"].replace("Z", "+00:00"))
        return dt >= datetime.now(timezone.utc) - timedelta(days=MAX_DAYS_BACK)
    except Exception:
        return True


def merge_items(items):
    merged = []
    order = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}

    for it in sorted(items, key=lambda x: x.get("date", ""), reverse=True):
        found = None
        for ex in merged:
            same_target = (
                it.get("target", "").lower() != "unknown"
                and it.get("target", "").lower() == ex.get("target", "").lower()
            )
            similar = (
                SequenceMatcher(
                    None,
                    canonical_title(it.get("title", "")),
                    canonical_title(ex.get("title", "")),
                ).ratio()
                >= SIMILARITY_THRESHOLD
            )
            if same_target or similar:
                found = ex
                break

        if found:
            if it["source"] not in found["sources"]:
                found["sources"].append(it["source"])
            for link in it.get("links", []):
                if link.get("url") and all(
                    existing.get("url") != link.get("url")
                    for existing in found.get("links", [])
                ):
                    found.setdefault("links", []).append(link)
            if order.get(it.get("severity", "Low"), 1) > order.get(
                found.get("severity", "Low"), 1
            ):
                found["severity"] = it["severity"]
            if len(it.get("summary", "")) > len(found.get("summary", "")):
                found["summary"] = it["summary"]
            if len(it.get("article_text", "")) > len(found.get("article_text", "")):
                found["article_text"] = it["article_text"]
            if it.get("quick_summary") and not found.get("quick_summary"):
                found["quick_summary"] = it["quick_summary"]
        else:
            merged.append(it)
    return merged


def load_history():
    if HISTORY_JSON.exists():
        try:
            return json.loads(HISTORY_JSON.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_history(items):
    HISTORY_JSON.write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def build_html(items, warnings):
    data = json.dumps(items, ensure_ascii=False)
    warns = json.dumps(warnings, ensure_ascii=False)
    generated = escape(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    html = """<!doctype html>
<html lang="el">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Local Cyber News Dashboard</title>
<style>
:root{--panel:#121a2d;--panel2:#0f172a;--panel3:#0b1428;--text:#e5e7eb;--muted:#94a3b8;--line:#263248}
*{box-sizing:border-box}body{margin:0;font-family:Segoe UI,Arial,sans-serif;background:#08111f;color:var(--text);font-size:16px}
header{padding:18px 26px;border-bottom:1px solid var(--line);position:sticky;top:0;background:#0b1020;z-index:10}
h1{margin:0 0 8px}.sub{color:var(--muted);font-size:13px}.tabs{display:flex;gap:10px;margin:14px 0}
.tab{border:1px solid #355175;background:#101a30;color:#dbeafe;border-radius:999px;padding:10px 16px;cursor:pointer;font-weight:700}.tab.active{background:#1e40af}
.searchrow{display:grid;grid-template-columns:1fr 150px;gap:10px}#q{font-size:18px;padding:14px;border:1px solid #365075;background:#081225;color:var(--text);border-radius:14px}
.wrap{padding:16px 26px}.cards{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}.card,.isnetbox,.item{background:var(--panel);border:1px solid #2d3c58;border-radius:16px}.card{padding:14px}.num{font-size:28px;font-weight:800}.label,.muted{color:var(--muted)}
.toolbar{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:14px 0}select,input.small{background:var(--panel2);color:var(--text);border:1px solid var(--line);border-radius:12px;padding:12px}
.isnetbox{display:none;padding:14px;margin:0 0 14px}.isnetbox.show{display:block}.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}.chip{background:#123155;border:1px solid #315a86;color:#dff3ff;border-radius:999px;padding:7px 10px}.chip button{margin-left:6px;background:#7f1d1d;border:0;color:#fecaca;border-radius:50%}.addrow{display:grid;grid-template-columns:1fr 130px;gap:10px;margin-top:10px}
.item{margin:12px 0;padding:18px;display:grid;grid-template-columns:105px 85px 135px 120px 170px 1fr 145px;gap:14px;cursor:pointer}.item:hover{background:#152039}.title{font-size:18px;color:#7dd3fc;line-height:1.35}.summary{color:#c7d2e8;margin-top:8px;font-size:14px;line-height:1.55;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.details{display:none;grid-column:1/-1;border-top:1px solid var(--line);margin-top:10px;padding-top:14px}.item.open .details{display:block}.item.open .summary{-webkit-line-clamp:8}.quick{background:#0b1b33;border:1px solid #26476d;border-radius:12px;padding:12px;margin:10px 0}.quick li{margin:6px 0}.article{white-space:pre-wrap;line-height:1.55;color:#d6e2f3}.pill{padding:5px 10px;border-radius:999px;font-size:12px;font-weight:800}.Critical{background:#4c1d1d;color:#fca5a5}.High{background:#432818;color:#fdba74}.Medium{background:#3f3511;color:#fde68a}.Low{background:#12351f;color:#86efac}
button{background:#1e3a5f;color:#dff3ff;border:1px solid #3b5f8f;border-radius:10px;padding:9px 12px;cursor:pointer}.warn{color:#fbbf24;font-size:12px}.hide{display:none}
@media(max-width:1200px){.item{grid-template-columns:1fr}.cards,.toolbar,.searchrow,.addrow{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>
<h1>Local Cyber News Dashboard</h1>
<div class="sub">Generated: __GENERATED__ | Details now include quick 3-line summary + extracted article text where possible</div>
<div class="tabs"><button id="tabGeneral" class="tab active" onclick="setTab('general')">General</button><button id="tabIsnet" class="tab" onclick="setTab('isnet')">ISNET</button></div>
<div class="searchrow"><input id="q" placeholder="Search: mikrotik, fortinet, veeam, microsoft, infostealer..."/><button onclick="q.value='';render()">Clear</button></div>
<div id="warn" class="warn"></div>
</header>
<div class="wrap">
<div id="isnetBox" class="isnetbox"><b>ISNET watchlist:</b> show only selected vendor/company keywords. Add/remove below. Saved locally in this browser.<div class="addrow"><input id="kwInput" class="small" placeholder="π.χ. mikrotik, sophos, vmware" onkeydown="if(event.key==='Enter')addKw()"/><button onclick="addKw()">Add</button></div><div id="chips" class="chips"></div></div>
<div class="cards"><div class="card"><div class="num" id="total">0</div><div class="label">Visible</div></div><div class="card"><div class="num" id="critical">0</div><div class="label">Critical</div></div><div class="card"><div class="num" id="high">0</div><div class="label">High</div></div><div class="card"><div class="num" id="weekly">0</div><div class="label">Weekly reports</div></div><div class="card"><div class="num" id="sources">0</div><div class="label">Sources</div></div></div>
<div class="toolbar"><select id="severity"><option value="">All severities</option><option>Critical</option><option>High</option><option>Medium</option><option>Low</option></select><select id="type"><option value="">All types</option></select><select id="source"><option value="">All sources</option></select><select id="quality"><option value="">All quality</option><option>High</option><option>Medium</option><option>Special</option></select></div>
<div id="rows"></div><div id="empty" class="muted hide">Δεν βρέθηκαν αποτελέσματα.</div>
</div>
<script>
const DATA=__DATA__;const WARNINGS=__WARNINGS__;let activeTab='general';
const DEFAULT_ISNET=['microsoft','office 365','m365','azure','entra','defender','fortinet','fortigate','forticlient','fortios','watchguard','truenas','veeam','backup','agent','agents','edr','xdr','ai','artificial intelligence','comodo','acronis','antivirus','anti-virus','endpoint','rmm','vpn','firewall','nas','storage','infostealer','stealer','credential','cookies','session'];
let isnetKeywords=JSON.parse(localStorage.getItem('isnetKeywords')||'null')||DEFAULT_ISNET.slice();
const rows=document.getElementById('rows'),q=document.getElementById('q'),sev=document.getElementById('severity'),typ=document.getElementById('type'),src=document.getElementById('source'),qual=document.getElementById('quality');
function esc(s){return String(s||'').replace(/[&<>'\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
function uniq(a){return[...new Set(a)].sort()}function fmtDate(iso){try{return new Date(iso).toLocaleString('el-GR')}catch(e){return iso}}
function fill(){uniq(DATA.map(x=>x.type)).forEach(v=>typ.innerHTML+=`<option>${esc(v)}</option>`);uniq(DATA.flatMap(x=>x.sources)).forEach(v=>src.innerHTML+=`<option>${esc(v)}</option>`);if(WARNINGS.length)document.getElementById('warn').textContent='Warnings: '+WARNINGS.join(' | ');renderChips()}
function setTab(t){activeTab=t;document.getElementById('tabGeneral').classList.toggle('active',t==='general');document.getElementById('tabIsnet').classList.toggle('active',t==='isnet');document.getElementById('isnetBox').classList.toggle('show',t==='isnet');render()}
function saveKw(){localStorage.setItem('isnetKeywords',JSON.stringify(isnetKeywords))}function addKw(){let v=document.getElementById('kwInput').value.trim().toLowerCase();if(!v)return;if(!isnetKeywords.includes(v))isnetKeywords.push(v);document.getElementById('kwInput').value='';saveKw();renderChips();render()}function delKw(k){isnetKeywords=isnetKeywords.filter(x=>x!==k);saveKw();renderChips();render()}function resetKw(){isnetKeywords=DEFAULT_ISNET.slice();saveKw();renderChips();render()}function renderChips(){document.getElementById('chips').innerHTML=isnetKeywords.map(k=>`<span class="chip">${esc(k)} <button onclick="delKw('${esc(k)}')">x</button></span>`).join('')+`<span class="chip"><button onclick="resetKw()">reset</button></span>`}
function openLink(url){if(url)window.open(url,'_blank','noopener')}function toggleDetails(ev,id){ev.stopPropagation();document.getElementById(id).classList.toggle('open')}function blob(x){return `${x.title} ${x.summary} ${x.article_text||''} ${x.target} ${x.type} ${x.sources.join(' ')} ${x.category}`.toLowerCase()}function matchIsnet(x){const b=blob(x);return isnetKeywords.some(k=>b.includes(k.toLowerCase()))}
function render(){const term=q.value.toLowerCase().trim();const f=DATA.filter(x=>{const b=blob(x);return(activeTab!=='isnet'||matchIsnet(x))&&(!term||b.includes(term))&&(!sev.value||x.severity===sev.value)&&(!typ.value||x.type===typ.value)&&(!src.value||x.sources.includes(src.value))&&(!qual.value||x.quality===qual.value)});rows.innerHTML=f.map((x,i)=>{const id='it'+i;const links=(x.links||[]).map(l=>`<li><a href="${esc(l.url)}" target="_blank" onclick="event.stopPropagation()">${esc(l.source)}</a></li>`).join('');const matched=isnetKeywords.filter(k=>(`${x.title} ${x.summary} ${x.article_text||''} ${x.target}`.toLowerCase()).includes(k)).join(', ')||'-';const qs=(x.quick_summary||[]).map(line=>`<li>${esc(line)}</li>`).join('');const article=esc(x.article_text||'Δεν βρέθηκε περισσότερο κείμενο από το άρθρο. Πάτα το link για όλο το άρθρο.');return `<div class="item" id="${id}" onclick="openLink('${esc(x.link)}')"><div>${fmtDate(x.date)}</div><div><span class="pill ${esc(x.severity)}">${esc(x.severity)}</span></div><div>${esc(x.type)}</div><div>${esc(x.quality||'')}</div><div>${esc(x.target)}</div><div><div class="title">${esc(x.title)}</div><div class="summary">${esc(x.summary)}</div><div class="muted" style="font-size:12px;margin-top:6px">${esc(x.category||x.scope||'')}</div></div><div><b>${x.sources.length}</b> source(s)<div class="muted" style="font-size:12px">${esc(x.sources.join(', '))}</div><button onclick="toggleDetails(event,'${id}')">Details</button></div><div class="details"><b>Quick summary:</b><ol class="quick">${qs}</ol><b>Περισσότερο κείμενο:</b><div class="article">${article}</div><br><b>Matched ISNET:</b> ${activeTab==='isnet'?esc(matched):'-'}<br><br><b>Links:</b><ul>${links}</ul></div></div>`}).join('');document.getElementById('empty').classList.toggle('hide',f.length>0);document.getElementById('total').textContent=f.length;document.getElementById('critical').textContent=f.filter(x=>x.severity==='Critical').length;document.getElementById('high').textContent=f.filter(x=>x.severity==='High').length;document.getElementById('weekly').textContent=f.filter(x=>x.type==='Weekly Threat Intel').length;document.getElementById('sources').textContent=uniq(f.flatMap(x=>x.sources)).length}
q.addEventListener('input',render);sev.addEventListener('input',render);typ.addEventListener('input',render);src.addEventListener('input',render);qual.addEventListener('input',render);fill();render();
</script>
</body></html>"""
    return (
        html.replace("__GENERATED__", generated)
        .replace("__DATA__", data)
        .replace("__WARNINGS__", warns)
    )


def main():
    print("Fetching sources...")
    fetched = []
    warnings = []

    for src in SOURCES:
        print(f" - {src['name']}")
        before = len(fetched)
        if src["type"] == "rss":
            fetched.extend(parse_rss(src))
        elif src["type"] == "weekly":
            fetched.extend(parse_weekly(src))
        elif src["type"] == "hudson_press":
            fetched.extend(parse_hudson_press(src))
        elif src["type"] == "html":
            fetched.extend(parse_html_links(src, only_relevant=True))
        else:
            warnings.append(f"{src['name']}: unknown source type {src['type']}")
        if len(fetched) == before:
            warnings.append(f"{src['name']}: 0 items")

    fetched = [x for x in fetched if is_recent(x)]
    all_items = merge_items(load_history() + fetched)
    all_items = sorted(all_items, key=lambda x: x.get("date", ""), reverse=True)[:900]

    save_history(all_items)
    OUT_HTML.write_text(build_html(all_items, warnings[:12]), encoding="utf-8")

    print(f"Article pages fetched for details: {article_fetch_count}")
    print(f"Done. Open: {OUT_HTML.resolve()}")
    print(f"Unique items: {len(all_items)}")


if __name__ == "__main__":
    main()
