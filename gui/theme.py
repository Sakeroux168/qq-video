"""界面风格(用户 2026-10-15:「前端风格也太丑了,给我几个风格样板看看选一下」)。

每套 = Fusion 风格 + 调色板 + 一段 QSS + 列表里状态行的底色(深色主题要用深一点的底色,不然字看不清)。
设置里 theme 存名字;main.py 启动时 apply()。"""
from PySide6.QtGui import QColor, QPalette

BASE_FONT = "font-family:'Microsoft YaHei';font-size:13px;"

THEMES = {
    "清爽白": {
        "desc": "白底浅灰,蓝色按钮,圆角;看着干净,适合白天长时间用",
        "pal": {"window": "#f4f6f9", "base": "#ffffff", "alt": "#f7f9fc", "text": "#1f2329", "button": "#ffffff",
                "highlight": "#2f6bff", "htext": "#ffffff", "mid": "#d9dde5"},
        "accent": "#2f6bff", "accent_hover": "#1f57e0", "radius": 6,
        "rows": {"yellow": "#fff6d6", "red": "#ffe1e1", "green": "#e1f5e6", "orange": "#ffe6c7"},
    },
    "暗夜": {
        "desc": "深灰黑底,亮蓝按钮;晚上用不刺眼",
        "pal": {"window": "#1f2125", "base": "#26282d", "alt": "#2b2e33", "text": "#e3e5e8", "button": "#2f3238",
                "highlight": "#4e8cff", "htext": "#ffffff", "mid": "#3a3d44"},
        "accent": "#4e8cff", "accent_hover": "#6a9fff", "radius": 6,
        "rows": {"yellow": "#4a4222", "red": "#5a2a2c", "green": "#24442f", "orange": "#5a3c1e"},
    },
    "暖橙": {
        "desc": "米白底,橙色按钮;暖色调,和企鹅号后台的感觉接近",
        "pal": {"window": "#faf6f0", "base": "#fffdf9", "alt": "#fbf6ee", "text": "#2b2620", "button": "#fffdf9",
                "highlight": "#ff8a1f", "htext": "#ffffff", "mid": "#e6dccd"},
        "accent": "#ff8a1f", "accent_hover": "#f07400", "radius": 8,
        "rows": {"yellow": "#fff3cf", "red": "#ffe0d9", "green": "#e3f3dc", "orange": "#ffdcb0"},
    },
    "护眼绿": {
        "desc": "淡绿灰底,墨绿按钮;颜色柔和,看久了眼睛舒服",
        "pal": {"window": "#eef3ef", "base": "#fbfdfb", "alt": "#f2f7f3", "text": "#1d2a22", "button": "#fbfdfb",
                "highlight": "#1f8a64", "htext": "#ffffff", "mid": "#cfdcd3"},
        "accent": "#1f8a64", "accent_hover": "#17704f", "radius": 6,
        "rows": {"yellow": "#fbf2cf", "red": "#f8dcdc", "green": "#d6efe0", "orange": "#fbe1c4"},
    },
}


def qss(t: dict) -> str:
    p, a, r = t["pal"], t["accent"], t["radius"]
    return f"""
QWidget {{ {BASE_FONT} color:{p['text']}; }}
QMainWindow, QDialog {{ background:{p['window']}; }}
QTabWidget::pane {{ border:1px solid {p['mid']}; border-radius:{r}px; background:{p['window']}; top:-1px; }}
QTabBar::tab {{ background:transparent; padding:7px 16px; margin-right:2px; border:none; color:{p['text']}; }}
QTabBar::tab:selected {{ color:{a}; border-bottom:2px solid {a}; font-weight:bold; }}
QPushButton {{ background:{p['button']}; border:1px solid {p['mid']}; border-radius:{r}px; padding:5px 14px; }}
QPushButton:hover {{ border-color:{a}; color:{a}; }}
QPushButton:disabled {{ color:#9aa0a6; border-color:{p['mid']}; }}
QPushButton#primary {{ background:{a}; color:#ffffff; border:1px solid {a}; font-weight:bold; padding:6px 22px; }}
QPushButton#primary:hover {{ background:{t['accent_hover']}; color:#ffffff; }}
QPushButton#primary:disabled {{ background:{p['mid']}; color:#ffffff; border-color:{p['mid']}; }}
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {{ background:{p['base']}; border:1px solid {p['mid']}; border-radius:{r}px; padding:4px 6px; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color:{a}; }}
QTreeWidget, QTableWidget {{ background:{p['base']}; alternate-background-color:{p['alt']}; border:1px solid {p['mid']};
    border-radius:{r}px; gridline-color:{p['mid']}; }}
QTreeWidget::item, QTableWidget::item {{ padding:3px 2px; }}
QTreeWidget::item:selected, QTableWidget::item:selected {{ background:{a}; color:#ffffff; }}
QHeaderView::section {{ background:{p['window']}; border:none; border-bottom:1px solid {p['mid']}; padding:6px 6px; font-weight:bold; }}
QGroupBox {{ border:1px solid {p['mid']}; border-radius:{r}px; margin-top:14px; padding:10px 8px 6px 8px; }}
QGroupBox::title {{ subcontrol-origin:margin; left:10px; padding:0 4px; color:{a}; font-weight:bold; }}
QCheckBox::indicator {{ width:15px; height:15px; }}
QScrollBar:vertical {{ background:transparent; width:10px; margin:0; }}
QScrollBar::handle:vertical {{ background:{p['mid']}; border-radius:5px; min-height:30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height:0; }}
QToolTip {{ background:{p['base']}; color:{p['text']}; border:1px solid {p['mid']}; padding:4px; }}
"""


def palette(t: dict) -> QPalette:
    p = t["pal"]
    pal = QPalette()
    for role, key in ((QPalette.ColorRole.Window, "window"), (QPalette.ColorRole.Base, "base"),
                      (QPalette.ColorRole.AlternateBase, "alt"), (QPalette.ColorRole.Text, "text"),
                      (QPalette.ColorRole.WindowText, "text"), (QPalette.ColorRole.ButtonText, "text"),
                      (QPalette.ColorRole.Button, "button"), (QPalette.ColorRole.Highlight, "highlight"),
                      (QPalette.ColorRole.HighlightedText, "htext"), (QPalette.ColorRole.ToolTipBase, "base"),
                      (QPalette.ColorRole.ToolTipText, "text"), (QPalette.ColorRole.PlaceholderText, "mid")):
        pal.setColor(role, QColor(p[key]))
    return pal


def apply(app, name: str) -> str:
    """套用主题;名字不认识就用「清爽白」。返回实际用的名字。也把列表状态行的底色换成这套的。"""
    if name not in THEMES:
        name = "清爽白"
    t = THEMES[name]
    app.setStyle("Fusion")
    app.setPalette(palette(t))
    app.setStyleSheet(qss(t))
    import gui.api_tab as A
    import gui.window as W
    from PySide6.QtGui import QBrush
    A.YELLOW, A.RED, A.GREEN, A.ORANGE = (QColor(t["rows"][k]) for k in ("yellow", "red", "green", "orange"))
    W.YELLOW, W.GREEN = QBrush(QColor(t["rows"]["yellow"])), QBrush(QColor(t["rows"]["green"]))
    W.GREY = QBrush(QColor(t["pal"]["alt"]))
    return name
