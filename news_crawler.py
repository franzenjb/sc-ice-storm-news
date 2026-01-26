#!/usr/bin/env python3
"""
South Carolina Ice Storm News Crawler
For American Red Cross news monitoring

Aggregates news from:
- Google News RSS
- Local SC news outlets (The State, Post and Courier, WLTX, WIS, etc.)
"""

import json
import hashlib
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus, urljoin
import feedparser
import requests
from bs4 import BeautifulSoup

# Configuration
SEARCH_TERMS = [
    "South Carolina ice storm",
    "SC ice storm",
    "South Carolina winter storm",
    "SC power outage ice",
    "South Carolina freezing rain",
    "SC winter weather emergency",
    "South Carolina ice storm shelter",
    "SC ice storm Red Cross",
]

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Local SC News Sources
SC_NEWS_SOURCES = {
    "The State (Columbia)": {
        "search_url": "https://www.thestate.com/search/?q={query}",
        "rss_url": "https://www.thestate.com/news/local/?widgetName=rssfeed&widgetContentId=712015&get498Legacy498702702702702702702",
        "base_url": "https://www.thestate.com",
    },
    "Post and Courier (Charleston)": {
        "search_url": "https://www.postandcourier.com/search/?q={query}",
        "base_url": "https://www.postandcourier.com",
    },
    "Greenville News": {
        "search_url": "https://www.greenvilleonline.com/search/?q={query}",
        "base_url": "https://www.greenvilleonline.com",
    },
    "WLTX (Columbia CBS)": {
        "search_url": "https://www.wltx.com/search?q={query}",
        "base_url": "https://www.wltx.com",
    },
    "WIS (Columbia NBC)": {
        "search_url": "https://www.wistv.com/search/?searchQuery={query}",
        "base_url": "https://www.wistv.com",
    },
    "WYFF (Greenville NBC)": {
        "search_url": "https://www.wyff4.com/search?q={query}",
        "base_url": "https://www.wyff4.com",
    },
    "WCSC (Charleston CBS)": {
        "search_url": "https://www.live5news.com/search/?searchQuery={query}",
        "base_url": "https://www.live5news.com",
    },
    "WMBF (Myrtle Beach)": {
        "search_url": "https://www.wmbfnews.com/search/?searchQuery={query}",
        "base_url": "https://www.wmbfnews.com",
    },
}


class NewsCrawler:
    def __init__(self):
        self.articles = []
        self.seen_urls = set()
        self.seen_titles = set()
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _generate_id(self, url: str) -> str:
        """Generate unique ID for article."""
        return hashlib.md5(url.encode()).hexdigest()[:12]

    def _normalize_title(self, title: str) -> str:
        """Normalize title for deduplication."""
        return re.sub(r'[^a-z0-9]', '', title.lower())

    def _is_duplicate(self, url: str, title: str) -> bool:
        """Check if article is duplicate."""
        norm_title = self._normalize_title(title)
        if url in self.seen_urls or norm_title in self.seen_titles:
            return True
        self.seen_urls.add(url)
        self.seen_titles.add(norm_title)
        return False

    def _is_relevant(self, title: str, description: str = "") -> bool:
        """Check if article is relevant to SC ice storm."""
        text = f"{title} {description}".lower()

        # Exclude crime/police stories
        exclude_terms = [
            'shooting', 'shot', 'murder', 'killed', 'arrest', 'arrested',
            'standoff', 'police', 'suspect', 'crime', 'robbery', 'assault',
            'homicide', 'investigation', 'custody', 'charged', 'victim',
            'mosque', 'church shooting', 'gunfire', 'gunman'
        ]
        if any(term in text for term in exclude_terms):
            return False

        # Must mention South Carolina or SC
        sc_match = any(term in text for term in ['south carolina', ' sc ', 'carolina'])

        # Must mention ACTUAL winter weather terms (not just "emergency" or "cold")
        weather_match = any(term in text for term in [
            'ice storm', 'winter storm', 'freezing rain', 'frozen',
            'freeze warning', 'ice accumulation', 'sleet', 'black ice',
            'power outage', 'outages', 'without power', 'power restored',
            'warming shelter', 'warming center', 'road conditions',
            'hazardous roads', 'icy roads', 'school closing', 'school delay',
            'winter weather', 'cold snap', 'below freezing', 'wind chill',
            'red cross shelter', 'emergency shelter'
        ])
        return sc_match and weather_match

    def fetch_google_news(self):
        """Fetch articles from Google News RSS."""
        print("\n[Google News] Fetching articles...")

        for term in SEARCH_TERMS[:4]:  # Use first 4 search terms
            encoded_term = quote_plus(term)
            rss_url = f"https://news.google.com/rss/search?q={encoded_term}&hl=en-US&gl=US&ceid=US:en"

            try:
                feed = feedparser.parse(rss_url)
                for entry in feed.entries[:10]:  # Limit per search term
                    title = entry.get('title', '')
                    link = entry.get('link', '')
                    published = entry.get('published', '')
                    summary = entry.get('summary', '')

                    # Clean up Google News redirect URLs
                    if 'news.google.com' in link:
                        # Try to extract actual URL from Google redirect
                        actual_link = link
                    else:
                        actual_link = link

                    if self._is_duplicate(actual_link, title):
                        continue

                    if not self._is_relevant(title, summary):
                        continue

                    # Clean summary HTML
                    if summary:
                        soup = BeautifulSoup(summary, 'html.parser')
                        summary = soup.get_text()[:300]

                    self.articles.append({
                        'id': self._generate_id(actual_link),
                        'title': title,
                        'url': actual_link,
                        'source': 'Google News',
                        'published': published,
                        'summary': summary,
                        'search_term': term,
                        'crawled_at': datetime.now().isoformat(),
                    })
                    print(f"  + {title[:60]}...")

            except Exception as e:
                print(f"  Error fetching Google News for '{term}': {e}")

    def fetch_local_news_rss(self):
        """Fetch from local news RSS feeds where available."""
        print("\n[Local News RSS] Checking feeds...")

        # Some local stations have RSS feeds
        rss_feeds = [
            ("WLTX Columbia", "https://www.wltx.com/feeds/syndication/rss/news/local"),
            ("WIS Columbia", "https://www.wistv.com/arc/outboundfeeds/rss/category/news/?outputType=xml"),
            ("WYFF Greenville", "https://www.wyff4.com/topstories-rss"),
        ]

        for source_name, rss_url in rss_feeds:
            try:
                feed = feedparser.parse(rss_url)
                count = 0
                for entry in feed.entries[:20]:
                    title = entry.get('title', '')
                    link = entry.get('link', '')
                    published = entry.get('published', '')
                    summary = entry.get('summary', entry.get('description', ''))

                    if self._is_duplicate(link, title):
                        continue

                    if not self._is_relevant(title, summary):
                        continue

                    # Clean summary
                    if summary:
                        soup = BeautifulSoup(summary, 'html.parser')
                        summary = soup.get_text()[:300]

                    self.articles.append({
                        'id': self._generate_id(link),
                        'title': title,
                        'url': link,
                        'source': source_name,
                        'published': published,
                        'summary': summary,
                        'crawled_at': datetime.now().isoformat(),
                    })
                    count += 1
                    print(f"  + [{source_name}] {title[:50]}...")

                if count == 0:
                    print(f"  [{source_name}] No relevant articles found")

            except Exception as e:
                print(f"  [{source_name}] RSS feed unavailable: {e}")

    def scrape_search_results(self, source_name: str, source_config: dict):
        """Scrape search results from a news site."""
        search_url = source_config.get('search_url', '')
        base_url = source_config.get('base_url', '')

        if not search_url:
            return

        # Use most specific search term
        query = "ice storm"
        url = search_url.format(query=quote_plus(query))

        try:
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                return

            soup = BeautifulSoup(response.text, 'html.parser')

            # Generic selectors that work across many news sites
            selectors = [
                'article a[href*="/news/"]',
                'article a[href*="/story/"]',
                '.search-result a',
                '.story-card a',
                'h2 a', 'h3 a',
                '.headline a',
                '[class*="title"] a',
                '[class*="headline"] a',
            ]

            links_found = set()
            for selector in selectors:
                for link in soup.select(selector)[:10]:
                    href = link.get('href', '')
                    title = link.get_text(strip=True)

                    if not href or not title or len(title) < 10:
                        continue

                    # Make absolute URL
                    if href.startswith('/'):
                        href = urljoin(base_url, href)
                    elif not href.startswith('http'):
                        continue

                    if href in links_found:
                        continue
                    links_found.add(href)

                    if self._is_duplicate(href, title):
                        continue

                    if not self._is_relevant(title, ''):
                        continue

                    self.articles.append({
                        'id': self._generate_id(href),
                        'title': title,
                        'url': href,
                        'source': source_name,
                        'published': '',
                        'summary': '',
                        'crawled_at': datetime.now().isoformat(),
                    })
                    print(f"  + [{source_name}] {title[:50]}...")

        except Exception as e:
            print(f"  [{source_name}] Search failed: {e}")

    def fetch_local_news_search(self):
        """Search local news sites."""
        print("\n[Local News Search] Scraping search results...")

        for source_name, config in SC_NEWS_SOURCES.items():
            self.scrape_search_results(source_name, config)

    def crawl(self):
        """Run the full crawl."""
        print("=" * 60)
        print("SC Ice Storm News Crawler")
        print("American Red Cross News Monitoring")
        print("=" * 60)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        self.fetch_google_news()
        self.fetch_local_news_rss()
        self.fetch_local_news_search()

        # Sort by crawled time (newest first)
        self.articles.sort(key=lambda x: x.get('published', ''), reverse=True)

        print("\n" + "=" * 60)
        print(f"Total articles found: {len(self.articles)}")
        print("=" * 60)

        return self.articles

    def save_json(self, filepath: str = "news_data.json"):
        """Save articles to JSON file."""
        output = {
            'metadata': {
                'crawled_at': datetime.now().isoformat(),
                'total_articles': len(self.articles),
                'search_terms': SEARCH_TERMS,
                'sources': list(SC_NEWS_SOURCES.keys()) + ['Google News'],
            },
            'articles': self.articles,
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\nJSON saved to: {filepath}")
        return filepath

    def save_html(self, filepath: str = "news_report.html"):
        """Save articles to styled HTML report."""
        html = self._generate_html()

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f"HTML saved to: {filepath}")
        return filepath

    def _generate_html(self) -> str:
        """Generate styled HTML report."""

        # Group articles by source
        by_source = {}
        for article in self.articles:
            source = article.get('source', 'Unknown')
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(article)

        # Generate article cards
        article_cards = ""
        for article in self.articles:
            published = article.get('published', 'Unknown date')
            if published and len(published) > 25:
                # Truncate long date strings
                published = published[:25]

            summary = article.get('summary', '')
            if summary:
                summary_html = f'<p class="summary">{summary}</p>'
            else:
                summary_html = ''

            article_cards += f'''
            <div class="article-card">
                <div class="article-source">{article.get('source', 'Unknown')}</div>
                <h3 class="article-title">
                    <a href="{article.get('url', '#')}" target="_blank">{article.get('title', 'No title')}</a>
                </h3>
                {summary_html}
                <div class="article-meta">
                    <span class="date">{published}</span>
                </div>
            </div>
            '''

        # Source summary
        source_summary = ""
        for source, articles in sorted(by_source.items(), key=lambda x: -len(x[1])):
            source_summary += f'<div class="source-item"><span class="source-name">{source}</span><span class="source-count">{len(articles)}</span></div>'

        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SC Ice Storm News | American Red Cross</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background-color: #f5f5f5;
            color: #333;
            line-height: 1.6;
        }}

        .header {{
            background-color: #d32f2f;
            color: white;
            padding: 24px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }}

        .header h1 {{
            font-size: 28px;
            margin-bottom: 8px;
        }}

        .header .subtitle {{
            font-size: 14px;
            opacity: 0.9;
        }}

        .header .updated {{
            font-size: 12px;
            margin-top: 12px;
            opacity: 0.8;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 24px;
        }}

        .stats-bar {{
            display: flex;
            gap: 16px;
            margin-bottom: 24px;
            flex-wrap: wrap;
        }}

        .stat-card {{
            background: white;
            border-radius: 8px;
            padding: 16px 24px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            flex: 1;
            min-width: 150px;
        }}

        .stat-card .number {{
            font-size: 32px;
            font-weight: bold;
            color: #c62828;
        }}

        .stat-card .label {{
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
        }}

        .main-content {{
            display: grid;
            grid-template-columns: 1fr 300px;
            gap: 24px;
        }}

        @media (max-width: 900px) {{
            .main-content {{
                grid-template-columns: 1fr;
            }}
        }}

        .articles-section {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 24px;
        }}

        .section-title {{
            font-size: 18px;
            color: #c62828;
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 2px solid #ffcdd2;
        }}

        .article-card {{
            padding: 16px 0;
            border-bottom: 1px solid #e0e0e0;
        }}

        .article-card:last-child {{
            border-bottom: none;
        }}

        .article-source {{
            font-size: 11px;
            color: #c62828;
            text-transform: uppercase;
            font-weight: 600;
            margin-bottom: 4px;
        }}

        .article-title {{
            font-size: 16px;
            line-height: 1.4;
            margin-bottom: 8px;
        }}

        .article-title a {{
            color: #333;
            text-decoration: none;
        }}

        .article-title a:hover {{
            color: #c62828;
            text-decoration: underline;
        }}

        .summary {{
            font-size: 14px;
            color: #666;
            margin-bottom: 8px;
        }}

        .article-meta {{
            font-size: 12px;
            color: #999;
        }}

        .sidebar {{
            display: flex;
            flex-direction: column;
            gap: 24px;
        }}

        .sidebar-card {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 20px;
        }}

        .sidebar-card h3 {{
            font-size: 14px;
            color: #c62828;
            text-transform: uppercase;
            margin-bottom: 16px;
        }}

        .source-item {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #f0f0f0;
            font-size: 13px;
        }}

        .source-item:last-child {{
            border-bottom: none;
        }}

        .source-count {{
            font-weight: bold;
            color: #c62828;
        }}

        .search-terms {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}

        .term-tag {{
            background: #ffebee;
            color: #c62828;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
        }}

        .footer {{
            text-align: center;
            padding: 24px;
            color: #999;
            font-size: 12px;
        }}

        .refresh-btn {{
            display: inline-block;
            background: #c62828;
            color: white;
            padding: 8px 16px;
            border-radius: 4px;
            text-decoration: none;
            font-size: 13px;
            margin-top: 16px;
        }}

        .refresh-btn:hover {{
            background: #b71c1c;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>South Carolina Ice Storm</h1>
        <div class="subtitle">News Monitoring | American Red Cross</div>
        <div class="updated">Last updated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</div>
    </div>

    <div class="container">
        <div class="stats-bar">
            <div class="stat-card">
                <div class="number">{len(self.articles)}</div>
                <div class="label">Total Articles</div>
            </div>
            <div class="stat-card">
                <div class="number">{len(by_source)}</div>
                <div class="label">News Sources</div>
            </div>
            <div class="stat-card">
                <div class="number">{len([a for a in self.articles if 'red cross' in a.get('title', '').lower() or 'red cross' in a.get('summary', '').lower()])}</div>
                <div class="label">Red Cross Mentions</div>
            </div>
        </div>

        <div class="main-content">
            <div class="articles-section">
                <h2 class="section-title">Latest Coverage</h2>
                {article_cards if article_cards else '<p style="color: #999; padding: 20px;">No articles found. Try running the crawler again.</p>'}
            </div>

            <div class="sidebar">
                <div class="sidebar-card">
                    <h3>Sources</h3>
                    {source_summary if source_summary else '<p style="color: #999;">No sources</p>'}
                </div>

                <div class="sidebar-card">
                    <h3>Search Terms</h3>
                    <div class="search-terms">
                        {''.join(f'<span class="term-tag">{term}</span>' for term in SEARCH_TERMS[:6])}
                    </div>
                </div>

                <div class="sidebar-card">
                    <h3>Quick Actions</h3>
                    <p style="font-size: 13px; color: #666; margin-bottom: 12px;">
                        Run <code>python news_crawler.py</code> to refresh the news feed.
                    </p>
                </div>
            </div>
        </div>
    </div>

    <div class="footer">
        American Red Cross | News Monitoring System | Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}
    </div>
</body>
</html>'''

        return html


def main():
    """Main entry point."""
    crawler = NewsCrawler()
    crawler.crawl()

    # Save outputs
    output_dir = Path(__file__).parent
    crawler.save_json(output_dir / "news_data.json")
    crawler.save_html(output_dir / "news_report.html")

    print("\nDone! Open news_report.html in a browser to view results.")


if __name__ == "__main__":
    main()
