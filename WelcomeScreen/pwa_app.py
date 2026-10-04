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
    {"name": "ISW تەتقىقات مەركىزى", "url": "https://www.understandingwar.org/rss.xml"},
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
    return "ئومۇمىي"

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
                    "link": getattr(entry, "link", ""),
                    "published": getattr(entry, "published", "يېڭى")[:16]
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
        "name": "NEXUS • خەۋەر & ئانالىز",
        "short_name": "NEXUS",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0B0F17",
        "theme_color": "#0B0F17",
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
        return jsonify({"content": f"تېكىستنى تارتىشتا كاشىلا كۆرۈلدى: {e}"})

@app.route("/")
def index():
    html = """
    <!DOCTYPE html>
    <html lang="ug" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
        <title>NEXUS • خەۋەر ۋە تەھلىل</title>
        <link rel="manifest" href="/manifest.json">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
        <style>
            @font-face {
                font-family: 'UKIJ Ekran';
                src: local('UKIJ Ekran');
            }
            :root {
                --bg: #0B0F17;
                --surface: rgba(22, 30, 46, 0.7);
                --surface-hover: rgba(30, 41, 59, 0.85);
                --border: rgba(255, 255, 255, 0.08);
                --accent: #38BDF8;
                --accent-gradient: linear-gradient(135deg, #38BDF8 0%, #6366F1 100%);
                --text-main: #F8FAFC;
                --text-sub: #94A3B8;
                --card-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
                --blur: blur(20px);
            }
            [data-theme="light"] {
                --bg: #F1F5F9;
                --surface: rgba(255, 255, 255, 0.85);
                --surface-hover: rgba(255, 255, 255, 0.95);
                --border: rgba(0, 0, 0, 0.08);
                --accent: #0284C7;
                --accent-gradient: linear-gradient(135deg, #0284C7 0%, #4F46E5 100%);
                --text-main: #0F172A;
                --text-sub: #64748B;
                --card-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.06);
            }

            * {
                box-sizing: border-box;
                margin: 0;
                padding: 0;
                font-family: 'UKIJ Ekran', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                -webkit-tap-highlight-color: transparent;
            }

            body {
                background: var(--bg);
                color: var(--text-main);
                padding-bottom: 95px;
                min-height: 100vh;
                transition: background 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }

            /* ئۈستۈنكى ئالىي بۆلەك */
            header {
                position: sticky;
                top: 0;
                background: var(--surface);
                backdrop-filter: var(--blur);
                -webkit-backdrop-filter: var(--blur);
                border-bottom: 1px solid var(--border);
                padding: 12px 18px;
                z-index: 50;
            }
            .header-top {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 12px;
            }
            .app-brand {
                font-size: 20px;
                font-weight: 900;
                letter-spacing: 0.5px;
                background: var(--accent-gradient);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            .brand-sub {
                font-size: 11px;
                color: var(--text-sub);
                font-weight: normal;
                margin-right: 6px;
            }
            .theme-pill {
                background: var(--surface-hover);
                border: 1px solid var(--border);
                padding: 6px 14px;
                border-radius: 20px;
                cursor: pointer;
                font-size: 13px;
                display: flex;
                align-items: center;
                gap: 6px;
                color: var(--text-main);
            }

            .search-bar {
                display: flex;
                align-items: center;
                background: var(--surface-hover);
                border: 1px solid var(--border);
                border-radius: 16px;
                padding: 0 14px;
            }
            .search-bar input {
                flex: 1;
                background: none;
                border: none;
                padding: 10px 0;
                font-size: 14px;
                color: var(--text-main);
                outline: none;
            }

            /* تۈر تاللاش سىيرىلما بەلبېغى (Pill Tabs) */
            .tabs-scroll {
                display: flex;
                gap: 8px;
                overflow-x: auto;
                padding: 14px 18px 6px;
                scrollbar-width: none;
            }
            .tabs-scroll::-webkit-scrollbar { display: none; }
            .pill-tab {
                white-space: nowrap;
                padding: 8px 18px;
                border-radius: 25px;
                background: var(--surface);
                border: 1px solid var(--border);
                color: var(--text-sub);
                font-size: 13px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.25s ease;
            }
            .pill-tab.active {
                background: var(--accent-gradient);
                color: #FFFFFF;
                border-color: transparent;
                box-shadow: 0 4px 15px rgba(56, 189, 248, 0.35);
                transform: translateY(-1px);
            }

            .container {
                padding: 12px 18px;
                max-width: 650px;
                margin: 0 auto;
            }

            /* چوڭ قىزىق نۇقتا كارتىسى (Hero / Spotlight Card) */
            .hero-card {
                position: relative;
                border-radius: 24px;
                overflow: hidden;
                margin-bottom: 20px;
                border: 1px solid var(--border);
                box-shadow: var(--card-shadow);
                cursor: pointer;
                background: var(--surface);
            }
            .hero-img {
                width: 100%;
                height: 230px;
                object-fit: cover;
                display: block;
            }
            .hero-overlay {
                position: absolute;
                inset: 0;
                background: linear-gradient(180deg, rgba(0,0,0,0.1) 20%, rgba(11,15,23,0.92) 100%);
                display: flex;
                flex-direction: column;
                justify-content: flex-end;
                padding: 20px;
            }
            .hero-tag {
                align-self: flex-start;
                background: var(--accent);
                color: #fff;
                font-size: 10px;
                font-weight: 800;
                padding: 4px 10px;
                border-radius: 8px;
                text-transform: uppercase;
                margin-bottom: 8px;
                letter-spacing: 0.5px;
            }
            .hero-title {
                color: #FFFFFF;
                font-size: 18px;
                font-weight: bold;
                line-height: 1.5;
            }

            /* ئۆلچەملىك خەۋەر كارتىسى */
            .bento-card {
                background: var(--surface);
                backdrop-filter: var(--blur);
                -webkit-backdrop-filter: var(--blur);
                border: 1px solid var(--border);
                border-radius: 20px;
                padding: 14px;
                margin-bottom: 14px;
                box-shadow: var(--card-shadow);
                display: flex;
                gap: 14px;
                cursor: pointer;
                transition: transform 0.2s ease, border-color 0.2s ease;
            }
            .bento-card:active {
                transform: scale(0.985);
            }
            .bento-thumb {
                width: 105px;
                height: 105px;
                border-radius: 14px;
                object-fit: cover;
                background: var(--surface-hover);
                flex-shrink: 0;
            }
            .bento-info {
                flex: 1;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
            }
            .bento-meta {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 6px;
            }
            .source-tag {
                font-size: 11px;
                font-weight: bold;
                color: var(--accent);
            }
            .cat-tag {
                font-size: 10px;
                background: var(--surface-hover);
                padding: 3px 8px;
                border-radius: 12px;
                color: var(--text-sub);
                border: 1px solid var(--border);
            }
            .bento-title {
                font-size: 14.5px;
                line-height: 1.45;
                font-weight: bold;
                color: var(--text-main);
                display: -webkit-box;
                -webkit-line-clamp: 2;
                -webkit-box-orient: vertical;
                overflow: hidden;
            }
            .bento-footer {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-top: 8px;
            }
            .time-txt {
                font-size: 11px;
                color: var(--text-sub);
            }
            .star-icon {
                font-size: 19px;
                color: var(--border);
                border: none;
                background: none;
                cursor: pointer;
            }
            .star-icon.active {
                color: #FBBF24;
            }

            /* تولۇق تېكىست ئوقۇش بېتى (Editorial Reader) */
            #detail-modal {
                display: none;
                position: fixed;
                inset: 0;
                background: var(--bg);
                z-index: 100;
                overflow-y: auto;
                padding-bottom: 60px;
            }
            .reader-header {
                position: sticky;
                top: 0;
                background: var(--surface);
                backdrop-filter: var(--blur);
                padding: 12px 18px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                border-bottom: 1px solid var(--border);
                z-index: 10;
            }
            .close-pill {
                background: var(--surface-hover);
                color: var(--text-main);
                border: 1px solid var(--border);
                padding: 6px 16px;
                border-radius: 20px;
                font-size: 13px;
                font-weight: bold;
                cursor: pointer;
            }
            .reader-content {
                max-width: 650px;
                margin: 0 auto;
                padding: 18px;
            }
            .reader-img {
                width: 100%;
                border-radius: 20px;
                margin-bottom: 16px;
                box-shadow: var(--card-shadow);
            }
            .reader-title {
                font-size: 21px;
                line-height: 1.5;
                font-weight: 900;
                color: var(--text-main);
                margin-bottom: 14px;
            }
            .reader-body {
                font-size: 16.5px;
                line-height: 2.1;
                color: var(--text-main);
                opacity: 0.92;
                white-space: pre-line;
            }

            /* يېڭى ئەۋلاد لەيلىمە كۆرۈنمە يول باشلاش تاختىسى (Floating Dock) */
            nav {
                position: fixed;
                bottom: 16px;
                left: 20px;
                right: 20px;
                max-width: 450px;
                margin: 0 auto;
                height: 64px;
                background: var(--surface);
                backdrop-filter: var(--blur);
                -webkit-backdrop-filter: var(--blur);
                border: 1px solid var(--border);
                border-radius: 35px;
                display: flex;
                justify-content: space-around;
                align-items: center;
                z-index: 60;
                box-shadow: 0 15px 35px rgba(0, 0, 0, 0.4);
            }
            .dock-btn {
                background: none;
                border: none;
                color: var(--text-sub);
                font-size: 11px;
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 3px;
                cursor: pointer;
                transition: color 0.2s ease, transform 0.2s ease;
            }
            .dock-btn span { font-size: 20px; }
            .dock-btn.active {
                color: var(--accent);
                font-weight: bold;
                transform: translateY(-2px);
            }
        </style>
    </head>
    <body>

        <!-- ئەپنىڭ ئۈستى باش قىسمى -->
        <header>
            <div class="header-top">
                <div>
                    <span class="app-brand">NEXUS</span>
                    <span class="brand-sub">تەھلىل ۋە خەۋەر</span>
                </div>
                <button class="theme-pill" onclick="toggleTheme()" id="theme-btn">
                    <span id="theme-icon">🌙</span> <span id="theme-text">كېچە</span>
                </button>
            </div>
            <div class="search-bar">
                <input type="text" id="search" placeholder="دۇنياۋى تېمىلارنى ئىزدىڭ..." oninput="onSearch()">
            </div>
        </header>

        <!-- يانتۇ سۈرۈلمە تۈر تۈگمىلىرى -->
        <div class="tabs-scroll" id="cat-tabs">
            <button class="pill-tab active" onclick="filterCategory('ھەممىسى')">بارلىق خەۋەرلەر</button>
            <button class="pill-tab" onclick="filterCategory('ئوتتۇرا شەرق')">🌍 ئوتتۇرا شەرق</button>
            <button class="pill-tab" onclick="filterCategory('شەرقىي تۈركىستان')">🌙 شەرقىي تۈركىستان</button>
            <button class="pill-tab" onclick="filterCategory('ئوتتۇرا ئاسىيا')">🏔️ ئوتتۇرا ئاسىيا</button>
            <button class="pill-tab" onclick="filterCategory('خىتاي')">🌐 خىتاي</button>
            <button class="pill-tab" onclick="filterCategory('بۇغۇزلار')">⚓ بۇغۇزلار</button>
        </div>

        <div class="container" id="feed-container">
            <div id="hero-area"></div>
            <div id="cards-list"></div>
        </div>

        <!-- ژۇرنال ئۇسلۇبىدىكى ئوقۇش كۆزنىكى -->
        <div id="detail-modal">
            <div class="reader-header">
                <button class="close-pill" onclick="closeDetail()">✕ تاقاش</button>
                <div id="reader-source" style="font-size:12px; font-weight:bold; color:var(--accent);"></div>
            </div>
            <div class="reader-content">
                <img id="reader-img" class="reader-img" style="display:none;">
                <h1 id="reader-title" class="reader-title"></h1>
                <div id="reader-body" class="reader-body"></div>
            </div>
        </div>

        <!-- لەيلىمە زامانىۋى نۇسخىدىكى يول باشلاش تاختىسى (Floating Dock) -->
        <nav>
            <button class="dock-btn active" onclick="switchMainTab('all')"><span>⚡</span>يېڭى</button>
            <button class="dock-btn" onclick="switchMainTab('analysis')"><span>📊</span>ئانالىز</button>
            <button class="dock-btn" onclick="switchMainTab('fav')"><span>⭐</span>ساقلانغان</button>
        </nav>

        <script>
            let newsData = [], analysisData = [], activeCategory = 'ھەممىسى', currentTab = 'all';
            let favorites = JSON.parse(localStorage.getItem('nexus_favs') || '[]');

            function toggleTheme() {
                let current = document.documentElement.getAttribute('data-theme');
                let next = current === 'light' ? 'dark' : 'light';
                document.documentElement.setAttribute('data-theme', next);
                document.getElementById('theme-icon').innerText = next === 'light' ? '☀️' : '🌙';
                document.getElementById('theme-text').innerText = next === 'light' ? 'كۈندۈز' : 'كېچە';
                localStorage.setItem('nexus_theme', next);
            }
            if(localStorage.getItem('nexus_theme') === 'light') toggleTheme();

            async function loadData() {
                try {
                    let res = await fetch('/api/data');
                    let d = await res.json();
                    newsData = d.news;
                    analysisData = d.analyses;
                    render();
                } catch(e){}
            }
            loadData();
            setInterval(loadData, 60000);

            function filterCategory(cat) {
                activeCategory = cat;
                document.querySelectorAll('.pill-tab').forEach(b => {
                    b.classList.toggle('active', b.innerText.includes(cat) || (cat==='ھەممىسى' && b.innerText==='بارلىق خەۋەرلەر'));
                });
                render();
            }

            function switchMainTab(tab) {
                currentTab = tab;
                document.querySelectorAll('.dock-btn').forEach(b => b.classList.remove('active'));
                event.currentTarget.classList.add('active');
                render();
            }

            function getActiveList() {
                let pool = [];
                if(currentTab === 'all') pool = newsData;
                else if(currentTab === 'analysis') pool = analysisData;
                else if(currentTab === 'fav') pool = favorites;

                if(activeCategory !== 'ھەممىسى') {
                    pool = pool.filter(i => (i.category || '').includes(activeCategory));
                }
                let q = document.getElementById('search').value.toLowerCase().trim();
                if(q) {
                    pool = pool.filter(i => i.title.toLowerCase().includes(q) || i.desc.toLowerCase().includes(q));
                }
                return pool;
            }

            function render() {
                let list = getActiveList();
                let heroArea = document.getElementById('hero-area');
                let listArea = document.getElementById('cards-list');

                if(!list.length) {
                    heroArea.innerHTML = '';
                    listArea.innerHTML = "<div style='text-align:center; padding:60px 0; color:var(--text-sub); font-size:14px;'>⏳ مەزمۇنلار تەرجىمە قىلىنماقتا...</div>";
                    return;
                }

                // قىزىق نۇقتا (Spotlight Card)
                let first = list[0];
                if(first && first.image && currentTab !== 'fav') {
                    heroArea.innerHTML = `
                    <div class="hero-card" onclick='openArticle(${JSON.stringify(first)})'>
                        <img class="hero-img" src="${first.image}" loading="lazy">
                        <div class="hero-overlay">
                            <span class="hero-tag">🔥 ئەڭ يېڭى فوكۇس</span>
                            <h2 class="hero-title">${first.title}</h2>
                        </div>
                    </div>`;
                    list = list.slice(1);
                } else {
                    heroArea.innerHTML = '';
                }

                // زامانىۋى Bento كارتىلىرى
                listArea.innerHTML = list.map(item => {
                    let isFav = favorites.some(f => f.title === item.title);
                    return `
                    <div class="bento-card">
                        <div class="bento-info" onclick='openArticle(${JSON.stringify(item)})'>
                            <div>
                                <div class="bento-meta">
                                    <span class="source-tag">${item.source}</span>
                                    <span class="cat-tag">${item.category}</span>
                                </div>
                                <h3 class="bento-title">${item.title}</h3>
                            </div>
                            <div class="bento-footer">
                                <span class="time-txt">${item.published || 'ھازىرلا'}</span>
                                <button class="star-icon ${isFav?'active':''}" onclick='event.stopPropagation(); toggleFav(${JSON.stringify(item)})'>${isFav?'★':'☆'}</button>
                            </div>
                        </div>
                        ${item.image ? `<img class="bento-thumb" src="${item.image}" loading="lazy" onclick='openArticle(${JSON.stringify(item)})'>` : ''}
                    </div>`;
                }).join('');
            }

            function toggleFav(item) {
                let idx = favorites.findIndex(f => f.title === item.title);
                if(idx > -1) favorites.splice(idx, 1);
                else favorites.push(item);
                localStorage.setItem('nexus_favs', JSON.stringify(favorites));
                render();
            }

            async function openArticle(item) {
                let m = document.getElementById('detail-modal');
                document.getElementById('reader-source').innerText = item.source + " • " + item.category;
                document.getElementById('reader-title').innerText = item.title;
                let img = document.getElementById('reader-img');
                if(item.image) {
                    img.src = item.image;
                    img.style.display = 'block';
                } else {
                    img.style.display = 'none';
                }
                document.getElementById('reader-body').innerText = "⏳ خەۋەرنىڭ ئەسلى مەنبەسىدىن تولۇق تېكىست چۈشۈرۈلۈپ ئۇيغۇرچىغا تەرجىمە قىلىنماقتا، سەل كۈتۈڭ...";
                m.style.display = 'block';

                let res = await fetch(`/api/article?link=${encodeURIComponent(item.link)}&source=${encodeURIComponent(item.source)}`);
                let d = await res.json();
                document.getElementById('reader-body').innerText = d.content;
            }

            function closeDetail() {
                document.getElementById('detail-modal').style.display = 'none';
            }

            function onSearch() {
                render();
            }
        </script>
    </body>
    </html>
    """
    return render_template_string(html)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
