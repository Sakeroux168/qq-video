"""界面风格(用户 2026-10-18 选的「G 一键驾驶舱」:大字 + 一个大按钮、问题做成卡片、明细能收起;
「白色界面有些字看不见好淡」→ 说明字一律深灰、最小 12px)。

两套:浅色(默认)/ 深色。每套 = 一组颜色(TOKENS)→ 调色板 + 一段 QSS + 列表里状态行的底色。
自己画的小部件(圆环、状态胶囊、开场动画)用 cur() 拿当前这套颜色。设置里 theme 存名字;main.py 启动时 apply()。"""
from PySide6.QtGui import QColor, QPalette

FONT = "'Microsoft YaHei UI','Microsoft YaHei'"

THEMES = {
    "浅色": {
        "desc": "白底、深色字、蓝色主按钮;白天用",
        "bg": "#f6f7f9", "card": "#ffffff", "side": "#ffffff", "line": "#dfe2e8", "line2": "#eceef2",
        "tx": "#111318", "tx2": "#2b303a", "mu": "#4b5260", "dim": "#6b7280",
        "acc": "#0066d6", "acc_h": "#0057b8", "acc_bg": "#e3eeff",
        "soft": "#eceef2", "soft_h": "#e2e5ea",
        "ok": "#1a7a33", "ok_bg": "#e3f5e8", "warn": "#b42f00", "warn_bg": "#fff0e0",
        "bad": "#c4231a", "bad_bg": "#fdeceb", "danger": "#d92d20", "danger_h": "#b42318",
        "orange": "#e8590c", "green": "#1f9d4c", "sel": "#dce9ff", "alt": "#fafbfc",
        "acc_btn": "#0066d6", "danger_btn": "#d92d20", "badge": "#e8590c", "track": "#dde1e8",
        "rows": {"yellow": "#fffaf0", "red": "#fff4f2", "green": "#f3faf5", "orange": "#fff5e8", "ready": "#eef4ff"},
    },
    "深色": {
        "desc": "深灰底、亮字;晚上用不刺眼",
        "bg": "#141418", "card": "#1d1e24", "side": "#1a1b20", "line": "#30323b", "line2": "#272830",
        "tx": "#f2f3f5", "tx2": "#dfe1e6", "mu": "#b4b8c2", "dim": "#9095a1",
        "acc": "#3b8cff", "acc_h": "#5c9fff", "acc_bg": "#1c2c47",
        "soft": "#2a2b33", "soft_h": "#33353e",
        "ok": "#4ade80", "ok_bg": "#16321f", "warn": "#ffa94d", "warn_bg": "#3a2a14",
        "bad": "#ff7b72", "bad_bg": "#3d1c1c", "danger": "#e5484d", "danger_h": "#f2555a",
        "orange": "#ff922b", "green": "#40c463", "sel": "#22385c", "alt": "#202128",
        "acc_btn": "#1f6fe0", "danger_btn": "#c9302c", "badge": "#d9480f", "track": "#3a3c47",
        "rows": {"yellow": "#2c2717", "red": "#331d1d", "green": "#18291e", "orange": "#33261a", "ready": "#1c2a40"},
    },
}
DEFAULT = "浅色"
_CUR = dict(THEMES[DEFAULT])


def cur() -> dict:
    """当前这套颜色(自己画的小部件用)。"""
    return _CUR


def _asset(name: str) -> str:
    import os
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", name).replace("\\", "/")


def qss(t: dict) -> str:
    down, up, chk = _asset("down.svg"), _asset("up.svg"), _asset("check.svg")
    return f"""
QWidget {{ font-family:{FONT}; font-size:13px; color:{t['tx']}; }}
QMainWindow, QDialog, QWidget#page, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{ background:{t['bg']}; }}
QLabel {{ background:transparent; }}

/* 左边导航 */
QFrame#sidebar {{ background:{t['side']}; border:none; border-right:1px solid {t['line']}; }}
QLabel#brand {{ font-size:15px; font-weight:bold; color:{t['tx']}; }}
QLabel#brandSub {{ font-size:12px; color:{t['dim']}; }}
QPushButton#nav {{ text-align:left; padding:9px 12px; border:none; border-radius:10px; background:transparent;
    font-size:14px; color:{t['tx2']}; }}
QPushButton#nav:hover {{ background:{t['soft']}; }}
QPushButton#nav:checked {{ background:{t['acc_bg']}; color:{t['acc']}; font-weight:bold; }}
QLabel#navBadge {{ background:{t['badge']}; color:#ffffff; border-radius:9px; padding:0 5px; font-size:11px; font-weight:bold; }}

/* 大字区(每页最上面) */
QFrame#hero {{ background:{t['card']}; border:1px solid {t['line']}; border-radius:16px; }}
QFrame#hero[open="false"] {{ background:transparent; border-color:transparent; }}
QLabel#heroMeta {{ color:{t['mu']}; font-size:13px; }}
QLabel#heroBig {{ font-weight:bold; color:{t['tx']}; }}
QLabel#heroBig[tone="good"] {{ color:{t['ok']}; }}
QLabel#heroBig[tone="warn"] {{ color:{t['warn']}; }}
QLabel#heroBig[tone="bad"] {{ color:{t['bad']}; }}
QLabel#heroSub {{ color:{t['mu']}; font-size:13px; }}
/* 明细收起时:大字区大一号、没有框,日期是个小胶囊,按钮也大(用户 2026-10-18:「高级感被压制了」) */
QFrame#hero[open="false"] QLabel#heroSub {{ font-size:15px; }}
QFrame#hero[open="false"] QLabel {{ font-size:14px; }}
QFrame#hero[open="false"] QLabel#heroBig {{ letter-spacing:-1px; }}
QFrame#hero[open="false"] QComboBox {{ border:none; background:{t['soft']}; border-radius:15px; padding:5px 14px; font-size:14px; }}
QFrame#hero[open="false"] QPushButton#primary {{ font-size:16px; padding:12px 38px; border-radius:25px; min-height:24px; }}
QFrame#hero[open="false"] QPushButton#danger {{ font-size:16px; padding:12px 38px; border-radius:25px; min-height:24px; }}
QFrame#hero[open="false"] QPushButton#pill {{ font-size:14px; padding:11px 24px; border-radius:23px; min-height:24px; }}
QLabel#pageTitle {{ font-size:20px; font-weight:bold; color:{t['tx']}; }}
QLabel#muted {{ color:{t['mu']}; font-size:12px; }}
QLabel#warnText {{ color:{t['danger']}; font-weight:bold; }}
QLabel#secTitle {{ font-size:14px; font-weight:bold; color:{t['tx']}; }}

/* 问题卡片(点了就处理) */
QFrame#probCard {{ background:{t['card']}; border:1px solid {t['line2']}; border-radius:18px; }}
QFrame#probCard:hover {{ border-color:{t['acc']}; }}
QLabel#probTitle {{ font-size:15px; font-weight:bold; color:{t['tx']}; }}
QLabel#probTitle[tone="done"] {{ color:{t['mu']}; }}
QLabel#probSub {{ color:{t['mu']}; font-size:12px; }}
QPushButton#cardBtn {{ background:transparent; border:none; color:{t['acc']}; font-weight:bold; padding:2px 0; text-align:left; }}
QPushButton#cardBtn:hover {{ color:{t['acc_h']}; text-decoration:underline; }}
QPushButton#cardBtn:disabled {{ color:{t['dim']}; }}
QPushButton#cardBtn::menu-indicator {{ image:none; width:0; }}

/* 白色大块(列表外面那层) */
QFrame#panel {{ background:{t['card']}; border:1px solid {t['line']}; border-radius:14px; }}
QFrame#stat {{ background:{t['card']}; border:1px solid {t['line']}; border-radius:14px; }}
QFrame#stat[click="true"]:hover {{ border-color:{t['acc']}; }}
QLabel#statLbl {{ color:{t['mu']}; font-size:13px; }}
QLabel#statVal {{ font-size:26px; font-weight:bold; color:{t['tx']}; }}
QLabel#statVal[tone="good"] {{ color:{t['ok']}; }}
QLabel#statVal[tone="warn"] {{ color:{t['warn']}; }}
QLabel#statSub {{ color:{t['mu']}; font-size:12px; }}

/* 「全部 / 要处理 / 能发 / 已发」 */
QFrame#seg {{ background:{t['soft']}; border-radius:10px; }}
QPushButton#segBtn {{ background:transparent; border:none; border-radius:8px; padding:5px 12px; color:{t['tx2']}; }}
QPushButton#segBtn:hover {{ background:{t['soft_h']}; }}
QPushButton#segBtn:checked {{ background:{t['card']}; color:{t['tx']}; font-weight:bold; }}

/* 按钮:主按钮(蓝)/ 普通 / 危险(红)/ 像链接的 */
QPushButton {{ background:{t['card']}; border:1px solid {t['line']}; border-radius:8px; padding:7px 14px; color:{t['tx']}; }}
QPushButton:hover {{ background:{t['soft']}; border-color:{t['dim']}; }}
QPushButton:pressed {{ background:{t['soft_h']}; }}
QPushButton:disabled {{ color:{t['dim']}; background:{t['soft']}; border-color:{t['soft']}; }}
QPushButton::menu-indicator {{ subcontrol-position:right center; right:6px; }}
QPushButton#primary {{ background:{t['acc_btn']}; color:#ffffff; border:1px solid {t['acc_btn']}; font-weight:bold; font-size:14px;
    padding:9px 24px; border-radius:19px; min-height:20px; }}
QPushButton#primary:hover {{ background:{t['acc_h']}; border-color:{t['acc_h']}; }}
QPushButton#ringCard {{ background:{t['card']}; border:1px solid {t['line']}; border-radius:16px; text-align:left; }}
QPushButton#ringCard:hover {{ border-color:{t['acc']}; }}
QPushButton#ringCard[bad="true"] {{ border-color:{t['bad']}; }}
QLabel#badTitle {{ color:{t['bad']}; font-weight:bold; font-size:15px; background:transparent; }}
QLabel#helpDot {{ background:{t['soft']}; color:{t['mu']}; border:1px solid {t['line']}; border-radius:8px; font-size:11px; font-weight:bold; }}
QLabel#heroSub[tone="warn"] {{ color:{t['warn']}; font-weight:bold; }}
QPushButton#primary[sel="true"] {{ background:{t['warn']}; border-color:{t['warn']}; }}
QPushButton#pill[sel="true"] {{ background:{t['warn_bg']}; color:{t['warn']}; font-weight:bold; }}
QPushButton#pill[sel="true"]:hover {{ background:{t['warn_bg']}; color:{t['tx']}; }}
QPushButton#primary:disabled {{ background:{t['soft']}; color:{t['dim']}; border-color:{t['soft']}; }}
QPushButton#danger {{ background:{t['danger_btn']}; color:#ffffff; border:1px solid {t['danger_btn']}; font-weight:bold; border-radius:16px; padding:7px 22px;
    min-height:18px; min-width:24px; }}
QPushButton#danger:hover {{ background:{t['danger_h']}; }}
QPushButton#danger:disabled {{ background:{t['soft']}; color:{t['dim']}; border-color:{t['soft']}; }}
QPushButton#pill {{ background:{t['soft']}; border:none; border-radius:16px; padding:7px 16px; color:{t['tx']}; min-height:18px; }}
QPushButton#pill:hover {{ background:{t['soft_h']}; }}
QPushButton#pill:disabled {{ color:{t['dim']}; }}
QPushButton#link, QPushButton#toggle {{ border:none; background:transparent; color:{t['acc']}; padding:4px 8px; }}
QPushButton#link:hover, QPushButton#toggle:hover {{ color:{t['acc_h']}; background:transparent; }}
QPushButton#toggle {{ font-weight:bold; }}
QPushButton#nextBtn {{ text-align:left; background:transparent; border:none; border-radius:10px; padding:8px; }}
QPushButton#nextBtn:hover {{ background:{t['soft']}; }}

/* 输入框 */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QPlainTextEdit, QTextEdit {{ background:{t['card']}; border:1px solid {t['line']};
    border-radius:8px; padding:6px 9px; selection-background-color:{t['acc']}; selection-color:#ffffff; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus, QPlainTextEdit:focus {{ border-color:{t['acc']}; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border:none; width:24px; }}
QComboBox::down-arrow, QDateEdit::down-arrow {{ image:url({down}); width:12px; height:12px; }}
QSpinBox::up-button, QSpinBox::down-button {{ border:none; width:20px; background:transparent; }}
QSpinBox::up-arrow {{ image:url({up}); width:10px; height:10px; }}
QSpinBox::down-arrow {{ image:url({down}); width:10px; height:10px; }}
QComboBox QAbstractItemView {{ background:{t['card']}; border:1px solid {t['line']}; selection-background-color:{t['acc_bg']};
    selection-color:{t['tx']}; outline:0; padding:4px; }}
QLineEdit#search {{ background:{t['soft']}; border:1px solid transparent; border-radius:16px; padding:6px 12px; }}
QLineEdit#search:focus {{ background:{t['card']}; border-color:{t['acc']}; }}
QPlainTextEdit#log {{ color:{t['mu']}; background:{t['card']}; font-size:12px; }}
QCheckBox {{ spacing:6px; color:{t['tx']}; }}
QCheckBox::indicator, QTreeView::indicator, QTableView::indicator {{ width:16px; height:16px; border-radius:5px;
    border:1.5px solid {t['dim']}; background:{t['card']}; }}
QCheckBox::indicator:hover, QTreeView::indicator:hover {{ border-color:{t['acc']}; }}
QCheckBox::indicator:checked, QTreeView::indicator:checked, QTableView::indicator:checked {{ background:{t['acc']};
    border-color:{t['acc']}; image:url({chk}); }}
QCheckBox::indicator:disabled, QTreeView::indicator:disabled {{ background:{t['soft']}; border-color:{t['line']}; }}

/* 列表 / 表格 */
QTreeWidget, QTableWidget {{ background:{t['card']}; alternate-background-color:{t['alt']}; border:1px solid {t['line']};
    border-radius:14px; gridline-color:{t['line2']}; outline:0; }}
QFrame#panel QTreeWidget, QFrame#panel QTableWidget {{ border:none; border-radius:0; }}
QTreeWidget::item, QTableWidget::item {{ padding:6px 4px; border:none; }}
QTreeWidget::item:hover, QTableWidget::item:hover {{ background:{t['soft']}; }}
QTreeWidget::item:selected, QTableWidget::item:selected {{ background:{t['sel']}; color:{t['tx']}; }}
QHeaderView {{ background:transparent; }}
QHeaderView::section {{ background:{t['card']}; border:none; border-bottom:1px solid {t['line']}; padding:9px 8px;
    font-weight:bold; color:{t['mu']}; font-size:12px; }}
QTableCornerButton::section {{ background:{t['card']}; border:none; }}
QSplitter::handle {{ background:transparent; width:10px; }}

QLabel#scope {{ color:{t['ok']}; font-weight:bold; padding:2px 0; }}
QLabel#scope[sel="true"] {{ background:{t['acc_bg']}; color:{t['acc']}; border-radius:8px; padding:4px 10px; }}
QFrame#chipBox {{ background:{t['soft']}; border:none; border-radius:13px; padding:0; }}
QLabel#chip {{ background:{t['soft']}; border:none; border-radius:13px; padding:4px 12px; color:{t['tx2']}; font-size:12px; }}
QLabel#chipText {{ color:{t['tx']}; font-size:12px; font-weight:bold; background:transparent; }}
QLabel#warnPill {{ background:{t['warn_bg']}; color:{t['warn']}; border-radius:13px; padding:4px 12px; font-weight:bold; }}
QLabel#warnPill[tone="good"] {{ background:{t['ok_bg']}; color:{t['ok']}; }}
QLabel#hint {{ background:{t['warn_bg']}; color:{t['warn']}; border:none; border-radius:10px; padding:9px 12px; font-weight:bold; }}
QGroupBox {{ background:{t['card']}; border:1px solid {t['line']}; border-radius:12px; margin-top:18px; padding:14px 12px 10px 12px; }}
QGroupBox::title {{ subcontrol-origin:margin; left:12px; padding:0 4px; color:{t['tx']}; font-weight:bold; font-size:14px; }}
QScrollBar:vertical {{ background:transparent; width:10px; margin:2px; }}
QScrollBar::handle:vertical {{ background:{t['line']}; border-radius:4px; min-height:30px; }}
QScrollBar::handle:vertical:hover {{ background:{t['dim']}; }}
QScrollBar:horizontal {{ background:transparent; height:10px; margin:2px; }}
QScrollBar::handle:horizontal {{ background:{t['line']}; border-radius:4px; min-width:30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height:0; width:0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background:transparent; }}
QToolTip {{ background:{t['card']}; color:{t['tx']}; border:1px solid {t['line']}; padding:6px; border-radius:6px; }}
QMenu {{ background:{t['card']}; border:1px solid {t['line']}; padding:6px; border-radius:10px; }}
QMenu::item {{ padding:7px 22px 7px 14px; border-radius:6px; color:{t['tx']}; }}
QMenu::item:selected {{ background:{t['acc_bg']}; color:{t['acc']}; }}
QMenu::item:disabled {{ color:{t['dim']}; }}
QMenu::separator {{ height:1px; background:{t['line']}; margin:4px 8px; }}
QMessageBox QLabel {{ font-size:13px; }}
QDialogButtonBox QPushButton {{ min-width:72px; }}
"""


def palette(t: dict) -> QPalette:
    pal = QPalette()
    for role, key in ((QPalette.ColorRole.Window, "bg"), (QPalette.ColorRole.Base, "card"),
                      (QPalette.ColorRole.AlternateBase, "alt"), (QPalette.ColorRole.Text, "tx"),
                      (QPalette.ColorRole.WindowText, "tx"), (QPalette.ColorRole.ButtonText, "tx"),
                      (QPalette.ColorRole.Button, "card"), (QPalette.ColorRole.Highlight, "sel"),
                      (QPalette.ColorRole.HighlightedText, "tx"), (QPalette.ColorRole.ToolTipBase, "card"),
                      (QPalette.ColorRole.ToolTipText, "tx"), (QPalette.ColorRole.PlaceholderText, "dim"),
                      (QPalette.ColorRole.Link, "acc")):
        pal.setColor(role, QColor(t[key]))
    return pal


def apply(app, name: str) -> str:
    """套用主题;名字不认识(老版本存的「抖音创作者」这些)就用默认的。返回实际用的名字。
    也把列表状态行的底色换成这套的(淡淡的一层,状态本身用彩色胶囊标)。"""
    if name not in THEMES:
        name = DEFAULT
    t = THEMES[name]
    _CUR.clear()
    _CUR.update(t)
    app.setStyle("Fusion")
    app.setPalette(palette(t))
    app.setStyleSheet(qss(t))
    import gui.api_tab as A
    import gui.window as W
    from PySide6.QtGui import QBrush
    A.YELLOW, A.RED, A.GREEN, A.ORANGE = (QColor(t["rows"][k]) for k in ("yellow", "red", "green", "orange"))
    A.GREY = QColor(t["dim"])
    W.YELLOW, W.GREEN = QBrush(QColor(t["rows"]["yellow"])), QBrush(QColor(t["rows"]["green"]))
    W.GREY = QBrush(QColor(t["rows"]["ready"]))
    W.RED = QBrush(QColor(t["rows"]["red"]))
    for w in app.topLevelWidgets():                    # 设置里换了马上生效:自己画的部件重画一下
        w.update()
    return name
