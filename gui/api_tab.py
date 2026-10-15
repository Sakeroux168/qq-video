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

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QHeaderView,
                               QInputDialog, QLabel, QLineEdit, QMenu, QMessageBox, QPlainTextEdit, QPushButton,
                               QSizePolicy, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from qe import apiacc, apisrc, checks, topic, vertical
from qe.config import bj_now, bj_str, data_dir
from qe.records import pkey

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
        return "没发成:号的密钥不对", "这个号的密钥不对或过期了 —— 去旧软件确认这个号还能用,再去左下角「设置」里点「从旧软件搬账号…」重新搬一次"
    if code == "40023" or "invalid_file_upload" in s:
        return "没发成:平台不收这个文件", "平台不收这个视频文件(可能坏了 / 格式不对)—— 先双击打开看能不能播,重新导出再发"
    if "网络连不上" in s or "超时" in s:
        return "没发成:网断了", "网络有问题 —— 网好了再点「发布」,会接着发没发的(发过的不会重发)"
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


def ask(parent, title: str, text: str, yes: str = "好", no: str = "先不", detail: str = "", default_no: bool = False) -> bool:
    """中文按钮的确认框(审查:Yes / No 是英文)。detail = 点「显示详细信息」才看得到的细节(确认框别太长)。"""
    box = QMessageBox(QMessageBox.Icon.Question, title, text, QMessageBox.StandardButton.NoButton, parent)
    b_yes = box.addButton(yes, QMessageBox.ButtonRole.YesRole)
    b_no = box.addButton(no, QMessageBox.ButtonRole.NoRole)
    if detail:
        box.setDetailedText(detail)
    box.setDefaultButton(b_no if default_no else b_yes)
    box.exec()
    return box.clickedButton() is b_yes


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
        self._build()
        self.reload_dates()

    # ---------------- 界面 ----------------
    def _build(self):
        from gui.widgets import StatCards
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 16, 20, 12)
        v.setSpacing(10)
        title = QLabel("16 个号 · 游戏 / 动漫,用官方接口发")
        title.setObjectName("pageTitle")
        v.addWidget(title)
        top = QHBoxLayout()
        top.addWidget(QLabel("要发哪天的:"))
        self.c_date = QComboBox()
        self.c_date.setMinimumWidth(110)
        self.c_date.currentIndexChanged.connect(self.load)
        top.addWidget(self.c_date)
        self.b_reload = b = QPushButton("刷新")
        b.setToolTip("重新读一遍素材文件夹(F5)")
        b.clicked.connect(self.reload_dates)
        top.addWidget(b)
        top.addSpacing(12)
        self.lab = QLabel("")
        self.lab.setStyleSheet("color:#777")
        self.lab.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)   # 太长就截,不把窗口撑宽
        top.addWidget(self.lab, 1)
        self.b_pick = b = QPushButton("给号选文件夹…")
        b.setToolTip("像旧软件的「选择」:手动给一个号挑这天要发的文件夹(比如电竞情报馆的「2电竞赛事」)。\n"
                     "选了以后这个号这天只发那个文件夹里的视频,不再自动找。右键列表里的号 / 视频也能选 / 取消。")
        b.clicked.connect(lambda: self.pick_folder())
        top.addWidget(b)
        v.addLayout(top)

        self.cards = StatCards([("all", "这天的视频"), ("ok", "能发"), ("bad", "要处理"), ("sent", "已发"), ("accs", "号发完")],
                               clickable=("bad", "ok"))
        self.cards.clicked.connect(self._card_clicked)
        v.addWidget(self.cards)
        view = QHBoxLayout()
        b = QPushButton("全部展开")
        b.clicked.connect(lambda: self.expand_all(True))
        view.addWidget(b)
        b = QPushButton("全部收起")
        b.clicked.connect(lambda: self.expand_all(False))
        view.addWidget(b)
        self.k_bad = QCheckBox("只看有问题的")
        self.k_bad.setToolTip("只显示要处理的(横屏 / 标题有别的平台 / 话题问题 / 没发成 / 结果不明)")
        self.k_bad.toggled.connect(lambda _on: self._apply_filter())
        view.addWidget(self.k_bad)
        self.e_find = QLineEdit()
        self.e_find.setPlaceholderText("搜标题…(Ctrl+F)")
        self.e_find.setClearButtonEnabled(True)
        self.e_find.setMaximumWidth(200)
        self.e_find.textChanged.connect(lambda _t: self._apply_filter())
        view.addWidget(self.e_find)
        view.addStretch(1)
        self.lab_sum = QLabel("")
        self.lab_sum.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.lab_sum.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        view.addWidget(self.lab_sum, 2)
        v.addLayout(view)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(len(COLS))
        self.tree.setHeaderLabels(COLS)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setToolTip("点号前面的小三角(或双击号)展开 / 收起;按住 Ctrl / Shift 多选;选中号 = 选中这个号的全部视频。\n"
                             "双击一条视频:打开它所在的文件夹。右键:检查 / 整理话题 / 改标题 / 发布 / 换文件夹。")
        self.tree.itemDoubleClicked.connect(self._double)
        self.tree.itemExpanded.connect(lambda it: self._remember(it, True))
        self.tree.itemCollapsed.connect(lambda it: self._remember(it, False))
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        self.tree.setUniformRowHeights(True)
        hh = self.tree.header()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        for i, wd in ((1, 90), (2, 230), (3, 170)):
            self.tree.setColumnWidth(i, wd)
        v.addWidget(self.tree, 1)

        # 第一行:这次管哪些(绿字)+ 取消选择
        scope = QHBoxLayout()
        self.lab_scope = QLabel("")
        self.lab_scope.setObjectName("scope")
        self.lab_scope.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        scope.addWidget(self.lab_scope, 1)
        self.b_clear = QPushButton("取消选择")
        self.b_clear.setToolTip("不选了:下面的按钮回到管全部(Esc)")
        self.b_clear.clicked.connect(self.tree.clearSelection)
        scope.addWidget(self.b_clear)
        self.b_log = QPushButton("展开日志")
        self.b_log.setObjectName("link")
        self.b_log.clicked.connect(self._toggle_log)
        scope.addWidget(self.b_log)
        v.addLayout(scope)

        # 第二行:处理 + 发布(按钮上不再每个都带条数,条数只在上面绿字写一次;窗口能缩到 1000 以内)
        bar = QHBoxLayout()
        self.b_check = QPushButton("检查")
        self.b_check.setToolTip("看每条:是不是竖屏、标题里有没有别的平台的名字、话题对不对。\n(换日期 / 刷新以后会自动检查新出现的)")
        self.b_check.clicked.connect(lambda: self.run_check())
        self.b_vert = QPushButton("转标准竖屏")
        self.b_vert.setToolTip("横屏、偏方(3:4 / 正方形)的转成标准竖屏 1080×1920:上下糊底、中间原画面。\n原片挪进同文件夹的「横屏原片」,不删。")
        self.b_vert.clicked.connect(lambda: self.run_vertical())
        self.b_topic = QPushButton("整理话题")
        self.b_topic.setToolTip("一键把话题弄对:\n· 写法不对的(结尾空格、「# 话题」「##话题」、话题前粘的 n、重复的)按固定规矩改,不用 AI;\n"
                                "· 挂了好几个话题的,AI 挑最好搜的留一个(游戏 / 剧 / 电影 / 动漫名优先)。\n改文件名,同名封面跟着改。能撤销。")
        self.b_topic.clicked.connect(lambda: self.run_topic())
        self.b_settopic = QPushButton("批量改话题…")
        self.b_settopic.setToolTip("话题全换成你填的那一个,比如填「英雄联盟」→ 结尾变成 #英雄联盟。原来没话题的就接在后面。能撤销。\n"
                                   "这个必须先选(选号 = 这个号全部),免得把别的游戏 / 动漫的号也改了。")
        self.b_settopic.clicked.connect(lambda: self.set_topic())
        self.b_undo = QPushButton("撤销上次改名")
        self.b_undo.clicked.connect(self.undo_topic)
        self.b_pub = QPushButton("发布")
        self.b_pub.setMinimumHeight(34)
        self.b_pub.setObjectName("primary")          # 主题里给它主色(gui/theme.py)
        self.b_pub.setToolTip("没有问题的(竖屏、标题里没别的平台、话题对、没发过的)用接口发出去;有问题的不发。点了会先弹框确认。\n"
                              "发成了挪到「X月发布视频\\企鹅号\\企鹅号软件发布\\游戏名」(设置里能改)。")
        self.b_pub.clicked.connect(lambda: self.run_publish())
        self.b_stop = QPushButton("停")
        self.b_stop.setMinimumHeight(34)
        self.b_stop.clicked.connect(self.stop)
        for b in (self.b_check, self.b_vert, self.b_topic, self.b_settopic, self.b_undo):
            bar.addWidget(b)
        bar.addStretch(1)
        bar.addWidget(self.b_pub)
        bar.addWidget(self.b_stop)
        v.addLayout(bar)
        self.logbox = QPlainTextEdit()
        self.logbox.setObjectName("log")
        self.logbox.setReadOnly(True)
        self.logbox.setMaximumBlockCount(3000)
        self.logbox.setMaximumHeight(60)                 # 平时只露两三行(体验报告:日志太占地方),「展开日志」看全
        v.addWidget(self.logbox)
        self.tree.itemSelectionChanged.connect(self._update_scope)

        # 快捷键
        for key, owner, fn in (("F5", self, self.reload_dates),
                               ("Ctrl+F", self, lambda: (self.e_find.setFocus(), self.e_find.selectAll())),
                               ("Escape", self.tree, self.tree.clearSelection),
                               ("F2", self.tree, self._edit_current)):
            sc = QShortcut(QKeySequence(key), owner)
            sc.activated.connect(fn)
        self._busy(False)

    def say(self, m: str):
        """日志写在这页下面(两页各记各的;体验报告:教育页日志里全是 [接口] 的)。"""
        self.logbox.appendPlainText(f"[{bj_str()[11:]}] {m}")

    def _toggle_log(self):
        big = self.logbox.maximumHeight() < 100
        self.logbox.setMaximumHeight(260 if big else 60)
        self.b_log.setText("收起日志" if big else "展开日志")

    def _card_clicked(self, key: str):
        """点「要处理」卡片 = 只看有问题的;点「能发」= 取消过滤看全部。"""
        self.k_bad.setChecked(key == "bad")

    def busy(self) -> bool:
        return bool(self.job and self.job.isRunning())

    def _busy(self, on: bool):
        has = bool(self.items)
        quiet = on and getattr(self, "_quiet", False)   # 只是后台自动检查:换日期 / 刷新 / 选文件夹照样能点
        for b in (self.b_check, self.b_vert, self.b_topic, self.b_settopic, self.b_pub):
            b.setEnabled(not on and has)
        for b in (self.b_undo, self.b_clear):
            b.setEnabled(not on)
        for b in (self.c_date, self.b_pick, self.b_reload):
            b.setEnabled(not on or quiet)
        self.b_stop.setEnabled(on)
        if not on:
            self._update_scope()

    def filtering(self) -> bool:
        return self.k_bad.isChecked() or bool(self.e_find.text().strip())

    def target_rows(self, only: list[int] | None = None) -> list[int]:
        """这次要管哪些:给了就是给的;没给 → 选中的;没选 → 列表里看得见的全部(「只看有问题的」/ 搜索过滤掉的不算)。"""
        if only is not None:
            return [i for i in only if 0 <= i < len(self.videos)]
        return self.selected_rows() or [i for i, it in self.items.items() if not it.isHidden()]

    def _can_send(self, i: int) -> bool:
        v = self.videos[i]
        return bool(v.checks) and not checks.problems(v) and not self._sent(i)

    def _update_scope(self):
        if self.busy():
            return
        undo = self.ledger.last()
        self.b_undo.setToolTip("把上一次改话题 / 批量改话题 / 改标题改回去" +
                               (f"\n上一次:{topic.Ledger.label(undo)}" if undo else "\n(现在没有能撤销的)"))
        if not self.c_date.currentText():
            self.lab_scope.setText("先在左上角选「要发哪天的」")
            self.b_clear.setVisible(False)
            self.b_pub.setText("发布")
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
            self.lab_scope.setText(f"过滤中:只管看得见的 {len(rows)} 条(要管全部:取消「只看有问题的」/ 清空搜索)")
        else:
            self.lab_scope.setText(f"没选:管全部 {len(rows)} 条" if rows else "这天没有视频")
        self.b_clear.setVisible(bool(sel))
        n = sum(1 for i in rows if self._can_send(i) and not self.state.get(i, "").startswith(FAILED))
        # 重试:号的密钥坏了的不算(再点也必然失败,体验报告)
        retry = sum(1 for i in rows if self._can_send(i) and self.state.get(i, "").startswith(FAILED)
                    and "密钥" not in self.state.get(i, ""))
        self.b_pub.setText(f"发布 {n} 条" + (f" + 再发一次没发成的 {retry} 条" if retry else "") if n else
                           (f"再发一次没发成的 {retry} 条" if retry else "没有能发的"))
        self.b_pub.setEnabled(bool(n or retry) and not self.busy())
        self.b_settopic.setText("批量改话题…" if sel else "批量改话题…(先选)")

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
        # 记住上次选的日期(用户 2026-10-15「可以记住」;教育页那边仍然不自动选)
        cur = self.c_date.currentText() or str(self.st.get("api_last_date") or "")
        self.c_date.blockSignals(True)
        self.c_date.clear()
        self.c_date.addItem("")
        ds = apisrc.dates(self.roots(), self.known())
        today = f"{bj_now().month}.{bj_now().day}"
        for x in list((self.st.get("api_picked") or {}).keys()) + [today]:   # 手选过文件夹的日子、今天:没有日期文件夹也能选
            if x and x not in ds:
                ds.append(x)
        ds.sort(key=lambda d: tuple(int(x) for x in d.split(".")))
        self.c_date.addItems(list(reversed(ds)))
        if cur:
            self.c_date.setCurrentText(cur)
        self.c_date.blockSignals(False)
        self.load()

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

    def _remember_check(self, v):
        sig = self._sig(v.path)
        if sig and v.checks:
            self.cache[pkey(v.path)] = (sig, dict(v.checks))

    def load(self):
        if self.busy() and getattr(self, "_quiet", False):   # 只是后台自动检查:停掉它,重读
            self.job.stop()
            self.job.wait()
            self._busy(False)
        if self.busy():                              # 后台按行号刷状态,这时重读列表会刷到别的视频上
            return
        d = self.c_date.currentText()
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
            elif not s.startswith("已发"):
                todo.append(i)
        # 这天已经发出去、挪走了的(列表里没有了,但记录里有):号那一行和上面卡片要算上
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
        if self.c_date.currentText():                     # 这天没找到视频的号也列出来(灰的),一眼看出少了谁
            for nick in apiacc.nicks():
                if nick not in self.groups:
                    g = group(nick)
            for nick, g in self.groups.items():
                if not g.childCount():
                    gone = self.archived.get(nick, 0)
                    if gone:
                        g.setText(0, f"{nick}  这天已发 {gone} 条(发完挪走了)")
                        g.setText(3, f"已发 {gone}")
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
        self._apply_filter()
        self._busy(self.busy())

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
        for col, t in enumerate([v.title, res, "、".join(probs) if c else "", st]):
            it.setText(col, t)
            it.setToolTip(col, v.path if col == 0 else (self.why.get(i) or t) if col == 3 else t)
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
        bad = sum(1 for i in checked if checks.problems(self.videos[i]) and not self._sent(i))
        fail = sum(1 for i in rows if self.state.get(i, "").startswith(FAILED[:2]))
        unsure = sum(1 for i in rows if self.state.get(i, "") == "结果不明")
        ok = sum(1 for i in rows if self._can_send(i) and not self.state.get(i, "").startswith(FAILED))
        pk = "(手选文件夹)" if nick in self.picked(self.c_date.currentText()) else ""
        g.setText(0, f"{nick}  {n} 条{pk}")
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
        g.setText(2, " · ".join(parts))
        g.setText(3, "✓ 发完了" if n and sent == n else (f"能发 {ok} · 已发 {sent}" if checked or sent else ""))
        g.setToolTip(0, self.picked(self.c_date.currentText()).get(nick, "") or nick)
        col = GREEN if n and sent == n else ORANGE if unsure else YELLOW if bad or fail else None
        for c in range(len(COLS)):
            g.setBackground(c, col if col else QColor(0, 0, 0, 0))
        self._update_sum()

    def _update_sum(self):
        n = len(self.videos)
        sent = sum(1 for i in range(n) if self.state.get(i, "").startswith("已发"))
        checked = [i for i in range(n) if self.videos[i].checks]
        ok = sum(1 for i in range(n) if self._can_send(i) and not self.state.get(i, "").startswith(FAILED))
        bad = sum(1 for i in checked if checks.problems(self.videos[i]) and not self._sent(i))
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
        self.lab_sum.setText("" if len(checked) >= n or not n else f"{n - len(checked)} 条还没检查完…")
        subs = [x for x in ((f"不确定发没发 {unsure}" if unsure else ""), (f"没发成 {fail}" if fail else ""),
                            (f"有问题 {bad}" if bad else "")) if x]
        self.cards.set(all=n + gone, ok=(ok, "good" if ok else ""), bad=(bad + fail + unsure, "warn" if bad + fail + unsure else ""),
                       sent=sent + gone, accs=(f"{done} / {len(accs)}" if accs else "–", "good" if accs and done == len(accs) else ""),
                       bad_sub=" · ".join(subs),
                       ok_sub="点「发布」发这些" if ok else "",
                       sent_sub=f"其中 {gone} 条已挪走" if gone else "", all_sub="")

    def _hidden(self, i: int) -> bool:
        key = self.e_find.text().strip().lower()
        if key and key not in self.videos[i].title.lower():
            return True
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
        d = self.c_date.currentText()
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
        d = self.c_date.currentText()
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
            if sel:
                for text, fn in ((f"检查选中的 {len(sel)} 条", lambda: self.run_check(sel)),
                                 (f"转标准竖屏(选中的 {len(sel)} 条)", lambda: self.run_vertical(sel)),
                                 (f"整理话题(选中的 {len(sel)} 条)", lambda: self.run_topic(sel)),
                                 (f"只整理写法、不用 AI(选中的 {len(sel)} 条)", lambda: self.tidy_titles(sel)),
                                 (f"批量改话题(选中的 {len(sel)} 条)…", lambda: self.set_topic(sel)),
                                 (f"发布选中的 {len(sel)} 条…", lambda: self.run_publish(sel)),
                                 (None, None),
                                 (f"只检查「{nick}」的 {len(mine)} 条", lambda: self.run_check(mine)),
                                 (f"只发「{nick}」的…", lambda: self.run_publish(mine))):
                    if text is None:
                        m.addSeparator()
                    else:
                        m.addAction(text, fn).setEnabled(not busy)
            if i != -1:
                m.addSeparator()
                m.addAction("改标题…(F2)", lambda: self.edit_title(i)).setEnabled(not busy and not self._sent(i))
                m.addAction("复制标题", lambda: self._copy(self.videos[i].title))
                m.addAction("打开所在文件夹", lambda: self.reveal(i))
            m.addSeparator()
            m.addAction(f"给「{nick}」换个文件夹…", lambda: self.pick_folder(nick)).setEnabled(not busy)
            if nick in self.picked(self.c_date.currentText()):
                m.addAction(f"「{nick}」不用手选的文件夹了(自动找)", lambda: self.unpick(nick)).setEnabled(not busy)
            m.addSeparator()
        m.addAction("给别的号选文件夹…", lambda: self.pick_folder()).setEnabled(not busy)
        m.addAction("全部展开", lambda: self.expand_all(True))
        m.addAction("全部收起", lambda: self.expand_all(False))
        m.exec(self.tree.viewport().mapToGlobal(pos))

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
            return
        if i < 0:
            self.say(t)
            return
        if t == CLEAR:
            self.state.pop(i, None)
        elif t:
            self.state[i] = t
            if t.startswith(("上传", "发布中")) and i in self.items:   # 发布中:列表跟着滚到正在发的那条
                self.tree.scrollToItem(self.items[i])
        if i in self.items:
            self._fill(i)

    def _on_done(self, msg: str):
        if self._stale():
            return
        self._quiet = False
        self._busy(False)
        if msg:
            self.say(msg)
        if getattr(self, "_show_bad_after", False):
            self._show_bad_after = False
            self.k_bad.setChecked(True)                   # 发完有失败的:直接只看有问题的
        pop = getattr(self, "_popup", None)
        self._popup = None
        if pop:
            QMessageBox.warning(self, pop[0], pop[1]) if pop[2] else QMessageBox.information(self, pop[0], pop[1])

    def stop(self):
        if self.job and self.job.isRunning():
            self.job.stop()
            self.lab_scope.setText("正在停…等手上这条做完(上传大文件可能要一会儿)")
            self.b_stop.setEnabled(False)
            self.say("正在停…(手上这条做完就停)")

    def run_check(self, only: list[int] | None = None, quiet: bool = False):
        rows = self.target_rows(only)
        if not rows or self.busy():
            return
        vs = self.videos
        words = self.st.get("api_platform_words") or None
        ff = vertical.ffmpeg_path()

        def fn(emit, stopped):
            done = [0]
            lock = threading.Lock()

            def one(i):
                if stopped():
                    return
                checks.check_one(vs[i], words, ff)
                self._remember_check(vs[i])
                emit(i, "")
                with lock:
                    done[0] += 1
                    k = done[0]
                if k % 10 == 0 or k == len(rows):
                    emit(PROGRESS, f"检查中 {k}/{len(rows)}…")
            with ThreadPoolExecutor(4) as ex:            # 4 条一起读(网络盘上一条条读太慢)
                list(ex.map(one, rows))
            if stopped():
                return "检查停下了"
            got = [vs[i] for i in rows]
            land = sum(1 for v in got if checks.needs_vertical(v.checks))
            plat = sum(1 for v in got if v.checks.get("platform"))
            many = sum(1 for v in got if len(v.checks.get("tags") or []) > 1)
            fmt = sum(1 for v in got if len(v.checks.get("tags") or []) <= 1 and topic.bad_format(v.title))
            unread = sum(1 for v in got if v.checks.get("bad_read"))
            ok = sum(1 for v in got if not checks.problems(v))
            return (f"检查完:{len(got)} 条,能发 {ok};横屏 / 偏方 {land} · 标题有别的平台 {plat}(要你自己改)· "
                    f"多个话题 {many} · 话题写法 / 结尾空格 {fmt}" + (f" · 视频读不出来 {unread}" if unread else "") +
                    ("" if ok == len(got) else "。话题问题点「整理话题」一键改"))
        self._start(fn, "" if quiet else f"检查中…({self._who(rows)})", quiet=quiet)

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
        if not ask(self, "横屏转竖屏", f"{self._who(rows)}转成标准竖屏(1080×1920)?横屏、偏方(3:4 / 正方形)的都转。\n\n原片挪进同一个文件夹里的「横屏原片」,不删。", "转", "先不"):
            return
        vs = self.videos
        ff = vertical.ffmpeg_path()
        words = self.st.get("api_platform_words") or None

        def one(i, emit, stopped):
            v = vs[i]
            emit(i, "转竖屏中…")
            try:
                new, _orig = vertical.to_vertical(v.path, ff, stop=stopped)
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
            with ThreadPoolExecutor(3) as ex:          # 3 条一起转最快(这台电脑试过)
                list(ex.map(lambda i: None if stopped() else one(i, emit, stopped), rows))
            return "转竖屏做完了"
        self._start(fn, f"转竖屏:{len(rows)} 条(3 条一起转)")

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
        t, ok = QInputDialog.getText(self, "改标题", "标题(= 文件名)" + (f",里面有「{'、'.join(hits)}」" if hits else "") + ":",
                                     text=v.title)
        t = topic.sanitize(t) if ok else ""
        if not t or t == v.title:
            return
        self._rename_rows([i], lambda _old: t, "改标题")

    def run_topic(self, only: list[int] | None = None):
        """整理话题:写法不对的按固定规矩改(不用 AI);挂了好几个话题的 AI 留一个。"""
        if self.busy():
            return
        only = self.target_rows(only)

        def multi(v):
            return len(topic.split_topics(v.title)["tags"]) > 1
        rows = [i for i in only if (multi(self.videos[i]) or topic.bad_format(self.videos[i].title)) and not self._sent(i)]
        if not rows:
            QMessageBox.information(self, "整理话题", "这些里话题都没问题。")
            return
        n_ai = sum(1 for i in rows if multi(self.videos[i]))
        n_fmt = len(rows) - n_ai
        key = self.st.ai_key() if hasattr(self.st, "ai_key") else ""
        if n_ai and not key:
            QMessageBox.warning(self, "整理话题", "有挂好几个话题的要用 AI 挑,先在「设置」里填阿里百炼 Key。\n\n"
                                                "(只想改写法的:右键「只整理写法、不用 AI」)")
            return
        model = str(self.st.get("topic_model") or "qwen-plus")
        lines = []
        if n_fmt:
            lines.append(f"· {n_fmt} 条话题写法不对 / 结尾多空格:按固定规矩改(不用 AI)")
        if n_ai:
            lines.append(f"· {n_ai} 条挂了好几个话题:AI 各留一个最好搜的(游戏 / 电视剧 / 电影 / 动漫名优先)")
        if not ask(self, "整理话题", f"{self._who(only)}里面:\n" + "\n".join(lines) +
                   "\n\n改文件名,同名的封面图跟着改。改错了可以点「撤销上次改名」。", "整理", "先不"):
            return
        vs = self.videos
        at = self._op("整理话题")
        lock = threading.Lock()

        def one(i, emit, stopped):
            v = vs[i]
            if stopped():
                return
            try:
                name = None
                if not multi(v):
                    name = topic.tidy(v.title)           # 只是写法不对:固定规矩改,不问 AI
                else:
                    for k in range(2):                   # 读不出顺序再问一次
                        try:
                            name = topic.new_name(v.title, lambda b, t: topic.ask_ai(b, t, key, model))
                            break
                        except RuntimeError:
                            if k:
                                raise
                if not name:
                    emit(i, "")
                    return
                note = self._tidy_note(v.title) if not multi(v) else ""
                with lock:
                    moves = topic.rename_logged(v.path, name, self.ledger, at)
                old = v.title
                self._after_rename(v, moves)
                emit(i, "")
                emit(-1, f"整理话题:{old} → {v.title}" + (f"({note})" if note else ""))
            except Exception as e:
                emit(-1, f"「{v.title}」整理话题失败:{e}")

        def fn(emit, stopped):
            with ThreadPoolExecutor(4) as ex:
                list(ex.map(lambda i: one(i, emit, stopped), rows))
            return "整理话题做完了"
        self._start(fn, f"整理话题:{len(rows)} 条" + (f"(其中 {n_ai} 条问 AI)" if n_ai else ""))

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
    def run_publish(self, only: list[int] | None = None):
        """only = 只发这几行(右键「只发这个号的」);None = 选中的,没选就是看得见的全部。发之前一定弹框让人点「发」。"""
        d = self.c_date.currentText()
        if not d or self.busy():
            return
        picked = only is not None or bool(self.selected_rows())
        scope = self.target_rows(only)
        if not scope:
            return
        unchecked = [i for i in scope if not self.videos[i].checks and not self._sent(i)]
        if unchecked:
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
        par = max(1, _num(self.st.get("api_threads"), 1))
        gap = max(0.0, float(_num(self.st.get("api_interval"), 5)))
        by_game = bool(self.st.get("api_archive_by_game", True))
        dest = apisrc.archive_dir(self.st, d)
        per = "\n".join(f"  · {n}:{len(idx)} 条 · {apiacc.CATEGORIES.get(accs[n].get('category'), accs[n].get('category'))}" +
                        (f" → {apisrc.game_folder(accs[n])}" if by_game else "") for n, idx in by_acc.items())
        mins = max(1, round(len(rows) * (gap + 25) / 60 / par))          # 一条大概传 + 发 25 秒,加上间隔
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
        msg = (warn_day + f"发 {d} 的 {len(rows)} 条 · {len(by_acc)} 个号 · 大概 {mins} 分钟\n\n{brief}\n{cat_line}\n\n" +
               (f"其中 {retry} 条是上次没发成的,再试一次。\n" if retry else "") +
               (f"有问题的 {held} 条这次不发。\n" if held else "") + "\n发吗?")
        detail = (f"每个号:\n{per}\n\n标题、简介 = 文件名;自主声明「无需标注」;AI 声明「非 AI 生成」;封面平台自己截。\n"
                  f"{'一条一条发' if par == 1 else f'{par} 个号一起发'},上一条发完歇 {gap:g} 秒再发下一条。\n"
                  f"发成了挪到:{dest}" + ("\\游戏名" if by_game else ""))
        if not ask(self, "发布", msg, "发", "先不发", detail=detail, default_no=bool(warn_day)):
            return
        vs = self.videos
        gate = {"last": 0.0}
        glock = threading.Lock()
        stats = {"ok": 0, "fail": 0, "unsure": 0, "skip": 0, "done": 0, "bad_acc": [], "fails": []}
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
            emit(PROGRESS, f"正在发 {stats['done']}/{len(rows)} · 成功 {stats['ok']} · 没发成 {stats['fail']}" +
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
            for k, i in enumerate(idx):
                if stopped():
                    return
                v = vs[i]
                if self.rec.blocked(v.path):              # 防重发:已发 / 结果不明都不发
                    emit(i, self.rec.status_of(v.path))
                    continue
                if not wait_turn(stopped):
                    return
                rid = {}

                def begin(vid, v=v, rid=rid):
                    got = _retry(lambda: self.rec.try_begin(v, f"vid={vid}"))
                    if got is None:
                        raise _Taken()
                    rid["id"] = got
                try:
                    r = cl.send(v.path, v.title, cat, stop=stopped, before_publish=begin,
                                on_progress=lambda o, s, i=i: emit(i, f"上传 {o * 100 // max(1, s)}%"),
                                log=lambda m, i=i: emit(i, m + "…"))
                except Stopped:
                    emit(i, "停下了,没发")
                    return
                except _Taken:                            # 别的号刚发过 / 正在发同一个文件:这条不发
                    emit(i, self.rec.status_of(v.path) or "已发")
                    emit(-1, f"「{nick}」{v.title}:这个文件别的号已经发了 / 正在发,这次不发")
                    done_one(emit)
                    continue
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
                    continue
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
                        left = idx[k + 1:]
                        for j in left:
                            self.rec.api_result(vs[j], "没发成", "没发:号的密钥坏了(没轮到)")
                            emit(j, "没发:号的密钥坏了")
                        bump("skip", len(left))
                        with slock:
                            stats["bad_acc"].append(nick)
                        return
                    continue
                note = f"article_id={r['article_id']} vid={r['vid']}" + ("" if r["status"] == "成功" else "(平台还在处理)")
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
                    continue
                try:
                    old = v.path
                    v.path = apisrc.move_published(v.path, apisrc.archive_dir(self.st, d, a))
                    if "id" in rid:                       # 记下新位置:之后在归档里再看到它也认得出发过
                        _retry(lambda: self.rec.mark_moved(rid["id"], v.path))
                except OSError as e:
                    emit(-1, f"「{v.title}」发了,但挪不走:{e}(发过的记着呢,不会重发)")
                except Exception:
                    pass
                emit(i, "已发" if r["status"] == "成功" else "已发(平台处理中)")
                done_one(emit)

        def fn(emit, stopped):
            with ThreadPoolExecutor(par) as ex:
                for n, f in [(n, ex.submit(acc_job, n, idx, emit, stopped)) for n, idx in by_acc.items()]:
                    try:
                        f.result()
                    except Exception as e:
                        emit(-1, f"「{n}」发的时候出了没想到的错({type(e).__name__}),这个号后面的先没发;已经发的记着呢")
            not_run = len(rows) - stats["ok"] - stats["fail"] - stats["unsure"] - stats["skip"]
            summary = (f"发完了:成功 {stats['ok']} · 没发成 {stats['fail']} · 结果不明 {stats['unsure']}" +
                       (f" · 号的密钥坏了没发 {stats['skip']}({'、'.join(stats['bad_acc'])})" if stats["skip"] else "") +
                       (f" · 停下了没发 {not_run}" if stopped() and not_run > 0 else ""))
            bad = stats["fail"] or stats["unsure"] or stats["skip"]
            lst = "".join(f"\n · {t[:26]}:{why}" for t, why in stats["fails"][:6]) + \
                ("\n · …" if len(stats["fails"]) > 6 else "")
            self._popup = ("发完了", summary + (f"\n\n这几条要你看一下:{lst}\n\n列表已经切到「只看有问题的」。"
                                               "结果不明的去后台看一眼,再右键标「发了 / 没发」;网络问题的网好了再点「发布」,"
                                               "会接着发没发的(发过的不会重发)。" if bad else ""), bool(bad))
            self._show_bad_after = bool(bad)
            return summary
        self._start(fn, f"开始发布:{len(rows)} 条," + ("一条一条发" if par == 1 else f"{min(par, len(by_acc))} 个号一起发") +
                    f",间隔 {gap:g} 秒")

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
