import threading
import time
import json
import urllib.parse
import urllib.request
import feedparser
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template_string, request, Response

app = Flask(__name__, static_folder='static')

NEWS_SOURCES = [
    {"name": "TRT ئۇيغۇرچە", "url": "https://www.trtuyghur.com/rss"},
    {"name": "ئانادولۇ ئاگېنتلىقى", "url": "https://www.aa.com.tr/tr/rss/default?cat=guncel"},
    {"name": "مېپا خەۋەرلىرى", "url": "https://www.mepanews.com/rss"},
    {"name": "فوكۇس پلۇس", "url": "https://www.fokusplus.com/rss"},
    {"name": "سېتا (SETA)", "url": "https://www.setav.org/feed/"}
]

ANALYSIS_SOURCES = [
    {"name": "ISW ئانالىز مەركىزى", "url": "https://www.understandingwar.org/rss.xml"},
    {"name": "فوكۇس ئوداك", "url": "https://www.fokusplus.com/rss"}
]

TRANSLATION_CACHE = {}
ALL_NEWS = []
ALL_ANALYSIS = []

def raw_google_call(text, sl, tl):
    try:
        encoded = urllib.parse.quote(text)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={sl}&tl={tl}&dt=t&q={encoded}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            res = response.read().decode('utf-8')
            data = json.loads(res)
            return "".join([part[0] for part in data[0] if part[0]])
    except Exception:
        return ""

def translate_to_uyghur(text):
    if not text or not text.strip():
        return ""
    clean = text.strip()
    if clean in TRANSLATION_CACHE:
        return TRANSLATION_CACHE[clean]

    result = raw_google_call(clean[:400], "auto", "ug")
    if not result or result == clean:
        en = raw_google_call(clean[:400], "auto", "en")
        if en:
            result = raw_google_call(en, "en", "ug")

    if result:
        TRANSLATION_CACHE[clean] = result
        return result
    return clean

def classify(text):
    t = text.lower()
    if any(w in t for w in ["ئوتتۇرا شەرق", "غەززە", "ئىسرائىلىيە", "ئىران", "سۈرىيە", "يەمەن", "middle east", "israel", "iran", "syria", "orta doğu"]):
        return "ئوتتۇرا شەرق"
    elif any(w in t for w in ["ئوتتۇرا ئاسىيا", "قازاقىستان", "ئۆزبېكىستان", "قىرغىزىستان", "central asia", "kazakhstan", "orta asya"]):
        return "ئوتتۇرا ئاسىيا"
    elif any(w in t for w in ["خىتاي", "بېيجىڭ", "پېكىن", "china", "chinese", "beijing", "çin"]):
        return "خىتاي"
    elif any(w in t for w in ["شەرقىي تۈركىستان", "ئۇيغۇر", "شىنجاڭ", "uyghur", "east turkestan", "doğu türkistan"]):
        return "شەرقىي تۈركىستان"
    elif any(w in t for w in ["بۇغۇز", "ھورمۇز", "تەيۋەن", "مالاككا", "strait", "hormuz", "taiwan", "malacca"]):
        return "بۇغۇزلار"
    return "ئومۇمىي خەۋەرلەر"

def fetch_feed(sources):
    items = []
    for s in sources:
        try:
            feed = feedparser.parse(s["url"])
            for entry in feed.entries[:5]:
                img_url = ""
                if "media_content" in entry and len(entry.media_content) > 0:
                    img_url = entry.media_content[0].get("url", "")
                elif "enclosures" in entry and len(entry.enclosures) > 0:
                    img_url = entry.enclosures[0].get("href", "")

                raw_title = getattr(entry, "title", "")
                raw_desc = getattr(entry, "summary", "")

                if "ئۇيغۇرچە" not in s["name"]:
                    tr_title = translate_to_uyghur(raw_title)
                    tr_desc = translate_to_uyghur(raw_desc[:250])
                    time.sleep(0.1)
                else:
                    tr_title = raw_title
                    tr_desc = raw_desc[:250]

                items.append({
                    "id": abs(hash(getattr(entry, "link", raw_title))),
                    "source": s["name"],
                    "title": tr_title,
                    "desc": tr_desc,
                    "category": classify(raw_title + " " + tr_title),
                    "image": img_url,
                    "link": getattr(entry, "link", "")
                })
        except Exception as e:
            print("RSS خاتالىقى:", e)
    return items

def update_loop():
    global ALL_NEWS, ALL_ANALYSIS
    while True:
        ALL_NEWS = fetch_feed(NEWS_SOURCES)
        ALL_ANALYSIS = fetch_feed(ANALYSIS_SOURCES)
        time.sleep(300)

threading.Thread(target=update_loop, daemon=True).start()

@app.route('/manifest.json')
def manifest():
    manifest_data = {
        "name": "ئۇيغۇرچە خەۋەر ۋە تەھلىل",
        "short_name": "خەۋەرلەر",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0F172A",
        "theme_color": "#1E293B",
        "orientation": "portrait"
    }
    return Response(json.dumps(manifest_data, ensure_ascii=False), mimetype='application/json')

@app.route("/api/data")
def get_data():
    return jsonify({"news": ALL_NEWS, "analyses": ALL_ANALYSIS})

@app.route("/api/article")
def get_article():
    link = request.args.get("link", "")
    src = request.args.get("source", "")
    if not link:
        return jsonify({"content": "ئۇلانما تېپىلمىدى."})
    try:
        req = urllib.request.Request(link, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as r:
            html = r.read()
        soup = BeautifulSoup(html, "html.parser")
        for s in soup(["script", "style", "nav", "header", "footer", "aside"]):
            s.decompose()
        pars = [p.get_text().strip() for p in soup.find_all("p") if len(p.get_text().strip()) > 30]
        
        translated = []
        is_uy = "ئۇيغۇرچە" in src
        for p in pars[:12]:
            translated.append(p if is_uy else translate_to_uyghur(p))
            if not is_uy: time.sleep(0.1)
        return jsonify({"content": "\n\n".join(translated)})
    except Exception as e:
        return jsonify({"content": f"مەزمۇننى تارتىشتا مەسىلە كۆرۈلدى: {e}"})

@app.route("/")
def index():
    html = """
    <!DOCTYPE html>
    <html lang="ug" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>دۇنيا خەۋەرلىرى ۋە ئانالىز</title>
        <link rel="manifest" href="/manifest.json">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
        <style>
            @font-face {
                font-family: 'UKIJ Ekran';
                src: local('UKIJ Ekran');
            }
            :root {
                --bg: #F8FAFC;
                --card-bg: #FFFFFF;
                --text: #0F172A;
                --text-muted: #64748B;
                --border: #E2E8F0;
                --primary: #2563EB;
                --primary-soft: #EFF6FF;
                --badge-bg: #F1F5F9;
                --shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.05);
            }
            [data-theme="dark"] {
                --bg: #090D16;
                --card-bg: #131B2E;
                --text: #F1F5F9;
                --text-muted: #94A3B8;
                --border: #1E293B;
                --primary: #3B82F6;
                --primary-soft: #1E293B;
                --badge-bg: #1E293B;
                --shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.3);
            }
            * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'UKIJ Ekran', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; transition: background-color 0.25s ease, color 0.25s ease; }
            body { background: var(--bg); color: var(--text); padding-bottom: 85px; -webkit-tap-highlight-color: transparent; }
            
            /* ئۈستۈنكى بۆلەك */
            header {
                position: sticky; top: 0; background: var(--card-bg);
                padding: 12px 16px; border-bottom: 1px solid var(--border);
                z-index: 20; box-shadow: var(--shadow);
                display: flex; gap: 10px; align-items: center;
            }
            .search-box {
                flex: 1; padding: 10px 18px; border-radius: 25px;
                border: 1px solid var(--border); background: var(--bg);
                color: var(--text); font-size: 14px; outline: none;
            }
            .theme-toggle {
                background: var(--bg); border: 1px solid var(--border);
                border-radius: 50%; width: 40px; height: 40px;
                display: flex; align-items: center; justify-content: center;
                cursor: pointer; font-size: 18px;
            }

            .container { padding: 16px; max-width: 600px; margin: 0 auto; }

            /* كاتېگورىيە كارتىلىرى */
            .cat-grid { display: grid; grid-template-columns: 1fr; gap: 12px; margin-top: 6px; }
            .cat-card {
                background: var(--card-bg); border-radius: 16px;
                padding: 18px; border: 1px solid var(--border);
                box-shadow: var(--shadow); cursor: pointer;
                display: flex; align-items: center; justify-content: space-between;
            }
            .cat-card:active { transform: scale(0.98); }
            .cat-card h3 { font-size: 16px; color: var(--text); display: flex; align-items: center; gap: 10px; }
            .cat-card p { font-size: 12px; color: var(--text-muted); margin-top: 4px; }
            .cat-arrow { font-size: 18px; color: var(--primary); }

            /* خەۋەر كارتىلىرى */
            .news-card {
                background: var(--card-bg); border-radius: 18px;
                padding: 14px; margin-bottom: 14px; border: 1px solid var(--border);
                box-shadow: var(--shadow); overflow: hidden;
            }
            .news-card img {
                width: 100%; height: 180px; object-fit: cover;
                border-radius: 12px; margin-bottom: 12px; background: var(--border);
            }
            .title-box { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
            .news-card h4 {
                font-size: 16px; font-weight: bold; line-height: 1.5;
                color: var(--text); cursor: pointer; flex: 1;
            }
            .news-card p {
                font-size: 13px; color: var(--text-muted);
                margin: 8px 0; line-height: 1.6; cursor: pointer;
            }
            .meta-bar {
                display: flex; align-items: center; justify-content: space-between;
                margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border);
            }
            .badge-group { display: flex; gap: 6px; }
            .badge {
                font-size: 11px; padding: 4px 10px; border-radius: 20px;
                background: var(--badge-bg); color: var(--text-muted); font-weight: 500;
            }
            .badge.src { color: var(--primary); background: var(--primary-soft); font-weight: bold; }
            .star-btn {
                background: none; border: none; font-size: 22px;
                color: var(--border); cursor: pointer; padding: 4px;
            }
            .star-btn.fav { color: #EAB308; }

            /* تەپسىلات كۆزنىكى */
            #detail-view {
                display: none; background: var(--card-bg); min-height: 100vh;
                padding: 20px 16px; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
                z-index: 100; overflow-y: auto;
            }
            .back-btn {
                background: var(--primary-soft); color: var(--primary);
                border: none; padding: 8px 20px; border-radius: 20px;
                font-size: 14px; font-weight: bold; cursor: pointer; margin-bottom: 14px;
            }
            #detail-title { font-size: 20px; line-height: 1.5; color: var(--text); margin: 10px 0; }
            #detail-body { font-size: 16px; line-height: 2; color: var(--text); margin-top: 16px; white-space: pre-line; }

            /* ئاستىنقى يول باشلاش */
            nav {
                position: fixed; bottom: 0; left: 0; right: 0; height: 68px;
                background: var(--card-bg); border-top: 1px solid var(--border);
                display: flex; justify-content: space-around; align-items: center;
                z-index: 30; box-shadow: 0 -4px 15px rgba(0,0,0,0.04);
            }
            .nav-item {
                background: none; border: none; text-align: center;
                color: var(--text-muted); font-size: 11px; cursor: pointer;
                display: flex; flex-direction: column; align-items: center; gap: 3px;
            }
            .nav-item span { font-size: 20px; }
            .nav-item.active { color: var(--primary); font-weight: bold; }
        </style>
    </head>
    <body>
        <header>
            <input type="text" id="search" class="search-box" placeholder="🔍 ئىزدەش..." oninput="onSearch()">
            <button class="theme-toggle" onclick="toggleTheme()" id="theme-btn">🌙</button>
        </header>

        <div class="container" id="main-content">
            <div id="home-view">
                <div class="cat-grid">
                    <div class="cat-card" onclick="openCategory('ئوتتۇرا شەرق')">
                        <div><h3>🌍 ئوتتۇرا شەرق</h3><p>ئىسرائىلىيە، ئىران، سۈرىيە، غەززە تەھلىللىرى</p></div>
                        <div class="cat-arrow">←</div>
                    </div>
                    <div class="cat-card" onclick="openCategory('ئوتتۇرا ئاسىيا')">
                        <div><h3>🏔️ ئوتتۇرا ئاسىيا</h3><p>قازاقىستان، ئۆزبېكىستان ۋە قىرغىزىستان خەۋەرلىرى</p></div>
                        <div class="cat-arrow">←</div>
                    </div>
                    <div class="cat-card" onclick="openCategory('خىتاي')">
                        <div><h3>🌐 خىتاي سىياسىتى</h3><p>بېيجىڭ سىياسىتى ۋە ئىقتىسادىي ئۆزگىرىشلەر</p></div>
                        <div class="cat-arrow">←</div>
                    </div>
                    <div class="cat-card" onclick="openCategory('شەرقىي تۈركىستان')">
                        <div><h3>🌙 شەرقىي تۈركىستان</h3><p>ۋەتەن خەۋەرلىرى ۋە ئەڭ يېڭى ھادىسىلەر</p></div>
                        <div class="cat-arrow">←</div>
                    </div>
                    <div class="cat-card" onclick="openCategory('بۇغۇزلار')">
                        <div><h3>⚓ ئىستراتېگىيىلىك بۇغۇزلار</h3><p>ھورمۇز، مالاككا ۋە تەيۋەن بوغۇزى ۋەزىيىتى</p></div>
                        <div class="cat-arrow">←</div>
                    </div>
                </div>
            </div>
            <div id="list-view" style="display:none;"></div>
        </div>

        <div id="detail-view">
            <button class="back-btn" onclick="closeDetail()">← كەينىگە قايتىش</button>
            <img id="detail-img" style="width:100%; border-radius:14px; display:none; margin-bottom:12px;">
            <h2 id="detail-title"></h2>
            <div id="detail-meta" class="badge-group" style="margin-bottom:14px;"></div>
            <div id="detail-body"></div>
        </div>

        <nav>
            <button class="nav-item active" onclick="switchTab('home')"><span>🏠</span>باشبەت</button>
            <button class="nav-item" onclick="switchTab('news')"><span>📰</span>خەۋەرلەر</button>
            <button class="nav-item" onclick="switchTab('analysis')"><span>📊</span>ئانالىزلار</button>
            <button class="nav-item" onclick="switchTab('fav')"><span>⭐</span>ساقلانغان</button>
        </nav>

        <script>
            let newsData = [], analysisData = [], currentDisplay = [];
            let favorites = JSON.parse(localStorage.getItem('favs') || '[]');

            function toggleTheme() {
                let current = document.documentElement.getAttribute('data-theme');
                let next = current === 'dark' ? 'light' : 'dark';
                document.documentElement.setAttribute('data-theme', next);
                document.getElementById('theme-btn').innerText = next === 'dark' ? '☀️' : '🌙';
                localStorage.setItem('theme', next);
            }
            if(localStorage.getItem('theme') === 'dark') toggleTheme();

            async function loadData() {
                try {
                    let res = await fetch('/api/data');
                    let d = await res.json();
                    newsData = d.news; analysisData = d.analyses;
                    if(document.getElementById('list-view').style.display === 'block') {
                        renderList(currentDisplay);
                    }
                } catch(e){}
            }
            loadData();
            setInterval(loadData, 60000);

            function switchTab(tab) {
                document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
                event.currentTarget.classList.add('active');
                let h = document.getElementById('home-view');
                let l = document.getElementById('list-view');

                if(tab === 'home') {
                    h.style.display = 'block'; l.style.display = 'none';
                } else if(tab === 'news') {
                    h.style.display = 'none'; l.style.display = 'block';
                    currentDisplay = newsData; renderList(currentDisplay);
                } else if(tab === 'analysis') {
                    h.style.display = 'none'; l.style.display = 'block';
                    currentDisplay = analysisData; renderList(currentDisplay);
                } else if(tab === 'fav') {
                    h.style.display = 'none'; l.style.display = 'block';
                    currentDisplay = favorites; renderList(currentDisplay);
                }
            }

            function openCategory(cat) {
                document.getElementById('home-view').style.display = 'none';
                document.getElementById('list-view').style.display = 'block';
                let all = [...newsData, ...analysisData];
                currentDisplay = all.filter(i => (i.category||'').includes(cat));
                renderList(currentDisplay.length ? currentDisplay : all);
            }

            function renderList(items) {
                let l = document.getElementById('list-view');
                if(!items.length) {
                    l.innerHTML = "<div style='text-align:center; color:var(--text-muted); margin-top:50px; font-size:14px;'>⏳ مەزمۇنلار تەرجىمە قىلىنىپ رەتلىنىۋاتىدۇ، سەل كۈتۈڭ...</div>";
                    return;
                }
                l.innerHTML = items.map(item => {
                    let isFav = favorites.some(f => f.title === item.title);
                    return `
                    <div class="news-card">
                        ${item.image ? `<img src="${item.image}" loading="lazy">` : ''}
                        <div class="title-box">
                            <h4 onclick='openDetail(${JSON.stringify(item)})'>${item.title}</h4>
                            <button class="star-btn ${isFav?'fav':''}" onclick='toggleFav(${JSON.stringify(item)})'>${isFav?'★':'☆'}</button>
                        </div>
                        <p onclick='openDetail(${JSON.stringify(item)})'>${item.desc.substring(0, 110)}...</p>
                        <div class="meta-bar">
                            <div class="badge-group">
                                <span class="badge src">${item.source}</span>
                                <span class="badge">${item.category}</span>
                            </div>
                        </div>
                    </div>`;
                }).join('');
            }

            function toggleFav(item) {
                let idx = favorites.findIndex(f => f.title === item.title);
                if(idx > -1) favorites.splice(idx, 1);
                else favorites.push(item);
                localStorage.setItem('favs', JSON.stringify(favorites));
                renderList(currentDisplay);
            }

            async function openDetail(item) {
                let d = document.getElementById('detail-view');
                document.getElementById('detail-title').innerText = item.title;
                document.getElementById('detail-meta').innerHTML = `
                    <span class="badge src">${item.source}</span>
                    <span class="badge">${item.category}</span>
                `;
                let img = document.getElementById('detail-img');
                if(item.image) { img.src = item.image; img.style.display = 'block'; }
                else { img.style.display = 'none'; }
                
                document.getElementById('detail-body').innerText = "⏳ تولۇق تېكىست مەنبەدىن تارتىلىپ ئۇيغۇرچىغا تەرجىمە قىلىنماقتا...";
                d.style.display = 'block';

                let res = await fetch(`/api/article?link=${encodeURIComponent(item.link)}&source=${encodeURIComponent(item.source)}`);
                let data = await res.json();
                document.getElementById('detail-body').innerText = data.content;
            }

            function closeDetail() {
                document.getElementById('detail-view').style.display = 'none';
            }

            function onSearch() {
                let q = document.getElementById('search').value.toLowerCase();
                let filtered = currentDisplay.filter(i => i.title.toLowerCase().includes(q) || i.desc.toLowerCase().includes(q));
                renderList(filtered);
            }
        </script>
    </body>
    </html>
    """
    return render_template_string(html)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
