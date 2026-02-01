"""
Vercel Serverless Function - SC Ice Storm News Crawler
Endpoint: /api/crawl
"""

import json
import hashlib
import re
import html
from datetime import datetime, timedelta
from urllib.parse import quote_plus
from http.server import BaseHTTPRequestHandler

import urllib.request
import urllib.error

def clean_html(text):
    """Remove all HTML tags and decode entities."""
    if not text:
        return ''
    text = text.replace('&nbsp;', ' ')
    text = html.unescape(text)
    text = text.replace('\xa0', ' ')
    text = text.replace('&nbsp;', ' ')
    text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

SEARCH_TERMS = [
    "South Carolina ice storm",
    "SC ice storm",
    "South Carolina winter storm",
    "SC power outage ice",
    "South Carolina freezing rain",
    "Columbia SC ice storm",
    "Greenville SC ice storm",
    "Charleston SC winter weather",
    "Upstate SC ice storm",
    "Duke Energy South Carolina outage",
    "SC emergency shelter ice storm",
    "South Carolina school closings ice",
    "Spartanburg SC winter storm",
    "Midlands SC ice storm",
    "Red Cross South Carolina ice storm",
    "American Red Cross SC winter storm",
    "Red Cross shelter South Carolina",
]

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

def fetch_url(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode('utf-8')
    except Exception:
        return None

def parse_rss_simple(xml_content):
    items = []
    if not xml_content:
        return items
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
            description = clean_html(desc_match.group(1))[:300]
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

    exclude_terms = [
        'shooting', 'shot', 'murder', 'killed', 'homicide', 'gunfire', 'gunman',
        'arrest', 'arrested', 'charged', 'custody', 'suspect', 'investigation',
        'standoff', 'police say', 'sheriff', 'deputies',
        'robbery', 'assault', 'stabbing', 'stabbed',
        'drug', 'trafficking', 'cocaine', 'heroin', 'fentanyl', 'meth',
        'machine gun', 'weapon', 'firearm',
        'missing person', 'found dead', 'body found',
        'traffic stop', 'pulled over', 'dui', 'dwi',
        'hospice', 'funeral', 'obituary', 'died of', 'passes away', 'cancer',
        'football', 'basketball', 'baseball', 'soccer', 'nfl', 'nba', 'ncaa',
        'game day', 'touchdown', 'playoff', 'coach enters',
        'election', 'vote', 'ballot', 'campaign', 'democrat', 'republican',
        'congress', 'senate',
        'real estate', 'restaurant', 'recipe', 'entertainment', 'movie', 'concert',
        'live cam', 'live look', 'photos:', 'viewer', 'share their',
        'fun in the snow', 'snow day:', 'afterglow', 'snow photos',
        'live cams:', 'photo gallery',
    ]
    if any(term in text for term in exclude_terms):
        return False

    if 'red cross' in text and any(loc in text for loc in ['south carolina', ' sc ', 'carolina']):
        return True

    location_match = any(term in text for term in [
        'south carolina', ' sc ', 'columbia', 'greenville', 'charleston',
        'spartanburg', 'upstate', 'midlands', 'lowcountry', 'pee dee',
        'anderson', 'florence', 'myrtle beach', 'rock hill', 'sumter',
        'aiken', 'orangeburg', 'beaufort', 'hilton head', 'lexington',
        'richland', 'horry', 'york', 'berkeley', 'dorchester', 'pickens',
        'oconee', 'laurens', 'newberry', 'saluda', 'edgefield', 'abbeville',
        'grand strand', 'santee', 'lake murray', 'clemson', 'conway'
    ])
    nc_only = 'north carolina' in text and 'south carolina' not in text
    if nc_only:
        return False
    weather_match = any(term in text for term in [
        'ice storm', 'winter storm', 'winter weather', 'freezing rain',
        'freezing temperature', 'sleet',
        'power outage', 'outage', 'without power',
        'shelter', 'warming center',
        'extreme cold', 'bitter cold', 'cold warning', 'cold temperature',
        'dangerous cold', 'dangerously cold', 'wind chill',
        'duke energy', 'dominion energy', 'santee cooper',
        'school clos', 'school delay', 'e-learning', 'elearning',
        'state of emergency', 'governor', 'mcmaster',
        'road clos', 'bridge clos', 'icy road', 'hazardous travel',
        'stay off the road', 'impassible', 'snow',
        'red cross', 'national guard', 'hypothermia',
    ])
    return location_match and weather_match

def parse_date(pub):
    if not pub:
        return None
    pub_clean = pub.strip()
    pub_clean = re.sub(r'\s+(GMT|UTC|EST|EDT|PST|PDT|CST|CDT)$', '', pub_clean)
    pub_clean = re.sub(r'\s*[+-]\d{4}$', '', pub_clean)
    for fmt in ['%a, %d %b %Y %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%d %b %Y %H:%M:%S']:
        try:
            return datetime.strptime(pub_clean, fmt)
        except:
            continue
    return None

def is_recent_enough(article, now):
    text = (article.get('title', '') + ' ' + article.get('summary', '')).lower()
    is_red_cross = 'red cross' in text
    cutoff = now - timedelta(days=7) if is_red_cross else now - timedelta(hours=48)
    pub_date = parse_date(article.get('published', ''))
    if pub_date:
        return pub_date >= cutoff
    pub = article.get('published', '')
    if is_red_cross:
        return '2026' in pub
    return '2026' in pub

def crawl_news():
    articles = []
    seen_urls = set()
    seen_titles = set()

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

    local_feeds = [
        ("WLTX Columbia", "https://www.wltx.com/feeds/syndication/rss/news/local"),
        ("WIS Columbia", "https://www.wistv.com/arc/outboundfeeds/rss/category/news/?outputType=xml"),
        ("WACH Fox Columbia", "https://wach.com/feed/rss/news/local"),
        ("The State", "https://www.thestate.com/news/local/?widgetName=rssfeed&widgetContentId=712015&getContent=true"),
        ("WYFF Greenville", "https://www.wyff4.com/topstories-rss"),
        ("Fox Carolina", "https://www.foxcarolina.com/search/?f=rss&t=article&c=news/local&l=50&s=start_time&sd=desc"),
        ("WSPA Spartanburg", "https://www.wspa.com/feed/"),
        ("Greenville News", "https://www.greenvilleonline.com/arcio/rss/"),
        ("WCSC Charleston", "https://www.live5news.com/search/?f=rss&t=article&c=news/local&l=50&s=start_time&sd=desc"),
        ("WCBD Charleston", "https://www.counton2.com/feed/"),
        ("Post and Courier", "https://www.postandcourier.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc"),
        ("WMBF Myrtle Beach", "https://www.wmbfnews.com/search/?f=rss&t=article&c=news&l=50&s=start_time&sd=desc"),
        ("WBTW Florence", "https://www.wbtw.com/feed/"),
        ("WPDE Myrtle Beach", "https://wpde.com/feed/rss/news/local"),
        ("WRDW Augusta", "https://www.wrdw.com/search/?f=rss&t=article&c=news/local&l=50"),
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

    now = datetime.now()
    filtered_articles = [a for a in articles if is_recent_enough(a, now)]

    def get_sort_date(article):
        pub_date = parse_date(article.get('published', ''))
        return pub_date if pub_date else datetime.min

    filtered_articles.sort(key=get_sort_date, reverse=True)

    return {
        'metadata': {
            'crawled_at': now.isoformat(),
            'total_articles': len(filtered_articles),
            'total_crawled': len(articles),
        },
        'articles': filtered_articles
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            result = crawl_news()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 's-maxage=10800, stale-while-revalidate=3600')
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
