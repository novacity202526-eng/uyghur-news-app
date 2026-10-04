# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.


def print_hi(name):
    # Use a breakpoint in the code line below to debug your script.
    print(f'Hi, {name}')  # Press Ctrl+F8 to toggle the breakpoint.


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    print_hi('PyCharm')

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QScrollArea, QFrame
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class MobileAppWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("خەۋەرلەر ۋە تەھلىللەر")

        # كۆچمە تېلېفون ئېكران رازمېرىغا كاپالەتلىك قىلىش
        self.setFixedSize(390, 750)

        # پۈتۈن كۆرۈنمە يۈزنى ئوڭدىن سولغا تەڭشەش
        self.setLayoutDirection(Qt.RightToLeft)

        # پۈتۈن ئەپنىڭ ئاساسىي ئۇسلۇبى ۋە UKIJ Ekran خەت نۇسخىسى
        self.setStyleSheet("""
            QWidget {
                background-color: #F8F9FA;
                font-family: 'UKIJ Ekran', 'Segoe UI', Arial;
            }
            /* ئىزدەش رامكىسى */
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 20px;
                padding: 10px 16px;
                font-size: 14px;
                color: #2D3748;
            }
            QLineEdit:focus {
                border: 1px solid #3182CE;
            }
            /* كاتېگورىيە تۈگمىلىرى */
            QPushButton.category-btn {
                background-color: #EDF2F7;
                color: #4A5568;
                border: none;
                border-radius: 16px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton.category-btn:hover {
                background-color: #E2E8F0;
            }
            QPushButton.category-btn-active {
                background-color: #2B6CB0;
                color: #FFFFFF;
                border: none;
                border-radius: 16px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            /* ئاستىنقى تىزىملىك تۈگمىلىرى */
            QPushButton.nav-btn {
                background-color: transparent;
                border: none;
                color: #718096;
                font-size: 12px;
                padding: 4px;
            }
            QPushButton.nav-btn:hover {
                color: #2B6CB0;
            }
        """)

        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(16, 16, 16, 0)
        main_layout.setSpacing(12)

        # ---------------- 1. ئۈستىدىكى ئىزدەش كۆزنىكى ----------------
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 ئىزدەش...")
        main_layout.addWidget(self.search_box)

        # ---------------- 2. 5 دانە كاتېگورىيە تىزىملىكى ----------------
        categories = ["ئوتتۇرا شەرق", "ئوتتۇرا ئاسىيا", "خىتاي", "شەرقىي تۈركىستان", "بۇغۇزلار"]

        cat_scroll = QScrollArea()
        cat_scroll.setWidgetResizable(True)
        cat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cat_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cat_scroll.setFixedHeight(48)
        cat_scroll.setFrameShape(QFrame.NoFrame)

        cat_content = QWidget()
        cat_layout = QHBoxLayout(cat_content)
        cat_layout.setContentsMargins(0, 0, 0, 0)
        cat_layout.setSpacing(8)

        # كۇنۇپكىلارنى رەتكە تىزىش
        for i, cat_name in enumerate(categories):
            btn = QPushButton(cat_name)
            # بىرىنچىسىنى تاللانغان قىلىپ كۆرسىتىش
            if i == 0:
                btn.setProperty("class", "category-btn-active")
            else:
                btn.setProperty("class", "category-btn")
            cat_layout.addWidget(btn)

        cat_layout.addStretch()
        cat_scroll.setWidget(cat_content)
        main_layout.addWidget(cat_scroll)

        # ---------------- 3. ئوتتۇرا بۆلەك (ئەپ مەزمۇن رايونى) ----------------
        content_area = QFrame()
        content_area.setStyleSheet("""
            background-color: #FFFFFF;
            border-radius: 16px;
            border: 1px solid #EDF2F7;
        """)
        content_layout = QVBoxLayout(content_area)
        content_layout.setAlignment(Qt.AlignCenter)

        placeholder_label = QLabel("بۇ يەردە تاللانغان مەزمۇنلار كۆرۈنىدۇ")
        placeholder_label.setStyleSheet("color: #A0AEC0; font-size: 14px;")
        content_layout.addWidget(placeholder_label)

        main_layout.addWidget(content_area, stretch=1)

        # ---------------- 4. ئاستىنقى يول باشلاش تىزىملىكى (ئوڭدىن سولغا) ----------------
        nav_bar = QFrame()
        nav_bar.setFixedHeight(65)
        nav_bar.setStyleSheet("""
            background-color: #FFFFFF;
            border-top: 1px solid #E2E8F0;
        """)
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(8, 6, 8, 6)

        # تەلەپ بويىچە ئوڭدىن سولغا تىزىلىدىغان 4 سىن بەلگىسى
        nav_items = [
            ("🏠", "باشبەت"),
            ("📰", "خەۋەرلەر"),
            ("📊", "ئانالىزلار"),
            ("⭐", "مۇھىم")
        ]

        for icon, title in nav_items:
            btn = QPushButton(f"{icon}\n{title}")
            btn.setProperty("class", "nav-btn")
            btn.setCursor(Qt.PointingHandCursor)
            nav_layout.addWidget(btn)

        main_layout.addWidget(nav_bar)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MobileAppWindow()
    window.show()
    sys.exit(app.exec_())