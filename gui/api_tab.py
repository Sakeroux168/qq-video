"""「接口发(16个号)」页:游戏 / 动漫 16 个号,用企鹅号官方接口直接发(不用罐头)。

先检查(横屏 / 标题里有别的平台 / 话题不止一个)→ 横屏一键转竖、话题 AI 留一个 / 批量改成指定的(能撤销)、平台名你自己改 →
发「能发的」/「选中的」:传视频 → 发布 → 发成了挪到「X月发布视频\\企鹅号\\企鹅号软件发布」,记进「记录」。
列表按号分组,每个号能收起 / 展开(用户 2026-10-15:看每条时展开,不看收起)。
"""
import os
import threading
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QHeaderView,
                               QInputDialog, QLabel, QLineEdit, QMenu, QMessageBox, QPlainTextEdit, QPushButton, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from qe import apiacc, apisrc, checks, topic, vertical
from qe.config import bj_now, bj_str, data_dir

COLS = ["号 / 标题(= 文件名)", "画面", "要处理的", "状态"]
YELLOW, RED, GREEN = QColor("#fff3c4"), QColor("#ffd6d6"), QColor("#d9f2d9")
ROW = Qt.ItemDataRole.UserRole            # 视频那一行:存它在 self.videos 里的下标;号那一行:存 -1
NICK = Qt.ItemDataRole.UserRole + 1       # 号那一行:存号的昵称


class Job(QThread):
    """在后台跑 fn(emit, stopped);emit(行号, 状态文字) 刷新那一行,emit(-1, 文字) 写日志。"""
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


class ApiTab(QWidget):
    def __init__(self, st, rec, say, parent=None):
        super().__init__(parent)
        self.st, self.rec, self._say_main = st, rec, say
        self.videos: list[apisrc.ApiVideo] = []
        self.state: dict[int, str] = {}           # 行号 → 状态文字(发布中 / 已发 / 没发成 …)
        self.items: dict[int, QTreeWidgetItem] = {}
        self.groups: dict[str, QTreeWidgetItem] = {}
        self.open_accounts: set[str] = set()      # 展开着的号(换日期 / 刷新后还展开着)
        self.job: Job | None = None
        self.ledger = topic.Ledger(data_dir() / "话题改名台账.json")
        self._build()
        self.reload_dates()

    # ---------------- 界面 ----------------
    def _build(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 8, 10, 8)
        top = QHBoxLayout()
        top.addWidget(QLabel("要发哪天的:"))
        self.c_date = QComboBox()
        self.c_date.setMinimumWidth(110)
        self.c_date.currentIndexChanged.connect(self.load)
        top.addWidget(self.c_date)
        b = QPushButton("刷新")
        b.clicked.connect(self.reload_dates)
        top.addWidget(b)
        top.addSpacing(16)
        self.lab = QLabel("")
        self.lab.setStyleSheet("color:#777")
        top.addWidget(self.lab, 1)
        b = QPushButton("给号选文件夹…")
        b.setToolTip("像旧软件的「选择」:手动给一个号挑这天要发的文件夹(比如电竞情报馆的「2电竞赛事」)。\n"
                     "选了以后这个号这天只发那个文件夹里的视频,不再自动找。右键列表里的号 / 视频也能选 / 取消。")
        b.clicked.connect(lambda: self.pick_folder())
        top.addWidget(b)
        b = QPushButton("从旧软件搬账号…")
        b.setToolTip("从旧软件「企鹅号批量发布」的数据库(qepm.db)把 16 个号搬过来。密钥加密存在这台电脑上,不显示。")
        b.clicked.connect(self.migrate)
        top.addWidget(b)
        v.addLayout(top)

        view = QHBoxLayout()
        b = QPushButton("全部展开")
        b.clicked.connect(lambda: self.expand_all(True))
        view.addWidget(b)
        b = QPushButton("全部收起")
        b.clicked.connect(lambda: self.expand_all(False))
        view.addWidget(b)
        self.k_bad = QCheckBox("只看有问题的")
        self.k_bad.setToolTip("只显示要处理的(横屏 / 标题有别的平台 / 话题不止一个 / 没发成)")
        self.k_bad.toggled.connect(lambda _on: self._apply_filter())
        view.addWidget(self.k_bad)
        self.e_find = QLineEdit()
        self.e_find.setPlaceholderText("搜标题…")
        self.e_find.setClearButtonEnabled(True)
        self.e_find.setMaximumWidth(220)
        self.e_find.textChanged.connect(lambda _t: self._apply_filter())
        view.addWidget(self.e_find)
        view.addStretch(1)
        self.lab_sum = QLabel("")
        view.addWidget(self.lab_sum)
        v.addLayout(view)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(len(COLS))
        self.tree.setHeaderLabels(COLS)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setToolTip("点号前面的小三角(或双击号)展开 / 收起;按住 Ctrl / Shift 多选;选中号 = 选中这个号的全部视频。\n"
                             "双击一条视频:打开它所在的文件夹。右键:只发 / 改话题 / 改标题 / 换文件夹。")
        self.tree.itemDoubleClicked.connect(self._double)
        self.tree.itemExpanded.connect(lambda it: self._remember(it, True))
        self.tree.itemCollapsed.connect(lambda it: self._remember(it, False))
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        self.tree.setUniformRowHeights(True)
        hh = self.tree.header()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setStretchLastSection(False)
        for i, wd in ((1, 90), (2, 230), (3, 150)):
            self.tree.setColumnWidth(i, wd)
        v.addWidget(self.tree, 1)

        # 规矩(用户 2026-10-15):选了东西,下面每个按钮都只管选中的;什么都没选,就管列表里看得见的全部。
        # 按钮上的字跟着变(「检查(选中 20 条)」/「检查(全部)」),一眼看出这次管哪些。
        bar = QHBoxLayout()
        self.lab_scope = QLabel("")
        self.lab_scope.setStyleSheet("color:#2a6;font-weight:bold")
        bar.addWidget(self.lab_scope)
        self.b_clear = QPushButton("取消选择")
        self.b_clear.setToolTip("不选了:下面的按钮回到管全部")
        self.b_clear.clicked.connect(self.tree.clearSelection)
        bar.addWidget(self.b_clear)
        self.b_check = QPushButton("检查")
        self.b_check.setToolTip("看每条:是不是竖屏、标题里有没有别的平台的名字、话题是不是只有一个")
        self.b_check.clicked.connect(lambda: self.run_check())
        self.b_vert = QPushButton("横屏转竖屏")
        self.b_vert.setToolTip("上下糊底、中间原画面,转成 1080×1920。原片挪进同文件夹的「横屏原片」,不删。")
        self.b_vert.clicked.connect(lambda: self.run_vertical())
        self.b_topic = QPushButton("话题只留一个(AI)")
        self.b_topic.setToolTip("和 AI 改名软件「只筛话题」一样:多个话题让 AI 挑最好搜的留一个(游戏 / 剧 / 电影 / 动漫名优先),\n"
                                "改文件名(同名封面跟着改)。能撤销。")
        self.b_topic.clicked.connect(lambda: self.run_topic())
        self.b_settopic = QPushButton("批量改话题…")
        self.b_settopic.setToolTip("话题全换成你填的那一个,比如填「英雄联盟」→ 结尾变成 #英雄联盟。原来没话题的就接在后面。能撤销。\n"
                                   "这个必须先选(选号 = 这个号全部),免得把别的游戏 / 动漫的号也改了。")
        self.b_settopic.clicked.connect(lambda: self.set_topic())
        self.b_undo = QPushButton("撤销上次改名")
        self.b_undo.setToolTip("把上一次改话题 / 批量改话题 / 改标题改回去")
        self.b_undo.clicked.connect(self.undo_topic)
        self.b_pub = QPushButton("发布")
        self.b_pub.setMinimumHeight(34)
        self.b_pub.setToolTip("没有问题的(竖屏、标题里没别的平台、话题只有一个、没发过的)用接口发出去;有问题的不发。\n"
                              "发成了挪到「X月发布视频\\企鹅号\\企鹅号软件发布」(设置里能改)。")
        self.b_pub.clicked.connect(lambda: self.run_publish())
        self.b_stop = QPushButton("停")
        self.b_stop.clicked.connect(self.stop)
        for b in (self.b_check, self.b_vert, self.b_topic, self.b_settopic, self.b_undo):
            bar.addWidget(b)
        bar.addStretch(1)
        bar.addWidget(self.b_pub)
        bar.addWidget(self.b_stop)
        v.addLayout(bar)
        self.logbox = QPlainTextEdit()
        self.logbox.setReadOnly(True)
        self.logbox.setMaximumBlockCount(3000)
        self.logbox.setMaximumHeight(150)
        v.addWidget(self.logbox)
        self.tree.itemSelectionChanged.connect(self._update_scope)
        self._busy(False)
        self._update_scope()

    def say(self, m: str):
        """日志写在这页下面(也照样写到主窗口)。"""
        self.logbox.appendPlainText(f"[{bj_str()[11:]}] {m}")
        self._say_main(m)

    def _busy(self, on: bool):
        for b in (self.b_check, self.b_vert, self.b_topic, self.b_settopic, self.b_undo, self.b_pub, self.b_clear,
                  self.c_date):
            b.setEnabled(not on)
        self.b_stop.setEnabled(on)
        if not on:
            self._update_scope()

    def target_rows(self, only: list[int] | None = None) -> list[int]:
        """这次要管哪些:给了就是给的;没给 → 选中的;没选 → 列表里看得见的全部(「只看有问题的」/ 搜索过滤掉的不算)。"""
        if only is not None:
            return [i for i in only if 0 <= i < len(self.videos)]
        return self.selected_rows() or [i for i, it in self.items.items() if not it.isHidden()]

    def _update_scope(self):
        sel = self.selected_rows()
        if sel:
            accs = sorted({self.videos[i].account for i in sel})
            who = accs[0] if len(accs) == 1 else f"{len(accs)} 个号"
            tag = f"选中 {len(sel)} 条"
            self.lab_scope.setText(f"▶ 只管选中的:{who} {len(sel)} 条")
        else:
            tag = "全部"
            self.lab_scope.setText("▶ 没选:管全部" if self.items else "")
        self.b_clear.setVisible(bool(sel))
        self.b_check.setText(f"检查({tag})")
        self.b_vert.setText(f"横屏转竖屏({tag})")
        self.b_topic.setText(f"话题只留一个 AI({tag})")
        self.b_settopic.setText(f"批量改话题…({tag})" if sel else "批量改话题…(先选)")
        self.b_pub.setText(f"发布({tag}里能发的)")

    def roots(self) -> list[str]:
        return list(self.st.get("api_roots") or apisrc.DEFAULT_ROOTS)

    def known(self):
        ns = apiacc.nicks()
        return set(ns) if ns else None

    # ---------------- 读素材 ----------------
    def reload_dates(self):
        if self.job and self.job.isRunning():
            return
        cur = self.c_date.currentText()
        self.c_date.blockSignals(True)
        self.c_date.clear()
        self.c_date.addItem("")                    # 不自动选:让人自己挑哪天
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
        """上面那行:素材到底从哪来(这天手选了文件夹的号按手选的说)。"""
        n = len(apiacc.load())
        head = f"{n} 个号" + ("" if n else "(还没搬账号,先点右边「从旧软件搬账号…」)")
        auto = "自动找:" + "、".join(self.roots())
        pk = self.picked(d) if d else {}
        if not pk:
            self.lab.setText(f"{head} · 素材{auto}")
            self.lab.setToolTip("")
            return
        parents = sorted({os.path.dirname(f) for f in pk.values()})
        rest = n - len(pk)
        self.lab.setText(f"{head} · {d} 有 {len(pk)} 个号用手选的文件夹({'、'.join(parents)})" +
                         (f",其余 {rest} 个号{auto}" if rest > 0 else ""))
        self.lab.setToolTip("\n".join(f"{k} → {v}" for k, v in sorted(pk.items())))

    def load(self):
        d = self.c_date.currentText()
        self._show_source(d)
        self.videos = apisrc.videos(self.roots(), d, self.known(), self.picked(d)) if d else []
        self.state = {}
        for i, v in enumerate(self.videos):
            s = self.rec.status_of(v.path)
            if s:
                self.state[i] = s
        self._build_tree()
        if d:
            accs = sorted({v.account for v in self.videos})
            pk = self.picked(d)
            self.say(f"接口发 {d}:{len(self.videos)} 条,{len(accs)} 个号。先点「检查」。" +
                     ("(手选的文件夹:" + ";".join(f"{n} → {os.path.basename(f)}" for n, f in pk.items()) + ")" if pk else ""))

    def _build_tree(self):
        self.tree.blockSignals(True)
        self.tree.clear()
        self.items, self.groups = {}, {}
        bold = QFont()
        bold.setBold(True)
        for i, v in enumerate(self.videos):
            g = self.groups.get(v.account)
            if g is None:
                g = QTreeWidgetItem([v.account])
                g.setData(0, ROW, -1)
                g.setData(0, NICK, v.account)
                for c in range(len(COLS)):
                    g.setFont(c, bold)
                self.tree.addTopLevelItem(g)
                self.groups[v.account] = g
            it = QTreeWidgetItem([v.title])
            it.setData(0, ROW, i)
            g.addChild(it)
            self.items[i] = it
            self._fill(i, group=False)
        for nick, g in self.groups.items():
            g.setExpanded(nick in self.open_accounts)
            self._fill_group(nick)
        self.tree.blockSignals(False)
        self._apply_filter()
        self._update_scope()

    def _remember(self, it: QTreeWidgetItem, on: bool):
        if it.data(0, ROW) == -1:
            (self.open_accounts.add if on else self.open_accounts.discard)(it.data(0, NICK))

    def expand_all(self, on: bool):
        for nick, g in self.groups.items():
            g.setExpanded(on)
        self.open_accounts = set(self.groups) if on else set()

    def _double(self, it: QTreeWidgetItem, _col: int):
        i = it.data(0, ROW)
        if isinstance(i, int) and i >= 0:
            self.reveal(i)

    def _status_text(self, i: int) -> tuple[str, list]:
        v = self.videos[i]
        c = v.checks or {}
        probs = checks.problems(v) if c else []
        return self.state.get(i, "") or ("能发" if c and not probs else ""), probs

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
            it.setToolTip(col, v.path if col == 0 else t)
        bg = GREEN if st.startswith("已发") else RED if st.startswith(("没发成", "转竖屏失败")) or (c and "横屏" in probs) \
            else YELLOW if probs else None
        for col in range(len(COLS)):
            it.setBackground(col, bg if bg else QColor(0, 0, 0, 0))
        if group:
            self._fill_group(v.account)
            self._apply_filter(only=it)

    def _fill_group(self, nick: str):
        g = self.groups.get(nick)
        if g is None:
            return
        rows = [g.child(k).data(0, ROW) for k in range(g.childCount())]
        n = len(rows)
        sent = sum(1 for i in rows if self.state.get(i, "").startswith("已发"))
        checked = [i for i in rows if self.videos[i].checks]
        bad = sum(1 for i in checked if checks.problems(self.videos[i]) and not self.state.get(i, "").startswith("已发"))
        fail = sum(1 for i in rows if self.state.get(i, "").startswith("没发成"))
        ok = sum(1 for i in checked if not checks.problems(self.videos[i]) and not self.state.get(i, "").startswith("已发"))
        pk = "(手选文件夹)" if nick in self.picked(self.c_date.currentText()) else ""
        g.setText(0, f"{nick}  {n} 条{pk}")
        g.setText(1, "")
        g.setText(2, (f"有问题 {bad}" if bad else ("" if checked else "没检查")) + (f" · 没发成 {fail}" if fail else ""))
        g.setText(3, f"能发 {ok} · 已发 {sent}" if checked or sent else (f"已发 {sent}" if sent else ""))
        g.setToolTip(0, self.picked(self.c_date.currentText()).get(nick, "") or nick)
        col = GREEN if n and sent == n else YELLOW if bad or fail else None
        for c in range(len(COLS)):
            g.setBackground(c, col if col else QColor(0, 0, 0, 0))
        self._update_sum()

    def _update_sum(self):
        n = len(self.videos)
        sent = sum(1 for i in range(n) if self.state.get(i, "").startswith("已发"))
        checked = [i for i in range(n) if self.videos[i].checks]
        ok = sum(1 for i in checked if not checks.problems(self.videos[i]) and not self.state.get(i, "").startswith("已发"))
        bad = sum(1 for i in checked if checks.problems(self.videos[i]) and not self.state.get(i, "").startswith("已发"))
        self.lab_sum.setText(f"共 {n} 条 · 能发 {ok} · 有问题 {bad} · 已发 {sent}" + ("" if checked or not n else " · 还没检查"))

    def _hidden(self, i: int) -> bool:
        key = self.e_find.text().strip().lower()
        if key and key not in self.videos[i].title.lower():
            return True
        if self.k_bad.isChecked():
            st, probs = self._status_text(i)
            return not (probs or st.startswith(("没发成", "转竖屏失败"))) or st.startswith("已发")
        return False

    def _apply_filter(self, only: QTreeWidgetItem | None = None):
        if only is not None:
            only.setHidden(self._hidden(only.data(0, ROW)))
            return
        for i, it in self.items.items():
            it.setHidden(self._hidden(i))
        filtering = self.k_bad.isChecked() or bool(self.e_find.text().strip())
        for nick, g in self.groups.items():
            vis = any(not g.child(k).isHidden() for k in range(g.childCount()))
            g.setHidden(not vis)
            if filtering and vis:
                g.setExpanded(True)

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
        d = self.c_date.currentText()
        if not d:
            QMessageBox.information(self, "给号选文件夹", "先在上面选是哪天的。")
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
        self._set_pick(d, nick, f)
        n = len(apisrc._videos_in(f, nick, d))
        self.say(f"{d}「{nick}」只发这个文件夹里的 {n} 条:{f}")
        self.load()

    def unpick(self, nick: str):
        d = self.c_date.currentText()
        self._set_pick(d, nick, "")
        self.say(f"{d}「{nick}」不用手选的文件夹了,回到自动找")
        self.load()

    def _menu(self, pos):
        it = self.tree.itemAt(pos)
        m = QMenu(self)
        if it is not None:
            if not it.isSelected():
                self.tree.clearSelection()
                it.setSelected(True)
            i = it.data(0, ROW)
            nick = it.data(0, NICK) if i == -1 else self.videos[i].account
            sel = self.selected_rows()
            busy = bool(self.job and self.job.isRunning())
            mine = self.rows_of(nick)
            for text, fn in ((f"检查选中的 {len(sel)} 条", lambda: self.run_check(sel)),
                             (f"横屏转竖屏(选中的 {len(sel)} 条)", lambda: self.run_vertical(sel)),
                             (f"话题只留一个(AI,选中的 {len(sel)} 条)", lambda: self.run_topic(sel)),
                             (f"批量改话题(选中的 {len(sel)} 条)…", lambda: self.set_topic(sel)),
                             (f"发布选中的 {len(sel)} 条", lambda: self.run_publish(sel)),
                             (None, None),
                             (f"只检查「{nick}」的 {len(mine)} 条", lambda: self.run_check(mine)),
                             (f"只发「{nick}」的", lambda: self.run_publish(mine))):
                if text is None:
                    m.addSeparator()
                else:
                    m.addAction(text, fn).setEnabled(not busy)
            if i != -1:
                m.addAction("改标题…", lambda: self.edit_title(i)).setEnabled(not busy)
                m.addSeparator()
                m.addAction("打开所在文件夹", lambda: self.reveal(i))
            m.addSeparator()
            m.addAction(f"给「{nick}」换个文件夹…", lambda: self.pick_folder(nick))
            if nick in self.picked(self.c_date.currentText()):
                m.addAction(f"「{nick}」不用手选的文件夹了(自动找)", lambda: self.unpick(nick))
            m.addSeparator()
        m.addAction("给别的号选文件夹…", lambda: self.pick_folder())
        m.addAction("全部展开", lambda: self.expand_all(True))
        m.addAction("全部收起", lambda: self.expand_all(False))
        m.exec(self.tree.viewport().mapToGlobal(pos))

    def reveal(self, row: int):
        if 0 <= row < len(self.videos):
            from gui.window import MainWindow
            MainWindow.reveal(self.videos[row].path)

    # ---------------- 后台活 ----------------
    def _start(self, fn, title: str):
        if self.job and self.job.isRunning():
            return
        self._busy(True)
        self.say(title)
        self.job = Job(fn, self)
        self.job.row.connect(self._on_row)
        self.job.done.connect(self._on_done)
        self.job.start()

    def _on_row(self, i: int, t: str):
        if i < 0:
            self.say(t)
            return
        if t:
            self.state[i] = t
        if i in self.items:
            self._fill(i)

    def _on_done(self, msg: str):
        self._busy(False)
        if msg:
            self.say(msg)

    def stop(self):
        if self.job:
            self.job.stop()
            self.say("正在停…(手上这条做完就停)")

    def run_check(self, only: list[int] | None = None):
        rows = self.target_rows(only)
        if not rows:
            return
        vs = self.videos
        words = self.st.get("api_platform_words") or None
        ff = vertical.ffmpeg_path()

        def fn(emit, stopped):
            for i in rows:
                if stopped():
                    return "停下了"
                checks.check_one(vs[i], words, ff)
                emit(i, "")
            got = [vs[i] for i in rows]
            land = sum(1 for v in got if v.checks.get("landscape"))
            plat = sum(1 for v in got if v.checks.get("platform"))
            many = sum(1 for v in got if len(v.checks.get("tags") or []) > 1)
            ok = sum(1 for v in got if not checks.problems(v))
            return f"检查完:{len(got)} 条,能发 {ok};横屏 {land},标题有别的平台 {plat}(要你自己改),话题不止一个 {many}"
        self._start(fn, f"检查中…({self._who(rows)})")

    def _who(self, rows: list[int]) -> str:
        accs = sorted({self.videos[i].account for i in rows})
        return f"{accs[0]} 的 {len(rows)} 条" if len(accs) == 1 else f"{len(accs)} 个号 {len(rows)} 条"

    def run_vertical(self, only: list[int] | None = None):
        rows = [i for i in self.target_rows(only) if (self.videos[i].checks or {}).get("landscape") and not self._sent(i)]
        if not rows:
            QMessageBox.information(self, "横屏转竖屏", "这些里没有横屏的(没检查过的先点「检查」)。")
            return
        if QMessageBox.question(self, "横屏转竖屏", f"{len(rows)} 条横屏转成竖屏?\n\n原片挪进同一个文件夹里的「横屏原片」,不删。") \
                != QMessageBox.StandardButton.Yes:
            return
        vs = self.videos
        ff = vertical.ffmpeg_path()
        words = self.st.get("api_platform_words") or None

        def one(i, emit, stopped):
            v = vs[i]
            emit(i, "转竖屏中…")
            try:
                new, _orig = vertical.to_vertical(v.path, ff, stop=stopped)
            except RuntimeError as e:
                emit(i, "转竖屏失败")
                emit(-1, f"「{v.title}」转竖屏失败:{e}")
                return
            v.path = new
            checks.check_one(v, words, ff)
            emit(i, "转好了")

        def fn(emit, stopped):
            with ThreadPoolExecutor(3) as ex:          # 3 条一起转最快(这台电脑试过)
                list(ex.map(lambda i: None if stopped() else one(i, emit, stopped), rows))
            return "转竖屏做完了"
        self._start(fn, f"转竖屏:{len(rows)} 条(3 条一起转)")

    def _sent(self, i: int) -> bool:
        return self.state.get(i, "").startswith("已发")

    # ---------------- 改名(话题 / 标题),都记台账能撤销 ----------------
    def _after_rename(self, v, moves):
        v.path = moves[0][1]
        v.title = os.path.splitext(os.path.basename(v.path))[0]
        if v.checks:
            v.checks["tags"] = topic.split_topics(v.title)["tags"]
            v.checks["platform"] = checks.platform_hits(v.title, self.st.get("api_platform_words") or None)

    def _rename_rows(self, rows: list[int], make, what: str) -> int:
        """在界面线程里直接改(只是改文件名,很快)。make(标题) → 新标题 / None。返回改了几条。"""
        at = bj_str()
        n = 0
        for i in rows:
            v = self.videos[i]
            if self._sent(i):
                continue
            new = make(v.title)
            if not new:
                continue
            try:
                moves = topic.rename_with_sidecars(v.path, new)
            except OSError as e:
                self.say(f"「{v.title}」{what}失败:{e}")
                continue
            self.ledger.add(at, moves)
            old = v.title
            self._after_rename(v, moves)
            self._fill(i)
            self.say(f"{what}:{old} → {v.title}")
            n += 1
        return n

    def set_topic(self, rows: list[int] | None = None):
        rows = self.selected_rows() if rows is None else rows
        rows = [i for i in rows if not self._sent(i)]
        if not rows:
            QMessageBox.information(self, "批量改话题", "先在列表里选要改的(选号 = 这个号全部;按住 Ctrl 可以多选)。")
            return
        last = str(self.st.get("api_last_topic") or "")
        tag, ok = QInputDialog.getText(self, "批量改话题", f"选中的 {len(rows)} 条,结尾的话题全换成(不用打 #):", text=last)
        tag = topic.clean_tag(tag) if ok else ""
        if not tag:
            return
        ex = next((topic.with_topic(self.videos[i].title, tag) for i in rows if topic.with_topic(self.videos[i].title, tag)), None)
        if not ex:
            QMessageBox.information(self, "批量改话题", f"选中的已经都是 #{tag} 了。")
            return
        if QMessageBox.question(self, "批量改话题", f"{len(rows)} 条的话题全换成 #{tag}?\n\n比如:\n{ex}\n\n"
                                                   "同名封面跟着改。改错了点「撤销上次改名」。") != QMessageBox.StandardButton.Yes:
            return
        self.st["api_last_topic"] = tag
        self.st.save()
        n = self._rename_rows(rows, lambda t: topic.with_topic(t, tag), f"改成 #{tag}")
        self.say(f"批量改话题:{n} 条改成 #{tag}")

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
        only = self.target_rows(only)

        def multi(v):
            return len(topic.split_topics(v.title)["tags"]) > 1

        def fix_only(v):                                  # 只有一个话题,但写成「# 话题」:改成「#话题」,不用问 AI
            return topic.bad_format(v.title)
        rows = [i for i in only if (multi(self.videos[i]) or fix_only(self.videos[i])) and not self._sent(i)]
        if not rows:
            QMessageBox.information(self, "话题只留一个", "这些里没有挂了好几个话题的。")
            return
        n_ai = sum(1 for i in rows if multi(self.videos[i]))
        key = self.st.ai_key() if hasattr(self.st, "ai_key") else ""
        if n_ai and not key:
            QMessageBox.warning(self, "话题只留一个", "要用 AI 挑话题,先在「设置」里填阿里百炼 Key。")
            return
        model = str(self.st.get("topic_model") or "qwen-plus")
        if QMessageBox.question(self, "话题只留一个", f"{self._who(only)}里面:" +
                                f"{n_ai} 条挂了好几个话题,让 AI 各留一个最好搜的(游戏 / 电视剧 / 电影 / 动漫名优先)" +
                                (f";另外 {len(rows) - n_ai} 条「# 话题」写法改成「#话题」" if len(rows) > n_ai else "") +
                                ",改文件名?\n\n同名的封面图跟着改。改错了可以点「撤销上次改名」。") \
                != QMessageBox.StandardButton.Yes:
            return
        vs = self.videos
        at = bj_str()
        lock = threading.Lock()

        def one(i, emit, stopped):
            v = vs[i]
            if stopped():
                return
            try:
                name = None
                for k in range(2):                       # 读不出顺序再问一次
                    try:
                        name = topic.new_name(v.title, lambda b, t: topic.ask_ai(b, t, key, model))
                        break
                    except RuntimeError:
                        if k:
                            raise
                if not name:
                    emit(i, "")
                    return
                with lock:
                    moves = topic.rename_with_sidecars(v.path, name)
                    self.ledger.add(at, moves)
                old = v.title
                self._after_rename(v, moves)
                emit(i, "")
                emit(-1, f"改话题:{old} → {v.title}")
            except Exception as e:
                emit(-1, f"「{v.title}」改话题失败:{e}")

        def fn(emit, stopped):
            with ThreadPoolExecutor(4) as ex:
                list(ex.map(lambda i: one(i, emit, stopped), rows))
            return "改话题做完了"
        self._start(fn, f"AI 挑话题:{len(rows)} 条")

    def undo_topic(self):
        b = self.ledger.last()
        if not b:
            QMessageBox.information(self, "撤销", "没有能撤销的改名。")
            return
        n = sum(1 for m in b["moves"] if os.path.splitext(m[0])[1].lower() in apisrc.VIDEO_EXTS)
        if QMessageBox.question(self, "撤销", f"把 {b['at']} 那次改的 {n} 条视频(和跟着改的封面)改回原名?") \
                != QMessageBox.StandardButton.Yes:
            return
        ok, bad = self.ledger.undo_last()
        self.say(f"撤销改名:改回 {ok} 个文件" + (f",{bad} 个改不回(文件不在了或原名被占)" if bad else ""))
        self.load()

    # ---------------- 发布 ----------------
    def run_publish(self, only: list[int] | None = None):
        """only = 只发这几行(右键「只发这个号的」);None = 选中的,没选就是看得见的全部。"""
        d = self.c_date.currentText()
        if not d:
            return
        picked = only is not None or bool(self.selected_rows())
        scope = self.target_rows(only)
        if not scope:
            return
        if [i for i in scope if not self.videos[i].checks]:
            QMessageBox.information(self, "发布", "先点「检查」。")
            return
        rows = [i for i in scope if not checks.problems(self.videos[i]) and not self._sent(i)
                and self.rec.status_of(self.videos[i].path) != "已发"]
        if not rows:
            QMessageBox.information(self, "发布", "选的这些里没有能发的(有问题的 / 发过的不发)。" if picked
                                    else "没有能发的。")
            return
        accs = {a["nick"]: a for a in apiacc.load()}
        miss = sorted({self.videos[i].account for i in rows if self.videos[i].account not in accs})
        if miss:
            QMessageBox.warning(self, "发布", "这些号还没搬账号:" + "、".join(miss))
            return
        dest = apisrc.archive_dir(self.st, d)
        held = len(scope) - len(rows) - sum(1 for i in scope if self._sent(i))
        by_acc: dict[str, list[int]] = {}
        for i in rows:
            by_acc.setdefault(self.videos[i].account, []).append(i)
        par = max(1, int(self.st.get("api_threads") or 1))
        gap = max(0.0, float(self.st.get("api_interval", 5) or 0))
        how = "一条一条发" if par == 1 else f"{par} 个号一起发"
        by_game = bool(self.st.get("api_archive_by_game", True))
        subs = "、".join(dict.fromkeys(apisrc.game_folder(accs[n]) for n in by_acc))
        msg = (f"用接口发 {len(rows)} 条({len(by_acc)} 个号:{'、'.join(by_acc)})" +
               (f",有问题的 {held} 条不发" if held else "") +
               f"。\n\n标题、简介 = 文件名;分类按号;声明「非 AI 生成」;封面平台自己截。\n"
               f"{how},每条之间歇 {gap:g} 秒。\n发成了挪到:\n{dest}" +
               (f"\n下面按游戏分子文件夹:{subs}" if by_game else "") + "\n\n发吗?")
        if QMessageBox.question(self, "发布", msg) != QMessageBox.StandardButton.Yes:
            return
        vs = self.videos
        gate = {"last": 0.0}
        glock = threading.Lock()

        def wait_turn(stopped) -> bool:
            """每条之间歇 gap 秒(几个号一起发也算总的);停了返回 False。"""
            import time
            with glock:
                while time.time() < gate["last"] + gap:
                    if stopped():
                        return False
                    time.sleep(0.2)
                gate["last"] = time.time()
            return not stopped()

        def acc_job(nick, idx, emit, stopped):
            from qe.omapi import ApiError, Client
            a = accs[nick]
            try:
                cl = Client(a["client_id"], apiacc.unseal(a["secret"]))
            except Exception as e:
                for i in idx:
                    emit(i, "没发成:账号密钥读不出来")
                emit(-1, f"「{nick}」密钥读不出来:{e}")
                return 0
            sent = 0
            for i in idx:
                if stopped():
                    return sent
                v = vs[i]
                if self.rec.status_of(v.path) == "已发":    # 防重发
                    emit(i, "已发")
                    continue
                if not wait_turn(stopped):
                    return sent
                try:
                    r = cl.send(v.path, v.title, a["category"], stop=stopped,
                                on_progress=lambda o, s, i=i: emit(i, f"上传 {o * 100 // max(1, s)}%"),
                                log=lambda m, i=i: emit(i, m + "…"))
                except (ApiError, OSError, Exception) as e:
                    self.rec.api_result(v, "没发成", str(e))
                    emit(i, "没发成")
                    emit(-1, f"「{nick}」{v.title}:没发成:{e}")
                    if "token" in str(e):
                        return sent
                    continue
                note = f"article_id={r['article_id']} vid={r['vid']}" + ("" if r["status"] == "成功" else "(平台还在处理)")
                self.rec.api_result(v, "已发", note)
                sent += 1
                try:
                    v.path = apisrc.move_published(v.path, apisrc.archive_dir(self.st, d, a))
                except OSError as e:
                    emit(-1, f"「{v.title}」发了,但挪不走:{e}")
                emit(i, "已发" if r["status"] == "成功" else "已发(平台处理中)")
            return sent

        def fn(emit, stopped):
            with ThreadPoolExecutor(par) as ex:
                futs = [ex.submit(acc_job, n, idx, emit, stopped) for n, idx in by_acc.items()]
                n = sum(f.result() for f in futs)
            return f"接口发完:发出去 {n} 条" + ("(停下了)" if stopped() else "")
        self._start(fn, f"接口发布:{len(rows)} 条," + ("一条一条发" if par == 1 else f"{min(par, len(by_acc))} 个号一起发") +
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
