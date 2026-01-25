"""
Vercel Serverless Function - SC Ice Storm News Crawler
Endpoint: /api/crawl
"""

import json
import hashlib
import re
import html
from datetime import datetime
from urllib.parse import quote_plus
from http.server import BaseHTTPRequestHandler

import urllib.request
import urllib.error

def clean_html(text):
    """Remove all HTML tags and decode entities."""
    if not text:
        return ''
    # Remove &nbsp; before unescaping (converts to \xa0 otherwise)
    text = text.replace('&nbsp;', ' ')
    # Decode HTML entities (&lt; -> <, &amp; -> &, etc.)
    text = html.unescape(text)
    # Replace non-breaking space unicode with regular space
    text = text.replace('\xa0', ' ')
    # Remove CDATA wrappers
    text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text, flags=re.DOTALL)
    # Remove all HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

SEARCH_TERMS = [
    "South Carolina ice storm",
    "SC ice storm",
    "South Carolina winter storm",
    "SC power outage ice",
]

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

def fetch_url(url):
    """Fetch URL content."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        return None

def parse_rss_simple(xml_content):
    """Simple RSS parser without external dependencies."""
    items = []
    if not xml_content:
        return items

    # Find all <item> or <entry> blocks
    import re
    item_pattern = re.compile(r'<item>(.*?)</item>', re.DOTALL)
    entry_pattern = re.compile(r'<entry>(.*?)</entry>', re.DOTALL)

    matches = item_pattern.findall(xml_content) or entry_pattern.findall(xml_content)

    for item_xml in matches[:15]:
        title_match = re.search(r'<title[^>]*>(.*?)</title>', item_xml, re.DOTALL)
        link_match = re.search(r'<link[^>]*>(.*?)</link>', item_xml, re.DOTALL) or \
                     re.search(r'<link[^>]*href="([^"]+)"', item_xml)
        pub_match = re.search(r'<pubDate>(.*?)</pubDate>', item_xml, re.DOTALL) or \
                    re.search(r'<published>(.*?)</published>', item_xml, re.DOTALL)
        desc_match = re.search(r'<description>(.*?)</description>', item_xml, re.DOTALL)

        title = clean_html(title_match.group(1)) if title_match else ''

        link = ''
        if link_match:
            link = link_match.group(1).strip()
            link = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', link)

        pub_date = pub_match.group(1).strip() if pub_match else ''

        description = ''
        if desc_match:
            description = clean_html(desc_match.group(1))[:200]

        if title and link:
            items.append({
                'title': title,
                'link': link,
                'published': pub_date,
                'description': description
            })

    return items

def generate_id(url):
    return hashlib.md5(url.encode()).hexdigest()[:12]

def normalize_title(title):
    return re.sub(r'[^a-z0-9]', '', title.lower())

def is_relevant(title, description=''):
    text = f"{title} {description}".lower()
    sc_match = any(term in text for term in ['south carolina', ' sc ', 'carolina'])
    weather_match = any(term in text for term in [
        'ice', 'winter', 'storm', 'freeze', 'freezing', 'cold',
        'power outage', 'shelter', 'emergency', 'weather'
    ])
    return sc_match and weather_match

def crawl_news():
    """Run the news crawl."""
    articles = []
    seen_urls = set()
    seen_titles = set()

    # Google News RSS
    for term in SEARCH_TERMS:
        encoded_term = quote_plus(term)
        rss_url = f"https://news.google.com/rss/search?q={encoded_term}&hl=en-US&gl=US&ceid=US:en"

        content = fetch_url(rss_url)
        if content:
            items = parse_rss_simple(content)
            for item in items:
                title = item['title']
                url = item['link']
                norm_title = normalize_title(title)

                if url in seen_urls or norm_title in seen_titles:
                    continue
                if not is_relevant(title, item.get('description', '')):
                    continue

                seen_urls.add(url)
                seen_titles.add(norm_title)

                articles.append({
                    'id': generate_id(url),
                    'title': title,
                    'url': url,
                    'source': 'Google News',
                    'published': item.get('published', ''),
                    'summary': item.get('description', ''),
                })

    # Local SC RSS feeds
    local_feeds = [
        ("WLTX Columbia", "https://www.wltx.com/feeds/syndication/rss/news/local"),
        ("WIS Columbia", "https://www.wistv.com/arc/outboundfeeds/rss/category/news/?outputType=xml"),
        ("WYFF Greenville", "https://www.wyff4.com/topstories-rss"),
    ]

    for source_name, rss_url in local_feeds:
        content = fetch_url(rss_url)
        if content:
            items = parse_rss_simple(content)
            for item in items:
                title = item['title']
                url = item['link']
                norm_title = normalize_title(title)

                if url in seen_urls or norm_title in seen_titles:
                    continue
                if not is_relevant(title, item.get('description', '')):
                    continue

                seen_urls.add(url)
                seen_titles.add(norm_title)

                articles.append({
                    'id': generate_id(url),
                    'title': title,
                    'url': url,
                    'source': source_name,
                    'published': item.get('published', ''),
                    'summary': item.get('description', ''),
                })

    return {
        'metadata': {
            'crawled_at': datetime.now().isoformat(),
            'total_articles': len(articles),
        },
        'articles': articles
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            result = crawl_news()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.end_headers()
