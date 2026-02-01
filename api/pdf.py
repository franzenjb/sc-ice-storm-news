"""
Vercel Serverless Function - PDF Generator Page
Endpoint: /api/pdf
"""

from http.server import BaseHTTPRequestHandler

HTML = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Generating PDF...</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
<style>
body{font-family:-apple-system,sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;background:#f5f5f5}
.box{text-align:center;background:white;padding:40px 60px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.1)}
.spinner{width:40px;height:40px;border:4px solid #ffcdd2;border-top:4px solid #c62828;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 16px}
@keyframes spin{to{transform:rotate(360deg)}}
h2{color:#c62828;margin-bottom:8px}p{color:#666}
</style>
</head>
<body>
<div class="box">
<div class="spinner" id="spinner"></div>
<h2 id="status">Generating PDF...</h2>
<p id="detail">Fetching latest news data</p>
</div>
<script>
function cl(s){return(s||'').replace(/&nbsp;/g,' ').replace(/\u00a0/g,' ').replace(/\s+/g,' ').trim();}

async function go(){
try{
document.getElementById('detail').textContent='Fetching latest news...';
var r=await fetch('/api/crawl');
if(!r.ok)throw new Error('API '+r.status);
var data=await r.json();
var articles=data.articles||[];
var meta=data.metadata||{};
var crawledAt=meta.crawled_at?new Date(meta.crawled_at):new Date();

document.getElementById('detail').textContent='Building PDF with '+articles.length+' articles...';

var sc={};
articles.forEach(function(a){sc[a.source]=(sc[a.source]||0)+1;});

var jsPDF=window.jspdf.jsPDF;
var doc=new jsPDF('p','pt','letter');
var W=doc.internal.pageSize.getWidth();
var H=doc.internal.pageSize.getHeight();
var M=50;
var U=W-M*2;
var y=0;

// Header
doc.setFillColor(198,40,40);
doc.rect(0,0,W,95,'F');
doc.setTextColor(255,255,255);
doc.setFontSize(26);doc.setFont('helvetica','bold');
doc.text('SC DR 153-26',M,35);
doc.setFontSize(14);doc.setFont('helvetica','normal');
doc.text('Winter Storm News Summary',M,54);
doc.setFontSize(10);
doc.text('American Red Cross | Disaster Operations',M,70);
doc.setFontSize(9);
var ts=crawledAt.toLocaleString('en-US',{month:'long',day:'numeric',year:'numeric',hour:'2-digit',minute:'2-digit'});
doc.text('Generated: '+ts,M,84);

y=115;

// Stats
doc.setTextColor(198,40,40);doc.setFontSize(32);doc.setFont('helvetica','bold');
doc.text(String(articles.length),M,y);
doc.setFontSize(9);doc.setTextColor(120,120,120);doc.setFont('helvetica','normal');
doc.text('ARTICLES',M,y+13);

doc.setTextColor(198,40,40);doc.setFontSize(32);doc.setFont('helvetica','bold');
doc.text(String(Object.keys(sc).length),M+130,y);
doc.setFontSize(9);doc.setTextColor(120,120,120);doc.setFont('helvetica','normal');
doc.text('SOURCES',M+130,y+13);

y+=40;
doc.setDrawColor(200,200,200);doc.line(M,y,W-M,y);
y+=20;

// Categories
var cats=[
['POWER & UTILITIES',['power','outage','electric','duke energy','dominion','grid','restore','without power','santee cooper']],
['ROAD CONDITIONS & TRAVEL',['road','highway','crash','driving','travel','bridge','icy road','hazardous','impassible','slide','wreck','flight','airport','dot','comet','bus service']],
['SCHOOLS & CLOSURES',['school','university','college','e-learning','elearning','closure','cancel','closed monday','schedule']],
['SHELTERS & EMERGENCY',['shelter','warming center','hotline','red cross','national guard','hypothermia','death','emergency']]
];

var catd={};var used={};
articles.forEach(function(a,i){
var t=(a.title+' '+(a.summary||'')).toLowerCase();
for(var c=0;c<cats.length;c++){
var kws=cats[c][1];
for(var k=0;k<kws.length;k++){
if(t.indexOf(kws[k])>=0&&!used[i]){
var cn=cats[c][0];
if(!catd[cn])catd[cn]=[];
catd[cn].push(a);
used[i]=true;break;
}}if(used[i])break;
}});
var other=articles.filter(function(_,i){return!used[i];});

function addCat(name,items){
if(!items||items.length===0)return;
if(y>H-90){doc.addPage();y=50;}
doc.setFillColor(198,40,40);
doc.roundedRect(M,y-13,U,20,3,3,'F');
doc.setTextColor(255,255,255);doc.setFontSize(10);doc.setFont('helvetica','bold');
doc.text(name+' ('+items.length+')',M+8,y+1);
y+=18;

items.forEach(function(a){
if(y>H-80){doc.addPage();y=50;}
var title=cl(a.title);
var url=a.url||'';
var src=cl(a.source);
var pub=cl(a.published||'');
if(pub.length>25)pub=pub.substring(0,25);
var sum=cl(a.summary||'');
if(sum.length>180)sum=sum.substring(0,180)+'...';

// Title as clickable link
doc.setTextColor(26,13,171);doc.setFontSize(11);doc.setFont('helvetica','bold');
var lines=doc.splitTextToSize(title,U-12);
lines.forEach(function(line){
if(y>H-40){doc.addPage();y=50;}
var tw=doc.getTextWidth(line);
doc.textWithLink(line,M+6,y,{url:url});
y+=14;
});

// Source and date
doc.setTextColor(150,150,150);doc.setFontSize(8);doc.setFont('helvetica','normal');
doc.text(src+(pub?' | '+pub:''),M+6,y);
y+=10;

// Summary
if(sum){
doc.setTextColor(100,100,100);doc.setFontSize(9);doc.setFont('helvetica','normal');
var sl=doc.splitTextToSize(sum,U-12);
sl.forEach(function(line){
if(y>H-40){doc.addPage();y=50;}
doc.text(line,M+6,y);
y+=11;
});
}
y+=10;
});
y+=8;
}

for(var c=0;c<cats.length;c++){addCat(cats[c][0],catd[cats[c][0]]);}
if(other.length>0){
var maxOther=other.slice(0,10);
addCat('OTHER COVERAGE',maxOther);
}

// Footer on every page
var tp=doc.internal.getNumberOfPages();
for(var p=1;p<=tp;p++){
doc.setPage(p);
doc.setDrawColor(198,40,40);doc.setLineWidth(0.5);
doc.line(M,H-32,W-M,H-32);
doc.setFontSize(8);doc.setTextColor(170,170,170);doc.setFont('helvetica','normal');
doc.text('American Red Cross | DR 153-26 News Summary | Page '+p+' of '+tp,M,H-20);
}

var ds=new Date().toISOString().slice(0,10);
doc.save('SC-DR153-26-News-Summary-'+ds+'.pdf');

document.getElementById('spinner').style.display='none';
document.getElementById('status').textContent='PDF Downloaded!';
document.getElementById('detail').textContent=articles.length+' articles. You can close this tab.';
}catch(e){
document.getElementById('spinner').style.display='none';
document.getElementById('status').textContent='Error';
document.getElementById('detail').textContent=e.message;
}}
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
