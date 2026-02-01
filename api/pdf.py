"""
Vercel Serverless Function - PDF Generator Page
Endpoint: /api/pdf
Returns an HTML page that fetches news and generates a PDF client-side.
Runs as a top-level page (not in iframe) so downloads work.
"""

from http.server import BaseHTTPRequestHandler

HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Generating PDF...</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
<style>
body { font-family: -apple-system, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #f5f5f5; }
.box { text-align: center; background: white; padding: 40px 60px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.spinner { width: 40px; height: 40px; border: 4px solid #ffcdd2; border-top: 4px solid #c62828; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 16px; }
@keyframes spin { to { transform: rotate(360deg); } }
h2 { color: #c62828; margin-bottom: 8px; }
p { color: #666; }
</style>
</head>
<body>
<div class="box">
<div class="spinner" id="spinner"></div>
<h2 id="status">Generating PDF...</h2>
<p id="detail">Fetching latest news data</p>
</div>
<script>
async function go() {
    try {
        document.getElementById('detail').textContent = 'Fetching latest news data...';
        var resp = await fetch('/api/crawl');
        if (!resp.ok) throw new Error('API returned ' + resp.status);
        var data = await resp.json();
        var articles = data.articles || [];
        var meta = data.metadata || {};
        var crawledAt = meta.crawled_at ? new Date(meta.crawled_at) : new Date();

        document.getElementById('detail').textContent = 'Building PDF with ' + articles.length + ' articles...';

        var sourceCounts = {};
        articles.forEach(function(a) { sourceCounts[a.source] = (sourceCounts[a.source] || 0) + 1; });

        var jsPDF = window.jspdf.jsPDF;
        var doc = new jsPDF('p', 'pt', 'letter');
        var pageW = doc.internal.pageSize.getWidth();
        var pageH = doc.internal.pageSize.getHeight();
        var margin = 50;
        var usable = pageW - margin * 2;
        var y = 0;

        doc.setFillColor(211, 47, 47);
        doc.rect(0, 0, pageW, 80, 'F');
        doc.setTextColor(255, 255, 255);
        doc.setFontSize(22);
        doc.setFont('helvetica', 'bold');
        doc.text('SC DR 153-26 | News Summary', margin, 35);
        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');
        doc.text('American Red Cross | Disaster Operations', margin, 52);
        var ts = crawledAt.toLocaleString('en-US', { month: 'long', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
        doc.text('Generated: ' + ts, margin, 67);
        y = 100;

        doc.setTextColor(198, 40, 40);
        doc.setFontSize(28);
        doc.setFont('helvetica', 'bold');
        doc.text(String(articles.length), margin, y);
        doc.setFontSize(9);
        doc.setTextColor(100, 100, 100);
        doc.setFont('helvetica', 'normal');
        doc.text('ARTICLES', margin, y + 12);
        doc.setTextColor(198, 40, 40);
        doc.setFontSize(28);
        doc.setFont('helvetica', 'bold');
        doc.text(String(Object.keys(sourceCounts).length), margin + 120, y);
        doc.setFontSize(9);
        doc.setTextColor(100, 100, 100);
        doc.setFont('helvetica', 'normal');
        doc.text('SOURCES', margin + 120, y + 12);
        y += 35;
        doc.setDrawColor(224, 224, 224);
        doc.line(margin, y, pageW - margin, y);
        y += 20;

        var categories = {
            'POWER & UTILITIES': ['power', 'outage', 'electric', 'duke energy', 'dominion', 'grid', 'restore'],
            'ROAD CONDITIONS': ['road', 'highway', 'crash', 'driving', 'travel', 'dot', 'bridge'],
            'SCHOOLS & CLOSURES': ['school', 'class', 'university', 'college', 'e-learning', 'closure', 'cancel'],
            'SHELTERS & EMERGENCY': ['shelter', 'warming', 'hotline', 'emergency', 'red cross', 'guard']
        };
        var categorized = {};
        var uncategorized = [];
        articles.forEach(function(a) {
            var text = (a.title + ' ' + (a.summary || '')).toLowerCase();
            var placed = false;
            Object.keys(categories).forEach(function(cat) {
                categories[cat].forEach(function(kw) {
                    if (!placed && text.indexOf(kw) >= 0) {
                        if (!categorized[cat]) categorized[cat] = [];
                        categorized[cat].push(a);
                        placed = true;
                    }
                });
            });
            if (!placed) uncategorized.push(a);
        });

        function addArticles(title, items) {
            if (items.length === 0) return;
            if (y > pageH - 100) { doc.addPage(); y = 50; }
            doc.setFillColor(198, 40, 40);
            doc.rect(margin, y - 12, usable, 18, 'F');
            doc.setTextColor(255, 255, 255);
            doc.setFontSize(10);
            doc.setFont('helvetica', 'bold');
            doc.text(title + ' (' + items.length + ')', margin + 6, y);
            y += 16;
            items.forEach(function(a) {
                if (y > pageH - 60) { doc.addPage(); y = 50; }
                doc.setTextColor(51, 51, 51);
                doc.setFontSize(10);
                doc.setFont('helvetica', 'bold');
                var lines = doc.splitTextToSize(a.title, usable - 10);
                doc.text(lines, margin + 5, y);
                y += lines.length * 13;
                doc.setTextColor(150, 150, 150);
                doc.setFontSize(8);
                doc.setFont('helvetica', 'normal');
                doc.text(a.source + (a.published ? '  |  ' + a.published.substring(0, 25) : ''), margin + 5, y);
                y += 8;
                if (a.summary) {
                    doc.setTextColor(100, 100, 100);
                    doc.setFontSize(9);
                    var sLines = doc.splitTextToSize(a.summary.substring(0, 150), usable - 10);
                    doc.text(sLines, margin + 5, y);
                    y += sLines.length * 11;
                }
                y += 8;
            });
            y += 6;
        }

        Object.keys(categories).forEach(function(cat) { addArticles(cat, categorized[cat] || []); });
        if (uncategorized.length > 0) addArticles('OTHER COVERAGE', uncategorized);

        var totalPages = doc.internal.getNumberOfPages();
        for (var i = 1; i <= totalPages; i++) {
            doc.setPage(i);
            doc.setFontSize(8);
            doc.setTextColor(170, 170, 170);
            doc.text('American Red Cross | DR 153-26 News Summary | Page ' + i + ' of ' + totalPages, margin, pageH - 20);
        }

        var dateStr = new Date().toISOString().slice(0, 10);
        doc.save('SC-DR153-26-News-Summary-' + dateStr + '.pdf');

        document.getElementById('spinner').style.display = 'none';
        document.getElementById('status').textContent = 'PDF Downloaded!';
        document.getElementById('detail').textContent = articles.length + ' articles included. You can close this tab.';
    } catch (e) {
        document.getElementById('spinner').style.display = 'none';
        document.getElementById('status').textContent = 'Error';
        document.getElementById('detail').textContent = e.message;
    }
}
go();
</script>
</body>
</html>"""


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(HTML.encode())
