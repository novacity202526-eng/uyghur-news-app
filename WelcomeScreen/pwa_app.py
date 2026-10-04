import threading
import time
import json
import urllib.parse
import urllib.request
import feedparser
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

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
    if any(w in t for w in
           ["ئوتتۇرا شەرق", "غەززە", "ئىسرائىلىيە", "ئىران", "سۈرىيە", "يەمەن", "middle east", "israel", "iran",
            "syria", "orta doğu"]):
        return "ئوتتۇرا شەرق"
    elif any(w in t for w in
             ["ئوتتۇرا ئاسىيا", "قازاقىستان", "ئۆزبېكىستان", "قىرغىزىستان", "central asia", "kazakhstan", "orta asya"]):
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
            for entry in feed.entries[:4]:
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


# API ئۇچۇرلىرى
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


# PWA نىڭ ھۆججەت كۆرۈنۈشى (HTML + CSS + JS)
@app.route("/")
def index():
    html = """
    <!DOCTYPE html>
    <html lang="ug" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
        <title>خەۋەر ۋە ئانالىز</title>
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
        <style>
            @font-face {
                font-family: 'UKIJ Ekran';
                src: local('UKIJ Ekran');
            }
            * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'UKIJ Ekran', 'Segoe UI', Tahoma, sans-serif; }
            body { background: #f7fafc; color: #2d3748; padding-bottom: 75px; -webkit-tap-highlight-color: transparent; }
            header { position: sticky; top: 0; background: #fff; padding: 12px 16px; border-bottom: 1px solid #e2e8f0; z-index: 10; }
            .search-box { width: 100%; padding: 10px 16px; border-radius: 20px; border: 1px solid #cbd5e0; font-size: 14px; outline: none; }
            .container { padding: 14px; }
            .cat-card { background: #fff; border-radius: 12px; padding: 16px; margin-bottom: 10px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
            .cat-card h3 { font-size: 16px; color: #2b6cb0; margin-bottom: 4px; }
            .cat-card p { font-size: 12px; color: #718096; }
            .news-card { background: #fff; border-radius: 12px; padding: 12px; margin-bottom: 12px; border: 1px solid #e2e8f0; }
            .news-card img { width: 100%; height: 160px; object-fit: cover; border-radius: 8px; margin-bottom: 8px; background: #edf2f7; }
            .news-card .title-box { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
            .news-card h4 { font-size: 15px; color: #1a202c; line-height: 1.4; flex: 1; }
            .star-btn { font-size: 20px; color: #cbd5e0; background: none; border: none; cursor: pointer; }
            .star-btn.fav { color: #ecc94b; }
            .news-card p { font-size: 12px; color: #4a5568; margin-top: 6px; line-height: 1.5; }
            .meta { font-size: 10px; color: #a0aec0; margin-top: 6px; }

            /* تەپسىلات كۆزنىكى */
            #detail-view { display: none; background: #fff; min-height: 100vh; padding: 16px; position: fixed; top: 0; left: 0; right: 0; bottom: 0; z-index: 100; overflow-y: auto; }
            .back-btn { background: #edf2f7; border: none; padding: 8px 16px; border-radius: 20px; color: #2b6cb0; font-weight: bold; margin-bottom: 12px; }
            #detail-body { font-size: 15px; line-height: 1.8; color: #2d3748; margin-top: 12px; white-space: pre-line; }

            /* ئاستىنقى يول باشلاش */
            nav { position: fixed; bottom: 0; left: 0; right: 0; height: 60px; background: #fff; border-top: 1px solid #e2e8f0; display: flex; justify-content: space-around; align-items: center; z-index: 10; }
            .nav-item { background: none; border: none; text-align: center; color: #718096; font-size: 11px; outline: none; }
            .nav-item span { font-size: 18px; display: block; margin-bottom: 2px; }
            .nav-item.active { color: #2b6cb0; font-weight: bold; }
        </style>
    </head>
    <body>
        <header>
            <input type="text" id="search" class="search-box" placeholder="🔍 ئىزدەش..." oninput="onSearch()">
        </header>

        <div class="container" id="main-content">
            <div id="home-view">
                <div class="cat-card" onclick="openCategory('ئوتتۇرا شەرق')"><h3>🌍 ئوتتۇرا شەرق</h3><p>ئىسرائىلىيە، ئىران، سۈرىيە ۋە رايون خەۋەرلىرى</p></div>
                <div class="cat-card" onclick="openCategory('ئوتتۇرا ئاسىيا')"><h3>🏔️ ئوتتۇرا ئاسىيا</h3><p>قازاقىستان، ئۆزبېكىستان، قىرغىزىستان خەۋەرلىرى</p></div>
                <div class="cat-card" onclick="openCategory('خىتاي')"><h3>🌐 خىتاي</h3><p>بېيجىڭ ۋە دۇنياۋى سىياسەت ئۆزگىرىشلىرى</p></div>
                <div class="cat-card" onclick="openCategory('شەرقىي تۈركىستان')"><h3>🌙 شەرقىي تۈركىستان</h3><p>ئۇيغۇر دىيارىغا دائىر مۇھىم ۋە يېڭى خەۋەرلەر</p></div>
                <div class="cat-card" onclick="openCategory('بۇغۇزلار')"><h3>⚓ بۇغۇزلار</h3><p>ھورمۇز، تەيۋەن ۋە ئىستراتېگىيىلىك دېڭىز لىنىيەلىرى</p></div>
            </div>
            <div id="list-view" style="display:none;"></div>
        </div>

        <!-- تولۇق ئوقۇش بېتى -->
        <div id="detail-view">
            <button class="back-btn" onclick="closeDetail()">← قايتىش</button>
            <img id="detail-img" style="width:100%; border-radius:10px; display:none; margin-bottom:10px;">
            <h2 id="detail-title" style="font-size:18px; color:#1a202c; margin-bottom:6px;"></h2>
            <div id="detail-meta" class="meta" style="margin-bottom:12px;"></div>
            <div id="detail-body"></div>
        </div>

        <nav>
            <button class="nav-item active" onclick="switchTab('home')"><span>🏠</span>باشبەت</button>
            <button class="nav-item" onclick="switchTab('news')"><span>📰</span>خەۋەرلەر</button>
            <button class="nav-item" onclick="switchTab('analysis')"><span>📊</span>ئانالىزلار</button>
            <button class="nav-item" onclick="switchTab('fav')"><span>⭐</span>مۇھىم</button>
        </nav>

        <script>
            let newsData = [], analysisData = [], currentDisplay = [];
            let favorites = JSON.parse(localStorage.getItem('favs') || '[]');

            async function loadData() {
                try {
                    let res = await fetch('/api/data');
                    let d = await res.json();
                    newsData = d.news; analysisData = d.analyses;
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
                    l.innerHTML = "<p style='text-align:center; color:#a0aec0; margin-top:40px;'>مەزمۇنلار تەرجىمە قىلىنماقتا، سەل كۈتۈڭ...</p>";
                    return;
                }
                l.innerHTML = items.map(item => {
                    let isFav = favorites.some(f => f.title === item.title);
                    return `
                    <div class="news-card">
                        ${item.image ? `<img src="${item.image}">` : ''}
                        <div class="title-box">
                            <h4 onclick='openDetail(${JSON.stringify(item)})'>${item.title}</h4>
                            <button class="star-btn ${isFav?'fav':''}" onclick='toggleFav(${JSON.stringify(item)})'>${isFav?'★':'☆'}</button>
                        </div>
                        <p onclick='openDetail(${JSON.stringify(item)})'>${item.desc.substring(0,90)}...</p>
                        <div class="meta">مەنبە: ${item.source} | ${item.category}</div>
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
                document.getElementById('detail-meta').innerText = item.source + " | " + item.category;
                let img = document.getElementById('detail-img');
                if(item.image) { img.src = item.image; img.style.display = 'block'; }
                else { img.style.display = 'none'; }

                document.getElementById('detail-body').innerText = "⏳ خەۋەرنىڭ پۈتۈن مەزمۇنى ئەسلى مەنبەدىن ئوقۇلۇپ تەرجىمە قىلىنماقتا...";
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
    # 0.0.0.0 بارلىق تېلېفون ۋە كومپيۇتېرلارنىڭ ئۇلىنىشىغا يول قويىدۇ
    app.run(host="0.0.0.0", port=5000, debug=False)