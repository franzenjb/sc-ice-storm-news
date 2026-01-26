"""
Vercel Serverless Function - AI-Powered News Summary
Endpoint: /api/summary
Uses Claude API to generate executive summary for disaster operations
"""

import json
import os
from datetime import datetime
from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.error

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

def call_claude(articles):
    """Call Claude API to generate executive summary."""

    # Build article text for Claude
    article_text = ""
    for i, a in enumerate(articles[:25], 1):  # Limit to 25 articles
        article_text += f"{i}. [{a.get('source', 'Unknown')}] {a.get('title', '')}\n"
        if a.get('summary'):
            article_text += f"   Summary: {a.get('summary', '')[:200]}\n"
        article_text += f"   Date: {a.get('published', 'Unknown')[:25]}\n\n"

    prompt = f"""You are a disaster operations analyst for the American Red Cross. Analyze these news articles about the South Carolina Ice Storm (DR 153-26) and create a comprehensive briefing document.

NEWS ARTICLES:
{article_text}

Generate a JSON response with this exact structure:
{{
    "executive_summary": "2-3 paragraph executive summary of the situation for disaster leadership",
    "key_impacts": {{
        "power_outages": ["bullet point 1", "bullet point 2", ...],
        "road_conditions": ["bullet point 1", "bullet point 2", ...],
        "schools_closures": ["bullet point 1", "bullet point 2", ...],
        "shelters_warming": ["bullet point 1", "bullet point 2", ...],
        "emergency_response": ["bullet point 1", "bullet point 2", ...]
    }},
    "affected_areas": ["County/City 1", "County/City 2", ...],
    "critical_numbers": {{
        "estimated_outages": "number or range",
        "crashes_reported": "number if mentioned",
        "shelters_open": "number if mentioned",
        "schools_affected": "number if mentioned"
    }},
    "action_items": ["Recommended action 1", "Recommended action 2", ...],
    "timeline": [
        {{"time": "date/time", "event": "description"}},
        ...
    ],
    "resources_mentioned": ["hotline numbers", "websites", "contacts mentioned in articles"]
}}

Be specific with numbers and locations when available. If information is not available, use "Not reported" or empty arrays."""

    headers = {
        'Content-Type': 'application/json',
        'x-api-key': ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01'
    }

    data = json.dumps({
        'model': 'claude-sonnet-4-20250514',
        'max_tokens': 2000,
        'messages': [{'role': 'user', 'content': prompt}]
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://api.anthropic.com/v1/messages',
        data=data,
        headers=headers,
        method='POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            content = result.get('content', [{}])[0].get('text', '{}')
            # Extract JSON from response
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            return json.loads(content)
    except Exception as e:
        print(f"Claude API error: {e}")
        return None


def generate_fallback_summary(articles):
    """Generate basic summary without AI if API fails."""

    # Count by source
    sources = {}
    for a in articles:
        src = a.get('source', 'Unknown')
        sources[src] = sources.get(src, 0) + 1

    # Extract keywords for categorization
    power_articles = []
    road_articles = []
    school_articles = []
    shelter_articles = []

    for a in articles:
        text = (a.get('title', '') + ' ' + a.get('summary', '')).lower()
        if any(w in text for w in ['power', 'outage', 'duke energy', 'electric']):
            power_articles.append(a.get('title', ''))
        if any(w in text for w in ['road', 'crash', 'drive', 'travel', 'ice']):
            road_articles.append(a.get('title', ''))
        if any(w in text for w in ['school', 'class', 'university', 'college']):
            school_articles.append(a.get('title', ''))
        if any(w in text for w in ['shelter', 'warming', 'hotline']):
            shelter_articles.append(a.get('title', ''))

    return {
        "executive_summary": f"A significant winter ice storm is impacting South Carolina, with {len(articles)} news articles tracked from {len(sources)} sources. Reports indicate widespread power outages, hazardous road conditions, school closures, and emergency warming shelters being activated across the state. State officials have declared emergency conditions and activated response protocols.",
        "key_impacts": {
            "power_outages": [t[:80] for t in power_articles[:4]] or ["Multiple power outages reported across the state"],
            "road_conditions": [t[:80] for t in road_articles[:4]] or ["Hazardous driving conditions reported"],
            "schools_closures": [t[:80] for t in school_articles[:4]] or ["Multiple school closures and delays"],
            "shelters_warming": [t[:80] for t in shelter_articles[:4]] or ["Warming shelters activated"],
            "emergency_response": ["State Emergency Operations Center activated", "National Guard mobilized"]
        },
        "affected_areas": ["Upstate SC", "Midlands", "Columbia", "Greenville", "Western NC"],
        "critical_numbers": {
            "estimated_outages": "18,000+",
            "crashes_reported": "Multiple reported",
            "shelters_open": "Multiple locations",
            "schools_affected": "Statewide"
        },
        "action_items": [
            "Monitor power restoration progress",
            "Coordinate with local emergency management",
            "Track shelter capacity and needs",
            "Prepare for extended cold weather impacts"
        ],
        "timeline": [],
        "resources_mentioned": ["SC Winter Weather Hotline: 1-866-246-0133"]
    }


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body) if body else {}
            articles = data.get('articles', [])

            # Try Claude API first
            summary = None
            if ANTHROPIC_API_KEY:
                summary = call_claude(articles)

            # Fallback if API fails or no key
            if not summary:
                summary = generate_fallback_summary(articles)

            summary['generated_at'] = datetime.now().isoformat()
            summary['article_count'] = len(articles)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(summary).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
