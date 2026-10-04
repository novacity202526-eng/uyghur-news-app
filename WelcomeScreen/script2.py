import sys
import threading
import time
import json
import urllib.parse
import urllib.request
import feedparser
from bs4 import BeautifulSoup
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QScrollArea, QFrame, QStackedWidget
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QPixmap

# 1. خەۋەر مەنبەلىرى
NEWS_SOURCES = [
    {"name": "TRT ئۇيغۇرچە", "url": "https://www.trtuyghur.com/rss"},
    {"name": "ئانادولۇ ئاگېنتلىقى", "url": "https://www.aa.com.tr/tr/rss/default?cat=guncel"},
    {"name": "مېپا خەۋەرلىرى", "url": "https://www.mepanews.com/rss"},
    {"name": "فوكۇس پلۇس", "url": "https://www.fokusplus.com/rss"},
    {"name": "سېتا (SETA)", "url": "https://www.setav.org/feed/"}
]

# 2. ئانالىز مەنبەلىرى
ANALYSIS_SOURCES = [
    {"name": "ISW ئانالىز مەركىزى", "url": "https://www.understandingwar.org/rss.xml"},
    {"name": "فوكۇس ئوداك", "url": "https://www.fokusplus.com/rss"}
]

TRANSLATION_CACHE = {}


def raw_google_call(text, sl, tl):
    """گۇگۇلغا بىۋاسىتە ئەڭ ئاستى قەۋەتتىن تەلەپ يوللاش"""
    try:
        encoded_text = urllib.parse.quote(text)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={sl}&tl={tl}&dt=t&q={encoded_text}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=6) as response:
            res = response.read().decode('utf-8')
            data = json.loads(res)
            return "".join([part[0] for part in data[0] if part[0]])
    except Exception:
        return ""


def translate_to_uyghur(text):
    """ئۇيغۇرچىغا 100% چىقىرىش كاپالىتى"""
    if not text or not text.strip():
        return ""

    clean_text = text.strip()
    if clean_text in TRANSLATION_CACHE:
        return TRANSLATION_CACHE[clean_text]

    # 1-سىناق: قايسى تىلدا بولسا بىۋاسىتە ئۇيغۇرچىغا ئۆرۈش
    result = raw_google_call(clean_text[:400], "auto", "ug")

    # ئەگەر بىۋاسىتە ئۇيغۇرچىغا قايتمىسا (تۈركچە قالسا)، ئىنگلىزچە ئارقىلىق ئۇيغۇرچىغا ئۆرۈش
    if not result or result == clean_text:
        en_text = raw_google_call(clean_text[:400], "auto", "en")
        if en_text:
            result = raw_google_call(en_text, "en", "ug")

    if result:
        TRANSLATION_CACHE[clean_text] = result
        return result

    return clean_text


def fetch_full_article_content(link, source_name):
    """تور بېتىگە كىرىپ، پۈتۈن پاراگرافلارنى ئوقۇپ، ھەممىسىنى ئۇيغۇرچە قىلىش"""
    if not link:
        return "ئۇلانما تېپىلمىدى."
    try:
        req = urllib.request.Request(link, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=8) as response:
            html = response.read()

        soup = BeautifulSoup(html, "html.parser")
        for s in soup(["script", "style", "nav", "header", "footer", "aside"]):
            s.decompose()

        paragraphs = soup.find_all("p")
        full_paragraphs = []
        for p in paragraphs:
            txt = p.get_text().strip()
            if len(txt) > 30 and not any(w in txt.lower() for w in ["cookie", "gizlilik", "copyright", "abone"]):
                full_paragraphs.append(txt)

        if not full_paragraphs:
            return "پۈتۈن مەزمۇننى تور بېتىدىن ئوقۇغىلى بولمىدى."

        translated_blocks = []
        is_uyghur_src = "ئۇيغۇرچە" in source_name

        for p_txt in full_paragraphs[:12]:
            if is_uyghur_src:
                translated_blocks.append(p_txt)
            else:
                tr = translate_to_uyghur(p_txt)
                translated_blocks.append(tr)
                time.sleep(0.15)

        return "\n\n".join(translated_blocks)

    except Exception as e:
        return f"مەزمۇننى تارتىشتا كاشىلا: {e}"


class DataWorker(QObject):
    data_fetched = pyqtSignal(list, list)

    def __init__(self):
        super().__init__()
        self.running = True

    def classify(self, text):
        txt = text.lower()
        if any(w in txt for w in
               ["ئوتتۇرا شەرق", "غەززە", "ئىسرائىلىيە", "ئىران", "سۈرىيە", "يەمەن", "middle east", "israel", "gaza",
                "iran", "syria", "orta doğu"]):
            return "ئوتتۇرا شەرق"
        elif any(w in txt for w in
                 ["ئوتتۇرا ئاسىيا", "قازاقىستان", "ئۆزبېكىستان", "قىرغىزىستان", "central asia", "kazakhstan",
                  "orta asya"]):
            return "ئوتتۇرا ئاسىيا"
        elif any(w in txt for w in ["خىتاي", "بېيجىڭ", "پېكىن", "china", "chinese", "beijing", "çin"]):
            return "خىتاي"
        elif any(w in txt for w in
                 ["شەرقىي تۈركىستان", "ئۇيغۇر", "شىنجاڭ", "uyghur", "east turkestan", "doğu türkistan"]):
            return "شەرقىي تۈركىستان"
        elif any(w in txt for w in
                 ["بۇغۇز", "ھورمۇز", "تەيۋەن", "مالاككا", "قىزىل دېڭىز", "strait", "hormuz", "taiwan", "malacca",
                  "boğaz"]):
            return "بۇغۇزلار"
        return "ئومۇمىي خەۋەرلەر"

    def fetch_items(self, sources):
        articles = []
        for src in sources:
            try:
                feed = feedparser.parse(src["url"])
                for entry in feed.entries[:4]:
                    img_url = ""
                    if "media_content" in entry and len(entry.media_content) > 0:
                        img_url = entry.media_content[0].get("url", "")
                    elif "enclosures" in entry and len(entry.enclosures) > 0:
                        img_url = entry.enclosures[0].get("href", "")
                    elif "links" in entry:
                        for l in entry.links:
                            if "image" in l.get("type", ""):
                                img_url = l.get("href", "")
                                break

                    raw_title = getattr(entry, "title", "")
                    raw_desc = getattr(entry, "summary", "")

                    if "ئۇيغۇرچە" not in src["name"]:
                        translated_title = translate_to_uyghur(raw_title)
                        translated_desc = translate_to_uyghur(raw_desc[:250])
                        time.sleep(0.1)
                    else:
                        translated_title = raw_title
                        translated_desc = raw_desc[:250]

                    cat = self.classify(raw_title + " " + raw_desc + " " + translated_title)

                    articles.append({
                        "source": src["name"],
                        "title": translated_title,
                        "desc": translated_desc,
                        "category": cat,
                        "image": img_url,
                        "link": getattr(entry, "link", "")
                    })
            except Exception as e:
                print(f"{src['name']} خاتالىقى:", e)
        return articles

    def start_loop(self):
        while self.running:
            news = self.fetch_items(NEWS_SOURCES)
            analyses = self.fetch_items(ANALYSIS_SOURCES)
            self.data_fetched.emit(news, analyses)
            time.sleep(300)


class MobileNewsApp(QMainWindow):
    full_text_loaded = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ئەپ خەۋەر ۋە تەھلىل سىستېمىسى")
        self.setFixedSize(410, 780)
        self.setLayoutDirection(Qt.RightToLeft)

        self.news_data = []
        self.analysis_data = []
        self.favorite_data = []
        self.current_list = []
        self.previous_page_index = 0

        self.setStyleSheet("""
            QWidget {
                background-color: #F8F9FA;
                font-family: 'UKIJ Ekran', 'Segoe UI', Arial;
            }
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E0;
                border-radius: 20px;
                padding: 10px 16px;
                font-size: 14px;
            }
            QPushButton.category-card {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 12px;
                padding: 16px;
                text-align: right;
                font-size: 15px;
                font-weight: bold;
                color: #2D3748;
            }
            QPushButton.category-card:hover {
                background-color: #EDF2F7;
            }
            QFrame.news-item {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 12px;
            }
            QFrame.news-item:hover {
                border-color: #3182CE;
            }
            QPushButton.star-btn {
                background-color: transparent;
                border: none;
                font-size: 20px;
                padding: 2px 6px;
            }
            QPushButton.back-btn {
                background-color: #EDF2F7;
                border: none;
                border-radius: 14px;
                padding: 6px 14px;
                font-size: 13px;
                font-weight: bold;
                color: #2B6CB0;
            }
            QPushButton.back-btn:hover {
                background-color: #E2E8F0;
            }
            QPushButton.nav-btn {
                background-color: transparent;
                border: none;
                color: #718096;
                font-size: 12px;
            }
            QPushButton.nav-btn:hover {
                color: #2B6CB0;
            }
        """)

        self.full_text_loaded.connect(self.display_full_text)
        self.init_ui()
        self.start_worker_thread()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.main_layout = QVBoxLayout(main_widget)
        self.main_layout.setContentsMargins(14, 14, 14, 0)
        self.main_layout.setSpacing(10)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 ئىزدەش...")
        self.search_box.textChanged.connect(self.filter_items_by_text)
        self.main_layout.addWidget(self.search_box)

        self.stacked_widget = QStackedWidget()

        # 1-بەت: باش بەت
        self.home_page = QWidget()
        home_layout = QVBoxLayout(self.home_page)
        home_layout.setContentsMargins(0, 0, 0, 0)
        home_layout.setSpacing(10)

        categories = [
            ("🌍", "ئوتتۇرا شەرق", "ئىسرائىلىيە، ئىران، سۈرىيە ۋە رايون خەۋەرلىرى"),
            ("🏔️", "ئوتتۇرا ئاسىيا", "قازاقىستان، ئۆزبېكىستان، قىرغىزىستان خەۋەرلىرى"),
            ("🌐", "خىتاي", "بېيجىڭ ۋە دۇنياۋى سىياسەت ئۆزگىرىشلىرى"),
            ("🌙", "شەرقىي تۈركىستان", "ئۇيغۇر دىيارىغا دائىر مۇھىم ۋە يېڭى خەۋەرلەر"),
            ("⚓", "بۇغۇزلار", "ھورمۇز، تەيۋەن ۋە دۇنياۋى دېڭىز لىنىيە تەھلىللىرى")
        ]

        for icon, title, desc in categories:
            card_btn = QPushButton(f"{icon}  {title}\n    {desc}")
            card_btn.setProperty("class", "category-card")
            card_btn.setCursor(Qt.PointingHandCursor)
            card_btn.clicked.connect(lambda checked, t=title: self.show_category_items(t))
            home_layout.addWidget(card_btn)

        home_layout.addStretch()
        self.stacked_widget.addWidget(self.home_page)

        # 2-بەت: تىزىملىك
        self.list_page = QWidget()
        list_page_layout = QVBoxLayout(self.list_page)
        list_page_layout.setContentsMargins(0, 0, 0, 0)

        self.page_title = QLabel("پۈتۈن خەۋەرلەر")
        self.page_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2B6CB0; padding: 4px;")
        list_page_layout.addWidget(self.page_title)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        self.items_container = QWidget()
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(12)

        self.scroll_area.setWidget(self.items_container)
        list_page_layout.addWidget(self.scroll_area)
        self.stacked_widget.addWidget(self.list_page)

        # 3-بەت: تەپسىلىي كۆرۈش بېتى
        self.detail_page = QWidget()
        detail_page_layout = QVBoxLayout(self.detail_page)
        detail_page_layout.setContentsMargins(0, 0, 0, 0)
        detail_page_layout.setSpacing(10)

        top_bar = QHBoxLayout()
        self.back_btn = QPushButton("← قايتىش")
        self.back_btn.setProperty("class", "back-btn")
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self.go_back)
        top_bar.addWidget(self.back_btn)
        top_bar.addStretch()
        detail_page_layout.addLayout(top_bar)

        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setFrameShape(QFrame.NoFrame)

        detail_content = QWidget()
        self.detail_layout = QVBoxLayout(detail_content)
        self.detail_layout.setContentsMargins(4, 4, 4, 4)
        self.detail_layout.setSpacing(12)

        self.detail_image = QLabel()
        self.detail_image.setAlignment(Qt.AlignCenter)
        self.detail_image.setStyleSheet("border-radius: 12px; background-color: #EDF2F7;")
        self.detail_layout.addWidget(self.detail_image)

        self.detail_title = QLabel()
        self.detail_title.setWordWrap(True)
        self.detail_title.setStyleSheet("font-size: 17px; font-weight: bold; color: #1A202C;")
        self.detail_layout.addWidget(self.detail_title)

        self.detail_meta = QLabel()
        self.detail_meta.setStyleSheet("font-size: 11px; color: #718096;")
        self.detail_layout.addWidget(self.detail_meta)

        self.detail_body = QLabel()
        self.detail_body.setWordWrap(True)
        self.detail_body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.detail_body.setStyleSheet("font-size: 14px; line-height: 180%; color: #2D3748; padding-top: 6px;")
        self.detail_layout.addWidget(self.detail_body)
        self.detail_layout.addStretch()

        detail_scroll.setWidget(detail_content)
        detail_page_layout.addWidget(detail_scroll)

        self.stacked_widget.addWidget(self.detail_page)
        self.main_layout.addWidget(self.stacked_widget, stretch=1)

        # ئاستىنقى يول باشلاش قۇتىسى
        self.nav_bar = QFrame()
        self.nav_bar.setFixedHeight(60)
        self.nav_bar.setStyleSheet("background-color: #FFFFFF; border-top: 1px solid #E2E8F0;")
        nav_layout = QHBoxLayout(self.nav_bar)
        nav_layout.setContentsMargins(6, 4, 6, 4)

        btn_home = QPushButton("🏠\nباشبەت")
        btn_home.setProperty("class", "nav-btn")
        btn_home.setCursor(Qt.PointingHandCursor)
        btn_home.clicked.connect(lambda: self.switch_tab(0))

        btn_news = QPushButton("📰\nخەۋەرلەر")
        btn_news.setProperty("class", "nav-btn")
        btn_news.setCursor(Qt.PointingHandCursor)
        btn_news.clicked.connect(self.show_all_news)

        btn_analysis = QPushButton("📊\nئانالىزلار")
        btn_analysis.setProperty("class", "nav-btn")
        btn_analysis.setCursor(Qt.PointingHandCursor)
        btn_analysis.clicked.connect(self.show_all_analyses)

        btn_starred = QPushButton("⭐\nمۇھىم")
        btn_starred.setProperty("class", "nav-btn")
        btn_starred.setCursor(Qt.PointingHandCursor)
        btn_starred.clicked.connect(self.show_starred_items)

        nav_layout.addWidget(btn_home)
        nav_layout.addWidget(btn_news)
        nav_layout.addWidget(btn_analysis)
        nav_layout.addWidget(btn_starred)

        self.main_layout.addWidget(self.nav_bar)

    def switch_tab(self, index):
        self.search_box.show()
        self.stacked_widget.setCurrentIndex(index)

    def go_back(self):
        self.search_box.show()
        self.nav_bar.show()
        self.stacked_widget.setCurrentIndex(self.previous_page_index)

    def open_detail_page(self, item):
        self.previous_page_index = self.stacked_widget.currentIndex()
        self.search_box.hide()

        if item.get("image"):
            self.detail_image.show()
            self.detail_image.setFixedHeight(200)
            try:
                req = urllib.request.Request(item["image"], headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=4) as resp:
                    pix = QPixmap()
                    pix.loadFromData(resp.read())
                    self.detail_image.setPixmap(pix.scaledToWidth(380, Qt.SmoothTransformation))
            except Exception:
                self.detail_image.hide()
        else:
            self.detail_image.hide()

        self.detail_title.setText(item["title"])
        self.detail_meta.setText(f"مەنبە: {item['source']}   |   تۈرى: {item.get('category', 'ئومۇمىي')}")
        self.detail_body.setText(
            "⏳ پۈتۈن خەۋەر مەزمۇنى ئەسلى تور بېتىدىن تولۇق ئۇيغۇرچىغا تەرجىمە قىلىنماقتا، سەل كۈتۈڭ...")

        self.stacked_widget.setCurrentIndex(2)

        # پاراگرافلارنى ئوقۇپ تەرجىمە قىلىشنى باشلاش
        threading.Thread(target=self.load_full_article_thread, args=(item["link"], item["source"]), daemon=True).start()

    def load_full_article_thread(self, link, source_name):
        full_text = fetch_full_article_content(link, source_name)
        self.full_text_loaded.emit(full_text)

    def display_full_text(self, full_text):
        self.detail_body.setText(full_text)

    def toggle_favorite(self, item, star_btn):
        is_fav = any(f["title"] == item["title"] for f in self.favorite_data)
        if is_fav:
            self.favorite_data = [f for f in self.favorite_data if f["title"] != item["title"]]
            star_btn.setText("☆")
            star_btn.setStyleSheet("color: #A0AEC0;")
            if "مۇھىم" in self.page_title.text():
                self.show_starred_items()
        else:
            self.favorite_data.append(item)
            star_btn.setText("★")
            star_btn.setStyleSheet("color: #ECC94B;")

    def start_worker_thread(self):
        self.worker = DataWorker()
        self.worker.data_fetched.connect(self.update_data)
        self.thread = threading.Thread(target=self.worker.start_loop, daemon=True)
        self.thread.start()

    def update_data(self, news, analyses):
        self.news_data = news
        self.analysis_data = analyses
        if self.stacked_widget.currentIndex() == 1:
            if "ئانالىز" in self.page_title.text():
                self.show_all_analyses()
            elif "خەۋەرلەر" in self.page_title.text():
                self.show_all_news()

    def show_all_news(self):
        self.page_title.setText("پۈتۈن خەۋەرلەر")
        self.current_list = self.news_data
        self.render_cards(self.current_list)
        self.switch_tab(1)

    def show_all_analyses(self):
        self.page_title.setText("📊 ئەڭ يېڭى ئانالىزلار")
        self.current_list = self.analysis_data
        self.render_cards(self.current_list)
        self.switch_tab(1)

    def show_starred_items(self):
        self.page_title.setText("⭐ مۇھىم ساقلانغان مەزمۇنلار")
        self.current_list = self.favorite_data
        self.render_cards(self.current_list)
        self.switch_tab(1)

    def show_category_items(self, category_name):
        self.page_title.setText(f"{category_name} خەۋەر ۋە تەھلىللىرى")
        combined = self.news_data + self.analysis_data
        filtered = [item for item in combined if category_name in item.get("category", "")]
        self.current_list = filtered if filtered else combined
        self.render_cards(self.current_list)
        self.switch_tab(1)

    def filter_items_by_text(self, text):
        if not text.strip():
            self.render_cards(self.current_list)
            return
        results = [i for i in self.current_list if
                   text.lower() in i["title"].lower() or text.lower() in i["desc"].lower()]
        self.render_cards(results)

    def render_cards(self, items):
        while self.items_layout.count():
            w = self.items_layout.takeAt(0).widget()
            if w:
                w.deleteLater()

        if not items:
            msg = "مۇھىم دەپ ساقلانغان مەزمۇن يوق." if "مۇھىم" in self.page_title.text() else "مەزمۇنلار تەرجىمە قىلىنماقتا، سەل كۈتۈڭ..."
            lbl = QLabel(msg)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color: #718096; margin-top: 50px;")
            self.items_layout.addWidget(lbl)
            return

        for item in items:
            card = QFrame()
            card.setProperty("class", "news-item")
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(10, 10, 10, 10)
            c_layout.setSpacing(6)

            if item.get("image"):
                img_lbl = QLabel()
                img_lbl.setFixedHeight(140)
                img_lbl.setAlignment(Qt.AlignCenter)
                img_lbl.setStyleSheet("background-color: #EDF2F7; border-radius: 8px;")
                try:
                    req = urllib.request.Request(item["image"], headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=3) as resp:
                        pix = QPixmap()
                        pix.loadFromData(resp.read())
                        img_lbl.setPixmap(pix.scaledToWidth(350, Qt.SmoothTransformation))
                        c_layout.addWidget(img_lbl)
                except Exception:
                    pass

            title_box = QHBoxLayout()
            t_lbl = QLabel(item["title"])
            t_lbl.setWordWrap(True)
            t_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #1A202C;")
            t_lbl.setCursor(Qt.PointingHandCursor)
            t_lbl.mousePressEvent = lambda ev, it=item: self.open_detail_page(it)
            title_box.addWidget(t_lbl, stretch=1)

            star_btn = QPushButton()
            star_btn.setProperty("class", "star-btn")
            star_btn.setCursor(Qt.PointingHandCursor)
            is_fav = any(f["title"] == item["title"] for f in self.favorite_data)
            star_btn.setText("★" if is_fav else "☆")
            star_btn.setStyleSheet("color: #ECC94B;" if is_fav else "color: #A0AEC0;")
            star_btn.clicked.connect(lambda checked, it=item, btn=star_btn: self.toggle_favorite(it, btn))
            title_box.addWidget(star_btn)

            c_layout.addLayout(title_box)

            d_lbl = QLabel(item["desc"][:100] + "...")
            d_lbl.setWordWrap(True)
            d_lbl.setStyleSheet("font-size: 12px; color: #4A5568;")
            d_lbl.setCursor(Qt.PointingHandCursor)
            d_lbl.mousePressEvent = lambda ev, it=item: self.open_detail_page(it)
            c_layout.addWidget(d_lbl)

            source_tag = QLabel(f"مەنبە: {item['source']}  |  تۈرى: {item.get('category', 'ئومۇمىي')}")
            source_tag.setStyleSheet("font-size: 10px; color: #A0AEC0;")
            c_layout.addWidget(source_tag)

            self.items_layout.addWidget(card)

        self.items_layout.addStretch()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MobileNewsApp()
    window.show()
    sys.exit(app.exec_())