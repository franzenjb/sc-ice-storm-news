# SC Ice Storm News App — Deployment & Operations Guide

## URLs
- **Live site:** https://sc-ice-storm-news.vercel.app
- **PDF export:** https://sc-ice-storm-news.vercel.app/api/pdf
- **Raw API:** https://sc-ice-storm-news.vercel.app/api/crawl
- **GitHub:** https://github.com/franzenjb/sc-ice-storm-news
- **Vercel plan:** Pro (supports crons every 3 hours)

---

## How It Works

1. **index.html** — Static page that dynamically fetches `/api/crawl` on load
2. **api/crawl.py** — Serverless function that crawls Google News RSS + 15 local SC TV station feeds, filters for winter storm relevance, returns JSON
3. **api/pdf.py** — Serverless function that serves an HTML page which fetches crawl data and generates a branded PDF client-side using jsPDF
4. **api/summary.py** — Optional AI summary endpoint using Claude API
5. **Vercel cron** — Hits `/api/crawl` every 3 hours to keep cache warm
6. **Cache** — API responses cached 3 hours (`s-maxage=10800`)

---

## Updating the PDF in the PDF Viewer (Separate App)

**PDF Viewer repo:** `/Users/jefffranzen/pdf-viewer/`
**PDF Viewer URL:** https://pdf-viewer-one-phi.vercel.app

### Steps to update the PDF:
1. Copy new PDF into the repo (use hyphens, no spaces in filename):
   ```bash
   cp "/path/to/new-file.pdf" /Users/jefffranzen/pdf-viewer/NewFileName.pdf
   ```
2. Edit `index.html` line ~128 — change the filename in the `pdfUrl` variable:
   ```javascript
   const pdfUrl = urlParams.get('pdf') || './NewFileName.pdf';
   ```
3. Commit and push (auto-deploys to Vercel):
   ```bash
   cd /Users/jefffranzen/pdf-viewer
   git add -A && git commit -m "Update PDF to NewFileName" && git push
   ```
4. Verify: open https://pdf-viewer-one-phi.vercel.app in browser

### Alternative: Use query parameter (no code change needed)
Embed with a specific PDF by adding `?pdf=filename.pdf` to the URL:
```
https://pdf-viewer-one-phi.vercel.app?pdf=NewFileName.pdf
```

---

## Embedding in Experience Builder

### News App
- Embed URL: `https://sc-ice-storm-news.vercel.app`
- Use the **Embed** widget in EB
- Articles load dynamically — always fresh
- "Export PDF" button opens PDF generator in new tab (works when accessed directly; EB sandbox may block it inside the iframe)

### PDF Viewer
- Embed URL: `https://pdf-viewer-one-phi.vercel.app`
- Or with specific PDF: `https://pdf-viewer-one-phi.vercel.app?pdf=SitRep2_WinterWeather_2-1-26.pdf`

### Cache Busting
If EB shows stale content, delete the embed widget and re-add it with the URL. Adding `?v=N` sometimes helps but EB caches aggressively.

---

## Modifying News Filters

Edit `/Users/jefffranzen/sc-ice-storm-news/api/crawl.py`:

- **Search terms:** `SEARCH_TERMS` list (~line 35)
- **Exclude terms:** `exclude_terms` in `is_relevant()` — blocks sports, crime, obits, etc.
- **Weather keywords:** `weather_match` terms in `is_relevant()` — must match along with a SC location
- **Local RSS feeds:** `local_feeds` list — add/remove TV stations
- **Time window:** `is_recent_enough()` — 48h for general news, 7 days for Red Cross mentions

After editing:
```bash
cd /Users/jefffranzen/sc-ice-storm-news
git add -A && git commit -m "Update filters" && git push
npx vercel --prod --yes
```

---

## Modifying PDF Design

Edit `/Users/jefffranzen/sc-ice-storm-news/api/pdf.py`:

- All PDF generation is JavaScript inside the `HTML` string
- Uses jsPDF library (loaded from CDN)
- Article titles are clickable blue links (`doc.textWithLink()`)
- Categories: Power & Utilities, Road Conditions, Schools & Closures, Shelters & Emergency
- "Other Coverage" capped at 10 articles

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Page shows old content | Delete EB widget, re-add with fresh URL |
| Deploys not working | Run `npx vercel --prod --yes` manually |
| Too many irrelevant articles | Add terms to `exclude_terms` in crawl.py |
| PDF links not clickable | Check `doc.textWithLink()` in pdf.py |
| Cron not running | Check Vercel dashboard > Crons tab |
| API returning 0 articles | Google News may be rate-limiting; wait and retry |
