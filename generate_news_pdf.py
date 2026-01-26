#!/usr/bin/env python3
"""
SC Ice Storm News PDF Generator
Generates a disaster briefing PDF with:
- AI-generated executive summary
- Categorized key impacts
- Red Cross mentions (7 days)
- All articles (36 hours)
- Clickable links

For American Red Cross emergency response
"""

import json
import os
import re
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

# API endpoint - single source of truth for news data
NEWS_API_URL = "https://sc-ice-storm-news.vercel.app/api/crawl"

# Configuration
OUTPUT_DIR = Path(__file__).parent
DR_NUMBER = "DR 153-26"
PREPARED_BY = "Disaster Operations"
ARTICLE_HOURS = 36  # General articles window
RED_CROSS_DAYS = 7  # Red Cross mentions window


# Categories for AI classification
CATEGORIES = {
    'power': {
        'name': 'POWER & UTILITIES',
        'keywords': ['power', 'outage', 'electric', 'utility', 'duke energy', 'dominion', 'grid', 'restore', 'linemen']
    },
    'roads': {
        'name': 'ROAD CONDITIONS',
        'keywords': ['road', 'highway', 'bridge', 'traffic', 'accident', 'crash', 'driving', 'icy road', 'dot', 'travel']
    },
    'schools': {
        'name': 'SCHOOLS & CLOSURES',
        'keywords': ['school', 'university', 'college', 'class', 'campus', 'student', 'closed', 'delay', 'virtual']
    },
    'shelters': {
        'name': 'SHELTERS & WARMING CENTERS',
        'keywords': ['shelter', 'warming', 'center', 'housing', 'homeless', 'displaced', 'evacuate']
    },
    'emergency': {
        'name': 'EMERGENCY RESPONSE',
        'keywords': ['emergency', 'rescue', 'first responder', 'national guard', 'fema', 'governor', 'state of emergency']
    }
}


def categorize_article(article: dict) -> str:
    """Categorize an article based on keywords."""
    text = f"{article.get('title', '')} {article.get('summary', '')}".lower()

    for cat_id, cat_info in CATEGORIES.items():
        if any(kw in text for kw in cat_info['keywords']):
            return cat_id

    return 'other'


def is_red_cross_mention(article: dict) -> bool:
    """Check if article mentions Red Cross."""
    text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
    return 'red cross' in text or 'redcross' in text or 'american red cross' in text


def parse_date(date_str: str) -> datetime:
    """Parse various date formats."""
    if not date_str:
        return datetime.now()

    formats = [
        '%a, %d %b %Y %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M:%S',
        '%a, %d %b %Y %H:%M:%S %z',
    ]

    for fmt in formats:
        try:
            # Remove timezone info for simplicity
            clean_date = re.sub(r'\s*[+-]\d{4}$', '', date_str)
            clean_date = re.sub(r'\s*GMT$', '', clean_date)
            return datetime.strptime(clean_date.strip(), fmt)
        except:
            continue

    return datetime.now()


def generate_executive_summary(articles: list, red_cross_articles: list) -> str:
    """Generate executive summary text."""
    sources = set(a.get('source', 'Unknown') for a in articles)

    # Count by category
    cat_counts = {}
    for a in articles:
        cat = categorize_article(a)
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    summary = f"This report summarizes {len(articles)} news articles from {len(sources)} sources "
    summary += "covering the South Carolina ice storm. "

    if red_cross_articles:
        summary += f"Red Cross is mentioned in {len(red_cross_articles)} articles. "

    summary += "See categorized headlines below for specific impacts reported by local media."

    return summary


class NewsPDFGenerator:
    """Generates disaster briefing PDF from news articles."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_styles()

    def _setup_styles(self):
        """Setup custom paragraph styles."""
        # Title style (white on red)
        self.styles.add(ParagraphStyle(
            'RedTitle',
            parent=self.styles['Heading1'],
            fontSize=28,
            textColor=colors.white,
            spaceAfter=6
        ))

        # Subtitle
        self.styles.add(ParagraphStyle(
            'Subtitle',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=colors.white,
            spaceAfter=4
        ))

        # Section header (red)
        self.styles.add(ParagraphStyle(
            'SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#c62828'),
            spaceBefore=16,
            spaceAfter=8
        ))

        # Category header
        self.styles.add(ParagraphStyle(
            'CategoryHeader',
            parent=self.styles['Heading3'],
            fontSize=11,
            textColor=colors.HexColor('#c62828'),
            spaceBefore=12,
            spaceAfter=4,
            fontName='Helvetica-Bold'
        ))

        # Bullet item
        self.styles.add(ParagraphStyle(
            'BulletItem',
            parent=self.styles['Normal'],
            fontSize=10,
            leftIndent=20,
            spaceBefore=2,
            spaceAfter=2
        ))

        # Article source
        self.styles.add(ParagraphStyle(
            'ArticleSource',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#c62828'),
            fontName='Helvetica-Bold',
            spaceBefore=12
        ))

        # Article title (clickable)
        self.styles.add(ParagraphStyle(
            'ArticleTitle',
            parent=self.styles['Normal'],
            fontSize=11,
            fontName='Helvetica-Bold',
            spaceBefore=2,
            spaceAfter=2
        ))

        # Article summary
        self.styles.add(ParagraphStyle(
            'ArticleSummary',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#555555'),
            spaceAfter=2
        ))

        # Article date
        self.styles.add(ParagraphStyle(
            'ArticleDate',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#888888'),
            spaceAfter=8
        ))

        # Stats line
        self.styles.add(ParagraphStyle(
            'StatsLine',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#c62828'),
            alignment=TA_CENTER,
            spaceBefore=8
        ))

    def generate(self, articles: list, output_path: str = None) -> str:
        """Generate the PDF report."""
        if output_path is None:
            timestamp = datetime.now().strftime('%Y-%m-%d_%H%M')
            output_path = OUTPUT_DIR / f"SC-{DR_NUMBER.replace(' ', '')}-News-Summary-{timestamp}.pdf"

        now = datetime.now()
        cutoff_articles = now - timedelta(hours=ARTICLE_HOURS)
        cutoff_redcross = now - timedelta(days=RED_CROSS_DAYS)

        # Filter articles by time
        recent_articles = []
        red_cross_articles = []

        for article in articles:
            pub_date = parse_date(article.get('published', ''))

            # Red Cross mentions (7 days)
            if is_red_cross_mention(article) and pub_date >= cutoff_redcross:
                red_cross_articles.append(article)

            # General articles (36 hours)
            if pub_date >= cutoff_articles:
                recent_articles.append(article)

        # Sort newest first
        recent_articles.sort(key=lambda x: parse_date(x.get('published', '')), reverse=True)
        red_cross_articles.sort(key=lambda x: parse_date(x.get('published', '')), reverse=True)

        # Dedupe
        seen_titles = set()
        deduped_articles = []
        for a in recent_articles:
            title_key = re.sub(r'[^a-z0-9]', '', a.get('title', '').lower())
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                deduped_articles.append(a)

        recent_articles = deduped_articles

        # Build PDF
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch
        )

        story = []

        # Header block (red background)
        story.extend(self._build_header(recent_articles, now))

        # Executive Summary
        story.append(Paragraph("EXECUTIVE SUMMARY", self.styles['SectionHeader']))
        summary_text = generate_executive_summary(recent_articles, red_cross_articles)
        story.append(Paragraph(summary_text, self.styles['Normal']))
        story.append(Spacer(1, 12))

        # Key Impacts by Category
        story.append(Paragraph("KEY IMPACTS FROM NEWS COVERAGE", self.styles['SectionHeader']))
        story.extend(self._build_categorized_bullets(recent_articles))

        # Red Cross Mentions Section
        if red_cross_articles:
            story.append(Spacer(1, 12))
            story.extend(self._build_red_cross_section(red_cross_articles))

        # News Article Details
        story.append(PageBreak())
        story.append(Paragraph("NEWS ARTICLE DETAILS", self.styles['SectionHeader']))
        story.append(Paragraph(
            f"(All content from South Carolina news sources within past {ARTICLE_HOURS} hours)",
            self.styles['ArticleDate']
        ))
        story.extend(self._build_article_list(recent_articles))

        # Footer
        story.append(Spacer(1, 20))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#cccccc')))
        story.append(Paragraph(
            f"American Red Cross | {DR_NUMBER} | Generated {now.strftime('%Y-%m-%d %H:%M')}",
            ParagraphStyle('Footer', parent=self.styles['Normal'], fontSize=8,
                          textColor=colors.gray, alignment=TA_CENTER)
        ))

        # Build PDF
        doc.build(story)

        print(f"PDF generated: {output_path}")
        return str(output_path)

    def _build_header(self, articles: list, now: datetime) -> list:
        """Build the red header section."""
        elements = []

        sources = set(a.get('source', 'Unknown') for a in articles)

        # Create header table with red background
        header_data = [
            [Paragraph("South Carolina Ice Storm", self.styles['RedTitle'])],
            [Paragraph(f"{DR_NUMBER} | Disaster Operations Briefing", self.styles['Subtitle'])],
            [Paragraph(f"Prepared By: {PREPARED_BY} | {now.strftime('%A, %B %d, %Y')}", self.styles['Subtitle'])],
        ]

        header_table = Table(header_data, colWidths=[7*inch])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#c62828')),
            ('LEFTPADDING', (0, 0), (-1, -1), 16),
            ('RIGHTPADDING', (0, 0), (-1, -1), 16),
            ('TOPPADDING', (0, 0), (0, 0), 16),
            ('BOTTOMPADDING', (0, -1), (-1, -1), 16),
        ]))

        elements.append(header_table)
        elements.append(Spacer(1, 8))

        # Stats line
        stats = f"<b>{len(articles)}</b> News Articles | <b>{len(sources)}</b> Sources | Report Generated: {now.strftime('%I:%M %p')}"
        elements.append(Paragraph(stats, self.styles['StatsLine']))
        elements.append(Spacer(1, 12))

        return elements

    def _build_categorized_bullets(self, articles: list) -> list:
        """Build categorized bullet points of headlines."""
        elements = []

        # Group by category
        by_category = {}
        for article in articles:
            cat = categorize_article(article)
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(article)

        # Output each category
        for cat_id, cat_info in CATEGORIES.items():
            if cat_id in by_category:
                elements.append(Paragraph(cat_info['name'], self.styles['CategoryHeader']))

                # Show top 3 headlines per category
                for article in by_category[cat_id][:3]:
                    title = article.get('title', 'No title')
                    # Truncate long titles
                    if len(title) > 90:
                        title = title[:87] + "..."
                    source = article.get('source', '').split()[0].lower()
                    bullet = f"- {title} - {source}"
                    elements.append(Paragraph(bullet, self.styles['BulletItem']))

        return elements

    def _build_red_cross_section(self, articles: list) -> list:
        """Build Red Cross mentions section with red highlight."""
        elements = []

        # Red Cross header with background
        rc_header = Table(
            [[Paragraph("RED CROSS MENTIONS", ParagraphStyle(
                'RCHeader', fontSize=14, textColor=colors.white, fontName='Helvetica-Bold'
            ))]],
            colWidths=[7*inch]
        )
        rc_header.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#c62828')),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(rc_header)
        elements.append(Spacer(1, 8))

        # List Red Cross articles
        for article in articles[:5]:  # Top 5
            elements.extend(self._build_article_item(article, highlight_rc=True))

        return elements

    def _build_article_list(self, articles: list) -> list:
        """Build the full article list."""
        elements = []

        for article in articles:
            elements.extend(self._build_article_item(article))

        return elements

    def _build_article_item(self, article: dict, highlight_rc: bool = False) -> list:
        """Build a single article entry."""
        elements = []

        source = article.get('source', 'Unknown')
        title = article.get('title', 'No title')
        summary = article.get('summary', '')
        url = article.get('url', '')
        published = article.get('published', '')

        # Source
        elements.append(Paragraph(source.upper(), self.styles['ArticleSource']))

        # Title (with link if available)
        if url:
            title_linked = f'<a href="{url}" color="blue">{title}</a>'
            # Also highlight Red Cross in title
            if highlight_rc:
                title_linked = title_linked.replace('Red Cross', '<font color="red"><b>Red Cross</b></font>')
        else:
            title_linked = title

        elements.append(Paragraph(title_linked, self.styles['ArticleTitle']))

        # Summary
        if summary:
            # Truncate long summaries
            if len(summary) > 200:
                summary = summary[:197] + "..."
            if highlight_rc:
                summary = summary.replace('Red Cross', '<font color="red"><b>Red Cross</b></font>')
            elements.append(Paragraph(summary, self.styles['ArticleSummary']))

        # Date
        if published:
            try:
                pub_date = parse_date(published)
                date_str = pub_date.strftime('%a, %d %b %Y %H:%M:%S')
            except:
                date_str = published
            elements.append(Paragraph(date_str, self.styles['ArticleDate']))

        return elements


def fetch_news_from_api():
    """Fetch news from the single API endpoint."""
    print(f"Fetching from {NEWS_API_URL}...")
    req = urllib.request.Request(
        NEWS_API_URL,
        headers={"User-Agent": "Mozilla/5.0 SC-News-PDF-Generator"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data.get('articles', [])
    except Exception as e:
        print(f"Error fetching from API: {e}")
        # Fallback: try local news_data.json
        local_file = Path(__file__).parent / "news_data.json"
        if local_file.exists():
            print(f"Using local cache: {local_file}")
            with open(local_file) as f:
                data = json.load(f)
                return data.get('articles', [])
        return []


def main():
    """Main entry point."""
    print("=" * 60)
    print("SC Ice Storm News PDF Generator")
    print("American Red Cross Disaster Briefing")
    print("=" * 60)
    print()

    # Fetch from single API source
    articles = fetch_news_from_api()

    if not articles:
        print("No articles found!")
        return

    # Save JSON backup
    backup_file = Path(__file__).parent / "news_data.json"
    with open(backup_file, 'w') as f:
        json.dump({'articles': articles, 'fetched_at': datetime.now().isoformat()}, f, indent=2)
    print(f"Saved backup: {backup_file}")

    # Generate PDF
    print("\nGenerating PDF report...")
    generator = NewsPDFGenerator()
    pdf_path = generator.generate(articles)

    print(f"\nDone! PDF saved to: {pdf_path}")
    print(f"Articles: {len(articles)}")


if __name__ == "__main__":
    main()
