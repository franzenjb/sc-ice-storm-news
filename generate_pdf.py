#!/usr/bin/env python3
"""Generate PDF report from live crawled news data."""

import json
import requests
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER

def generate_pdf(output_path):
    # Fetch live news
    print("Fetching live news from API...")
    try:
        resp = requests.get("https://sc-ice-storm-news.vercel.app/api/crawl", timeout=30)
        data = resp.json()
        articles = data.get('articles', [])
        print(f"Found {len(articles)} articles")
    except Exception as e:
        print(f"Error fetching news: {e}")
        articles = []

    # Fetch AI summary
    print("Fetching AI summary...")
    ai_summary = None
    try:
        resp = requests.post(
            "https://sc-ice-storm-news.vercel.app/api/summary",
            json={"articles": articles},
            timeout=45
        )
        ai_summary = resp.json()
        print("AI summary received")
    except Exception as e:
        print(f"AI summary failed: {e}")

    # Setup PDF
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=HexColor('#FFFFFF'),
        spaceAfter=6,
        fontName='Helvetica-Bold'
    )

    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=HexColor('#FFFFFF'),
        spaceAfter=4
    )

    section_style = ParagraphStyle(
        'Section',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=HexColor('#C62828'),
        spaceBefore=16,
        spaceAfter=8,
        fontName='Helvetica-Bold'
    )

    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontSize=10,
        textColor=HexColor('#333333'),
        spaceAfter=6,
        leading=14
    )

    bullet_style = ParagraphStyle(
        'Bullet',
        parent=styles['Normal'],
        fontSize=9,
        textColor=HexColor('#333333'),
        leftIndent=15,
        spaceAfter=4
    )

    source_style = ParagraphStyle(
        'Source',
        parent=styles['Normal'],
        fontSize=8,
        textColor=HexColor('#C62828'),
        fontName='Helvetica-Bold',
        spaceAfter=2
    )

    headline_style = ParagraphStyle(
        'Headline',
        parent=styles['Normal'],
        fontSize=11,
        textColor=HexColor('#333333'),
        fontName='Helvetica-Bold',
        spaceAfter=3
    )

    meta_style = ParagraphStyle(
        'Meta',
        parent=styles['Normal'],
        fontSize=8,
        textColor=HexColor('#999999'),
        spaceAfter=10
    )

    story = []
    now = datetime.now()
    date_str = now.strftime("%A, %B %d, %Y")

    # Header table (red background)
    header_data = [[
        Paragraph("South Carolina Ice Storm", title_style),
    ], [
        Paragraph("DR 153-26 | Disaster Operations Briefing", subtitle_style),
    ], [
        Paragraph(f"Prepared By: Gary Pelletier | {date_str}", subtitle_style),
    ]]

    header_table = Table(header_data, colWidths=[7*inch])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor('#D32F2F')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 16))

    # Stats
    sources = {}
    for a in articles:
        sources[a.get('source', 'Unknown')] = sources.get(a.get('source', 'Unknown'), 0) + 1

    stats_text = f"<b>{len(articles)}</b> News Articles | <b>{len(sources)}</b> Sources | Report Generated: {now.strftime('%I:%M %p')}"
    stats_style = ParagraphStyle('Stats', parent=body_style, fontSize=10, textColor=HexColor('#C62828'), alignment=TA_CENTER)
    story.append(Paragraph(stats_text, stats_style))
    story.append(Spacer(1, 16))

    # Executive Summary
    story.append(Paragraph("EXECUTIVE SUMMARY", section_style))
    exec_summary = ai_summary.get('executive_summary', f'This report compiles {len(articles)} news articles from South Carolina media sources.') if ai_summary else f'This report compiles {len(articles)} news articles from South Carolina media sources covering the current ice storm.'
    story.append(Paragraph(exec_summary, body_style))
    story.append(Spacer(1, 8))

    # Key Impacts
    if ai_summary and ai_summary.get('key_impacts'):
        story.append(Paragraph("KEY IMPACTS FROM NEWS COVERAGE", section_style))

        categories = [
            ('Power & Utilities', 'power_outages'),
            ('Road Conditions', 'road_conditions'),
            ('Schools & Closures', 'schools_closures'),
            ('Shelters & Warming Centers', 'shelters_warming'),
            ('Emergency Response', 'emergency_response'),
        ]

        for cat_name, cat_key in categories:
            items = ai_summary['key_impacts'].get(cat_key, [])
            if items and items != ['See news coverage below']:
                story.append(Paragraph(f"<b>{cat_name.upper()}</b>", ParagraphStyle('Cat', parent=body_style, fontSize=9, textColor=HexColor('#C62828'))))
                for item in items[:3]:
                    story.append(Paragraph(f"- {item}", bullet_style))

        story.append(Spacer(1, 8))

    # Critical Numbers (only if AI returned specific numbers)
    if ai_summary and ai_summary.get('critical_numbers'):
        nums = ai_summary['critical_numbers']
        # Only show if we have actual numbers, not "See coverage"
        has_real_numbers = any(v and v != 'See coverage' and 'see' not in v.lower() for v in nums.values())
        if has_real_numbers:
            story.append(Paragraph("REPORTED NUMBERS", section_style))
            for key, val in nums.items():
                if val and val != 'See coverage' and 'see' not in val.lower():
                    label = key.replace('_', ' ').title()
                    story.append(Paragraph(f"<b>{label}:</b> {val}", bullet_style))
            story.append(Spacer(1, 8))

    # Resources (only if AI found actual resources)
    if ai_summary and ai_summary.get('resources_mentioned'):
        resources = ai_summary['resources_mentioned']
        real_resources = [r for r in resources if r and 'see' not in r.lower()]
        if real_resources:
            story.append(Paragraph("RESOURCES & CONTACTS", section_style))
            for r in real_resources[:5]:
                story.append(Paragraph(f"- {r}", bullet_style))
            story.append(Spacer(1, 8))

    # Time filters - 36 hours for regular, 7 days for Red Cross
    from datetime import timedelta
    cutoff_36h = now - timedelta(hours=36)
    cutoff_7d = now - timedelta(days=7)

    def parse_date(pub):
        """Try to parse article date, return None if unparseable."""
        if not pub:
            return None
        for fmt in ['%a, %d %b %Y %H:%M:%S', '%a, %d %b %Y %H:%M:%S %z', '%Y-%m-%dT%H:%M:%S']:
            try:
                return datetime.strptime(pub[:25].strip(), fmt)
            except:
                continue
        return None

    def is_within_36h(article):
        pub_date = parse_date(article.get('published', ''))
        if pub_date:
            return pub_date >= cutoff_36h
        # Fallback: check for Jan 2026 in string (recent dates only)
        pub = article.get('published', '')
        return '2026' in pub and 'Jan' in pub and any(d in pub for d in ['25', '26', '27'])

    def is_within_7d(article):
        pub_date = parse_date(article.get('published', ''))
        if pub_date:
            return pub_date >= cutoff_7d
        # Fallback: check for Jan 2026 in string
        pub = article.get('published', '')
        return '2026' in pub and 'Jan' in pub

    # Separate and filter articles
    red_cross_articles = []
    other_articles = []
    for a in articles:
        text = (a.get('title', '') + ' ' + a.get('summary', '')).lower()
        is_rc = 'red cross' in text

        if is_rc:
            # Red Cross: 7 day max
            if is_within_7d(a):
                red_cross_articles.append(a)
        else:
            # Regular: 36 hour max
            if is_within_36h(a):
                other_articles.append(a)

    # Sort both lists newest to oldest
    def get_sort_date(article):
        pub_date = parse_date(article.get('published', ''))
        return pub_date if pub_date else datetime.min

    red_cross_articles.sort(key=get_sort_date, reverse=True)
    other_articles.sort(key=get_sort_date, reverse=True)

    # Red Cross Section (if any)
    if red_cross_articles:
        rc_section_style = ParagraphStyle('RCSection', parent=section_style, textColor=HexColor('#FFFFFF'))
        rc_header = Table([[Paragraph("RED CROSS MENTIONS", rc_section_style)]], colWidths=[7*inch])
        rc_header.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), HexColor('#C62828')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(rc_header)
        story.append(Spacer(1, 8))

        for article in red_cross_articles[:10]:
            story.append(Paragraph(article.get('source', 'Unknown').upper(), source_style))
            # Highlight "Red Cross" in title
            title = article.get('title', 'No title')
            title_highlighted = title.replace('Red Cross', '<font color="#C62828"><b>Red Cross</b></font>')
            title_highlighted = title_highlighted.replace('red cross', '<font color="#C62828"><b>Red Cross</b></font>')
            story.append(Paragraph(title_highlighted, headline_style))
            if article.get('summary'):
                summary_text = article['summary'][:200]
                summary_highlighted = summary_text.replace('Red Cross', '<font color="#C62828"><b>Red Cross</b></font>')
                summary_highlighted = summary_highlighted.replace('red cross', '<font color="#C62828"><b>Red Cross</b></font>')
                story.append(Paragraph(summary_highlighted, ParagraphStyle('Summary', parent=body_style, fontSize=9, textColor=HexColor('#666666'))))
            pub_date = article.get('published', '')[:25] if article.get('published') else ''
            if pub_date:
                story.append(Paragraph(pub_date, meta_style))
            else:
                story.append(Spacer(1, 8))

        story.append(Spacer(1, 12))

    # Other News Articles
    story.append(Paragraph("NEWS ARTICLE DETAILS", section_style))
    story.append(Paragraph("(All content from South Carolina news sources within past 48 hours)", meta_style))

    for article in other_articles[:15]:  # Limit to 15 for PDF
        story.append(Paragraph(article.get('source', 'Unknown').upper(), source_style))
        story.append(Paragraph(article.get('title', 'No title'), headline_style))
        if article.get('summary'):
            summary_text = article['summary'][:200]
            story.append(Paragraph(summary_text, ParagraphStyle('Summary', parent=body_style, fontSize=9, textColor=HexColor('#666666'))))
        pub_date = article.get('published', '')[:25] if article.get('published') else ''
        if pub_date:
            story.append(Paragraph(pub_date, meta_style))
        else:
            story.append(Spacer(1, 8))

    # Footer
    story.append(Spacer(1, 20))
    footer_style = ParagraphStyle('Footer', parent=body_style, fontSize=8, textColor=HexColor('#999999'), alignment=TA_CENTER)
    story.append(Paragraph(f"American Red Cross | DR 153-26 | Generated {now.strftime('%Y-%m-%d %H:%M')}", footer_style))

    # Build PDF
    doc.build(story)
    print(f"PDF saved to: {output_path}")

if __name__ == "__main__":
    output = "/Users/jefffranzen/Desktop/SC-DR153-26-News-Summary.pdf"
    generate_pdf(output)
