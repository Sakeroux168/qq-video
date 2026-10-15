"""「接口发(16个号)」页:游戏 / 动漫 16 个号,用企鹅号官方接口直接发(不用罐头)。

先检查(横屏 / 标题里有别的平台 / 话题不止一个)→ 横屏一键转竖、话题 AI 留一个(能撤销)、平台名你自己改 →
发「能发的」:传视频 → 发布 → 发成了挪到「X月发布视频\\企鹅号\\企鹅号软件发布」,记进「记录」。
"""
import os
import threading
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFileDialog, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
                               QMenu, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from qe import apiacc, apisrc, checks, topic, vertical
from qe.config import bj_now, bj_str, data_dir

COLS = ["号", "标题(= 文件名)", "画面", "要处理的", "状态"]
YELLOW, RED, GREEN = QColor("#fff3c4"), QColor("#ffd6d6"), QColor("#d9f2d9")


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
        self.st, self.rec, self.say = st, rec, say
        self.videos: list[apisrc.ApiVideo] = []
        self.state: dict[int, str] = {}           # 行号 → 状态文字(发布中 / 已发 / 没发成 …)
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
                     "选了以后这个号这天只发那个文件夹里的视频,不再自动找。右键列表里的一条也能选 / 取消。")
        b.clicked.connect(lambda: self.pick_folder())
        top.addWidget(b)
        b = QPushButton("从旧软件搬账号…")
        b.setToolTip("从旧软件「企鹅号批量发布」的数据库(qepm.db)把 16 个号搬过来。密钥加密存在这台电脑上,不显示。")
        b.clicked.connect(self.migrate)
        top.addWidget(b)
        v.addLayout(top)

        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setToolTip("双击一条:在资源管理器里打开它所在的文件夹(标题里有别的平台的名字,去那改文件名)")
        self.table.cellDoubleClicked.connect(lambda r, _c: self.reveal(r))
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._menu)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for i, wd in ((0, 120), (2, 90), (3, 220), (4, 150)):
            self.table.setColumnWidth(i, wd)
        v.addWidget(self.table, 1)

        bar = QHBoxLayout()
        self.b_check = QPushButton("检查")
        self.b_check.setToolTip("看每条:是不是竖屏、标题里有没有别的平台的名字、话题是不是只有一个")
        self.b_check.clicked.connect(self.run_check)
        self.b_vert = QPushButton("横屏的转竖屏")
        self.b_vert.setToolTip("上下糊底、中间原画面,转成 1080×1920。原片挪进同文件夹的「横屏原片」,不删。")
        self.b_vert.clicked.connect(self.run_vertical)
        self.b_topic = QPushButton("话题只留一个(AI)")
        self.b_topic.setToolTip("和 AI 改名软件「只筛话题」一样:多个话题让 AI 挑最好搜的留一个,改文件名(同名封面跟着改)。能撤销。")
        self.b_topic.clicked.connect(self.run_topic)
        self.b_undo = QPushButton("撤销上次改话题")
        self.b_undo.clicked.connect(self.undo_topic)
        self.b_pub = QPushButton("发能发的")
        self.b_pub.setMinimumHeight(34)
        self.b_pub.setToolTip("没有问题的(竖屏、标题里没别的平台、话题最多一个、没发过的)用接口发出去;\n"
                              "发成了挪到「X月发布视频\\企鹅号\\企鹅号软件发布」(设置里能改)。")
        self.b_pub.clicked.connect(self.run_publish)
        self.b_stop = QPushButton("停")
        self.b_stop.clicked.connect(self.stop)
        for b in (self.b_check, self.b_vert, self.b_topic, self.b_undo):
            bar.addWidget(b)
        bar.addStretch(1)
        bar.addWidget(self.b_pub)
        bar.addWidget(self.b_stop)
        v.addLayout(bar)
        self._busy(False)

    def _busy(self, on: bool):
        for b in (self.b_check, self.b_vert, self.b_topic, self.b_undo, self.b_pub, self.c_date):
            b.setEnabled(not on)
        self.b_stop.setEnabled(on)

    def roots(self) -> list[str]:
        return list(self.st.get("api_roots") or apisrc.DEFAULT_ROOTS)

    def known(self):
        ns = apiacc.nicks()
        return set(ns) if ns else None

    # ---------------- 读素材 ----------------
    def reload_dates(self):
        if self.job and self.job.isRunning():
            return
        n = len(apiacc.load())
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
        self.lab.setText(f"{n} 个号" + ("" if n else "(还没搬账号,先点右边「从旧软件搬账号…」)") +
                         f" · 素材:{'、'.join(self.roots())}")
        self.load()

    def load(self):
        d = self.c_date.currentText()
        self.videos = apisrc.videos(self.roots(), d, self.known(), self.picked(d)) if d else []
        self.state = {}
        for i, v in enumerate(self.videos):
            s = self.rec.status_of(v.path)
            if s:
                self.state[i] = s
        self.table.setRowCount(len(self.videos))
        for i in range(len(self.videos)):
            self._fill(i)
        if d:
            accs = sorted({v.account for v in self.videos})
            pk = self.picked(d)
            self.say(f"接口发 {d}:{len(self.videos)} 条,{len(accs)} 个号。先点「检查」。" +
                     ("(手选的文件夹:" + ";".join(f"{n} → {os.path.basename(f)}" for n, f in pk.items()) + ")" if pk else ""))

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
        r = self.table.rowAt(pos.y())
        m = QMenu(self)
        if 0 <= r < len(self.videos):
            nick = self.videos[r].account
            m.addAction("打开所在文件夹", lambda: self.reveal(r))
            m.addAction(f"给「{nick}」换个文件夹…", lambda: self.pick_folder(nick))
            if nick in self.picked(self.c_date.currentText()):
                m.addAction(f"「{nick}」不用手选的文件夹了(自动找)", lambda: self.unpick(nick))
            m.addSeparator()
        m.addAction("给别的号选文件夹…", lambda: self.pick_folder())
        m.exec(self.table.viewport().mapToGlobal(pos))

    def _fill(self, i: int):
        v = self.videos[i]
        c = v.checks or {}
        probs = checks.problems(v) if c else []
        res = (f"{c['w']}×{c['h']}" if c.get("w") else "") if c else "没检查"
        st = self.state.get(i, "")
        cells = [v.account, v.title, res, "、".join(probs) if c else "", st or ("能发" if c and not probs else "")]
        for col, t in enumerate(cells):
            it = self.table.item(i, col)
            if it is None:
                it = QTableWidgetItem()
                self.table.setItem(i, col, it)
            it.setText(t)
            it.setToolTip(v.path if col == 1 else t)
            bg = GREEN if st == "已发" else RED if st.startswith("没发成") or (c and "横屏" in probs) else \
                YELLOW if probs else None
            it.setBackground(bg if bg else QColor(0, 0, 0, 0))

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
        if i < self.table.rowCount():
            self._fill(i)

    def _on_done(self, msg: str):
        self._busy(False)
        if msg:
            self.say(msg)

    def stop(self):
        if self.job:
            self.job.stop()
            self.say("正在停…(手上这条做完就停)")

    def run_check(self):
        vs = list(self.videos)
        words = self.st.get("api_platform_words") or None
        ff = vertical.ffmpeg_path()

        def fn(emit, stopped):
            for i, v in enumerate(vs):
                if stopped():
                    return "停下了"
                checks.check_one(v, words, ff)
                emit(i, "")
            land = sum(1 for v in vs if v.checks.get("landscape"))
            plat = sum(1 for v in vs if v.checks.get("platform"))
            many = sum(1 for v in vs if len(v.checks.get("tags") or []) > 1)
            ok = sum(1 for v in vs if not checks.problems(v))
            return f"检查完:{len(vs)} 条,能发 {ok};横屏 {land},标题有别的平台 {plat}(要你自己改),话题不止一个 {many}"
        self._start(fn, "检查中…")

    def run_vertical(self):
        rows = [i for i, v in enumerate(self.videos) if (v.checks or {}).get("landscape") and self.state.get(i) != "已发"]
        if not rows:
            QMessageBox.information(self, "横屏转竖屏", "没有横屏的(先点「检查」)。")
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
                emit(i, f"转竖屏失败")
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

    def run_topic(self):
        rows = [i for i, v in enumerate(self.videos)
                if len(topic.split_topics(v.title)["tags"]) > 1 and self.state.get(i) != "已发"]
        if not rows:
            QMessageBox.information(self, "话题只留一个", "没有挂了好几个话题的。")
            return
        key = self.st.ai_key() if hasattr(self.st, "ai_key") else ""
        if not key:
            QMessageBox.warning(self, "话题只留一个", "要用 AI 挑话题,先在「设置」里填阿里百炼 Key。")
            return
        model = str(self.st.get("topic_model") or "qwen-plus")
        if QMessageBox.question(self, "话题只留一个", f"{len(rows)} 条挂了好几个话题,让 AI 各留一个最好搜的,改文件名?\n\n"
                                                     "同名的封面图跟着改。改错了可以点「撤销上次改话题」。") \
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
                v.path = moves[0][1]
                v.title = os.path.splitext(os.path.basename(v.path))[0]
                if v.checks:
                    v.checks["tags"] = topic.split_topics(v.title)["tags"]
                    v.checks["platform"] = checks.platform_hits(v.title, self.st.get("api_platform_words") or None)
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
        self.say(f"撤销改话题:改回 {ok} 个文件" + (f",{bad} 个改不回(文件不在了或原名被占)" if bad else ""))
        self.load()

    def run_publish(self):
        d = self.c_date.currentText()
        if not d:
            return
        unchecked = [v for v in self.videos if not v.checks]
        if unchecked:
            QMessageBox.information(self, "发布", "先点「检查」。")
            return
        rows = [i for i, v in enumerate(self.videos) if not checks.problems(v) and self.state.get(i) != "已发"
                and self.rec.status_of(v.path) != "已发"]
        if not rows:
            QMessageBox.information(self, "发布", "没有能发的。")
            return
        accs = {a["nick"]: a for a in apiacc.load()}
        miss = sorted({self.videos[i].account for i in rows if self.videos[i].account not in accs})
        if miss:
            QMessageBox.warning(self, "发布", "这些号还没搬账号:" + "、".join(miss))
            return
        dest = apisrc.archive_dir(self.st, d)
        held = len(self.videos) - len(rows) - sum(1 for i in range(len(self.videos)) if self.state.get(i) == "已发")
        by_acc: dict[str, list[int]] = {}
        for i in rows:
            by_acc.setdefault(self.videos[i].account, []).append(i)
        par0 = max(1, int(self.st.get("api_threads") or 1))
        how = "一条一条发" if par0 == 1 else f"{par0} 个号一起发"
        msg = (f"用接口发 {len(rows)} 条({len(by_acc)} 个号)" + (f",有问题的 {held} 条不发" if held else "") +
               f"。\n\n标题、简介 = 文件名;分类按号;声明「非 AI 生成」;封面平台自己截。\n"
               f"{how},每条之间歇 {self.st.get('api_interval', 5)} 秒。\n发成了挪到:\n{dest}\n\n发吗?")
        if QMessageBox.question(self, "发布", msg) != QMessageBox.StandardButton.Yes:
            return
        vs = self.videos
        par = max(1, int(self.st.get("api_threads") or 1))
        gap = max(0.0, float(self.st.get("api_interval", 5) or 0))
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
                    v.path = apisrc.move_published(v.path, dest)
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
