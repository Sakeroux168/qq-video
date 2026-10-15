"""界面风格(用户 2026-10-15:「前端风格也太丑了,给我几个风格样板看看选一下」)。

每套 = Fusion 风格 + 调色板 + 一段 QSS + 列表里状态行的底色(深色主题要用深一点的底色,不然字看不清)。
设置里 theme 存名字;main.py 启动时 apply()。"""
from PySide6.QtGui import QColor, QPalette

BASE_FONT = "font-family:'Microsoft YaHei';font-size:13px;"

THEMES = {
    "抖音创作者": {
        "desc": "白卡片、浅灰底、红粉色强调、大数字(用户 2026-10-15 选的)",
        "pal": {"window": "#f5f6f7", "base": "#ffffff", "alt": "#fafafb", "text": "#161823", "button": "#ffffff",
                "highlight": "#ffe8ed", "htext": "#161823", "mid": "#e6e7ea", "muted": "#8a8b91", "side": "#ffffff"},
        "accent": "#fe2c55", "accent_hover": "#e8173f", "soft": "#fff0f3", "radius": 8,
        "rows": {"yellow": "#fff7e0", "red": "#ffe7eb", "green": "#e6f7ec", "orange": "#ffeedd", "ready": "#eef4ff"},
    },
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


def _get(t: dict) -> dict:
    """补齐可选的颜色:muted(灰字)、side(导航栏底)、soft(强调色的浅底)。"""
    p = dict(t["pal"])
    p.setdefault("muted", "#8a8f99")
    p.setdefault("side", p["base"])
    return p


def _blend(c1: str, c2: str, k: float) -> str:
    """c1 和 c2 按 k 混(k=0.12 → 12% 的 c1)。用来从强调色调出浅底。"""
    a, b = QColor(c1), QColor(c2)
    return QColor(round(a.red() * k + b.red() * (1 - k)), round(a.green() * k + b.green() * (1 - k)),
                  round(a.blue() * k + b.blue() * (1 - k))).name()


def _asset(name: str) -> str:
    import os
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", name).replace("\\", "/")


def qss(t: dict) -> str:
    p, a, r = _get(t), t["accent"], t["radius"]
    # 选中项的浅底:没写 soft 的主题从强调色调淡(审查:原来用 highlight = 强调色,蓝底蓝字看不见)
    soft = t.get("soft") or _blend(a, p["base"], 0.16)
    down, up = _asset("down.svg"), _asset("up.svg")
    return f"""
QWidget {{ {BASE_FONT} color:{p['text']}; }}
QMainWindow, QDialog, QWidget#page, QStackedWidget {{ background:{p['window']}; }}
QFrame#sidebar {{ background:{p['side']}; border-right:1px solid {p['mid']}; }}
QLabel#brand {{ font-size:18px; font-weight:bold; color:{a}; padding-left:6px; }}
QLabel#brandSub {{ font-size:12px; color:{p['muted']}; padding-left:6px; }}
QPushButton#nav {{ text-align:left; padding:9px 14px; border:none; border-radius:{r}px; background:transparent;
    font-size:14px; color:{p['text']}; }}
QPushButton#nav:hover {{ background:{p['window']}; color:{p['text']}; }}
QPushButton#nav:checked {{ background:{soft}; color:{a}; font-weight:bold; }}
QLabel#pageTitle {{ font-size:18px; font-weight:bold; padding:2px 0 4px 0; }}
QFrame#stat {{ background:{p['base']}; border:1px solid {p['mid']}; border-radius:{r + 2}px; }}
QLabel#statLbl {{ color:{p['muted']}; font-size:13px; }}
QLabel#statVal {{ font-size:26px; font-weight:bold; color:{p['text']}; }}
QLabel#statVal[tone="good"] {{ color:#1aa260; }}
QLabel#statVal[tone="warn"] {{ color:{a}; }}
QLabel#statSub {{ color:{p['muted']}; font-size:12px; }}
QTabWidget::pane {{ border:1px solid {p['mid']}; border-radius:{r}px; background:{p['window']}; top:-1px; }}
QTabBar::tab {{ background:transparent; padding:7px 16px; margin-right:2px; border:none; color:{p['text']}; }}
QTabBar::tab:selected {{ color:{a}; border-bottom:2px solid {a}; font-weight:bold; }}
QPushButton {{ background:{p['button']}; border:1px solid {p['mid']}; border-radius:{r}px; padding:6px 14px; }}
QPushButton:hover {{ border-color:{a}; color:{a}; }}
QPushButton:disabled {{ color:{p['muted']}; border-color:{p['mid']}; background:{p['window']}; }}
QPushButton#primary {{ background:{a}; color:#ffffff; border:1px solid {a}; font-weight:bold; padding:7px 24px; }}
QPushButton#primary:hover {{ background:{t['accent_hover']}; color:#ffffff; }}
QPushButton#primary:disabled {{ background:{p['mid']}; color:{p['muted']}; border-color:{p['mid']}; }}
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {{ background:{p['base']}; border:1px solid {p['mid']}; border-radius:{r}px; padding:5px 8px; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color:{a}; }}
QComboBox::drop-down {{ border:none; width:24px; }}
QComboBox::down-arrow {{ image:url({down}); width:12px; height:12px; }}
QSpinBox::up-button, QSpinBox::down-button {{ border:none; width:20px; background:transparent; }}
QSpinBox::up-arrow {{ image:url({up}); width:10px; height:10px; }}
QSpinBox::down-arrow {{ image:url({down}); width:10px; height:10px; }}
QComboBox QAbstractItemView {{ background:{p['base']}; border:1px solid {p['mid']}; selection-background-color:{soft}; selection-color:{a}; }}
QPlainTextEdit#log {{ color:{p['muted']}; }}
QTreeWidget, QTableWidget {{ background:{p['base']}; alternate-background-color:{p['alt']}; border:1px solid {p['mid']};
    border-radius:{r + 2}px; gridline-color:{p['mid']}; }}
QTreeWidget::item, QTableWidget::item {{ padding:4px 2px; }}
QTreeWidget::item:selected, QTableWidget::item:selected {{ background:{soft}; color:{p['text']}; }}
QHeaderView::section {{ background:{p['base']}; border:none; border-bottom:1px solid {p['mid']}; padding:8px 6px;
    font-weight:bold; color:{p['muted']}; }}
QGroupBox {{ background:{p['base']}; border:1px solid {p['mid']}; border-radius:{r + 2}px; margin-top:16px; padding:12px 10px 8px 10px; }}
QGroupBox::title {{ subcontrol-origin:margin; left:12px; padding:0 4px; color:{a}; font-weight:bold; }}
QCheckBox::indicator {{ width:15px; height:15px; }}
QScrollBar:vertical {{ background:transparent; width:10px; margin:0; }}
QScrollBar::handle:vertical {{ background:{p['mid']}; border-radius:5px; min-height:30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height:0; }}
QToolTip {{ background:{p['base']}; color:{p['text']}; border:1px solid {p['mid']}; padding:4px; }}
QMenu {{ background:{p['base']}; border:1px solid {p['mid']}; padding:4px; }}
QMenu::item {{ padding:6px 18px; border-radius:{r}px; }}
QMenu::item:selected {{ background:{soft}; color:{a}; }}
"""


def palette(t: dict) -> QPalette:
    p = _get(t)
    pal = QPalette()
    for role, key in ((QPalette.ColorRole.Window, "window"), (QPalette.ColorRole.Base, "base"),
                      (QPalette.ColorRole.AlternateBase, "alt"), (QPalette.ColorRole.Text, "text"),
                      (QPalette.ColorRole.WindowText, "text"), (QPalette.ColorRole.ButtonText, "text"),
                      (QPalette.ColorRole.Button, "button"), (QPalette.ColorRole.Highlight, "highlight"),
                      (QPalette.ColorRole.HighlightedText, "htext"), (QPalette.ColorRole.ToolTipBase, "base"),
                      (QPalette.ColorRole.ToolTipText, "text"), (QPalette.ColorRole.PlaceholderText, "muted")):
        pal.setColor(role, QColor(p[key]))
    return pal


DEFAULT = "抖音创作者"


def apply(app, name: str) -> str:
    """套用主题;名字不认识就用默认的。返回实际用的名字。也把列表状态行的底色换成这套的。"""
    if name not in THEMES:
        name = DEFAULT
    t = THEMES[name]
    app.setStyle("Fusion")
    app.setPalette(palette(t))
    app.setStyleSheet(qss(t))
    import gui.api_tab as A
    import gui.window as W
    from PySide6.QtGui import QBrush
    A.YELLOW, A.RED, A.GREEN, A.ORANGE = (QColor(t["rows"][k]) for k in ("yellow", "red", "green", "orange"))
    W.YELLOW, W.GREEN = QBrush(QColor(t["rows"]["yellow"])), QBrush(QColor(t["rows"]["green"]))
    # 教育页「摆好」那行:要和背景分得开(审查:原来用 alt,几乎和底色一样看不出来)
    W.GREY = QBrush(QColor(t["rows"].get("ready") or t["rows"]["orange"]))
    return name
