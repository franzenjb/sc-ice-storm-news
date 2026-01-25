#!/bin/bash
# SC Ice Storm News Crawler - Runner Script
# Called by n8n or cron for scheduled execution

cd "$(dirname "$0")"
source venv/bin/activate
python news_crawler.py

# Return the path to the generated files
echo "HTML: $(pwd)/news_report.html"
echo "JSON: $(pwd)/news_data.json"
