"""「接口发(16个号)」页:游戏 / 动漫 16 个号,用企鹅号官方接口直接发(不用罐头)。

先检查(横屏 / 标题里有别的平台 / 话题问题)→ 横屏一键转竖、整理话题(写法固定规矩改 + 多个的 AI 留一个)/
批量改成指定话题(都能撤销)、平台名你自己改 → 发布:传视频 → 发布 → 发成了挪到「X月发布视频\\企鹅号\\企鹅号软件发布\\游戏名」,
记进「记录」。列表按号分组,每个号能收起 / 展开。

规矩(用户 2026-10-15):选了东西,下面每个按钮都只管选中的(选号 = 这个号全部);没选就管列表里看得见的全部。
发布永远要人点「发」确认(这个软件里没有自动发布)。
"""
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
                               QInputDialog, QLabel, QLineEdit, QMenu, QMessageBox, QPlainTextEdit, QPushButton,
                               QSizePolicy, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from qe import apiacc, apisrc, checks, plan, titleclean, topic, vertical, wmstore
from qe.config import bj_now, bj_str, data_dir
from qe.records import pkey
from html import escape as html_escape

COLS = ["号 / 标题(= 文件名)", "画面", "要处理的", "状态"]
YELLOW, RED, GREEN, ORANGE = QColor("#fff3c4"), QColor("#ffd6d6"), QColor("#d9f2d9"), QColor("#ffd9a8")
GREY = QColor("#999999")
ROW = Qt.ItemDataRole.UserRole            # 视频那一行:存它在 self.videos 里的下标;号那一行:存 -1
NICK = Qt.ItemDataRole.UserRole + 1       # 号那一行:存号的昵称
CLEAR = "-"                               # emit(i, CLEAR):把这行的状态清掉(回到按检查结果显示)
PROGRESS = -2                             # emit(PROGRESS, 文字):发布进度,写在下面那行绿字里
FAILED = ("没发成", "没发:", "转竖屏失败")      # 「没发:号的密钥坏了」= 原来的「没轮到」


def friendly(e) -> tuple[str, str]:
    """出错 → (行里显示的大白话, 日志里写的:大白话 + 下一步)。原始报错放在鼠标悬停里。"""
    from qe.omapi import ApiError
    s = str(e)
    code = getattr(e, "code", "") if isinstance(e, ApiError) else ""
    if getattr(e, "fatal", False):
        return "没发成:号的密钥不对", "这个号的密钥不对或过期了 —— 去左下角「设置」里点「登录取钥匙…」,扫码登录这个号,软件会自己换上新钥匙"
    if code == "40023" or "invalid_file_upload" in s:
        return "没发成:平台不收这个文件", "平台不收这个视频文件(可能坏了 / 格式不对)—— 先双击打开看能不能播,重新导出再发"
    if "网络连不上" in s or "超时" in s:
        return "没发成:网断了", "网络有问题 —— 网好了再点「现在发布」,会接着发没发的(发过的不会重发)"
    if "标题" in s and ("长" in s or "字" in s):
        return "没发成:标题不合格", f"平台说标题不行({s})—— 右键「改标题」改短一点再发"
    return "没发成", s


class Job(QThread):
    """在后台跑 fn(emit, stopped);emit(行号, 状态文字) 刷新那一行,emit(-1, 文字) 写日志,emit(-2, 文字) 写进度。"""
    row = Signal(int, str)
    done = Signal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self.fn = fn
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        try:
            msg = self.fn(lambda i, t: self.row.emit(i, t), self._stop.is_set)
            self.done.emit(msg or "")
        except Exception as e:
            self.done.emit(f"出错:{type(e).__name__}: {e}")


class _Taken(Exception):
    """要发的时候发现这个文件别的号已经发过 / 正在发(两个号手选了同一个文件夹)。"""


def _num(x, default: int) -> int:
    """设置里手写坏了的数字(「5秒」)也不让发布按钮没反应。"""
    try:
        return int(float(str(x).strip().rstrip("秒")))
    except (TypeError, ValueError):
        return default


def _retry(fn, n: int = 3):
    """记录库偶尔被别的程序锁住:等一下再试几次。"""
    import sqlite3
    for k in range(n):
        try:
            return fn()
        except sqlite3.OperationalError:
            if k == n - 1:
                raise
            time.sleep(2)


def ask(parent, title: str, text: str, yes: str = "好", no: str = "先不", detail: str = "", default_no: bool = False,
        head: str = "", extra: str = "", on_extra=None, danger: bool = False) -> bool:
    """中文按钮的确认框(审查:Yes / No 是英文)。detail = 点「显示详细信息」才看得到的细节(确认框别太长)。
    head = 第一行红字加粗(要人一眼看到的:「现在马上发出去」「这次会自动点发布」);
    extra = 第三个按钮(比如「改成定时…」),点了调 on_extra(),返回 False;danger = 「好」那个按钮画红(会真发出去的)。"""
    box = QMessageBox(QMessageBox.Icon.Question, title, text, QMessageBox.StandardButton.NoButton, parent)
    if head:
        import html
        box.setTextFormat(Qt.TextFormat.RichText)
        from gui.theme import cur
        box.setText(f'<p style="color:{cur()["danger"]};font-weight:bold">{html.escape(head)}</p>'
                    + html.escape(text).replace("\n", "<br>"))
    b_yes = box.addButton(yes, QMessageBox.ButtonRole.YesRole)
    if danger:
        b_yes.setObjectName("danger")
    b_extra = box.addButton(extra, QMessageBox.ButtonRole.ActionRole) if extra else None
    b_no = box.addButton(no, QMessageBox.ButtonRole.NoRole)
    if detail:
        box.setDetailedText(detail)
    box.setDefaultButton(b_no if default_no else b_yes)
    box.setEscapeButton(b_no)
    box.exec()
    if b_extra is not None and box.clickedButton() is b_extra and on_extra:
        on_extra()
    return box.clickedButton() is b_yes


class _SayBox:
    """定时发布没人看着:代替 QMessageBox,要弹的话写进日志(最后一句记在 last,定时没发成时说清楚为什么)。"""

    def __init__(self, say):
        self._say = say
        self.last = ""

    def information(self, _parent, title, text):
        self.last = f"{title}:" + str(text).replace("\n", " ")
        self._say("⚠ " + self.last)

    warning = information


class ApiTab(QWidget):
    def __init__(self, st, rec, say, parent=None):
        super().__init__(parent)
        self.st, self.rec, self._say_main = st, rec, say
        self.videos: list[apisrc.ApiVideo] = []
        self.state: dict[int, str] = {}           # 行号 → 状态文字(发布中 / 已发 / 没发成 …)
        self.why: dict[int, str] = {}             # 行号 → 原始报错(鼠标悬停看)
        self.items: dict[int, QTreeWidgetItem] = {}
        self.groups: dict[str, QTreeWidgetItem] = {}
        self.open_accounts: set[str] = set()      # 展开着的号(换日期 / 刷新后还展开着)
        self.cache: dict[str, tuple] = {}         # 检查结果:pkey(路径) → ((大小, 修改时间), checks);刷新 / 撤销后不用重新检查
        self.job: Job | None = None
        self.ledger = topic.Ledger(data_dir() / "话题改名台账.json")
        self._auto = ""                           # 定时发布:"" / "等检查"(到点了,等自动检查做完)/ "发"(正在发)
        self._blocked: dict[str, int] = {}        # 这天可能整批放错了的号(像别的游戏的条数),人确认前整批不发
        self._dups: dict[int, str] = {}           # 重复的(发过同名的 / 同一天同名的):不发
        self._sent_keys: dict = {}
        from qe import gamecheck
        gamecheck.configure(st)
        self._build()
        from gui.schedule import Scheduler
        self.sched = Scheduler(self.st, "api", self.say, self._sched_fire, self._sched_changed, self, problem=self._sched_note)
        self._notice0 = bool(((self.st.get("sched_notice") or {}).get("api") or {}).get("msg"))   # 打开时就有的才弹(含刚错过的)
        self._sched_changed()
        self.reload_dates()
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1500, self._pop_notice)     # 上次定时没开始 / 没发成:打开软件弹一次

    # ---------------- 界面 ----------------
    def _build(self):
        """用户 2026-10-18 选的「G 一键驾驶舱」:最上面一句大字(37 条可以发了)+ 大按钮;问题做成卡片,点了就处理;
        「看每个号的明细」点开才出列表(展开 / 收起有动画,记住上次)。按钮还是原来那些按钮,只是换了地方。"""
        from gui.widgets import Hero, MenuButton, PillDelegate, ProbCard, Segmented, StatCards
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 18, 24, 14)
        v.setSpacing(12)
        self._gap = QWidget()                            # 明细收起时大字往下放一点(居中好看)
        self._gap.setFixedHeight(0)
        v.addWidget(self._gap)
        self.hero = Hero(open_=False)
        m = self.hero.meta
        m.addWidget(QLabel("要发哪天的:"))
        self.c_date = QComboBox()
        self.c_date.setMinimumWidth(130)
        self.c_date.currentIndexChanged.connect(self.load)
        m.addWidget(self.c_date)
        self.b_reload = b = QPushButton("刷新")
        b.setObjectName("link")
        b.setToolTip("重新读一遍素材文件夹(F5)")
        b.clicked.connect(self.reload_dates)
        m.addWidget(b)
        self.lab = QLabel("")
        self.lab.setObjectName("heroMeta")
        self.lab.setMaximumWidth(380)
        m.addWidget(self.lab)
        self.b_pick = b = QPushButton("给号选文件夹…")
        b.setObjectName("link")
        b.setToolTip("像旧软件的「选择」:手动给一个号挑这天要发的文件夹(比如电竞情报馆的「2电竞赛事」)。\n"
                     "选了以后这个号这天只发那个文件夹里的视频,不再自动找。右键列表里的号 / 视频也能选 / 取消。")
        b.clicked.connect(lambda: self.pick_folder())
        m.addWidget(b)
        self.b_prev = b = QPushButton("")                # 「昨天 10.20 还剩 6 条没发 · 看看」(打开默认选今天以后,昨天剩的单独说)
        b.setObjectName("link")
        b.setProperty("tone", "warn")
        b.clicked.connect(lambda: self.set_day(self._prev[0]) if getattr(self, "_prev", None) else None)
        b.hide()
        m.addWidget(b)
        # 大按钮那一排:定时离「现在发布」远一点(用户 2026-10-17 想定时点成了发布,10 条提前发出去只能去后台删)
        a = self.hero.acts
        self.b_sched = QPushButton("到点自动发…")
        self.b_sched.setObjectName("pill")
        self.b_sched.setMinimumHeight(36)
        self.b_sched.setToolTip("选哪天的素材、几点开始:到点软件自己点「发布」(全部,不管选中),发到完为止。\n"
                                "话题、标准竖屏先处理好;到点还有问题的不发。电脑别关机,软件和创作罐头开着(传封面要用罐头)。")
        self.b_sched.clicked.connect(self.schedule_clicked)
        a.addWidget(self.b_sched)
        self.lab_sched = QLabel("")
        self.lab_sched.setObjectName("warnText")
        self.lab_sched.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lab_sched.mousePressEvent = self._ack_notice
        a.addWidget(self.lab_sched)
        a.addSpacing(28)
        self.b_unsel = QPushButton("")                  # 选中了东西时出来:「选中 1 条 × 取消选中」(老手 / 新员工试用 2026-10-21)
        self.b_unsel.setObjectName("pill")              # 和「到点自动发…」一样的圆胶囊,橙色字
        self.b_unsel.setProperty("sel", True)
        self.b_unsel.setToolTip("现在只管选中的;点一下(或按 Esc)取消选中,按钮回到管全部")
        self.b_unsel.clicked.connect(lambda: self.tree.clearSelection())
        self.b_unsel.hide()
        a.addWidget(self.b_unsel)
        self.b_pub = QPushButton("现在发布")
        self.b_pub.setMinimumHeight(40)
        self.b_pub.setObjectName("primary")          # 主题里给它主色(gui/theme.py)
        self.b_pub.setToolTip("没有问题的(竖屏、标题里没别的平台、话题对、没发过的)用接口发出去;有问题的不发。点了会先弹框确认。\n"
                              "发成了挪到「X月发布视频\\企鹅号\\企鹅号软件发布\\游戏名」(设置里能改)。")
        self.b_pub.clicked.connect(lambda: self.run_publish())
        a.addWidget(self.b_pub)
        self.b_stop = QPushButton("停")
        self.b_stop.setObjectName("danger")
        self.b_stop.setMinimumHeight(34)
        self.b_stop.clicked.connect(self.stop)
        a.addWidget(self.b_stop)
        self._head = QWidget()                           # 大字 + 卡片 + 「看明细」:收起时收在中间一栏(用户 2026-10-18:铺满太散,高级感没了)
        # 发布进度(用户 2026-10-19 选的 B):纸飞机进度条 + 每秒网速 + 正在发哪条 + 成功 / 没发成 + 还要多久;平时藏着
        from gui.widgets import BusyDots, PubStrip
        self.pub_strip = PubStrip()
        self.hero.extra.addWidget(self.pub_strip)
        self.dots = BusyDots()
        self.dots.hide()
        self.hero.meta.addWidget(self.dots)
        self._pub = None
        self._fun = ""
        self._pub_timer = QTimer(self)
        self._pub_timer.setInterval(1000)                # 每秒量一次网速
        self._pub_timer.timeout.connect(self._pub_tick)
        self._fun_timer = QTimer(self)
        self._fun_timer.setInterval(7000)                # 小字 7 秒换一句
        self._fun_timer.timeout.connect(self._fun_next)
        hv = QVBoxLayout(self._head)
        hv.setContentsMargins(0, 0, 0, 0)
        hv.setSpacing(14)
        hv.addWidget(self.hero)
        v.addWidget(self._head)

        # 问题卡片:问题和处理它的按钮放一起(原来一排 8 个按钮一样大,不知道点哪个)
        self.b_check = MenuButton("检查")              # 鼠标挪上去弹出:普通检查 / 高级检查(用户 2026-10-16)
        self.b_check.setToolTip("普通检查:是不是竖屏、标题里有没有别的平台的名字、话题对不对(换日期 / 刷新会自动做)。\n"
                                "高级检查:再查一遍有没有别的平台的水印 / 广告图标(B站、抖音、快手、得物、转转 …),慢一些。")
        self.b_check.add("普通检查", lambda: self.run_check(),
                         "竖屏、标题里的平台名、话题。换日期 / 刷新以后会自动做")
        self.b_check.add("高级检查(再查水印)", lambda: self.run_check(deep=True),
                         "普通检查 + 查水印 / 广告图标。普通检查过的只查水印;查过水印、文件没变的不再查")
        self.b_check.add("查口播广告", lambda: self.run_ads(),
                         "把视频里说的话转成文字,找「点击下方链接」「扫码」「得物」这类广告词,标出第几秒。转过的不再转")
        self.b_vert = QPushButton("转标准竖屏")
        self.b_vert.setToolTip("横屏、偏方(3:4 / 正方形)的转成标准竖屏 1080×1920:上下糊底、中间原画面。\n转好以后原来的横屏视频直接删掉(转失败的不动)。")
        self.b_vert.clicked.connect(lambda: self.run_vertical())
        self.b_blur = MenuButton("去水印 / 广告")
        self.b_blur.setToolTip("查到的水印糊掉、查到的口播广告剪掉。原片都留着(「水印原片」「广告原片」),不删。")
        self.b_blur.add("模糊水印", lambda: self.run_blur(),
                        "高级检查查到水印的,把水印那块糊掉(只糊水印出现的那几段)。原片挪进同文件夹的「水印原片」")
        self.b_blur.add("剪掉口播广告", lambda: self.run_cut(),
                        "查口播广告查到的那几句剪掉(前后各多剪 0.3 秒)。原片挪进同文件夹的「广告原片」")
        self.b_topic = QPushButton("整理标题")
        self.b_topic.setToolTip("一键把标题弄干净:\n· 莫名其妙的乱码尾巴(一长串数字英文符号)、「@某某 / @某平台」那段删掉,不用 AI;\n· 话题写法不对的(结尾空格、「# 话题」「##话题」、话题前粘的 n、重复的)按固定规矩改,不用 AI;\n"
                                "· 挂了好几个话题的,AI 挑最好搜的留一个(游戏 / 剧 / 电影 / 动漫名优先)。\n改文件名,同名封面跟着改。能撤销。")
        self.b_topic.clicked.connect(lambda: self.run_topic())
        self.b_settopic = QPushButton("批量改话题…")
        self.b_settopic.setToolTip("话题全换成你填的那一个,比如填「英雄联盟」→ 结尾变成 #英雄联盟。原来没话题的就接在后面。能撤销。\n"
                                   "这个必须先选(选号 = 这个号全部),免得把别的游戏 / 动漫的号也改了。")
        self.b_settopic.clicked.connect(lambda: self.set_topic())
        self.b_undo = QPushButton("撤销上次改名")
        self.b_undo.clicked.connect(self.undo_topic)
        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.card_v = ProbCard("rotate", "横屏 / 偏方", [self.b_vert])
        from gui.widgets import help_dot
        self.card_v.add_help("偏方")
        self.card_t = ProbCard("tag", "标题 / 话题", [self.b_topic])
        self.card_w = ProbCard("scan", "水印 / 口播广告", [self.b_check, self.b_blur])
        for c in (self.card_v, self.card_t, self.card_w):
            cards.addWidget(c, 1)
        hv.addLayout(cards)

        self.b_detail = QPushButton("")
        self.b_detail.setObjectName("toggle")
        self.b_detail.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_detail.clicked.connect(lambda: self.set_detail(self.detail.isHidden()))
        hv.addWidget(self.b_detail, 0, Qt.AlignmentFlag.AlignHCenter)

        # ---------- 明细(点「看每个号的明细」才出来) ----------
        self.detail = QWidget()
        dv = QVBoxLayout(self.detail)
        dv.setContentsMargins(0, 0, 0, 0)
        dv.setSpacing(8)
        self.cards = StatCards([("all", "这天的视频"), ("ok", "能发"), ("bad", "要处理"), ("sent", "已发"), ("accs", "今天达标")],
                               clickable=("bad", "ok"))
        self.cards.clicked.connect(self._card_clicked)
        self.cards.hide()                                # 数字都在大字和「全部 / 要处理 / 能发 / 已发」上了
        dv.addWidget(self.cards)
        view = QHBoxLayout()
        view.setSpacing(8)
        self.seg = Segmented([("all", "全部"), ("bad", "要处理"), ("ok", "能发"), ("sent", "已发")])
        self.seg.changed.connect(self._seg_changed)
        view.addWidget(self.seg)
        from gui.widgets import help_dot
        view.addWidget(help_dot("要处理"))
        self.k_undone = QPushButton("只看没发完的号")
        self.k_undone.setObjectName("toggle")
        self.k_undone.setCheckable(True)
        self.k_undone.setToolTip("发完的号(能发的都发了 / 今天发够了)先藏起来;发完的号本来就沉在最下面")
        self.k_undone.toggled.connect(lambda _on: self._apply_filter())
        view.addWidget(self.k_undone)
        self.k_bad = QCheckBox("只看有问题的")
        self.k_bad.setToolTip("只显示要处理的(横屏 / 标题有别的平台 / 话题问题 / 没发成 / 结果不明)")
        self.k_bad.toggled.connect(self._kbad_toggled)
        self.k_bad.hide()                                # 就是「要处理」那一格
        view.addWidget(self.k_bad)
        view.addStretch(1)
        self.lab_sum = QLabel("")
        self.lab_sum.setObjectName("muted")
        view.addWidget(self.lab_sum)
        self.e_find = QLineEdit()
        self.e_find.setObjectName("search")
        self.e_find.setPlaceholderText("搜标题…(Ctrl+F)")
        self.e_find.setClearButtonEnabled(True)
        self.e_find.setMaximumWidth(220)
        self.e_find.textChanged.connect(lambda t: (None if t.strip() else self.tree.clearSelection(), self._apply_filter()))
        view.addWidget(self.e_find)
        self.b_more = MenuButton("更多")
        self.b_more.setToolTip("不常用的:全部展开 / 收起、批量改话题、撤销上次改名")
        self.b_more.menu_.aboutToShow.connect(self._more_menu)
        view.addWidget(self.b_more)
        dv.addLayout(view)

        panel = QFrame()
        panel.setObjectName("panel")
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(1, 1, 1, 1)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(len(COLS))
        self.tree.setHeaderLabels(COLS)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setToolTip("点号前面的小三角(或双击号)展开 / 收起;按住 Ctrl / Shift 多选;选中号 = 选中这个号的全部视频。\n"
                             "双击一条视频:打开它所在的文件夹。右键:检查 / 整理标题 / 改标题 / 发布 / 换文件夹。")
        self.tree.itemDoubleClicked.connect(self._double)
        self.tree.itemExpanded.connect(lambda it: self._remember(it, True))
        self.tree.itemCollapsed.connect(lambda it: self._remember(it, False))
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        self.tree.setUniformRowHeights(False)          # 号那一行高一点(头像)、视频那一行矮一点
        self.tree.setAnimated(True)
        self.tree.setIndentation(20)
        from gui.widgets import ApiTreeDelegate
        self.tree.setItemDelegate(ApiTreeDelegate(self.tree))
        hh = self.tree.header()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        for i, wd in ((1, 96), (2, 250), (3, 230)):
            self.tree.setColumnWidth(i, wd)
        pl.addWidget(self.tree)
        dv.addWidget(panel, 1)

        # 这次管哪些(绿字)+ 取消选择 + 最近一句日志
        scope = QHBoxLayout()
        self.lab_scope = QLabel("")
        self.lab_scope.setObjectName("scope")
        self.lab_scope.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        scope.addWidget(self.lab_scope, 3)
        self.b_clear = QPushButton("取消选择")
        self.b_clear.setToolTip("不选了:下面的按钮回到管全部(Esc)")
        self.b_clear.clicked.connect(self.tree.clearSelection)
        scope.addWidget(self.b_clear)
        self.lab_last = QLabel("")
        self.lab_last.setObjectName("muted")
        self.lab_last.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        scope.addWidget(self.lab_last, 2)
        self.b_log = QPushButton("展开日志")
        self.b_log.setObjectName("link")
        self.b_log.clicked.connect(self._toggle_log)
        scope.addWidget(self.b_log)
        dv.addLayout(scope)
        self.logbox = QPlainTextEdit()
        self.logbox.setObjectName("log")
        self.logbox.setReadOnly(True)
        self.logbox.setMaximumBlockCount(3000)
        self.logbox.setMaximumHeight(200)
        self.logbox.hide()                               # 平时只露最近一句(体验报告:日志太占地方),「展开日志」看全
        dv.addWidget(self.logbox)
        v.addWidget(self.detail, 1)
        self._filler = QWidget()                         # 明细收起时把上面的东西顶在上面
        v.addWidget(self._filler, 1)
        self.tree.itemSelectionChanged.connect(self._update_scope)
        self.on_badge = None                             # 主窗口给:左边导航「16 个号」后面的数字
        self.set_detail(bool(self.st.get("api_detail_open", False)), animate_=False)

        # 快捷键
        for key, owner, fn in (("F5", self, self.reload_dates),
                               ("Ctrl+F", self, lambda: (self.set_detail(True), self.e_find.setFocus(), self.e_find.selectAll())),
                               ("Escape", self.tree, self.tree.clearSelection),
                               ("F2", self.tree, self._edit_current)):
            sc = QShortcut(QKeySequence(key), owner)
            sc.activated.connect(fn)
        self._busy(False)

    def set_detail(self, on: bool, animate_: bool = True):
        """看每个号的明细 / 收起:大字区跟着变大变小,列表从下面拉开(用户 2026-10-18 要丝滑)。"""
        from gui.widgets import animate, slide
        on = bool(on)
        if self.st.get("api_detail_open", False) != on:
            self.st["api_detail_open"] = on
        self.hero.set_open(on, animate_=animate_)
        self._filler.setVisible(not on)
        self._head.layout().setSpacing(14 if on else 30)
        self.lab.setVisible(on)                          # 收起时上面只留日期:一长串说明 / 给号选文件夹 展开才露(「更多」里也有)
        self.b_pick.setVisible(on)
        self.b_pub.setMinimumHeight(40 if on else 50)
        self.b_sched.setMinimumHeight(36 if on else 46)
        self.b_stop.setMinimumHeight(36 if on else 46)
        self.b_stop.setMinimumWidth(72 if on else 96)
        self._fit_head()
        if animate_ and self.isVisible():
            slide(self.detail, on)
            animate(self._gap, "gap", self._gap.height(), 0 if on else self._gap_h(), 360, lambda h: self._gap.setFixedHeight(int(h)))
        else:
            self.detail.setVisible(on)
            self._gap.setFixedHeight(0 if on else self._gap_h())
        self._detail_text()

    # ---------------- 发布进度(大字区下面那块) ----------------
    @staticmethod
    def _net_sent():
        """整台电脑一共往外传了多少字节(用户 2026-10-19 选的:每秒量整台电脑,别的程序在传也会算进去)。"""
        try:
            import psutil
            return psutil.net_io_counters().bytes_sent
        except Exception:
            return None

    def _pub_begin(self, total: int):
        from gui.widgets import fun_line
        self._pub = {"total": total, "done": 0, "ok": 0, "fail": 0, "t0": time.time(), "cur": None, "pct": "", "end": False}
        self._net = (self._net_sent(), time.time())
        s = self.pub_strip
        s.track.done = False
        s.track._set(0)
        s.track.set_running(True)
        s.spark.vals = []
        s.set_speed(None)
        s.set_numbers(0, 0, "准备上传第一条…", "算一下要多久…")
        self.hero._extra_w.show()
        self.dots.show()
        self._fun = fun_line()
        self._pub_timer.start()
        self._fun_timer.start()

    def _pub_progress(self, t: str):
        import re
        p = self._pub
        m = re.match(r"正在发 (\d+)/(\d+) · 成功 (\d+) · 没发成 (\d+)", t or "")
        if not p or p["end"] or not m:
            return
        p["done"], p["total"], p["ok"], p["fail"] = (int(x) for x in m.groups())
        self.pub_strip.track.set_value(p["done"] / max(1, p["total"]))
        self._pub_show()

    def _pub_show(self):
        p = self._pub
        cur = ""
        i = p.get("cur")
        if i is not None and 0 <= i < len(self.videos):
            v = self.videos[i]
            title = v.title if len(v.title) <= 16 else v.title[:16] + "…"
            cur = f"正在发 <b>{html_escape(v.account)}</b> · 《{html_escape(title)}》 {p.get('pct', '')}"
        if p["done"]:
            rem = (time.time() - p["t0"]) / p["done"] * (p["total"] - p["done"])
            eta = "不到 1 分钟" if rem < 60 else f"还要大约 {round(rem / 60)} 分钟"
        else:
            eta = "算一下要多久…"
        self.pub_strip.set_numbers(p["ok"], p["fail"], cur or "准备上传…", eta)

    def _pub_tick(self):
        """每秒:量一次网速、更新正在发哪条 / 还要多久。"""
        if not self._pub or self._pub["end"]:
            return
        now, (b0, t0) = time.time(), self._net
        b = self._net_sent()
        if b is not None and b0 is not None and now > t0:
            self.pub_strip.set_speed((b - b0) / (now - t0) / 1024 / 1024)
        self._net = (b, now)
        self._pub_show()

    def _fun_next(self):
        from gui.widgets import fade_in, fun_line
        if not self._pub or self._pub["end"]:
            return
        self._fun = fun_line()
        self.hero.sub.setText(self._fun)
        fade_in(self.hero.sub, 450)

    def _pub_end(self, msg: str):
        p = self._pub
        if not p or p["end"]:
            return
        p["end"] = True
        self._pub_timer.stop()
        self._fun_timer.stop()
        self.dots.hide()
        s = self.pub_strip
        s.track.set_running(False)
        s.track.done = p["fail"] == 0 and p["done"] >= p["total"]
        s.track.set_value(p["done"] / max(1, p["total"]))
        s.set_speed(None)
        mins = (time.time() - p["t0"]) / 60
        took = "用时不到 1 分钟" if mins < 1 else f"用时 {round(mins)} 分钟"
        if "停下了没发" in msg:
            line = "停好了,发过的都记着呢"
        elif p["fail"]:
            line = "差一点点全中,没发成的再点一下「再发一次没发成的」就好"
        else:
            line = "全部收工,今天也很高效"
        s.set_numbers(p["ok"], p["fail"], line, took)
        if p["ok"] and self.isVisible():
            from gui.widgets import Confetti
            Confetti(self.hero)                         # 发完撒一把彩带

    def _spill(self, nick: str, emit=None, only_day: str = "") -> int:
        """这个号今天发够了:列表里它还没发的(没发过 / 没发成的)连同同名封面挪到明天的日期文件夹(没有就建,和这天的放一起)。
        手选的文件夹(名字不是日期)不挪,明天接着从那里发。only_day = 只挪这个日期文件夹里的(打开页面时自动挪用)。返回挪了几条。"""
        tmr = plan.tomorrow_folder()
        n = 0
        for i, v in enumerate(self.videos):
            if v.account != nick or self.state.get(i, "").startswith("已发") or self.rec.status_of(v.path) or not os.path.isfile(v.path):
                continue
            d = os.path.dirname(v.path)
            dk = apisrc.date_key(os.path.basename(d))
            if not dk or (only_day and dk != only_day) or os.path.basename(d) == tmr:
                continue
            dst = os.path.join(os.path.dirname(d), tmr)
            try:
                stem = os.path.splitext(os.path.basename(v.path))[0].strip()
                covers = [os.path.join(d, x) for x in os.listdir(d)          # 同名封面:名字前后多个空格也认(2026-10-20 实测有)
                          if os.path.splitext(x)[1].lower() in (".jpg", ".jpeg", ".png", ".webp") and os.path.splitext(x)[0].strip() == stem]
                for f in [v.path] + covers:
                    plan.move_noclobber(f, dst)
                n += 1
                if emit:
                    emit(i, f"挪到明天({tmr})")
            except OSError as e:
                (emit or (lambda *_a: None))(-1, f"「{v.title}」挪不到明天的文件夹:{e}")
        if n:
            (emit or (lambda _i, m: self.say(m)))(-1, f"「{nick}」今天发够规定条数了,还没发的 {n} 条挪到明天的文件夹 {tmr}")
        return n

    def _auto_spill(self) -> bool:
        """打开 / 刷新时:今天已经发够规定条数的号,它在今天日期文件夹里还没发的,自动挪到明天(用户 2026-10-20:
        「pubg 这里面剩的咋还没放到下一个文件夹里面」—— 原来只有点了发布才挪)。挪了返回 True(要重读列表)。"""
        if self.st.get("quota_open", False) or self.busy() or getattr(self, "_spilling", False):
            return False
        from qe.config import bj_now
        today_md = f"{bj_now().month}.{bj_now().day}"
        sent = getattr(self, "today_sent", None) or {}
        full = sorted({v.account for v in self.videos if plan.left_today(self.rec, self.st, v.account, sent=sent) == 0})
        return sum(self._spill(n, only_day=today_md) for n in full) > 0

    def unsend_rows(self, rows: list[int]):
        """已发的改回没发(用户 2026-10-24):视频挪回原来的文件夹、记录改成没发成;之后刷新再发。"""
        from qe import verify
        recs = [(i, self.rec.sent_row(self.videos[i].path)) for i in rows]
        recs = [(i, r) for i, r in recs if r]
        if not recs:
            QMessageBox.information(self, "改回没发", "选中的里没有记成已发的。")
            return
        if not ask(self, "改回没发", f"这 {len(recs)} 条记成已发的,其实没发上?\n\n" +
                   "\n".join(f"· {self.videos[i].title[:30]}" for i, _r in recs[:8]) + ("\n…" if len(recs) > 8 else "") +
                   "\n\n视频挪回原来的文件夹、记录改成没发成,之后能再发(不会自己发)。", "改回没发", "先不", default_no=True):
            return
        notes = [f"{r['title'][:20]}:{m}" for _i, r in recs for m in (verify.unsend(self.rec, r),) if m]
        self.say(f"{len(recs)} 条改回没发" + (";" + ";".join(notes) if notes else "") + " —— 点刷新以后能再发")
        if notes:
            QMessageBox.information(self, "改回没发", "\n".join(notes))
        self.load()

    def verify_one(self, nick: str):
        """去企鹅号核对这一个号今天的(只读);没发上的能拎回来重发。"""
        from gui.verify_dialog import VerifyDialog
        VerifyDialog(self.rec, plan.today(), self, nicks=[nick], st=self.st).exec()
        self.load()

    def add_extra_today(self, nick: str, n: int | None = None) -> int:
        """今天临时多发几条(用户 2026-10-23):今天这个号上限加 n(明天照旧);发够以后挪到明天文件夹里的,挪 n 条回今天的文件夹。
        返回挪回来几条。n 不给就问。"""
        if self.busy() and not getattr(self, "_quiet", False):
            return 0
        if n is None:
            q = plan.quota_on(self.st, nick)
            n, ok = QInputDialog.getInt(self, "今天临时多发", f"「{nick}」今天规定 {q} 条,临时再多发几条?\n"
                                        "(只管今天,明天还是原来的条数;已经挪到明天文件夹的,挪这么多条回今天的文件夹)", 5, 1, 500, 1)
            if not ok:
                return 0
        total = plan.add_extra(self.st, nick, n)
        moved = self._pull_back(nick, n)
        self.say(f"「{nick}」今天临时多发 {total} 条(今天一共 {plan.quota_on(self.st, nick)} 条)" +
                 (f";从明天的文件夹挪回 {moved} 条" if moved else ""))
        self.load()
        return moved

    def _pull_back(self, nick: str, n: int) -> int:
        """把这个号明天文件夹里最前面 n 条(连同名封面)挪回今天的日期文件夹(没有就建)。"""
        tmr = plan.tomorrow_folder()
        today_md = f"{bj_now().month}.{bj_now().day}"
        moved = 0
        for folder in apisrc.account_folder_list(self.roots(), self.known()).get(nick, []):
            src = os.path.join(folder, tmr)
            if moved >= n or not os.path.isdir(src):
                continue
            dst = os.path.join(folder, today_md)
            for v in apisrc._videos_in(src, nick, tmr):
                if moved >= n:
                    break
                if self.rec.status_of(v.path):
                    continue
                stem = os.path.splitext(os.path.basename(v.path))[0].strip()
                try:
                    covers = [os.path.join(src, x) for x in os.listdir(src)
                              if os.path.splitext(x)[1].lower() in (".jpg", ".jpeg", ".png", ".webp") and os.path.splitext(x)[0].strip() == stem]
                    for f in [v.path] + covers:
                        plan.move_noclobber(f, dst)
                    moved += 1
                except OSError as e:
                    self.say(f"「{v.title[:24]}」挪不回今天的文件夹:{e}")
        return moved

    def _quota_cap(self, idxs) -> tuple[int, int]:
        """这些能发的里,按每个号今天还能发几条,真正会发几条;多出来几条(发够以后挪到明天)。"""
        sent = getattr(self, "today_sent", None) or {}
        by: dict[str, int] = {}
        for i in idxs:
            by[self.videos[i].account] = by.get(self.videos[i].account, 0) + 1
        n = extra = 0
        for nick, c in by.items():
            left = plan.left_today(self.rec, self.st, nick, sent=sent)
            k = c if left is None else min(c, left)
            n, extra = n + k, extra + c - k
        return n, extra

    def _gap_h(self) -> int:
        """明细收起时大字往下放多少:窗口高的一成多一点,看着在中间偏上。"""
        content = (self.hero.sizeHint().height() + self.card_v.sizeHint().height() + self.b_detail.sizeHint().height() + 40)
        return max(24, int((self.height() - content) * 0.42))

    def _fit_head(self):
        """收起时大字 + 卡片收在中间一栏(最宽 920);展开时铺满。"""
        lay = self.layout()
        if self._filler.isHidden():
            self._head.setMinimumWidth(0)
            self._head.setMaximumWidth(16777215)
            lay.setAlignment(self._head, Qt.AlignmentFlag(0))
        else:
            self._head.setFixedWidth(min(920, max(560, self.width() - 48)))
            lay.setAlignment(self._head, Qt.AlignmentFlag.AlignHCenter)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "_filler"):
            self._fit_head()
            if self._filler.isVisible():
                self._gap.setFixedHeight(self._gap_h())

    def _detail_text(self):
        n = len(self.videos)
        self.b_detail.setText("︿  收起明细" if not self.detail.isHidden() and self._filler.isHidden()
                              else f"﹀  看每个号的明细({n} 条)" if n else "﹀  看每个号的明细")

    def _more_menu(self):
        mm = self.b_more.menu_
        mm.clear()
        for text, fn, ok, tip in ((self.b_pick.text(), self.b_pick.click, self.b_pick.isEnabled(), self.b_pick.toolTip()),
                                  ("全部展开", lambda: self.expand_all(True), True, ""),
                                  ("全部收起", lambda: self.expand_all(False), True, ""),
                                  (self.b_settopic.text(), self.b_settopic.click, self.b_settopic.isEnabled(), self.b_settopic.toolTip()),
                                  ("批量替换标题里的字…", lambda: self.replace_titles(), bool(self.items) and not self.busy(),
                                   "比如标题里都有「快手热门」:一次换掉 / 删掉(先给你看会改成什么样,改完能撤销)"),
                                  (self.b_undo.text(), self.b_undo.click, self.b_undo.isEnabled(), self.b_undo.toolTip())):
            act = mm.addAction(text, fn)
            act.setEnabled(ok)
            if tip:
                act.setToolTip(tip)

    def _seg_changed(self, k: str):
        """「全部 / 要处理 / 能发 / 已发」:要处理 = 原来的「只看有问题的」。"""
        self._segk = k if k in ("ok", "sent") else "all"
        self.tree.clearSelection()                       # 换了看哪些:原来选中的多半看不见了,别留着悄悄管按钮
        self.k_bad.blockSignals(True)
        self.k_bad.setChecked(k == "bad")
        self.k_bad.blockSignals(False)
        self._apply_filter()

    def _kbad_toggled(self, on: bool):
        if on:
            self._segk = "all"
            self.seg.select("bad")
            if self.detail.isHidden():
                self.set_detail(True)
        elif self.seg.key() == "bad":
            self.seg.select("all")
        self._apply_filter()

    def _hero_update(self, n, sent, checked, ok, bad, fail, unsure, gone, cats):
        """大字:一句话说现在怎么样;下面一行说接下来干什么。按钮就在旁边。"""
        if not hasattr(self, "hero"):
            return
        quota = self._quota_sub()
        if not self.day():
            big, sub, tone = "先选要发哪天的", "在上面「要发哪天的」里挑一天", ""
        elif self.busy() and self._pub and not self._pub["end"]:
            p = self._pub
            big, sub, tone = f"正在发布 · {min(p['done'] + 1, p['total'])} / {p['total']}", self._fun, ""
        elif self.busy() and not getattr(self, "_quiet", False):
            prog = self.lab_scope.text()
            big = "正在发布…" if prog.startswith("正在发") else (getattr(self, "_job_title", "") or "正在处理…")
            sub, tone = prog, ""
        elif not n and not gone and not apiacc.nicks():
            big, sub, tone = "还没有号", "去左下角「设置」→「从旧软件搬账号…」把号搬过来", ""
        elif not n and not gone:
            big, sub, tone = "这天没有视频", "换一天看看,或者点「给号选文件夹…」", ""
        elif fail:
            big, tone = f"{fail} 条没发成", "bad"
            sub = "点「再发一次没发成的」再试;为什么没发成:列表里鼠标放在状态上看"
        elif unsure:
            big, tone = f"{unsure} 条不确定发没发", "warn"
            sub = "去企鹅号后台看一眼,回来在列表里双击它标「发了 / 没发」"
        elif checked < n:
            big, sub, tone = f"正在检查 {n} 条…", f"检查完 {checked} / {n} 条,马上就好", ""
        elif ok:
            big, tone = f"{ok} 条可以发了", ""
            sub = f"还有 {bad} 条有点小问题,处理好能多发 {bad} 条" if bad else "都检查过了,没有问题"
            if getattr(self, "_over", 0):
                sub += f" · 另外 {self._over} 条超过今天的规定条数,发够以后挪到明天"
        elif n + gone and sent + gone >= n + gone:
            big, sub, tone = "这天的都发完了 √", "", "good"
        elif bad:
            big, tone = f"{bad} 条要先处理一下", "warn"
            sub = "处理好就能发(用下面的卡片)"
        else:
            big, sub, tone = "没有能发的", "", ""
        sel = self.selected_rows() if self.day() and not self.busy() else []
        if sel:
            sub = f"现在选中了 {len(sel)} 条 —— 旁边的按钮只管这 {len(sel)} 条(按 Esc 或点「× 取消选中」回到全部)" + ("\n" + sub if sub else "")
        if self._blocked and not self.busy():
            bl = "、".join(f"{k}({c} 条像别的游戏)" for k, c in self._blocked.items())
            sub += ("\n" if sub else "") + (f"可能整批放错了,这些号先不发:{bl} —— 先看一眼:放错了右键那条「放错了:挪到…」;"
                                             "真没放错才右键号「这批确认没放错」")
            tone = tone or "warn"
        if cats.get("o") and not self.busy():
            sub += ("\n" if sub else "") + f"其中 {cats['o']} 条标题里有别的平台的名字,要你自己改(列表里右键「改标题」)"
        if quota and self.day() and not (self.busy() and not getattr(self, "_quiet", False)) and sub != self._fun:
            sub = (sub + " · " if sub else "") + quota
        self.hero.set(big, sub, tone)
        idle = not n or checked < n or not self.day()
        self.card_v.set(f"{cats['v']} 条横屏 / 偏方" if cats["v"] else ("横屏 / 偏方:还没查" if idle else "没有横屏 / 偏方"),
                        "warn" if cats["v"] else ("" if idle else "done"))
        self.card_t.set(f"{cats['t']} 条标题 / 话题要整理" if cats["t"] else ("标题 / 话题:还没查" if idle else "标题 / 话题都没问题"),
                        "warn" if cats["t"] else ("" if idle else "done"))
        self.card_w.set(f"{cats['w']} 条有水印 / 广告" if cats["w"] else "查水印 / 口播广告", "warn" if cats["w"] else "")
        for k, text in (("all", f"全部 {n}"), ("bad", f"要处理 {bad + fail + unsure}"), ("ok", f"能发 {ok}"), ("sent", f"已发 {sent}")):
            self.seg.set_text(k, text)
        self._detail_text()
        if self.on_badge:
            self.on_badge(bad + fail + unsure)

    def say(self, m: str):
        """日志写在这页下面(两页各记各的;体验报告:教育页日志里全是 [接口] 的)。"""
        self.logbox.appendPlainText(f"[{bj_str()[11:]}] {m}")
        if hasattr(self, "lab_last"):
            last = m.strip().splitlines()[0] if m.strip() else ""
            self.lab_last.setText(f"最近 {bj_str()[11:16]}:{last}")
            self.lab_last.setToolTip(m)

    def _toggle_log(self):
        big = self.logbox.isHidden()
        self.logbox.setVisible(big)
        self.b_log.setText("收起日志" if big else "展开日志")
        if big:
            self.logbox.verticalScrollBar().setValue(self.logbox.verticalScrollBar().maximum())

    def _card_clicked(self, key: str):
        """点「要处理」卡片 = 只看有问题的;点「能发」= 取消过滤看全部。"""
        self.k_bad.setChecked(key == "bad")

    def busy(self) -> bool:
        return bool(self.job and self.job.isRunning())

    def _busy(self, on: bool):
        has = bool(self.items)
        quiet = on and getattr(self, "_quiet", False)   # 只是后台自动检查:换日期 / 刷新 / 选文件夹照样能点
        for b in (self.b_check, self.b_vert, self.b_blur, self.b_topic, self.b_settopic, self.b_pub):
            b.setEnabled(not on and has)
        for b in (self.b_undo, self.b_clear):
            b.setEnabled(not on)
        for b in (self.c_date, self.b_pick, self.b_reload):
            b.setEnabled(not on or quiet)
        self.b_stop.setEnabled(on)
        self.b_stop.setVisible(on and not quiet)        # 「停」只在干活的时候出来(大红按钮)
        self.b_pub.setVisible(not (on and not quiet))   # 干活的时候灰掉的「现在发布」先藏起来,只留「停」
        if on and not quiet:
            self.b_unsel.hide()
        if not on:
            self._update_scope()
        if hasattr(self, "hero"):
            self._update_sum()

    def filtering(self) -> bool:
        return (self.k_bad.isChecked() or bool(self.e_find.text().strip()) or getattr(self, "_segk", "all") != "all"
                or (hasattr(self, "k_undone") and self.k_undone.isChecked()))

    def target_rows(self, only: list[int] | None = None) -> list[int]:
        """这次要管哪些:给了就是给的;没给 → 选中的;没选 → 列表里看得见的全部(「只看有问题的」/ 搜索过滤掉的不算)。"""
        if only is not None:
            return [i for i in only if 0 <= i < len(self.videos)]
        return self.selected_rows() or [i for i, it in self.items.items() if not it.isHidden()]

    def _can_send(self, i: int) -> bool:
        v = self.videos[i]
        return (bool(v.checks) and not checks.problems(v) and not self._sent(i) and not self._blocked.get(v.account)
                and i not in self._dups)

    # ---------------- 查重:号 + 标题(用户 2026-10-24:16 个号也要「发过同名的不发、同一天同名只发一条」,和教育号一样) ----------------
    @staticmethod
    def _dkey(account: str, title: str) -> tuple[str, str]:
        """号 + 标题:去掉话题、空格、标点(「xxx #和平精英」和「xxx」算同一条)。"""
        from qe.folders import norm_name
        body = topic.split_topics(title)["body"] or title
        return account, (norm_name(body) or norm_name(title) or title)

    def _load_sent_keys(self):
        """记录里每个号发过的标题(已发的)。员工把发过的复制一份 / 重新下一个同名的放进新文件夹,按路径认不出,按这个认。"""
        keys: dict = {}
        try:
            for r in self.rec.rows():
                if r["status"] == "已发":
                    keys.setdefault(self._dkey(r["account"], r["title"]), {"date": r["date"], "path": r["path"]})
        except Exception:
            pass
        self._sent_keys = keys

    def _refresh_dups(self):
        """哪几条不发(重复):① 这个号以前发过同名的;② 列表里同一个号同名的,只留第一条。{行: 为什么}。"""
        out, first = {}, {}
        keys = getattr(self, "_sent_keys", {})
        for i, v in enumerate(self.videos):
            if self._sent(i):
                continue
            k = self._dkey(v.account, v.title)
            r = keys.get(k)
            if r and pkey(r.get("path") or "") != pkey(v.path):
                out[i] = f"这个号发过同名的({r.get('date') or '之前'}),不再发(真要发就让员工改个名)"
                continue
            if k in first:
                out[i] = f"和「{self.videos[first[k]].title[:20]}」同名,同一个号只发一条(两条都要发就让员工改个名)"
                continue
            first[k] = i
        self._dups = out

    def _refresh_blocked(self):
        """一个号这天有 3 条以上(或超过一成)标题像别的游戏 → 可能整批放错了,人点「确认没放错」前整批不发(用户 2026-10-20)。"""
        from qe import gamecheck
        s, day = gamecheck.store(), self.day()
        by: dict[str, list[int]] = {}
        for i, v in enumerate(self.videos):
            if not self._sent(i):
                by.setdefault(v.account, []).append(i)
        out = {}
        for nick, idx in by.items():
            if not gamecheck.account_game(nick) or s.batch_ok(nick, day):
                continue
            n = sum(1 for i in idx if gamecheck.alien(nick, self.videos[i].title))
            if n >= 3 or (n and n * 10 > len(idx)):
                out[nick] = n
        old, self._blocked = self._blocked, out
        for nick in {k for k in set(old) | set(out) if old.get(k) != out.get(k)}:   # 变了的号:那几行和号那一行重画
            for i in self.rows_of(nick):
                self._fill(i, group=False)
            self._fill_group(nick)

    def _update_scope(self):
        if self.busy():
            return
        undo = self.ledger.last()
        self.b_undo.setToolTip("把上一次改话题 / 批量改话题 / 改标题改回去" +
                               (f"\n上一次:{topic.Ledger.label(undo)}" if undo else "\n(现在没有能撤销的)"))
        if not self.day():
            self.lab_scope.setText("先在左上角选「要发哪天的」")
            self.b_clear.setVisible(False)
            self.b_pub.setText("现在发布")
            return
        sel = self.selected_rows()
        rows = self.target_rows()
        self.lab_scope.setProperty("sel", bool(sel))
        self.lab_scope.style().unpolish(self.lab_scope)
        self.lab_scope.style().polish(self.lab_scope)
        if sel:
            accs = sorted({self.videos[i].account for i in sel})
            who = accs[0] if len(accs) == 1 else f"{len(accs)} 个号"
            self.lab_scope.setText(f"只管选中的:{who} {len(sel)} 条(按钮都只管这些;Esc 取消选择)")
        elif self.filtering():
            self.lab_scope.setText(f"过滤中:只管看得见的 {len(rows)} 条(要管全部:点上面「全部」/ 清空搜索)")
        else:
            self.lab_scope.setText(f"没选:管全部 {len(rows)} 条" if rows else "这天没有视频")
        self.b_clear.setVisible(bool(sel))
        n, _over = self._quota_cap([i for i in rows if self._can_send(i) and not self.state.get(i, "").startswith(FAILED)])
        # 重试:号的密钥坏了的不算(再点也必然失败,体验报告)
        retry = sum(1 for i in rows if self._can_send(i) and self.state.get(i, "").startswith(FAILED)
                    and "密钥" not in self.state.get(i, ""))
        if sel:                                          # 选中了:大按钮写「只发选中的」、换颜色(原来悄悄变成只管 1 条,试用的人都被坑)
            self.b_pub.setText(f"只发选中的 {n} 条" + (f" + 重发 {retry} 条" if retry else "") if n else
                               (f"选中的重发 {retry} 条" if retry else "选中的没有能发的"))
        elif self.filtering() and not n and not retry:
            self.b_pub.setText("点「全部」再发")
        else:
            self.b_pub.setText(f"现在发布 {n} 条" + (f" + 再发一次没发成的 {retry} 条" if retry else "") if n else
                               (f"再发一次没发成的 {retry} 条" if retry else "没有能发的"))
        self.b_pub.setEnabled(bool(n or retry) and not self.busy())
        from gui.widgets import repolish
        repolish(self.b_pub, sel=bool(sel))
        self.b_pub.setMinimumWidth(min(240, self.b_pub.sizeHint().width()))   # 收起时字被切(「在发布 393」);太长的照旧能缩
        self.b_unsel.setText("× 取消选中")
        self.b_unsel.setVisible(bool(sel) and not self.b_pub.isHidden())
        for b, base in ((self.b_vert, "转标准竖屏"), (self.b_topic, "整理标题")):
            b.setText(f"{base}(选中 {len(sel)} 条)" if sel else base)
        self.b_settopic.setText("批量改话题…" if sel else "批量改话题…(先选)")
        if getattr(self, "_hero_args", None):
            self._hero_update(*self._hero_args)

    def roots(self) -> list[str]:
        return list(self.st.get("api_roots") or apisrc.DEFAULT_ROOTS)

    def known(self):
        ns = apiacc.nicks()
        return set(ns) if ns else None

    # ---------------- 读素材 ----------------
    def reload_dates(self):
        if self.busy() and getattr(self, "_quiet", False):
            self.job.stop()
            self.job.wait()
        if self.busy():
            return
        from gui.widgets import fill_dates, newest_first
        ds = apisrc.dates(self.roots(), self.known())
        has = set(ds) | {k for k, v in (self.st.get("api_picked") or {}).items() if v}
        today = f"{bj_now().month}.{bj_now().day}"
        # 刚打开:今天的文件夹在就选今天(试用的人早上打开都停在昨天);没有才回到上次选的那天
        cur = self.day() or (today if today in has else str(self.st.get("api_last_date") or ""))
        self._prev = self._leftover(ds, has, today)
        for x in list((self.st.get("api_picked") or {}).keys()) + [today]:   # 手选过文件夹的日子、今天:没有日期文件夹也能选
            if x and x not in ds:
                ds.append(x)
        # 和教育号页一样:最新的在上面、今天标出来、没日期文件夹的(今天还没建)灰掉(审查 15)
        fill_dates(self.c_date, newest_first(ds), cur, empty={d for d in ds if d not in has})
        self.load()

    def _leftover(self, ds, has, today) -> tuple[str, int] | None:
        """今天之前最近的那天还剩几条没发(文件夹里还在、记录里不是已发的)。没有 / 读不了 = None。"""
        from qe.folders import day_of

        def k(d):
            x = day_of(d)
            return (int(x.split(".")[0]), int(x.split(".")[1])) if x else (0, 0)
        t = k(today)
        older = [d for d in ds if d in has and (0, 0) < k(d) < t]
        if not older:
            return None
        d = max(older, key=k)
        try:
            vs = apisrc.videos(self.roots(), d, self.known(), (self.st.get("api_picked") or {}).get(d))
        except OSError:
            return None
        n = sum(1 for v in vs if not str(self.rec.status_of(v.path) or "").startswith("已发"))
        return (d, n) if n else None

    def day(self) -> str:
        """现在选的是哪天(「10.19」;下拉里的字可能多了「(今天)」,日期存在数据里)。"""
        d = self.c_date.currentData()
        return d if isinstance(d, str) else self.c_date.currentText()

    def set_day(self, date: str) -> bool:
        """选到这天(换了会自己重读);下拉里没有返回 False。"""
        i = self.c_date.findData(date)
        if i < 0:
            i = self.c_date.findText(date)
        if i < 0:
            return False
        self.c_date.setCurrentIndex(i)
        return True

    def _show_prev(self):
        p = getattr(self, "_prev", None)
        on = bool(p) and self.day() == f"{bj_now().month}.{bj_now().day}"
        if on:
            self.b_prev.setText(f"昨天还剩 {p[1]} 条 ›")
            self.b_prev.setToolTip(f"{p[0]} 的文件夹里还有 {p[1]} 条没发出去;点一下切过去看")
        self.b_prev.setVisible(on)

    def _show_source(self, d: str):
        """上面那行:素材到底从哪来(短说;完整的放鼠标悬停里)。"""
        n = len(apiacc.load())
        if not n:
            self.lab.setText("还没搬账号:去左下角「设置」里点「从旧软件搬账号…」")
            return
        pk = self.picked(d) if d else {}
        auto = "、".join(self.roots())
        if not pk:
            self.lab.setText(f"{n} 个号 · 素材:自动找")
            self.lab.setToolTip(f"按日期文件夹自动找:{auto}")
            return
        rest = n - len(pk)
        self.lab.setText(f"{n} 个号 · {len(pk)} 个用手选的文件夹" + (f",{rest} 个自动找" if rest > 0 else ""))
        self.lab.setToolTip("手选的文件夹:\n" + "\n".join(f"{k} → {v}" for k, v in sorted(pk.items())) +
                            (f"\n\n其余的自动找:{auto}" if rest > 0 else ""))

    @staticmethod
    def _sig(path: str):
        try:
            s = os.stat(path)
            return (s.st_size, int(s.st_mtime))
        except OSError:
            return None

    @staticmethod
    def _attach_wm(v):
        """查过水印 / 口播广告的(记在硬盘上,关了再开也在)挂到 checks 上;文件变了 / 没查过就没有。"""
        if v.checks is not None:
            for k, store in (("wm", wmstore.WM), ("ads", wmstore.ADS)):
                w = store.get(v.path)
                if w is not None:
                    v.checks[k] = w
                else:
                    v.checks.pop(k, None)

    def _remember_check(self, v):
        sig = self._sig(v.path)
        if sig and v.checks:
            self.cache[pkey(v.path)] = (sig, dict(v.checks))

    def load(self):
        self._show_prev()
        if not self.busy() and hasattr(self, "pub_strip"):   # 换日期 / 刷新:上一轮的发布进度收起来
            self.hero._extra_w.hide()
            self._pub = None
        if self.busy() and getattr(self, "_quiet", False):   # 只是后台自动检查:停掉它,重读
            self.job.stop()
            self.job.wait()
            self._busy(False)
        if self.busy():                              # 后台按行号刷状态,这时重读列表会刷到别的视频上
            return
        d = self.day()
        if d and self.st.get("api_last_date") != d:
            self.st["api_last_date"] = d
            self.st.save()
        self._show_source(d)
        self.videos = apisrc.videos(self.roots(), d, self.known(), self.picked(d)) if d else []
        self.state, self.why = {}, {}
        words = self.st.get("api_platform_words") or None
        todo = []
        for i, v in enumerate(self.videos):
            s = self.rec.status_of(v.path)
            if s:
                self.state[i] = s
            hit = self.cache.get(pkey(v.path))
            if hit and hit[0] == self._sig(v.path):      # 检过的、文件没变:不用重新检查(标题可能改过,话题 / 平台名重算)
                v.checks = dict(hit[1])
                v.checks["tags"] = topic.split_topics(v.title)["tags"]
                v.checks["platform"] = checks.platform_hits(v.title, words)
                self._attach_wm(v)
            elif not s.startswith("已发"):
                todo.append(i)
        self._load_sent_keys()
        self._refresh_dups()
        # 这天已经发出去、挪走了的(列表里没有了,但记录里有):号那一行和上面卡片要算上
        self.today_sent = self.rec.sent_on(plan.today())
        self.archived = {}
        if d:
            here = {pkey(v.path) for v in self.videos}
            seen = set()
            for r in self.rec.rows(d):
                if r["employee"] == "接口" and r["status"] == "已发" and pkey(r["path"]) not in here and pkey(r["path"]) not in seen:
                    seen.add(pkey(r["path"]))
                    self.archived[r["account"]] = self.archived.get(r["account"], 0) + 1
        new_day = d != getattr(self, "_shown_day", None)
        self._shown_day = d
        self._build_tree()
        if new_day:
            self.tree.scrollToTop()                       # ②5 换了日期回到最上面
        if d:
            accs = sorted({v.account for v in self.videos})
            unsure = sum(1 for x in self.state.values() if x == "结果不明")
            if unsure:
                self.say(f"⚠ 有 {unsure} 条「结果不明」(发布请求发出去了没收到回话,或者上次发到一半软件被关了)。"
                         "去企鹅号后台看一眼,再右键标「发了 / 没发」;标之前软件不会再发它们。")
            missing = [n for n in apiacc.nicks() if n not in accs]
            self.say(f"接口发 {d}:{len(self.videos)} 条,{len(accs)} 个号" +
                     (f";这天没找到视频的号:{'、'.join(missing)}" if missing else "") + "。")
            if self._auto_spill():                    # 今天发够的号:今天文件夹里没发的先挪到明天,再重读
                self._spilling = True
                try:
                    self.load()
                finally:
                    self._spilling = False
                return
            if todo:
                self.run_check(todo, quiet=True)          # 新出现的自动检查(审查:原来每次刷新都要重新点「检查」)

    def _build_tree(self):
        self.tree.blockSignals(True)
        self.tree.clear()
        self.items, self.groups = {}, {}
        bold = QFont()
        bold.setBold(True)

        def group(nick):
            g = QTreeWidgetItem([nick])
            g.setData(0, ROW, -1)
            g.setData(0, NICK, nick)
            for c in range(len(COLS)):
                g.setFont(c, bold)
            self.tree.addTopLevelItem(g)
            self.groups[nick] = g
            return g
        for i, v in enumerate(self.videos):
            g = self.groups.get(v.account) or group(v.account)
            it = QTreeWidgetItem([v.title])
            it.setData(0, ROW, i)
            g.addChild(it)
            self.items[i] = it
            self._fill(i, group=False)
        if self.day():                     # 这天没找到视频的号也列出来(灰的),一眼看出少了谁
            for nick in apiacc.nicks():
                if nick not in self.groups:
                    g = group(nick)
            for nick, g in self.groups.items():
                if not g.childCount():
                    gone = self.archived.get(nick, 0)
                    if gone:
                        g.setText(0, f"{nick}  这天已发 {gone} 条(发完挪走了)")
                        g.setText(3, self._quota_text(nick) or f"已发 {gone}")
                        g.setToolTip(0, "这天的视频都发出去了,已经挪到「企鹅号软件发布」里")
                        for c in range(len(COLS)):
                            g.setBackground(c, GREEN)
                        continue
                    g.setText(0, f"{nick}  这天没找到视频")
                    g.setToolTip(0, "这个号这天没有日期文件夹 / 文件夹里没视频。员工放错地方了?可以右键「给这个号选文件夹」")
                    for c in range(len(COLS)):
                        g.setForeground(c, QBrush(GREY))
                    g.setFont(0, QFont())
        for nick, g in self.groups.items():
            if g.childCount():
                g.setExpanded(nick in self.open_accounts)
                self._fill_group(nick)
        self.tree.blockSignals(False)
        self._reorder()
        self._apply_filter()
        self._busy(self.busy())

    def _done(self, nick: str) -> bool:
        """这个号这天发完了:能发的都发了(列表里的都已发 / 发完挪走了),或者今天发够规定条数了。"""
        g = self.groups.get(nick)
        if g is None:
            return False
        rows = [g.child(k).data(0, ROW) for k in range(g.childCount())]
        if not rows:
            return bool(self.archived.get(nick))
        if all(self._sent(i) for i in rows):
            return True
        sent = getattr(self, "today_sent", None) or {}
        return plan.left_today(self.rec, self.st, nick, sent=sent) == 0

    def _reorder(self):
        """发完的号沉到下面、收起来、名字后面写「发完了」(用户 2026-10-23:abcde 里 abd 发完了 → c e a b d)。
        没发完的照原来的顺序在上面。"""
        if not self.groups:
            return
        cur = [self.tree.topLevelItem(k) for k in range(self.tree.topLevelItemCount())]
        done = {g.data(0, NICK): self._done(g.data(0, NICK)) for g in cur}
        want = [g for g in cur if not done[g.data(0, NICK)]] + [g for g in cur if done[g.data(0, NICK)]]
        self.tree.blockSignals(True)
        if want != cur:
            opened = {g.data(0, NICK) for g in cur if g.isExpanded()}
            sel = self.selected_rows()
            for g in cur:
                self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(g))
            for g in want:
                self.tree.addTopLevelItem(g)
                g.setExpanded(g.data(0, NICK) in opened and not done[g.data(0, NICK)])
            for i in sel:
                if i in self.items:
                    self.items[i].setSelected(True)
        for g in want:
            nick = g.data(0, NICK)
            if g.childCount():
                self._fill_group(nick)                   # 名字后面写「· 发完了」
                if done[nick]:
                    g.setExpanded(False)
        self.tree.blockSignals(False)

    def _remember(self, it: QTreeWidgetItem, on: bool):
        if it.data(0, ROW) == -1:
            (self.open_accounts.add if on else self.open_accounts.discard)(it.data(0, NICK))

    def expand_all(self, on: bool):
        for nick, g in self.groups.items():
            g.setExpanded(on)
        self.open_accounts = set(self.groups) if on else set()

    def _double(self, it: QTreeWidgetItem, _col: int):
        i = it.data(0, ROW)
        if not (isinstance(i, int) and i >= 0):
            return
        if self.state.get(i) == "结果不明" and not self.busy():   # 双击「不确定发没发」的:直接问(体验报告)
            v = self.videos[i]
            box = QMessageBox(QMessageBox.Icon.Question, "这条发出去了吗?",
                              f"「{v.title[:40]}」\n\n发布请求发出去了,但没收到企鹅号的回话。\n去企鹅号后台看一眼,这条有没有发出去?",
                              QMessageBox.StandardButton.NoButton, self)
            b1 = box.addButton("发出去了", QMessageBox.ButtonRole.YesRole)
            b2 = box.addButton("没发出去(可以再发)", QMessageBox.ButtonRole.NoRole)
            box.addButton("还没去看", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() in (b1, b2):
                self.resolve_unsure(i, box.clickedButton() is b1)
            return
        self.reveal(i)

    def _edit_current(self):
        it = self.tree.currentItem()
        i = it.data(0, ROW) if it else -1
        if isinstance(i, int) and i >= 0 and not self.busy():
            self.edit_title(i)

    def _status_text(self, i: int) -> tuple[str, list]:
        v = self.videos[i]
        c = v.checks or {}
        probs = checks.problems(v) if c else []
        st = self.state.get(i, "")
        if st == "结果不明":
            return "不确定发没发 · 双击确认", probs
        if st:
            return st, probs
        if c and probs:
            return "要处理", probs
        if c and i in self._dups:
            return "要处理", [self._dups[i]]
        if c and self._blocked.get(v.account):
            return "要处理", [f"这个号整批先不发({self._blocked[v.account]} 条像别的游戏,可能放错了)"]
        if c and not probs:
            return ("能发(已转竖屏)" if c.get("converted") else "能发"), probs
        return "", probs

    def _fill(self, i: int, group: bool = True):
        v = self.videos[i]
        it = self.items.get(i)
        if it is None:
            return
        c = v.checks or {}
        st, probs = self._status_text(i)
        res = (f"{c['w']}×{c['h']}" if c.get("w") else "") if c else "没检查"
        from qe import gamecheck
        hint = gamecheck.ai_hint(v.account, v.title) if c and not self._sent(i) else ""
        note = "、".join(probs) if c else ""
        if hint:
            note = (note + "、" if note else "") + f"(AI 觉得像《{hint}》,不拦)"
        for col, t in enumerate([v.title, res, note, st]):
            it.setText(col, t)
            it.setToolTip(col, v.path if col == 0 else (self.why.get(i) or t) if col == 3 else t)
        ad = c.get("ads") or {}
        if ad.get("hits") and not (c.get("wm") or {}).get("hits"):     # 鼠标放上去看是哪几句
            it.setToolTip(2, "查到的口播广告" + ("(已经剪掉了)" if ad.get("blurred") else "(你标过:不是广告)" if ad.get("ok") else "") +
                          ":\n" + "\n".join(f"{int(x['start']) // 60}:{int(x['start']) % 60:02d}  {x['text']}" for x in ad["hits"][:8]))
        wm = c.get("wm") or {}
        if wm.get("hits") and wm.get("shot") and os.path.isfile(wm["shot"]):   # 鼠标放上去看查到水印的那一帧(红框)
            from PySide6.QtCore import QUrl
            src = QUrl.fromLocalFile(wm["shot"]).toString()
            it.setToolTip(2, f"<b>{checks.wm_text(wm)}</b>" + ("(已经糊掉了)" if wm.get("blurred") else "(你标过:不用管)" if wm.get("ok") else "") +
                          f"<br><img src='{src}' width='300'><br>不是水印:右键「没水印 / 不用管,这条能发」")
        bg = GREEN if st.startswith("已发") else ORANGE if st == "结果不明" else RED if st.startswith(FAILED) \
            else YELLOW if probs else None
        for col in range(len(COLS)):
            it.setBackground(col, bg if bg else QColor(0, 0, 0, 0))
        if group:
            self._fill_group(v.account)
            self._apply_filter(only=it)

    def _fill_group(self, nick: str):
        g = self.groups.get(nick)
        if g is None or not g.childCount():
            return
        rows = [g.child(k).data(0, ROW) for k in range(g.childCount())]
        n = len(rows)
        sent = sum(1 for i in rows if self.state.get(i, "").startswith("已发"))
        checked = [i for i in rows if self.videos[i].checks]
        bad = sum(1 for i in checked if (checks.problems(self.videos[i]) or self._blocked.get(self.videos[i].account)
                                         or i in self._dups) and not self._sent(i))
        fail = sum(1 for i in rows if self.state.get(i, "").startswith(FAILED[:2]))
        unsure = sum(1 for i in rows if self.state.get(i, "") == "结果不明")
        ok = sum(1 for i in rows if self._can_send(i) and not self.state.get(i, "").startswith(FAILED))
        pk = "(手选文件夹)" if nick in self.picked(self.day()) else ""
        g.setText(0, f"{nick}  {n} 条{pk}" + (" · 发完了" if self._done(nick) else ""))
        g.setText(1, "")
        parts = []
        if not checked:
            parts.append("没检查")
        if bad:
            parts.append(f"有问题 {bad}")
        if fail:
            parts.append(f"没发成 {fail}")
        if unsure:
            parts.append(f"结果不明 {unsure}")
        if self._blocked.get(nick):
            parts.insert(0, f"可能放错了 {self._blocked[nick]}")
        g.setText(2, " · ".join(parts))
        base = "发完了" if n and sent == n else (f"能发 {ok}" if checked else "")
        q = self._quota_text(nick)
        g.setText(3, " · ".join(x for x in (base, q) if x))
        g.setToolTip(3, "「今天 X / Y」= 今天(按发出去的时间)已经发了 X 条,规定每天 Y 条")
        g.setToolTip(0, self.picked(self.day()).get(nick, "") or nick)
        col = GREEN if n and sent == n else ORANGE if unsure else YELLOW if bad or fail else None
        for c in range(len(COLS)):
            g.setBackground(c, col if col else QColor(0, 0, 0, 0))
        self._update_sum()

    def _quota_text(self, nick: str) -> str:
        q = plan.quota_on(self.st, nick)
        t = (getattr(self, "today_sent", {}) or {}).get(nick, 0)
        if not q:
            return f"今天 {t}" if t else ""
        return f"今天 {t}/{q}" + (" √" if t >= q else "")

    def _quota_nicks(self) -> list[tuple[str, int]]:
        """有规定条数的号:[(号, 每天几条)]。账号还没搬(nicks 空)就用列表里出现的号(审查 14:原来没号可算时写「都发够了」)。"""
        names = apiacc.nicks() or sorted({v.account for v in self.videos})
        return [(n, q) for n in names for q in (plan.quota_on(self.st, n),) if q]

    def _quota_card(self):
        """「今天达标」卡片:有规定的号里今天发够了几个(按发出去的时间算)。"""
        got = getattr(self, "today_sent", {}) or {}
        qs = self._quota_nicks()
        if not qs:
            return "–"
        ok = sum(1 for n, q in qs if got.get(n, 0) >= q)
        return (f"{ok} / {len(qs)}", "good" if ok == len(qs) else "")

    def _quota_sub(self) -> str:
        got = getattr(self, "today_sent", {}) or {}
        qs = self._quota_nicks()
        if not qs:
            return "没有规定条数的号"
        short = sum(max(0, q - got.get(n, 0)) for n, q in qs)
        return f"今天还差 {short} 条" if short else "今天都发够了 √"

    def _update_sum(self):
        self._refresh_dups()
        self._refresh_blocked()
        n = len(self.videos)
        sent = sum(1 for i in range(n) if self.state.get(i, "").startswith("已发"))
        checked = [i for i in range(n) if self.videos[i].checks]
        n_done = sum(1 for i in range(n) if self.videos[i].checks or self._sent(i))
        ok, self._over = self._quota_cap([i for i in range(n) if self._can_send(i) and not self.state.get(i, "").startswith(FAILED)])
        bad = sum(1 for i in checked if (checks.problems(self.videos[i]) or self._blocked.get(self.videos[i].account)
                                         or i in self._dups) and not self._sent(i))
        fail = sum(1 for i in range(n) if self.state.get(i, "").startswith(FAILED[:2]))
        accs = {}
        for i, v in enumerate(self.videos):
            accs.setdefault(v.account, []).append(self.state.get(i, "").startswith("已发"))
        arch = getattr(self, "archived", {}) or {}
        for nick in arch:
            accs.setdefault(nick, [])                     # 发完挪走了的号:列表里没视频,算发完
        done = sum(1 for xs in accs.values() if all(xs))
        unsure = sum(1 for i in range(n) if self.state.get(i, "") == "结果不明")
        gone = sum(arch.values())
        self.lab_sum.setText("" if n_done >= n or not n else f"{n - n_done} 条还没检查完…")
        subs = [x for x in ((f"不确定发没发 {unsure}" if unsure else ""), (f"没发成 {fail}" if fail else ""),
                            (f"有问题 {bad}" if bad else "")) if x]
        self.cards.set(all=n + gone, ok=(ok, "good" if ok else ""), bad=(bad + fail + unsure, "warn" if bad + fail + unsure else ""),
                       sent=sent + gone, accs=self._quota_card(),
                       bad_sub=" · ".join(subs),
                       ok_sub="点「现在发布」发这些" if ok else "",
                       sent_sub=f"其中 {gone} 条已挪走" if gone else "", all_sub="", accs_sub=self._quota_sub())
        cats = {"v": 0, "t": 0, "w": 0, "o": 0}
        for i in checked:
            if self._sent(i):
                continue
            ps = checks.problems(self.videos[i])
            if any(p in ("横屏", "偏方要转竖屏") for p in ps):
                cats["v"] += 1
            if any("话题" in p or "空格" in p or "要删" in p for p in ps):
                cats["t"] += 1
            if any("水印" in p or "广告" in p for p in ps):
                cats["w"] += 1
            if any(p.startswith("标题有「") and "要删" not in p for p in ps):
                cats["o"] += 1
        self._hero_args = (n, sent, n_done, ok, bad, fail, unsure, gone, cats)
        self._hero_update(*self._hero_args)

    def _hidden(self, i: int) -> bool:
        if getattr(self, "k_undone", None) is not None and self.k_undone.isChecked() and self._done(self.videos[i].account):
            return True
        key = self.e_find.text().strip().lower()
        if key and key not in self.videos[i].title.lower():
            return True
        seg = getattr(self, "_segk", "all")
        if seg == "ok":
            return not (self._can_send(i) and not self.state.get(i, "").startswith(FAILED))
        if seg == "sent":
            return not self.state.get(i, "").startswith("已发")
        if self.k_bad.isChecked():
            st, probs = self._status_text(i)
            return not (probs or st.startswith(FAILED) or st == "结果不明") or st.startswith("已发")
        return False

    def _apply_filter(self, only: QTreeWidgetItem | None = None):
        if only is not None:
            only.setHidden(self._hidden(only.data(0, ROW)))
            return
        for i, it in self.items.items():
            it.setHidden(self._hidden(i))
        for nick, g in self.groups.items():
            if not g.childCount():
                g.setHidden(self.filtering())
                continue
            vis = any(not g.child(k).isHidden() for k in range(g.childCount()))
            g.setHidden(not vis)
            if self.filtering() and vis:
                g.setExpanded(True)
        self._update_scope()

    def selected_rows(self) -> list[int]:
        """选中的视频;选中号 = 这个号的全部(过滤掉了看不见的不算)。"""
        out = set()
        for it in self.tree.selectedItems():
            i = it.data(0, ROW)
            if i == -1:
                out |= {it.child(k).data(0, ROW) for k in range(it.childCount()) if not it.child(k).isHidden()}
            elif isinstance(i, int):
                out.add(i)
        return sorted(out)

    def rows_of(self, nick: str) -> list[int]:
        return [i for i, x in enumerate(self.videos) if x.account == nick]

    # ---------------- 手动给号选文件夹(旧软件的「选择」) ----------------
    def picked(self, date: str) -> dict:
        return dict((self.st.get("api_picked") or {}).get(date) or {})

    def _set_pick(self, date: str, nick: str, folder: str):
        allp = dict(self.st.get("api_picked") or {})
        day = dict(allp.get(date) or {})
        if folder:
            day[nick] = folder
        else:
            day.pop(nick, None)
        if day:
            allp[date] = day
        else:
            allp.pop(date, None)
        self.st["api_picked"] = allp
        self.st.save()

    def pick_folder(self, nick: str = ""):
        if self.busy() and getattr(self, "_quiet", False):
            self.job.stop()
            self.job.wait()
        if self.busy():
            QMessageBox.information(self, "给号选文件夹", "后台还在做事(发布 / 转竖屏 / 改话题 / 检查),做完或点「停」以后再换文件夹。")
            return
        d = self.day()
        if not d:
            QMessageBox.information(self, "给号选文件夹", "先在左上角选是哪天的。")
            return
        if not nick:
            names = apiacc.nicks()
            if not names:
                QMessageBox.information(self, "给号选文件夹", "还没搬账号。")
                return
            nick, ok = QInputDialog.getItem(self, "给号选文件夹", f"{d} 给哪个号选文件夹?", names, 0, False)
            if not ok:
                return
        start = self.picked(d).get(nick) or apisrc.account_folders(self.roots(), {nick}).get(nick) or (self.roots() or [""])[0]
        f = QFileDialog.getExistingDirectory(self, f"{nick}:{d} 要发的视频在哪个文件夹", start)
        if not f:
            return
        f = os.path.normpath(f)
        why = self._bad_pick(d, nick, f)
        if why:
            QMessageBox.warning(self, "给号选文件夹", why)
            return
        self._set_pick(d, nick, f)
        n = len(apisrc._videos_in(f, nick, d))
        self.say(f"{d}「{nick}」只发这个文件夹里的 {n} 条:{os.path.basename(f)}")
        self.load()

    def _bad_pick(self, d: str, nick: str, f: str) -> str:
        """这个文件夹不能给这个号:返回原因;能用返回 ""。"""
        k = pkey(f)
        base = os.path.basename(f)
        if any(w in base for w in ("已发", "不能用", "脏话", "不行")):
            return f"「{base}」看名字是不发的(已发 / 不能用 / 脏话),不能选它。"
        arch = str(self.st.get("api_archive") or apisrc.DEFAULT_ARCHIVE).split("{")[0].rstrip("\\/")
        if arch and (k == pkey(arch) or k.startswith(pkey(arch) + os.sep)):
            return "这是发完挪过去的「已发布」文件夹,里面的都发过了,不能再选。"
        for other, path in self.picked(d).items():
            if other != nick and pkey(path) == k:
                return f"这个文件夹已经给「{other}」用了。一个文件夹只能给一个号,不然同一条视频会发到两个号。"
        for other, paths in apisrc.account_folder_list(self.roots(), self.known()).items():
            if other != nick and any(k == pkey(p) or k.startswith(pkey(p) + os.sep) for p in paths):
                return f"这个文件夹是「{other}」的素材文件夹,不能给「{nick}」。"
        return ""

    def unpick(self, nick: str):
        if self.busy() and getattr(self, "_quiet", False):
            self.job.stop()
            self.job.wait()
        if self.busy():
            return
        d = self.day()
        self._set_pick(d, nick, "")
        self.say(f"{d}「{nick}」不用手选的文件夹了,回到自动找")
        self.load()

    def _menu(self, pos):
        it = self.tree.itemAt(pos)
        m = QMenu(self)
        busy = self.busy()
        if it is not None:
            if not it.isSelected():
                self.tree.clearSelection()
                it.setSelected(True)
            i = it.data(0, ROW)
            nick = it.data(0, NICK) if i == -1 else self.videos[i].account
            sel = self.selected_rows()
            mine = self.rows_of(nick)
            if i != -1 and self.state.get(i) == "结果不明" and len(sel) == 1:
                # 不确定发没发的:只给这几项(体验报告:原来埋在 21 项菜单中间)
                m.addAction("我去后台看了:发出去了", lambda: self.resolve_unsure(i, True)).setEnabled(not busy)
                m.addAction("我去后台看了:没发出去(可以再发)", lambda: self.resolve_unsure(i, False)).setEnabled(not busy)
                m.addSeparator()
                m.addAction("复制标题(去后台搜)", lambda: self._copy(self.videos[i].title))
                m.exec(self.tree.viewport().mapToGlobal(pos))
                return
            # 老手试用 2026-10-21:原来 21 项、一屏放不下,常用的埋在下面 → 常用的放上面,不常用的收进子菜单,发布放最底下
            n_s = len(sel)
            if i != -1 and self.state.get(i, "").startswith("已发") or (i != -1 and self.rec.sent_row(self.videos[i].path)):
                m.addAction("改回没发(拎回来重发)…", lambda: self.unsend_rows(sel or [i])).setEnabled(not busy)
                m.addSeparator()
            if i != -1:
                m.addAction("改标题…(F2)", lambda: self.edit_title(i)).setEnabled(not busy and not self._sent(i))
                m.addAction("复制标题", lambda: self._copy(self.videos[i].title))
                m.addAction("打开所在文件夹", lambda: self.reveal(i))
            if sel:
                m.addAction(f"转标准竖屏(选中 {n_s} 条)", lambda: self.run_vertical(sel)).setEnabled(not busy)
                m.addAction(f"整理标题(选中 {n_s} 条)", lambda: self.run_topic(sel)).setEnabled(not busy)
            from qe import gamecheck
            if i != -1 and not self._sent(i) and gamecheck.account_game(nick):
                g0 = gamecheck.by_words(nick, self.videos[i].title)[0] or gamecheck.ai_hint(nick, self.videos[i].title)
                hint = gamecheck.ai_hint(nick, self.videos[i].title)
                if hint and not gamecheck.alien(nick, self.videos[i].title):
                    home = self._game_home(hint)
                    if home:
                        m.addSeparator()
                        d = os.path.basename(os.path.dirname(self.videos[i].path))
                        m.addAction(f"AI 觉得像《{hint}》:真放错了就挪到「{home[0]}」的 {d}",
                                    lambda: self.move_to_game(i)).setEnabled(not busy)
                if gamecheck.store().ok(nick, self.videos[i].title):
                    m.addSeparator()
                    m.addAction("其实不是这个号的游戏(先不发)", lambda: self.set_game_ok(i, False)).setEnabled(not busy)
                elif gamecheck.alien(nick, self.videos[i].title):
                    # 新员工试用 2026-10-21:原来只有「能发」一条路,真放错了没地方点。放错了排第一个
                    m.addSeparator()
                    m.addAction(f"标题像《{g0}》的").setEnabled(False)
                    home = self._game_home(g0)
                    if home:
                        d = os.path.basename(os.path.dirname(self.videos[i].path))
                        m.addAction(f"放错了:挪到「{home[0]}」的 {d}", lambda: self.move_to_game(i)).setEnabled(not busy)
                    m.addAction("先不发,留在这", lambda: self.set_game_ok(i, False)).setEnabled(not busy)
                    m.addAction("看过了,是这个号的,能发", lambda: self.confirm_game_ok(i)).setEnabled(not busy)
            if gamecheck.account_game(nick):
                day = self.day()
                if self._blocked.get(nick):
                    m.addSeparator()
                    m.addAction(f"「{nick}」这批确认没放错,能发", lambda: self.set_batch_ok(nick, True)).setEnabled(not busy)
                elif gamecheck.store().batch_ok(nick, day):
                    m.addSeparator()
                    m.addAction(f"「{nick}」取消「确认没放错」(这批先不发)", lambda: self.set_batch_ok(nick, False)).setEnabled(not busy)
            if i != -1 and not self._sent(i) and titleclean.ad_words(self.videos[i].title):
                m.addSeparator()
                if titleclean.store().ok(self.videos[i].account, self.videos[i].title):
                    m.addAction("标题广告:其实还没剪(先不发)", lambda: self.set_title_ad_ok(i, False)).setEnabled(not busy)
                else:
                    m.addAction("标题有广告词:视频里的广告剪好了 / 不是广告,能发", lambda: self.set_title_ad_ok(i, True)).setEnabled(not busy)
            ad = (self.videos[i].checks or {}).get("ads") if i != -1 else None
            if ad and ad.get("hits") and not self._sent(i):
                m.addSeparator()
                if ad.get("blurred"):
                    m.addAction("口播广告已经剪掉了(原片在「广告原片」里)").setEnabled(False)
                elif ad.get("ok"):
                    m.addAction("其实是广告(先不发)", lambda: self.set_ad_ok(i, False)).setEnabled(not busy)
                else:
                    m.addAction("不是广告,这条能发", lambda: self.set_ad_ok(i, True)).setEnabled(not busy)
            wm = (self.videos[i].checks or {}).get("wm") if i != -1 else None
            if wm and wm.get("hits") and not self._sent(i):
                m.addSeparator()
                if wm.get("shot"):
                    m.addAction("看水印截图", lambda: self._open_file(wm["shot"]))
                if wm.get("blurred"):
                    m.addAction("水印已经糊掉了(原片在「水印原片」里)").setEnabled(False)
                elif wm.get("ok"):
                    m.addAction("其实有水印(先不发)", lambda: self.set_wm_ok(i, False)).setEnabled(not busy)
                else:
                    m.addAction("没水印 / 不用管,这条能发", lambda: self.set_wm_ok(i, True)).setEnabled(not busy)
            m.addSeparator()
            if sel:
                mc = m.addMenu("检查")
                mc.addAction(f"检查选中的 {n_s} 条", lambda: self.run_check(sel)).setEnabled(not busy)
                mc.addAction(f"高级检查选中的 {n_s} 条(再查水印)", lambda: self.run_check(sel, deep=True)).setEnabled(not busy)
                mc.addAction(f"查口播广告(选中 {n_s} 条)", lambda: self.run_ads(sel)).setEnabled(not busy)
                mw = m.addMenu("水印 / 口播广告")
                mw.addAction(f"模糊水印(选中 {n_s} 条)", lambda: self.run_blur(sel)).setEnabled(not busy)
                mw.addAction(f"剪掉口播广告(选中 {n_s} 条)", lambda: self.run_cut(sel)).setEnabled(not busy)
                mt = m.addMenu("标题 / 话题")
                mt.addAction(f"只整理写法、不用 AI(选中 {n_s} 条)", lambda: self.tidy_titles(sel)).setEnabled(not busy)
                mt.addAction(f"批量改话题(选中 {n_s} 条)…", lambda: self.set_topic(sel)).setEnabled(not busy)
                mt.addAction(f"批量替换标题里的字(选中 {n_s} 条)…", lambda: self.replace_titles(sel)).setEnabled(not busy)
            ma = m.addMenu(f"「{nick}」这个号")
            ma.addAction(f"只检查「{nick}」的 {len(mine)} 条", lambda: self.run_check(mine)).setEnabled(not busy)
            ma.addAction(f"去企鹅号核对「{nick}」今天发了几条…", lambda: self.verify_one(nick))
            ma.addAction(f"给「{nick}」换个文件夹…", lambda: self.pick_folder(nick)).setEnabled(not busy)
            if nick in self.picked(self.day()):
                ma.addAction(f"「{nick}」不用手选的文件夹了(自动找)", lambda: self.unpick(nick)).setEnabled(not busy)
            if plan.quota_of(self.st, nick):
                ma.addAction(f"今天临时多发几条…(今天规定 {plan.quota_on(self.st, nick)} 条)",
                             lambda: self.add_extra_today(nick)).setEnabled(not busy)
            ma.addSeparator()
            ma.addAction(f"只发「{nick}」的…", lambda: self.run_publish(mine)).setEnabled(not busy)
            mo = m.addMenu("其它")
            mo.addAction("给别的号选文件夹…", lambda: self.pick_folder()).setEnabled(not busy)
            mo.addAction("全部展开", lambda: self.expand_all(True))
            mo.addAction("全部收起", lambda: self.expand_all(False))
            if sel:
                m.addSeparator()
                m.addAction(f"发布选中的 {n_s} 条…", lambda: self.run_publish(sel)).setEnabled(not busy)
            m.exec(self.tree.viewport().mapToGlobal(pos))
            return
        m.addAction("给别的号选文件夹…", lambda: self.pick_folder()).setEnabled(not busy)
        m.addAction("全部展开", lambda: self.expand_all(True))
        m.addAction("全部收起", lambda: self.expand_all(False))
        m.exec(self.tree.viewport().mapToGlobal(pos))

    @staticmethod
    def _open_file(path: str):
        try:
            os.startfile(path)
        except OSError:
            pass

    def set_wm_ok(self, i: int, ok: bool):
        """人看过截图:ok=True 是误报(没水印 / 不用管)→ 能发;False 确实有水印 → 不发。选了好几条一起标。"""
        rows = [r for r in (self.selected_rows() or [i]) if (self.videos[r].checks or {}).get("wm", {}).get("hits")]
        for r in rows or [i]:
            v = self.videos[r]
            wmstore.set_ok(v.path, ok)
            if v.checks and v.checks.get("wm"):
                v.checks["wm"]["ok"] = ok
            self._remember_check(v)
            self._fill(r)
        self.say(f"{len(rows) or 1} 条标成" + ("「没水印,能发」" if ok else "「有水印,先不发」"))
        self._update_scope()

    @staticmethod
    def _copy(t: str):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(t)

    def resolve_unsure(self, i: int, sent: bool):
        v = self.videos[i]
        self.rec.resolve_unsure(v.path, sent)
        self.state[i] = "已发" if sent else "没发成"
        self.say(f"「{v.title}」记成" + ("已发(你去后台看过了)" if sent else "没发(你去后台看过了,可以再发)"))
        self._fill(i)
        self.tree.clearSelection()                       # 右键标完别留着一个看不见的选择(体验报告)
        self._update_scope()

    def reveal(self, row: int):
        if 0 <= row < len(self.videos):
            from gui.window import MainWindow
            MainWindow.reveal(self.videos[row].path)

    # ---------------- 后台活 ----------------
    def _start(self, fn, title: str, quiet: bool = False):
        if self.busy():
            return False
        self._quiet = quiet
        self._job_title = (title.split(":")[0].split("(")[0].split(":")[0].rstrip("…") + "…") if title else ""
        self._busy(True)
        if title:
            self.say(title)
        self.job = Job(fn, self)
        self.job.row.connect(self._on_row)
        self.job.done.connect(self._on_done)
        self.job.start()
        return True

    def _stale(self) -> bool:
        """信号是不是从已经被换掉的旧任务来的(换日期时停掉的自动检查):是就不理,免得刷到新列表的别的行上。"""
        s = self.sender()
        return s is not None and s is not self.job

    def _on_row(self, i: int, t: str):
        if self._stale():
            return
        if i == PROGRESS:
            self.lab_scope.setText(t)
            self._pub_progress(t)
            self._update_sum()
            return
        if i < 0:
            self.say(t)
            return
        if self._pub and not self._pub["end"] and t.startswith("上传"):
            self._pub["cur"], self._pub["pct"] = i, t.split("%")[0].replace("上传", "").strip() + "%"
        if t == CLEAR:
            self.state.pop(i, None)
        elif t:
            if t.startswith("已发") and not self.state.get(i, "").startswith("已发"):
                self.today_sent = self.rec.sent_on(plan.today())
                v0 = self.videos[i]
                self._sent_keys.setdefault(self._dkey(v0.account, v0.title), {"date": v0.date, "path": v0.path})
            self.state[i] = t
            # 不再跟着滚到正在发的那条(用户 2026-10-18:发布的时候列表一直往回跳,没法上下翻看别的);进度看下面那行绿字
        if i in self.items:
            self._fill(i)

    def _on_done(self, msg: str):
        if self._stale():
            return
        self._quiet = False
        p = getattr(self, "_pub", None)
        if p and p.get("ok") and not p.get("end") and not self._auto:
            self._clear_notice()                         # 定时没发成以后,人自己点「现在发布」发成了:提醒清掉
        self._pub_end(msg or "")
        self._busy(False)
        if msg:
            self.say(msg)
        if self._auto == "发":                            # 定时发布发完了 / 停下了
            pop = getattr(self, "_popup", None)
            bad = bool(pop and pop[2]) or "停下了没发" in (msg or "")
            self._sched_end("⏰ 定时发布结束:" + (msg or ""), problem=bad)
        if getattr(self, "_show_bad_after", False):
            self._show_bad_after = False
            self.k_bad.setChecked(True)                   # 发完有失败的:直接只看有问题的
        pop = getattr(self, "_popup", None)
        self._popup = None
        if pop:
            QMessageBox.warning(self, pop[0], pop[1]) if pop[2] else QMessageBox.information(self, pop[0], pop[1])
        self._clean_empty_dirs()                          # 发空了的文件夹删掉(发了的已经在归档里,列表上「已发」照旧看得见,不用重读)
        self._sched_changed()
        self._reorder()                                   # 发完的号沉底
        if getattr(self, "_reload_after", False):          # 多的挪到明天了:重读列表(挪走的不在这天了)
            self._reload_after = False
            self.load()

    JUNK = ("thumbs.db", "desktop.ini", ".ds_store")

    def _clean_empty_dirs(self) -> int:
        """发完:这次发出去的视频原来所在的文件夹,视频都没了 → 剩下的图(和别的零碎文件)挪进发布归档,再删掉这个空文件夹
        (用户 2026-10-21:「每次发完视频该文件夹空了后自动把该文件夹删除」;选的:剩下的图挪走再删、16 个号的日期文件夹 + 手选的文件夹)。
        号的总文件夹、素材根目录、里面还有子文件夹 / 视频的,都不动。返回删了几个。"""
        dirs = dict(getattr(self, "_pub_dirs", {}) or {})
        self._pub_dirs = {}
        if not dirs:
            return 0
        roots = {os.path.normcase(os.path.abspath(r)) for r in self.roots()}
        acc_dirs = {os.path.normcase(os.path.abspath(p)) for ps in apisrc.account_folder_list(self.roots()).values() for p in ps}
        picked = {os.path.normcase(os.path.abspath(p)): (day, nick) for day, m in (self.st.get("api_picked") or {}).items()
                  for nick, p in (m or {}).items() if p}
        n = 0
        for d, acc in dirs.items():
            key = os.path.normcase(os.path.abspath(d))
            if key in roots or key in acc_dirs or not os.path.isdir(d):
                continue
            if os.path.normcase(os.path.dirname(os.path.abspath(d))) in roots:
                continue                                  # 直接在素材根目录下的(「2电竞赛事」这种号常年用的文件夹)不删
            if not (apisrc.date_key(os.path.basename(d)) or key in picked):
                continue                                  # 名字不是日期、也不是手选的:不动
            try:
                names = os.listdir(d)
            except OSError:
                continue
            paths = [os.path.join(d, x) for x in names]
            if any(os.path.isdir(p) for p in paths) or any(os.path.splitext(x)[1].lower() in apisrc.VIDEO_EXTS for x in names):
                continue                                  # 还有视频 / 子文件夹:没空
            rest = [p for p in paths if os.path.basename(p).lower() not in self.JUNK]
            try:
                dest = apisrc.archive_dir(self.st, "", acc)
                for p in rest:
                    plan.move_noclobber(p, dest)          # 剩下的封面图挪进归档(同一天、同一个游戏文件夹),不删
                for p in paths:
                    if os.path.basename(p).lower() in self.JUNK and os.path.isfile(p):
                        os.remove(p)                      # Thumbs.db 这种系统自己生成的,删
                os.rmdir(d)                               # 只删空的;里面又有了东西就删不掉,不硬删
            except OSError as e:
                self.say(f"「{d}」发完了,但文件夹没删掉:{e.strerror or e}")
                continue
            n += 1
            self.say(f"「{d}」发完空了,删了" + (f"(剩下 {len(rest)} 个文件挪进了发布归档)" if rest else ""))
            # 手选的文件夹删了:手选那条留着(这天这个号就没东西了),不回到自动找 —— 免得把别的日期文件夹(10.1)的视频列出来顺手发了
        return n

    def stop(self):
        if self.job and self.job.isRunning():
            self.job.stop()
            self.lab_scope.setText("正在停…等手上这条做完(上传大文件可能要一会儿)")
            self.b_stop.setEnabled(False)
            self.say("正在停…(手上这条做完就停)")

    def run_check(self, only: list[int] | None = None, quiet: bool = False, deep: bool = False):
        """deep = 高级检查:普通检查 + 查水印。普通检查过的(文件没变)不再做一遍,只查水印;水印查过的也不再查。"""
        rows = self.target_rows(only)
        if not rows or self.busy():
            return
        vs = self.videos
        words = self.st.get("api_platform_words") or None
        ff = vertical.ffmpeg_path()
        if deep:
            rows = [i for i in rows if not self._sent(i)]          # 发过的不用查水印了
            if not rows:
                QMessageBox.information(self, "高级检查", "这些都发过了,不用查水印。")
                return

        def fn(emit, stopped):
            done = [0]
            lock = threading.Lock()

            def one(i):
                if stopped():
                    return
                if not (deep and vs[i].checks):          # 高级检查:普通检查过的就不再做一遍
                    checks.check_one(vs[i], words, ff)
                    self._attach_wm(vs[i])
                    self._remember_check(vs[i])
                    emit(i, "")
                with lock:
                    done[0] += 1
                    k = done[0]
                if not deep and (k % 10 == 0 or k == len(rows)):
                    emit(PROGRESS, f"检查中 {k}/{len(rows)}…")
            with ThreadPoolExecutor(4) as ex:            # 4 条一起读(网络盘上一条条读太慢)
                list(ex.map(one, rows))
            if stopped():
                return "检查停下了"
            if not deep:
                self._ai_games(rows, emit, stopped)       # 关键词看不出是哪个游戏的:问 AI(问过的记着)
            if deep:
                self._scan_wm(rows, emit, stopped, ff)
                if stopped():
                    return "查水印停下了(查完的记着,下次接着查没查的)"
            got = [vs[i] for i in rows]
            land = sum(1 for v in got if checks.needs_vertical(v.checks))
            plat = sum(1 for v in got if v.checks.get("platform"))
            many = sum(1 for v in got if len(v.checks.get("tags") or []) > 1)
            fmt = sum(1 for v in got if len(v.checks.get("tags") or []) <= 1 and topic.bad_format(v.title))
            unread = sum(1 for v in got if v.checks.get("bad_read"))
            ok = sum(1 for v in got if not checks.problems(v))
            wm = sum(1 for v in got if checks.wm_blocks(v.checks.get("wm")))
            from qe import gamecheck
            alien = sum(1 for v in got if gamecheck.alien(v.account, v.title))
            return (("高级检查完" if deep else "检查完") + f":{len(got)} 条,能发 {ok};横屏 / 偏方 {land} · 标题有别的平台 {plat}(要你自己改)· "
                    f"多个话题 {many} · 话题写法 / 结尾空格 {fmt}" + (f" · 视频读不出来 {unread}" if unread else "") +
                    (f" · 有水印 {wm}(鼠标放在「要处理的」上看截图;不是水印就右键「没水印,能发」)" if deep else "") +
                    (f" · 标题像别的游戏 {alien}(是这个号的就右键「是这个号的,能发」)" if alien else "") +
                    ("" if ok == len(got) or deep else "。标题乱码 / @ / 话题问题点「整理标题」一键改"))
        self._start(fn, "" if quiet else (f"高级检查中…({self._who(rows)})" if deep else f"检查中…({self._who(rows)})"),
                    quiet=quiet)

    def _ai_games(self, rows: list[int], emit, stopped) -> int:
        """关键词看不出是哪个游戏的标题(「哈哈哈」「G镇六个苟分点」),按号一批问 AI(百炼),答案记在 游戏判断.json。
        没填 Key / 出错:只按关键词查,写一句日志。返回问了几条。"""
        from qe import gamecheck
        key = self.st.ai_key() if hasattr(self.st, "ai_key") else ""
        if not key:
            return 0
        vs = self.videos
        by: dict[str, list[int]] = {}
        for i in rows:
            if not self._sent(i) and gamecheck.need_ai(vs[i].account, vs[i].title):
                by.setdefault(vs[i].account, []).append(i)
        if by:
            emit(PROGRESS, f"问 AI 这些标题是哪个游戏的 · {sum(map(len, by.values()))} 条…")
        n = 0
        for nick, idx in by.items():
            for k in range(0, len(idx), 40):
                if stopped():
                    return n
                part = idx[k:k + 40]
                try:
                    got = gamecheck.ask_ai(gamecheck.account_game(nick), [vs[i].title for i in part], key)
                except Exception as e:
                    emit(-1, f"AI 判断是哪个游戏没成({str(e)[:60]}),这次只按关键词查")
                    return n
                gamecheck.store().set_ai(got)
                n += len(got)
                for i in part:
                    emit(i, "")
        return n

    def _game_home(self, game: str) -> tuple[str, str] | None:
        """这个游戏的号和它的素材文件夹(「三角洲行动」→(三角洲密探君, …\三角洲行动--三角洲密探君));没有就 None。"""
        from qe import gamecheck
        folders = apisrc.account_folders(self.roots(), self.known())
        for nick, g in gamecheck.ACCOUNT_GAME.items():
            if g == game and folders.get(nick):
                return nick, folders[nick]
        return None

    def move_to_game(self, i: int):
        """标题像别的游戏、真放错了:视频连同名封面挪到那个游戏号同一天的文件夹(没有就建)。选了好几条就挪选中的里像别的游戏的。"""
        from qe import gamecheck
        rows = [r for r in (self.selected_rows() or [i]) if not self._sent(r)]
        moved, miss = [], []
        for r in rows:
            v = self.videos[r]
            g = gamecheck.alien(v.account, v.title) or gamecheck.ai_hint(v.account, v.title)
            home = self._game_home(g) if g else None
            if not home:
                miss.append(v.title)
                continue
            d = os.path.dirname(v.path)
            dst = os.path.join(home[1], os.path.basename(d))
            stem = os.path.splitext(os.path.basename(v.path))[0].strip()
            try:
                covers = [os.path.join(d, x) for x in os.listdir(d)
                          if os.path.splitext(x)[1].lower() in (".jpg", ".jpeg", ".png", ".webp") and os.path.splitext(x)[0].strip() == stem]
                for f in [v.path] + covers:
                    plan.move_noclobber(f, dst)
                moved.append(f"{v.title[:20]} → {home[0]}")
            except OSError as e:
                miss.append(f"{v.title[:20]}({e})")
        if moved:
            self.say(f"放错了的挪走了 {len(moved)} 条:" + ";".join(moved[:5]) + ("…" if len(moved) > 5 else ""))
        if miss:
            QMessageBox.warning(self, "挪走", f"{len(miss)} 条没挪(找不到那个游戏的号的文件夹 / 挪不动):\n" + "\n".join(miss[:8]))
        if moved:
            self.tree.clearSelection()
            self.load()

    def confirm_game_ok(self, i: int):
        """右键「看过了,是这个号的,能发」:直接标(用户 2026-10-21:原来还要再确认一次、默认「先不」,
        点完菜单以为好了,其实没标上,还是「要处理」)。菜单里这一项本身就是确认;「放错了:挪到…」排在它前面。"""
        self.set_game_ok(i, True)

    def set_game_ok(self, i: int, ok: bool):
        """标题像别的游戏、人看过:是这个号的(能发)/ 其实不是(先不发)。选了好几条一起标。"""
        from qe import gamecheck
        rows = self.selected_rows() or [i]
        for r in rows:
            gamecheck.store().set_ok(self.videos[r].account, self.videos[r].title, ok)
            self._fill(r)
        self.say(f"{len(rows)} 条标成" + ("「是这个号的,能发」" if ok else "「不是这个号的,先不发」"))
        self._update_sum()                               # 大字「还有 N 条有点小问题」、号那一行一起更新
        self._update_scope()

    def set_batch_ok(self, nick: str, ok: bool):
        """可能整批放错了的号:人看过,确认没放错(这天整批放行)/ 取消确认。"""
        from qe import gamecheck
        gamecheck.store().set_batch_ok(nick, self.day(), ok)
        self.say(f"「{nick}」{self.day()}:" + ("确认没放错,这批能发了" if ok else "取消确认,这批先不发"))
        self._refresh_blocked()
        for i in self.rows_of(nick):
            self._fill(i, group=False)
        self._fill_group(nick)
        self._update_scope()

    def _scan_wm(self, rows: list[int], emit, stopped, ff: str):
        """查水印(后台线程里):查过、文件没变的不再查;3 条一起查(解码 + 找 logo 吃 CPU)。"""
        from qe import watermark as WM
        vs = self.videos
        todo = []
        for i in rows:
            w = wmstore.get(vs[i].path)
            if w is not None:
                vs[i].checks["wm"] = w
                emit(i, "")
            else:
                todo.append(i)
        if not todo:
            return
        done = [0]
        lock = threading.Lock()
        emit(PROGRESS, f"查水印 0/{len(todo)}…(一条几秒,点「停」随时停,查完的记着)")

        def one(i):
            if stopped():
                return
            v = vs[i]
            emit(i, "查水印中…")
            try:
                info = {"w": v.checks.get("w", 0), "h": v.checks.get("h", 0), "dur": v.checks.get("dur", 0)}
                res = WM.detect(v.path, ff, info, stop=stopped)
            except Exception as e:                      # 查不了不拦着(和没查一样),日志里说一声
                emit(-1, f"「{v.title}」查水印出错:{type(e).__name__} {e}")
                emit(i, CLEAR)
                return
            if stopped():
                emit(i, CLEAR)
                return
            v.checks["wm"] = wmstore.put(v.path, res)
            self._remember_check(v)
            emit(i, CLEAR)
            with lock:
                done[0] += 1
                k = done[0]
            emit(PROGRESS, f"查水印 {k}/{len(todo)}…")
        with ThreadPoolExecutor(3) as ex:
            list(ex.map(one, todo))

    def _who(self, rows: list[int]) -> str:
        accs = sorted({self.videos[i].account for i in rows})
        return f"{accs[0]} 的 {len(rows)} 条" if len(accs) == 1 else f"{len(accs)} 个号 {len(rows)} 条"

    def run_vertical(self, only: list[int] | None = None):
        if self.busy():
            return
        rows = [i for i in self.target_rows(only) if checks.needs_vertical(self.videos[i].checks) and not self._sent(i)]
        if not rows:
            QMessageBox.information(self, "横屏转竖屏", "这些里没有横屏 / 偏方的(没检查过的先点「检查」)。")
            return
        if not ask(self, "横屏转竖屏", f"{self._who(rows)}转成标准竖屏(1080×1920)?横屏、偏方(3:4 / 正方形)的都转。\n\n转好的用原来的名字放回去,原来的横屏视频直接删掉(转失败的不动)。", "转", "先不"):
            return
        vs = self.videos
        ff = vertical.ffmpeg_path()
        words = self.st.get("api_platform_words") or None

        def one(i, emit, stopped):
            v = vs[i]
            emit(i, "转竖屏中…")
            try:
                new, _orig = vertical.to_vertical(v.path, ff, stop=stopped, keep_orig=False)   # 用户 2026-10-20:原片不要了
            except Exception as e:
                if stopped() or str(e) == "停下了":
                    emit(i, "停下了,没转")
                    return
                emit(i, "转竖屏失败")
                emit(-1, f"「{v.title}」转竖屏失败:{e}")
                return
            v.path = new
            checks.check_one(v, words, ff)
            v.checks["converted"] = True
            self._remember_check(v)
            emit(i, CLEAR)

        def fn(emit, stopped):
            t0, done, lock = time.time(), [0], threading.Lock()
            emit(PROGRESS, f"转竖屏:已转 0 / {len(rows)} 条…")

            def step(i):
                if stopped():
                    return
                one(i, emit, stopped)
                with lock:
                    done[0] += 1
                    k = done[0]
                left = (time.time() - t0) / k * (len(rows) - k)    # 老手试用:113 条转 7 分半,原来只写「转竖屏…」不知道还要多久
                emit(PROGRESS, f"转竖屏:已转 {k} / {len(rows)} 条" +
                     ("" if k == len(rows) else f" · 还要约 {max(1, round(left / 60))} 分钟" if left >= 60 else " · 马上好"))
            with ThreadPoolExecutor(3) as ex:          # 3 条一起转最快(这台电脑试过)
                list(ex.map(step, rows))
            return "转竖屏做完了"
        self._start(fn, f"转竖屏:{len(rows)} 条(3 条一起转)")

    def run_blur(self, only: list[int] | None = None):
        """查到水印的糊掉(高级检查查出来的框、只糊出现的那几段)。原片挪进「水印原片」。"""
        if self.busy():
            return
        from qe import blur
        rows = [i for i in self.target_rows(only) if checks.wm_blocks((self.videos[i].checks or {}).get("wm"))
                and not self._sent(i) and blur.boxes_of(self.videos[i].checks["wm"])]
        if not rows:
            QMessageBox.information(self, "模糊水印", "这些里没有查到水印的(还没查的先点「检查 → 高级检查」)。")
            return
        if not ask(self, "模糊水印", f"{self._who(rows)}:把查到的水印糊掉(只糊水印出现的那几段)?\n\n"
                   "原片挪进同一个文件夹里的「水印原片」,不删。糊完鼠标放在那条上能看截图对不对。", "糊掉", "先不"):
            return
        vs = self.videos
        ff = vertical.ffmpeg_path()
        words = self.st.get("api_platform_words") or None

        def one(i, emit, stopped):
            v = vs[i]
            wm = dict(v.checks["wm"])
            emit(i, "糊水印中…")
            try:
                new, _orig = blur.blur(v.path, blur.boxes_of(wm), ff, stop=stopped)
            except Exception as e:
                if stopped() or str(e) == "停下了":
                    emit(i, "停下了,没糊")
                    return
                emit(i, CLEAR)
                emit(-1, f"「{v.title}」模糊水印失败:{e}")
                return
            v.path = new
            checks.check_one(v, words, ff)
            v.checks["wm"] = wmstore.put(new, wm, ok=True, blurred=True)   # 糊过的不再拦
            self._remember_check(v)
            emit(i, CLEAR)
            emit(-1, f"「{v.title}」糊掉了:{checks.wm_text(wm)}")

        def fn(emit, stopped):
            with ThreadPoolExecutor(2) as ex:
                list(ex.map(lambda i: None if stopped() else one(i, emit, stopped), rows))
            return "模糊水印做完了(原片在各自文件夹的「水印原片」里)"
        self._start(fn, f"模糊水印:{len(rows)} 条")

    def run_ads(self, only: list[int] | None = None):
        """查口播广告:转文字(本地模型,转过的不再转)→ 找广告词。查到的标「口播广告 N 处」不发。"""
        if self.busy():
            return
        from qe import asr
        if not asr.model_dir():
            QMessageBox.information(self, "查口播广告", "这台电脑上没有语音识别模型(ainame 的 sense-voice),查不了。")
            return
        rows = [i for i in self.target_rows(only) if not self._sent(i)]
        if not rows:
            return
        vs = self.videos
        ff = vertical.ffmpeg_path()
        words = self.st.get("api_platform_words") or None
        from qe import ads
        kw = ads.split_keywords(self.st.get("ad_keywords") or ads.DEFAULT_KEYWORDS)

        def fn(emit, stopped):
            T = asr.shared(ff)
            n = [0]
            for i in rows:
                if stopped():
                    return "查口播广告停下了(查完的记着)"
                v = vs[i]
                if not v.checks:
                    checks.check_one(v, words, ff)
                    self._attach_wm(v)
                old = wmstore.ADS.get(v.path)
                if old is None:
                    emit(i, "听广告中…")
                    try:
                        sents = T.transcribe(v.path, stop=stopped)
                    except Exception as e:
                        emit(i, CLEAR)
                        emit(-1, f"「{v.title}」查口播广告出错:{e}")
                        continue
                    if stopped():
                        emit(i, CLEAR)
                        return "查口播广告停下了(查完的记着)"
                    old = wmstore.ADS.put(v.path, {"hits": ads.groups(sents, kw)})
                v.checks["ads"] = old
                self._remember_check(v)
                emit(i, CLEAR)
                n[0] += 1
                emit(PROGRESS, f"查口播广告 {n[0]}/{len(rows)}…")
            bad = sum(1 for i in rows if checks.wm_blocks(vs[i].checks.get("ads")))
            return (f"查口播广告完了:{len(rows)} 条,有广告 {bad}(鼠标放在「要处理的」上看是哪几句;"
                    "要剪就点「去水印 / 广告 → 剪掉口播广告」,不是广告就右键「不是广告,能发」)")
        self._start(fn, f"查口播广告:{self._who(rows)}(一条几秒,转过的不再转)")

    def run_cut(self, only: list[int] | None = None):
        """把查到的口播广告那几句剪掉。原片挪进「广告原片」。"""
        if self.busy():
            return
        from qe import ads, cut
        rows = [i for i in self.target_rows(only) if checks.wm_blocks((self.videos[i].checks or {}).get("ads"))
                and not self._sent(i)]
        if not rows:
            QMessageBox.information(self, "剪掉口播广告", "这些里没有查到口播广告的(还没查的先点「检查 → 查口播广告」)。")
            return
        lines = []
        for i in rows[:6]:
            h = self.videos[i].checks["ads"]["hits"]
            lines.append(f"· {self.videos[i].title[:20]}:" + ";".join(f"{int(x['start']) // 60}:{int(x['start']) % 60:02d}「{x['text'][:14]}」"
                                                                       for x in h[:2]))
        if not ask(self, "剪掉口播广告", f"{self._who(rows)}:把这些广告句剪掉(前后各多剪 0.3 秒)?\n\n" + "\n".join(lines) +
                   ("\n…" if len(rows) > 6 else "") + "\n\n原片挪进同一个文件夹里的「广告原片」,不删。", "剪掉", "先不"):
            return
        vs = self.videos
        ff = vertical.ffmpeg_path()
        words = self.st.get("api_platform_words") or None

        def one(i, emit, stopped):
            v = vs[i]
            hits = list(v.checks["ads"]["hits"])
            emit(i, "剪广告中…")
            try:
                new, _orig, gone = cut.cut(v.path, hits, ff, stop=stopped)
            except Exception as e:
                if stopped() or str(e) == "停下了":
                    emit(i, "停下了,没剪")
                    return
                emit(i, CLEAR)
                emit(-1, f"「{v.title}」剪广告失败:{e}")
                return
            v.path = new
            checks.check_one(v, words, ff)
            v.checks["ads"] = wmstore.ADS.put(new, {"hits": hits}, ok=True, blurred=True)   # 剪过的不再拦
            self._remember_check(v)
            emit(i, CLEAR)
            emit(-1, f"「{v.title}」剪掉了 {gone} 秒口播广告")

        def fn(emit, stopped):
            with ThreadPoolExecutor(2) as ex:
                list(ex.map(lambda i: None if stopped() else one(i, emit, stopped), rows))
            return "剪口播广告做完了(原片在各自文件夹的「广告原片」里)"
        self._start(fn, f"剪掉口播广告:{len(rows)} 条")

    def set_title_ad_ok(self, i: int, ok: bool):
        """标题有广告词的(视频里八成有广告):人剪好了 / 看过不是广告 → 能发。选了好几条就一起标。"""
        rows = [r for r in (self.selected_rows() or [i]) if titleclean.ad_words(self.videos[r].title)] or [i]
        for r in rows:
            v = self.videos[r]
            titleclean.store().set(v.account, v.title, ok)
            self._fill(r)
        self.say(f"{len(rows)} 条标题有广告词的标成" + ("「剪好了,能发」" if ok else "「还没剪,先不发」"))
        self._update_scope()

    def set_ad_ok(self, i: int, ok: bool):
        rows = [r for r in (self.selected_rows() or [i]) if (self.videos[r].checks or {}).get("ads", {}).get("hits")]
        for r in rows or [i]:
            v = self.videos[r]
            wmstore.ADS.set_ok(v.path, ok)
            if v.checks and v.checks.get("ads"):
                v.checks["ads"]["ok"] = ok
            self._remember_check(v)
            self._fill(r)
        self.say(f"{len(rows) or 1} 条标成" + ("「不是广告,能发」" if ok else "「是广告,先不发」"))
        self._update_scope()

    def _sent(self, i: int) -> bool:
        """已发 / 结果不明:不能再发、不能再改名(改名会让防重发认不出来)。"""
        st = self.state.get(i, "")
        return st.startswith("已发") or st == "结果不明"

    # ---------------- 改名(话题 / 标题),都记台账能撤销 ----------------
    @staticmethod
    def _op(what: str) -> str:
        """台账的批次:一次操作一批(审查:原来按秒分批,同一秒的两次操作会被一起撤销)。"""
        return f"{bj_str()}¦{what}¦{uuid.uuid4().hex[:6]}"

    def _after_rename(self, v, moves):
        old = v.path
        v.path = moves[0][1]
        v.title = os.path.splitext(os.path.basename(v.path))[0]
        if v.checks:
            v.checks["tags"] = topic.split_topics(v.title)["tags"]
            v.checks["platform"] = checks.platform_hits(v.title, self.st.get("api_platform_words") or None)
        hit = self.cache.pop(pkey(old), None)
        wmstore.move(old, v.path)                        # 查水印 / 口播广告的结果跟着新名字走
        wmstore.ADS.move(old, v.path)
        if hit:
            self._remember_check(v)

    def _rename_rows(self, rows: list[int], make, what: str, note=None) -> int:
        """在界面线程里直接改(只是改文件名,很快)。make(标题) → 新标题 / None。返回改了几条。"""
        at = self._op(what)
        n = 0
        for i in rows:
            v = self.videos[i]
            if self._sent(i):
                continue
            new = make(v.title)
            if not new:
                continue
            try:
                moves = topic.rename_logged(v.path, new, self.ledger, at)
            except OSError as e:
                self.say(f"「{v.title}」{what}失败:{e.strerror or e}")
                continue
            old = v.title
            self._after_rename(v, moves)
            self._fill(i)
            self.say(f"{what}:{old} → {v.title}" + (f"({note(old)})" if note and note(old) else ""))
            n += 1
        if n:                                            # 改了名:重复的可能变了(改成不同名就能发了)
            self._refresh_dups()
            for k in range(len(self.videos)):
                self._fill(k, group=False)
            self._update_sum()
        self._update_scope()
        return n

    def set_topic(self, rows: list[int] | None = None):
        rows = self.selected_rows() if rows is None else rows
        rows = [i for i in rows if not self._sent(i)]
        if not rows:
            QMessageBox.information(self, "批量改话题", "先在列表里选要改的(点号那一行 = 这个号全部;按住 Ctrl 可以多选)。")
            return
        last = str(self.st.get("api_last_topic") or "")
        # 现成的选项:这些视频上已经挂着的话题(按出现次数),再加上次填的;也能直接打字(体验报告)
        cnt: dict[str, int] = {}
        for i in rows:
            for t in topic.split_topics(self.videos[i].title)["tags"]:
                cnt[t] = cnt.get(t, 0) + 1
        opts = [t for t, _n in sorted(cnt.items(), key=lambda x: -x[1])][:12]
        if last and last not in opts:
            opts.insert(0, last)
        tag, ok = QInputDialog.getItem(self, "批量改话题", f"{self._who(rows)},结尾的话题全换成(可以选,也可以直接打字,不用打 #):",
                                       opts or [""], 0, True)
        tag = topic.clean_tag(tag) if ok else ""
        if not tag:
            return
        ex = next((topic.with_topic(self.videos[i].title, tag) for i in rows if topic.with_topic(self.videos[i].title, tag)), None)
        if not ex:
            QMessageBox.information(self, "批量改话题", f"选中的已经都是 #{tag} 了。")
            return
        if not ask(self, "批量改话题", f"{self._who(rows)}的话题全换成 #{tag}?\n\n比如:\n{ex}\n\n同名封面跟着改。改错了点「撤销上次改名」。",
                   "改", "先不"):
            return
        self.st["api_last_topic"] = tag
        self.st.save()
        n = self._rename_rows(rows, lambda t: topic.with_topic(t, tag), f"批量改成 #{tag}")
        self.say(f"批量改话题:{n} 条改成 #{tag}")

    @staticmethod
    def _tidy_note(old: str) -> str:
        new = topic.tidy(old)
        return "去掉结尾空格" if new is not None and new == old.rstrip() else ""

    def tidy_titles(self, only: list[int] | None = None):
        rows = [i for i in self.target_rows(only) if topic.bad_format(self.videos[i].title) and not self._sent(i)]
        if not rows:
            QMessageBox.information(self, "整理写法", "这些里没有话题写法不对 / 结尾多空格的。")
            return
        ex = "\n".join(f"{self.videos[i].title!r}\n  → {topic.tidy(self.videos[i].title)!r}" for i in rows[:3])
        if not ask(self, "整理写法", f"{self._who(rows)}话题写法不对 / 结尾多了空格,一键改好?(不用 AI)\n\n比如:\n{ex}\n\n"
                                     "同名封面跟着改。改错了点「撤销上次改名」。", "改", "先不"):
            return
        n = self._rename_rows(rows, topic.tidy, "整理写法", note=self._tidy_note)
        self.say(f"整理写法:改了 {n} 条")

    def edit_title(self, i: int):
        if not (0 <= i < len(self.videos)) or self._sent(i):
            return
        v = self.videos[i]
        hits = (v.checks or {}).get("platform") or []
        t, ok = self._ask_title("标题(= 文件名)" + (f",里面有「{'、'.join(hits)}」" if hits else "") + ":", v.title)
        t = topic.sanitize(t) if ok else ""
        if not t or t == v.title:
            return
        self._rename_rows([i], lambda _old: t, "改标题")
        self.tree.clearSelection()                       # 改完别留着选中(老手试用:按钮一直只管这 1 条)
        self._goto_next_problem(i)

    def _ask_title(self, label: str, text: str) -> tuple[str, bool]:
        """改标题的框:宽到能看全一整行(老手试用:原来 200 多像素,40 字的标题只看得到结尾)。"""
        d = QInputDialog(self)
        d.setWindowTitle("改标题")
        d.setLabelText(label)
        d.setTextValue(text)
        d.setMinimumWidth(min(760, max(520, self.fontMetrics().horizontalAdvance(text) + 120)))
        ok = d.exec() == QInputDialog.DialogCode.Accepted
        return d.textValue(), ok

    def _goto_next_problem(self, i: int):
        """改完一条:光标(不是选中)跳到它后面下一条要处理的,按 F2 接着改(老手试用:原来光标停在看不见的行上)。"""
        order = [self.tree.topLevelItem(k).child(j).data(0, ROW) for k in range(self.tree.topLevelItemCount())
                 for j in range(self.tree.topLevelItem(k).childCount())]
        if i not in order:
            return
        k = order.index(i)
        for r in order[k + 1:] + order[:k]:
            it = self.items.get(r)
            if it is None or it.isHidden() or self._sent(r):
                continue
            st, probs = self._status_text(r)
            if probs:
                from PySide6.QtCore import QItemSelectionModel
                self.tree.setCurrentItem(it, 0, QItemSelectionModel.SelectionFlag.NoUpdate)
                self.tree.scrollToItem(it)
                return

    def replace_titles(self, rows: list[int] | None = None):
        """批量替换标题里的字:「快手热门」换成别的 / 删掉。管选中的,没选管看得见的全部;先预览,改完能撤销(老手试用)。"""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QVBoxLayout
        rows = [i for i in self.target_rows(rows) if not self._sent(i)]
        if not rows:
            QMessageBox.information(self, "批量替换", "没有能改的(发过的不改)。")
            return
        d = QDialog(self)
        d.setWindowTitle("批量替换标题里的字")
        d.resize(620, 460)
        v = QVBoxLayout(d)
        f = QFormLayout()
        e_find, e_to = QLineEdit(), QLineEdit()
        e_find.setPlaceholderText("比如:快手热门")
        e_to.setPlaceholderText("空着 = 删掉")
        f.addRow("把", e_find)
        f.addRow("换成", e_to)
        v.addLayout(f)
        lab = QLabel(f"管:{self._who(rows)}(发过的不改)")
        lab.setObjectName("muted")
        v.addWidget(lab)
        pv = QPlainTextEdit()
        pv.setReadOnly(True)
        v.addWidget(pv, 1)
        bb = QDialogButtonBox()
        b_ok = bb.addButton("改", QDialogButtonBox.ButtonRole.AcceptRole)
        bb.addButton("先不", QDialogButtonBox.ButtonRole.RejectRole)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        v.addWidget(bb)

        def make(t: str):
            a = e_find.text()
            if not a or a not in t:
                return None
            new = topic.sanitize(" ".join(t.replace(a, e_to.text()).split()))
            return new if new and new != t else None

        def show():
            hit = [(self.videos[i].title, make(self.videos[i].title)) for i in rows]
            hit = [(o, n) for o, n in hit if n]
            pv.setPlainText("\n".join(f"{o}\n  → {n}" for o, n in hit[:40]) + (f"\n…还有 {len(hit) - 40} 条" if len(hit) > 40 else "")
                            if hit else ("没有标题里有这几个字的" if e_find.text() else "上面填要换掉的字"))
            b_ok.setText(f"改这 {len(hit)} 条")
            b_ok.setEnabled(bool(hit))
        e_find.textChanged.connect(lambda _t: show())
        e_to.textChanged.connect(lambda _t: show())
        show()
        if d.exec() != QDialog.DialogCode.Accepted:
            return
        n = self._rename_rows(rows, make, "批量替换")
        self.say(f"批量替换:改了 {n} 条(「{e_find.text()}」→「{e_to.text() or '删掉'}」;点「更多 → 撤销」能改回去)")

    def run_topic(self, only: list[int] | None = None):
        """整理标题:先删乱码尾巴 / @ 那段(titleclean,不用 AI);话题写法不对的按固定规矩改;挂了好几个话题的 AI 留一个。"""
        if self.busy():
            return
        only = self.target_rows(only)

        def base(v):                                 # 先删乱码尾巴 / @ 那段(titleclean),再看话题
            return titleclean.clean(v.title) or v.title

        def multi(v):
            return len(topic.split_topics(base(v))["tags"]) > 1
        rows = [i for i in only if (multi(self.videos[i]) or topic.bad_format(base(self.videos[i]))
                                    or base(self.videos[i]) != self.videos[i].title) and not self._sent(i)]
        if not rows:
            QMessageBox.information(self, "整理标题", "这些里标题都没问题(没有乱码、@、话题问题)。")
            return
        n_ai = sum(1 for i in rows if multi(self.videos[i]))
        n_junk = sum(1 for i in rows if base(self.videos[i]) != self.videos[i].title)
        n_fmt = sum(1 for i in rows if not multi(self.videos[i]) and topic.bad_format(base(self.videos[i])))
        key = self.st.ai_key() if hasattr(self.st, "ai_key") else ""
        no_key = 0
        if n_ai and not key:                         # 新员工试用:原来没 Key 就整个不改 → 不用 AI 的先改,只跳过要 AI 的
            no_key, n_ai = n_ai, 0
            rows = [i for i in rows if not multi(self.videos[i])]
            if not rows:
                QMessageBox.warning(self, "整理标题", f"这 {no_key} 条挂了好几个话题,要用 AI 挑一个,先在「设置」里填阿里百炼 Key。")
                return
        model = str(self.st.get("topic_model") or "qwen-plus")
        lines = []
        if no_key:
            lines.append(f"· {no_key} 条挂了好几个话题要 AI 挑,还没填阿里百炼 Key,这次先不改(设置里填了再点)")
        if n_junk:
            ex = next(self.videos[i] for i in rows if base(self.videos[i]) != self.videos[i].title)
            lines.append(f"· {n_junk} 条标题有乱码 / @ 那段:删掉(比如「{ex.title[:30]}」→「{base(ex)[:30]}」)")
        if n_fmt:
            lines.append(f"· {n_fmt} 条话题写法不对 / 结尾多空格:按固定规矩改(不用 AI)")
        if n_ai:
            lines.append(f"· {n_ai} 条挂了好几个话题:AI 各留一个最好搜的(游戏 / 电视剧 / 电影 / 动漫名优先)")
        if not ask(self, "整理标题", f"{self._who(only)}里面:\n" + "\n".join(lines) +
                   "\n\n改文件名,同名的封面图跟着改。改错了可以点「撤销上次改名」。", "整理", "先不"):
            return
        vs = self.videos
        at = self._op("整理标题")
        lock = threading.Lock()

        def one(i, emit, stopped):
            v = vs[i]
            if stopped():
                return
            try:
                name = None
                b0 = base(v)
                if not multi(v):
                    name = topic.tidy(b0)                # 只是写法不对:固定规矩改,不问 AI
                else:
                    for k in range(2):                   # 读不出顺序再问一次
                        try:
                            name = topic.new_name(b0, lambda b, t: topic.ask_ai(b, t, key, model))
                            break
                        except RuntimeError:
                            if k:
                                raise
                if not name and b0 != v.title:          # 只删了乱码 / @
                    name = b0
                if not name:
                    emit(i, "")
                    return
                note = self._tidy_note(v.title) if not multi(v) else ""
                with lock:
                    moves = topic.rename_logged(v.path, name, self.ledger, at)
                old = v.title
                self._after_rename(v, moves)
                emit(i, "")
                emit(-1, f"整理标题:{old} → {v.title}" + (f"({note})" if note else ""))
            except Exception as e:
                emit(-1, f"「{v.title}」整理标题失败:{e}")

        def fn(emit, stopped):
            with ThreadPoolExecutor(4) as ex:
                list(ex.map(lambda i: one(i, emit, stopped), rows))
            return "整理标题做完了"
        self._start(fn, f"整理标题:{len(rows)} 条" + (f"(其中 {n_ai} 条问 AI)" if n_ai else ""))

    def undo_topic(self):
        b = self.ledger.last()
        if not b:
            QMessageBox.information(self, "撤销", "没有能撤销的改名。")
            return
        n = len(topic.Ledger.groups_of(b))
        if not ask(self, "撤销", f"撤销「{topic.Ledger.label(b)}」:把那次改的 {n} 条视频(和跟着改的封面)改回原名?\n\n"
                                 "已经发了的不改回去(免得被当成新视频再发一次)。", "撤销", "先不"):
            return
        ok, bad, skipped = self.ledger.undo_last(skip=self.rec.blocked)
        self.say(f"撤销「{topic.Ledger.label(b)}」:改回 {ok} 个文件" + (f",{bad} 个改不回(文件不在了或原名被占)" if bad else "") +
                 (f";{skipped} 条已经发了(或结果不明),不改回去" if skipped else ""))
        self.load()

    # ---------------- 发布 ----------------
    def run_publish(self, only: list[int] | None = None, auto: bool = False):
        """only = 只发这几行(右键「只发这个号的」);None = 选中的,没选就是看得见的全部。发之前一定弹框让人点「发」。
        auto = 定时发布到点了(人定时的时候已经确认过):不弹框,有问题的 / 没检查出来的跳过,能发的都发。"""
        d = self.day()
        if not d or self.busy():
            return
        if auto:
            QMessageBox = self._auto_box = _SayBox(self.say)   # noqa: N806 定时发布没人看着:要弹的框改成写日志
        else:
            from PySide6.QtWidgets import QMessageBox
        picked = only is not None or bool(self.selected_rows())
        self._pub_dirs = {}                              # 这次发出去的视频原来在哪个文件夹 → 号(发完看空没空,空了删)
        scope = self.target_rows(only)
        if not scope:
            return
        unchecked = [i for i in scope if not self.videos[i].checks and not self._sent(i)]
        if unchecked and auto:
            self.say(f"⚠ 有 {len(unchecked)} 条没检查出来(文件打不开?),这次不发")
        elif unchecked:
            QMessageBox.information(self, "发布", f"还有 {len(unchecked)} 条没检查完,等检查完(或点「检查」)再发。")
            return
        rows = [i for i in scope if self._can_send(i) and not self.rec.blocked(self.videos[i].path)]
        if not rows:
            if not picked and self.filtering():
                QMessageBox.information(self, "发布", "现在开着「只看有问题的」/ 搜索,看得见的这些里没有能发的。\n\n"
                                                    "要发全部:先取消勾选「只看有问题的」、清空搜索。")
            else:
                QMessageBox.information(self, "发布", "选的这些里没有能发的(有问题的 / 发过的不发)。" if picked else "没有能发的。")
            return
        accs = {a["nick"]: a for a in apiacc.load()}
        miss = sorted({self.videos[i].account for i in rows if self.videos[i].account not in accs})
        if miss:
            QMessageBox.warning(self, "发布", "这些号还没搬账号:" + "、".join(miss))
            return
        seen: dict[str, str] = {}
        dup = []
        for i in rows:
            k, acc = pkey(self.videos[i].path), self.videos[i].account
            if k in seen and seen[k] != acc:
                dup.append((self.videos[i].title, seen[k], acc))
            seen.setdefault(k, acc)
        if dup:
            t, a1, a2 = dup[0]
            QMessageBox.warning(self, "发布", f"有 {len(dup)} 条视频同时挂在两个号下面(比如「{t[:24]}」在「{a1}」和「{a2}」),"
                                             "一条视频只能发一个号。\n\n多半是两个号手选了同一个文件夹:右键号 →「换个文件夹」改对了再发。")
            return
        held = sum(1 for i in scope if not self._sent(i)) - len(rows)
        retry = sum(1 for i in rows if self.state.get(i, "").startswith(FAILED[:2]))
        by_acc: dict[str, list[int]] = {}
        for i in rows:
            by_acc.setdefault(self.videos[i].account, []).append(i)
        # 每天规定条数的闸(用户 2026-10-20 PUBG 多发了 21 条):每个号最多发到规定条数;没发成的拿下一条补;
        # 发够了这个号还没发的挪到明天的文件夹。设置里「开闸」才不管
        sent0 = self.rec.sent_on(plan.today())
        left_of = {n: plan.left_today(self.rec, self.st, n, sent=sent0) for n in by_acc}
        full = [n for n, x in left_of.items() if x == 0]
        for n in full:
            by_acc.pop(n)
        tmr = plan.tomorrow_folder()
        if not by_acc:
            moved = sum(self._spill(n) for n in full)
            QMessageBox.information(self, "发布", f"这些号今天已经发够规定条数了:{'、'.join(full)}。这次不发。" +
                                    (f"\n\n它们还没发的 {moved} 条挪到了明天的文件夹({tmr})。" if moved else "") +
                                    "\n\n真要多发:去「设置」里打开「开闸:允许超过每天规定条数」。")
            if moved:
                self.load()
            return
        plan_n = sum(len(idx) if left_of[n] is None else min(len(idx), left_of[n]) for n, idx in by_acc.items())
        over = sum(len(idx) for idx in by_acc.values()) - plan_n
        quota_line = (("⚠ 闸开着:不管每天规定条数,能发的都发。\n" if self.st.get("quota_open", False) else "") +
                      (f"按每天规定条数:" + "、".join(f"{n} 还能发 {left_of[n]} 条" for n, idx in by_acc.items()
                                               if left_of[n] is not None and len(idx) > left_of[n]) +
                       f",多的 {over} 条发够以后挪到明天的文件夹({tmr})。\n" if over else "") +
                      (f"今天已经发够的号这次不发:{'、'.join(full)}(它们没发的也挪到明天)。\n" if full else ""))
        par = max(1, _num(self.st.get("api_threads"), 1))
        per_acc = max(1, min(5, _num(self.st.get("api_per_acc"), 1)))   # 同一个号一次传几条(用户 2026-10-19,默认 1)
        gap = max(0.0, float(_num(self.st.get("api_interval"), 5)))
        by_game = bool(self.st.get("api_archive_by_game", True))
        dest = apisrc.archive_dir(self.st)                 # 按发出去的那天(北京时间)分
        per = "\n".join(f"  · {n}:{len(idx)} 条 · {apiacc.CATEGORIES.get(accs[n].get('category'), accs[n].get('category'))}" +
                        (f" → {apisrc.game_folder(accs[n])}" if by_game else "") for n, idx in by_acc.items())
        mins = max(1, round(plan_n * (gap + 25) / 60 / par / min(per_acc, 3)))   # 一条大概传 + 发 25 秒,加上间隔(同时传 3 条以上网就满了)
        # 确认框:第一行大白话;号多就写个概要,细节放「显示详细信息」(体验报告:15 行号列表 + 声明细节太长)
        names = [f"{n} {len(idx)}" for n, idx in by_acc.items()]
        brief = "、".join(names) if len(names) <= 5 else "、".join(names[:4]) + f" … 等 {len(names)} 个号"
        catn: dict[str, int] = {}
        for n in by_acc:
            c = str(apiacc.CATEGORIES.get(accs[n].get("category"), accs[n].get("category")))
            catn[c] = catn.get(c, 0) + 1
        cat_line = "分类:" + "、".join(f"{c} {k} 个号" for c, k in catn.items())
        today = f"{bj_now().month}.{bj_now().day}"
        warn_day = f"⚠ 注意:这是 {d} 的,不是今天({today})!\n\n" if d != today else ""
        msg = (warn_day + f"发 {d} 的 {plan_n} 条 · {len(by_acc)} 个号 · 大概 {mins} 分钟\n\n{brief}\n{cat_line}\n\n" + quota_line +
               (f"其中 {retry} 条是上次没发成的,再试一次。\n" if retry else "") +
               (f"有问题的 {held} 条这次不发。\n" if held else "") + "\n发吗?")
        from qe import apicover
        cmode = str(self.st.get("api_cover") or "原样")
        ncov = 0 if cmode == "不传" else sum(1 for i in rows if apicover.find(self.videos[i].path))
        cov_line = ("封面:不传,平台自己截" if cmode == "不传" else
                    f"封面:{ncov} 条有同名封面会传上去({cmode})" + (f",{len(rows) - ncov} 条没有,平台自己截" if ncov < len(rows) else ""))
        msg = msg.replace("\n\n发吗?", f"\n{cov_line}\n\n发吗?")
        detail = (f"每个号:\n{per}\n\n标题、简介 = 文件名;自主声明「无需标注」;AI 声明「非 AI 生成」;{cov_line}。\n"
                  f"{'一条一条发' if par == 1 else f'{par} 个号一起发'}" + (f",同一个号一次传 {per_acc} 条,这组发完歇 {gap:g} 秒再下一组。\n" if per_acc > 1 else
                                                                             f",上一条发完歇 {gap:g} 秒再发下一条。\n") +
                  f"发成了挪到:{dest}" + ("\\游戏名" if by_game else "") + "(同名封面跟着挪)")
        if auto:
            self.say("⏰ 定时发布:" + msg.replace("\n", " ").replace("发吗?", "").strip())
        elif not ask(self, "现在发布", msg, "现在发出去", "先不发", detail=detail, default_no=True,   # 默认永远「先不发」
                     head="现在马上发出去(不是定时),发了只能去后台删",
                     extra="改成定时…", on_extra=self.schedule_clicked, danger=True):
            return
        vs = self.videos
        gate = {"last": 0.0}
        glock = threading.Lock()
        upsem = threading.Semaphore(6 if per_acc > 1 else 10 ** 6)       # 所有号加起来同时最多传 6 条(4 个号 × 5 条挤在一起反而慢)
        stats = {"ok": 0, "fail": 0, "unsure": 0, "skip": 0, "done": 0, "bad_acc": [], "fails": [], "acc_ok": {}}
        slock = threading.Lock()

        def bump(k, n=1):
            with slock:
                stats[k] += n

        def wait_turn(stopped) -> bool:
            """上一条发完(成功失败都算)以后歇够 gap 秒再发下一条(和旧软件一样;几个号一起发也算总的)。停了返回 False。"""
            with glock:
                while time.time() < gate["last"] + gap:
                    if stopped():
                        return False
                    time.sleep(0.2)
            return not stopped()

        def done_one(emit):
            with glock:
                gate["last"] = time.time()
            bump("done")
            if self.job and self.job._stop.is_set():
                return
            emit(PROGRESS, f"正在发 {min(stats['done'], plan_n)}/{plan_n} · 成功 {stats['ok']} · 没发成 {stats['fail']}" +
                 (f" · 结果不明 {stats['unsure']}" if stats["unsure"] else "") + "(点「停」:手上这条做完就停)")

        def acc_job(nick, idx, emit, stopped):
            from qe.omapi import ApiError, Client, Stopped, Unknown, redact
            a = accs[nick]
            try:
                cl = Client(a["client_id"], apiacc.unseal(a["secret"]))
            except Exception as e:
                for i in idx:
                    emit(i, "没发成:账号密钥读不出来")
                emit(-1, f"「{nick}」账号密钥读不出来(换了电脑 / Windows 用户?点「搬账号…」重新搬):{type(e).__name__}")
                bump("fail", len(idx))
                return
            try:
                cat = int(a.get("category"))
            except (TypeError, ValueError):
                for i in idx:
                    emit(i, "没发成:号的分类不对")
                emit(-1, f"「{nick}」的分类不对({a.get('category')!r}),先不发 —— 去「设置」里重新「从旧软件搬账号…」")
                bump("fail", len(idx))
                return
            def one(k, i, turn=True):
                """发一条:返回 "ok" / "next"(这条跳过或没发成,接着下一条)/ "stop"(停了)/ "fatal"(号的密钥坏了,这个号后面的别发)。"""
                if stopped():
                    return "stop"
                v = vs[i]
                if self.rec.blocked(v.path):              # 防重发:已发 / 结果不明都不发
                    emit(i, self.rec.status_of(v.path))
                    return "next"
                if turn and not wait_turn(stopped):
                    return "stop"
                rid = {}

                def begin(vid, v=v, rid=rid):
                    got = _retry(lambda: self.rec.try_begin(v, f"vid={vid}"))
                    if got is None:
                        raise _Taken()
                    rid["id"] = got
                from qe import apicover, omcover
                src = apicover.find(v.path) if cmode != "不传" else ""
                try:
                    cimg = apicover.prepare(src, cmode) if src else ""
                except Exception as e:
                    cimg = ""
                    emit(-1, f"「{v.title}」封面图读不出来({type(e).__name__}),这条用平台截的")
                try:
                    r = cl.send(v.path, v.title.strip(), cat, stop=stopped, before_publish=begin, cover=cimg,
                                cover_upload=omcover.upload,
                                on_progress=lambda o, s, i=i: emit(i, f"上传 {o * 100 // max(1, s)}%({o >> 20}/{s >> 20}MB)"),
                                log=lambda m, i=i: emit(i, m + "…"))
                except Stopped:
                    emit(i, "停下了,没发")
                    return "stop"
                except _Taken:                            # 别的号刚发过 / 正在发同一个文件:这条不发
                    emit(i, self.rec.status_of(v.path) or "已发")
                    emit(-1, f"「{nick}」{v.title}:这个文件别的号已经发了 / 正在发,这次不发")
                    done_one(emit)
                    return "next"
                except Unknown as e:                      # 发布请求发出去了没收到回话:可能发了,不能自动再发
                    if "id" in rid:
                        self.rec.api_finish(rid["id"], "结果不明", str(e))
                    else:
                        self.rec.api_result(v, "结果不明", str(e))
                    self.why[i] = str(e)
                    with slock:
                        stats["fails"].append((v.title, "结果不明(去后台看一眼)"))
                    emit(i, "结果不明")
                    emit(-1, f"「{nick}」{v.title}:结果不明 —— 去企鹅号后台看一眼,再右键标「发了 / 没发」")
                    bump("unsure")
                    done_one(emit)
                    return "unsure"                       # 可能已经发了:算进今天的条数(宁可少发也不多发)
                except Exception as e:
                    raw = redact(str(e)) if isinstance(e, ApiError) else f"{type(e).__name__}: {redact(str(e))}"
                    short, tip = friendly(e)
                    with slock:
                        stats["fails"].append((v.title, short.replace("没发成:", "") or "没发成"))
                    if "id" in rid:
                        self.rec.api_finish(rid["id"], "没发成", raw)
                    else:
                        self.rec.api_result(v, "没发成", raw)
                    self.why[i] = raw
                    emit(i, short)
                    emit(-1, f"「{nick}」{v.title}:{tip}")         # 原话放鼠标悬停里(界面不放开发者话)
                    bump("fail")
                    done_one(emit)
                    if getattr(e, "fatal", False):        # 换不到 token:这个号后面的都别试了,标出来
                        return "fatal"
                    return "next"
                apicover.cleanup(cimg, src)
                note = f"article_id={r['article_id']} vid={r['vid']}" + ("" if r["status"] == "成功" else "(平台还在处理)") + \
                    (f";封面{r.get('cover')}" if r.get("cover") else "")
                if str(r.get("cover") or "").startswith(("没传上", "平台不收")):
                    emit(-1, f"「{v.title}」发了,但封面{r['cover']}")
                bump("ok")
                try:
                    if "id" in rid:
                        _retry(lambda: self.rec.api_finish(rid["id"], "已发", note))
                    else:
                        _retry(lambda: self.rec.api_result(v, "已发", note))
                except Exception as e:                    # 记录库写不进去(被别的程序锁住):「发布中」那笔还在,不会重发
                    emit(i, "已发(但没记上,去后台核对)")
                    emit(-1, f"「{v.title}」发出去了,但发布记录写不进去({type(e).__name__}),先不挪文件。软件不会再发它;去后台核对一下")
                    done_one(emit)
                    return "ok"
                try:
                    old = v.path
                    v.path = apisrc.move_published(v.path, apisrc.archive_dir(self.st, "", a))
                    self._pub_dirs[os.path.dirname(old)] = a
                    if "id" in rid:                       # 记下新位置:之后在归档里再看到它也认得出发过
                        _retry(lambda: self.rec.mark_moved(rid["id"], v.path))
                except OSError as e:
                    emit(-1, f"「{v.title}」发了,但挪不走:{e}(发过的记着呢,不会重发)")
                except Exception:
                    pass
                emit(i, "已发" if r["status"] == "成功" else "已发(平台处理中)")
                done_one(emit)
                return "ok"

            def fatal_rest(left):
                for j in left:
                    self.rec.api_result(vs[j], "没发成", "没发:号的密钥坏了(没轮到)")
                    emit(j, "没发:号的密钥坏了")
                bump("skip", len(left))
                with slock:
                    stats["bad_acc"].append(nick)
            def run1(ki):
                with upsem:
                    return "stop" if stopped() else one(ki[0], ki[1], turn=False)
            # 用户 2026-10-20:发到这个号今天的规定条数就停(need = 还能发几条;None = 不限),没发成的拿下一条补
            # 用户 2026-10-19:同一个号一次传几条 —— 一组同时传,这组都发完歇「间隔」秒再下一组;所有号加起来同时最多 6 条
            need = left_of.get(nick)
            okc, pos = 0, 0
            try:
                while pos < len(idx) and (need is None or okc < need):
                    if stopped():
                        return
                    size = per_acc if need is None else min(per_acc, need - okc)
                    grp = list(enumerate(idx[pos:pos + size], pos))
                    pos += len(grp)
                    if per_acc == 1:                           # 一条一条发(原来的样子)
                        res1 = [one(*grp[0])]
                    else:
                        if not wait_turn(stopped):
                            return
                        with ThreadPoolExecutor(len(grp)) as ex:
                            res1 = list(ex.map(run1, grp))
                    okc += res1.count("ok") + res1.count("unsure")
                    if "fatal" in res1:
                        fatal_rest(idx[pos:])
                        return
                    if "stop" in res1:
                        return
            finally:
                with slock:
                    stats["acc_ok"][nick] = okc

        def fn(emit, stopped):
            with ThreadPoolExecutor(par) as ex:
                for n, f in [(n, ex.submit(acc_job, n, idx, emit, stopped)) for n, idx in by_acc.items()]:
                    try:
                        f.result()
                    except Exception as e:
                        emit(-1, f"「{n}」发的时候出了没想到的错({type(e).__name__}),这个号后面的先没发;已经发的记着呢")
            not_run = plan_n - stats["ok"] - stats["unsure"]
            spilled, short = 0, []
            if not stopped():
                for n in list(by_acc) + full:
                    need = left_of.get(n)
                    if need is None:
                        continue
                    if n in full or stats["acc_ok"].get(n, 0) >= need:
                        spilled += self._spill(n, emit)            # 发够了:多的挪到明天
                    else:
                        short.append(f"{n} 还差 {need - stats['acc_ok'].get(n, 0)} 条")
            summary = (f"发完了:成功 {stats['ok']} · 没发成 {stats['fail']} · 结果不明 {stats['unsure']}" +
                       (f" · 号的密钥坏了没发 {stats['skip']}({'、'.join(stats['bad_acc'])})" if stats["skip"] else "") +
                       (f" · 停下了没发 {not_run}" if stopped() and not_run > 0 else "") +
                       (f" · 发够了,多的 {spilled} 条挪到明天的文件夹({tmr})" if spilled else "") +
                       (f" · 没发够(素材不够 / 没发成):{'、'.join(short)}" if short else ""))
            self._reload_after = bool(spilled)
            bad = stats["fail"] or stats["unsure"] or stats["skip"]
            lst = "".join(f"\n · {t[:26]}:{why}" for t, why in stats["fails"][:6]) + \
                ("\n · …" if len(stats["fails"]) > 6 else "")
            self._popup = ("发完了", summary + (f"\n\n这几条要你看一下:{lst}\n\n列表已经切到「只看有问题的」。"
                                               "结果不明的去后台看一眼,再右键标「发了 / 没发」;网络问题的网好了再点「现在发布」,"
                                               "会接着发没发的(发过的不会重发)。" if bad else ""), bool(bad))
            self._show_bad_after = bool(bad)
            return summary
        self._pub_begin(plan_n)
        self._start(fn, f"开始发布:{len(rows)} 条," + ("一条一条发" if par == 1 else f"{min(par, len(by_acc))} 个号一起发") +
                    (f",同一个号一次传 {per_acc} 条" if per_acc > 1 else "") + f",间隔 {gap:g} 秒")

    # ---------------- 定时发布(到点自己点「发布」,发到完为止) ----------------
    def _sched_changed(self):
        t = self.sched.label() if hasattr(self, "sched") else ""
        note = (self.st.get("sched_notice") or {}).get("api") or {}
        if note.get("msg") and str(note.get("at", ""))[:10] != bj_str()[:10]:
            self._clear_notice()                         # 不是今天的:不再挂着(用户 2026-10-24:10-21 那条挂了好几天)
            note = {}
        bad = f"⏰ 上次定时({note.get('at', '')[5:]})没发成 / 没开始,点这看为什么" if note.get("msg") else ""
        self.lab_sched.setText(t or ("⏰ 定时发布正在自己发…" if self._auto else bad))
        self.lab_sched.setToolTip(note.get("msg", "") if bad and not t and not self._auto else "")
        self.b_sched.setText("取消定时" if t else "停下定时发布" if self._auto else "到点自动发…")

    def _sched_note(self, msg: str):
        """定时没开始 / 没发成(用户 2026-10-18 审查:只写在小日志里看不到):⏰ 那行红字常驻,下次打开软件弹一次。
        重新定时以后才清掉。"""
        self.say(msg)
        s = dict(self.st.get("sched_notice") or {})
        s["api"] = {"at": bj_str()[:16], "msg": msg.lstrip("⚠⏰ "), "popped": False}
        self.st["sched_notice"] = s
        self.st.save()
        self._sched_changed()

    def _pop_notice(self):
        s = dict(self.st.get("sched_notice") or {})
        note = dict(s.get("api") or {})
        if not self._notice0 or not note.get("msg") or note.get("popped"):
            return
        note["popped"] = True
        s["api"] = note
        self.st["sched_notice"] = s
        self.st.save()
        QMessageBox.warning(self, "上次定时没发成", f"16 个号上次的定时({note.get('at', '')})没发成 / 没开始:\n\n{note['msg']}\n\n"
                                                 "去列表里看看还有哪些没发,要发就点「现在发布」或重新定时。")

    def _clear_notice(self):
        s = dict(self.st.get("sched_notice") or {})
        if s.pop("api", None):
            self.st["sched_notice"] = s
            self.st.save()

    def _ack_notice(self, _e=None):
        """点那行红字:说一遍为什么,点「知道了」就不再挂着。"""
        note = (self.st.get("sched_notice") or {}).get("api") or {}
        if not note.get("msg") or (hasattr(self, "sched") and self.sched.label()) or self._auto:
            return
        QMessageBox.information(self, "上次定时没发成", f"16 个号上次的定时({note.get('at', '')})没发成 / 没开始:\n\n{note['msg']}")
        self._clear_notice()
        self._sched_changed()

    def schedule_clicked(self):
        if self._auto:
            if ask(self, "定时发布", "定时发布正在自己发。停下来吗?(手上这条做完就停,已经发的记着)", "停下", "接着发"):
                if self._auto == "发":
                    self.stop()
                else:
                    self._sched_end("定时发布停下了(还没开始发)")
            return
        if self.sched.pending():
            if ask(self, "定时发布", self.sched.label() + "\n\n取消这个定时吗?", "取消定时", "留着"):
                self.sched.cancel()
            return
        from gui.schedule import ask_schedule
        dates = [self.c_date.itemData(i) for i in range(self.c_date.count()) if self.c_date.itemData(i)]
        if not dates:
            QMessageBox.information(self, "定时发布", "还没有能选的日期。")
            return
        r = ask_schedule(self, "定时发布 · 16 个号", dates, self.day(),
                         "到点会发这天所有号能发的(不管选中;「只看有问题的」/ 搜索会清掉),按设置里「几个号一起发」。\n"
                         "话题、标准竖屏先处理好;到点还有问题的不发。",
                         head="16 个号是软件到点自己一条条发:到点前、发完前电脑不能关,软件和创作罐头都要开着。",
                         time_label="几点开始发(北京时间):", overview=self._sched_overview)
        if r:
            self._clear_notice()
            self.sched.set(*r)

    def _sched_overview(self, date: str) -> str:
        """定时框最上面的总览:这天每个号还有几条没发(到点还有问题的不发,所以是「最多」)。"""
        per: dict[str, int] = {}
        for v in apisrc.videos(self.roots(), date, self.known(), self.picked(date)):
            if not self.rec.blocked(v.path):
                per[v.account] = per.get(v.account, 0) + 1
        if not per:
            return "这天没有要发的视频(都发过了 / 还没有素材)"
        return (f"最多发 {sum(per.values())} 条(到点还有问题的不发):" +
                "、".join(f"{n} {k} 条" for n, k in sorted(per.items(), key=lambda x: -x[1])))

    def _sched_fire(self, date: str):
        if self.busy() and not getattr(self, "_quiet", False):
            self._sched_note("⚠ 到点了,但这页还在发布 / 处理别的,定时发布没开始")
            return
        from gui.schedule import keep_awake
        self._auto = "等检查"
        keep_awake("定时-api-发", True)
        self._sched_changed()
        self.k_bad.setChecked(False)
        self.e_find.clear()
        self.tree.clearSelection()
        if self.c_date.findData(date) < 0:
            self.reload_dates()
        if self.c_date.findData(date) < 0:
            self._sched_end(f"⚠ 到点了,但没有「{date}」这天的素材,定时发布没开始", problem=True)
            return
        if self.day() == date:
            self.reload_dates()                           # 同一天也重读(员工可能加了视频);会自动检查新的
        else:
            self.set_day(date)                            # 换日期会自己重读 + 自动检查
        self._sched_wait = 0
        self._auto_poll()

    def _auto_poll(self):
        """到点以后:等自动检查做完再发(最多等 30 分钟)。"""
        from PySide6.QtCore import QTimer
        if self._auto != "等检查":
            return
        if self.busy():
            self._sched_wait += 1
            if self._sched_wait > 360:
                self.stop()
                self._sched_end("⚠ 等检查等了 30 分钟还没做完,定时发布没开始", problem=True)
                return
            QTimer.singleShot(5000, self._auto_poll)
            return
        self.k_bad.setChecked(False)                      # 发全部:不管「只看有问题的」/ 搜索 / 选中
        self.e_find.clear()
        self.tree.clearSelection()
        self._auto_box = None
        self.run_publish(auto=True)
        if self.busy():
            self._auto = "发"
            self._sched_changed()
        else:
            why = getattr(self._auto_box, "last", "") if self._auto_box else ""
            self._sched_end("⚠ 定时发布没发:" + (why or "没有能发的(都发过了 / 有问题的不发)"), problem=True)

    def _sched_end(self, msg: str, problem: bool = False):
        from gui.schedule import keep_awake
        self._auto = ""
        keep_awake("定时-api-发", False)
        if problem and msg:
            self._sched_note(msg)                         # 红字常驻 + 下次打开弹一次(里面会写日志)
        elif msg:
            self.say(msg)
        self._sched_changed()

    def relogin_key(self, parent=None):
        """登录取钥匙:开一个这个号专用的浏览器,人扫码登录企鹅号,软件读出这个号的接口钥匙换上(不用再开旧软件)。"""
        from PySide6.QtCore import QThread
        from PySide6.QtWidgets import QApplication, QProgressDialog
        from qe import omlogin
        parent = parent or self
        if self.busy():
            QMessageBox.information(parent, "登录取钥匙", "后台还在发布 / 处理,做完再弄。")
            return
        names = apiacc.nicks()
        if not names:
            QMessageBox.information(parent, "登录取钥匙", "还没有号。先「从旧软件搬账号…」。")
            return
        nick, ok = QInputDialog.getItem(parent, "登录取钥匙", "哪个号的钥匙要重新取?(一般是发布报「号的密钥不对」的那个)", names, 0, False)
        if not ok:
            return
        acc = apiacc.find(nick) or {}
        try:
            proc, port = omlogin.launch(nick)
        except Exception as e:
            QMessageBox.warning(parent, "登录取钥匙", f"浏览器打不开:{e}")
            return
        res = {}

        class T(QThread):
            def run(self_):
                res["r"] = omlogin.wait_keys(port, stopped=lambda: res.get("stop", False))
        t = T(self)
        dlg = QProgressDialog(f"在刚打开的浏览器里登录「{nick}」的企鹅号(扫码)。\n登录好了软件会自己读钥匙,不用点别的。\n"
                              "(这个浏览器只给这个号用,登录一次以后再取就不用扫码了)", "不弄了", 0, 0, parent)
        dlg.setWindowTitle("登录取钥匙")
        dlg.setMinimumDuration(0)
        dlg.setValue(0)
        dlg.canceled.connect(lambda: res.__setitem__("stop", True))
        dlg.show()
        t.start()
        while not t.wait(200):
            QApplication.processEvents()
        dlg.close()
        try:
            proc.terminate()                         # 关掉这个专用浏览器(登录还记着,下次不用再扫)
        except Exception:
            pass
        status, keys, shp = res.get("r", ("停下了", [], ""))
        if status in ("停下了", "超时"):
            self.say(f"登录取钥匙「{nick}」:{status},钥匙没动")
            return
        if status != "读到了":
            self.say(f"登录取钥匙「{nick}」:登录了,但没读到钥匙。回话样子:{shp[:300]}")
            QMessageBox.warning(parent, "登录取钥匙", "登录好了,但没读到这个号的接口钥匙(可能企鹅号后台还没开「接口发布」权限)。\n"
                                                   "现在的钥匙没动。把日志里那句发给做软件的人看看。")
            return
        k = omlogin.match(keys, nick, str(acc.get("source_id") or ""), str(acc.get("client_id") or ""))
        if k is None:
            labels = [f"{x.get('name') or '没名字'}({x.get('media_id') or '?'})" for x in keys]
            pick, ok = QInputDialog.getItem(parent, "登录取钥匙", f"这个账号下有 {len(keys)} 个号,哪个是「{nick}」?", labels, 0, False)
            if not ok:
                return
            k = keys[labels.index(pick)]
        try:
            same = k["client_id"] == acc.get("client_id") and k["secret"] == apiacc.unseal(acc.get("secret") or "")
        except Exception:
            same = False
        if same:
            QMessageBox.information(parent, "登录取钥匙", f"「{nick}」的钥匙读到了,和现在用的一样,不用换。\n\n"
                                                       "(如果发布还报「密钥不对」,可能是企鹅号那边的问题,去后台看看这个号的状态)")
            self.say(f"登录取钥匙「{nick}」:读到了,和现在的一样")
            return
        if not ask(parent, "登录取钥匙", f"读到「{k.get('name') or nick}」的新钥匙了,和现在用的不一样。\n\n换上吗?(换了以后这个号就用新钥匙发)",
                   "换上", "先不换"):
            return
        apiacc.set_key(nick, k["client_id"], k["secret"])
        self.say(f"登录取钥匙「{nick}」:换上新钥匙了")
        QMessageBox.information(parent, "登录取钥匙", f"「{nick}」换上新钥匙了。之前「密钥不对」没发成的,再点「现在发布」就行。")

    def migrate(self):
        db = apiacc.OLD_DB if os.path.isfile(apiacc.OLD_DB) else ""
        if not db:
            db, _ = QFileDialog.getOpenFileName(self, "旧软件的数据库 qepm.db", "", "qepm.db (*.db)")
            if not db:
                return
        try:
            n = apiacc.migrate(db)
        except Exception as e:
            QMessageBox.warning(self, "搬账号", f"没搬成:{e}")
            return
        names = [f"{a['nick']}({apiacc.CATEGORIES.get(a['category'], a['category'])})" for a in apiacc.load()]
        self.say(f"搬了 {n} 个号:" + "、".join(names))
        self.reload_dates()
