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

    prompt = f"""You are a disaster operations analyst for the American Red Cross. Analyze these news articles about the South Carolina Ice Storm (DR 153-26).

CRITICAL: Only include FACTUAL information explicitly stated in the articles below. DO NOT make up numbers, speculate, or include any information not directly from these sources. If data is not available, say "Not reported in coverage".

NEWS ARTICLES:
{article_text}

Generate a JSON response with this exact structure:
{{
    "executive_summary": "2-3 paragraph executive summary ONLY using facts from the articles above",
    "key_impacts": {{
        "power_outages": ["ONLY facts from articles about power"],
        "road_conditions": ["ONLY facts from articles about roads"],
        "schools_closures": ["ONLY facts from articles about schools"],
        "shelters_warming": ["ONLY facts from articles about shelters"],
        "emergency_response": ["ONLY facts from articles about emergency response"]
    }},
    "affected_areas": ["ONLY locations explicitly mentioned in articles"],
    "critical_numbers": {{
        "estimated_outages": "ONLY if specific number in articles, otherwise 'See coverage'",
        "crashes_reported": "ONLY if specific number in articles, otherwise 'See coverage'",
        "shelters_open": "ONLY if specific number in articles, otherwise 'See coverage'",
        "schools_affected": "ONLY if specific number in articles, otherwise 'See coverage'"
    }},
    "action_items": ["Practical actions based on article content"],
    "timeline": [
        {{"time": "date/time from article", "event": "what happened"}},
        ...
    ],
    "resources_mentioned": ["ONLY hotlines/contacts explicitly in articles"]
}}

IMPORTANT: Zero hallucination. Every fact must trace to an article above."""

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

    # Only include actual article headlines as impacts - no made up data
    return {
        "executive_summary": f"This report summarizes {len(articles)} news articles from {len(sources)} sources covering the South Carolina ice storm. See article headlines below for specific impacts reported by local media.",
        "key_impacts": {
            "power_outages": [t[:100] for t in power_articles[:4]] if power_articles else ["See news coverage below"],
            "road_conditions": [t[:100] for t in road_articles[:4]] if road_articles else ["See news coverage below"],
            "schools_closures": [t[:100] for t in school_articles[:4]] if school_articles else ["See news coverage below"],
            "shelters_warming": [t[:100] for t in shelter_articles[:4]] if shelter_articles else ["See news coverage below"],
            "emergency_response": ["See news coverage below for emergency response details"]
        },
        "affected_areas": ["See specific locations in articles below"],
        "critical_numbers": {
            "estimated_outages": "See coverage",
            "crashes_reported": "See coverage",
            "shelters_open": "See coverage",
            "schools_affected": "See coverage"
        },
        "action_items": [
            "Review article details below for current situation",
            "Check power company websites for outage updates",
            "Monitor local news for road conditions",
            "Contact local emergency management for shelter info"
        ],
        "timeline": [],
        "resources_mentioned": ["See articles for contact information"]
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
