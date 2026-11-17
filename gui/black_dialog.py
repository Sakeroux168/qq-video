"""「查黑封面 / 模糊封面」窗口(用户 2026-11-06 查黑封面;2026-11-17 加查模糊封面 + 自动截封面 + 双击去罐头搜)。只读,不发不删。"""
import os

from PySide6.QtCore import QDate, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QDateEdit, QDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout)

from qe import blackcover, config


class BlackWorker(QThread):
    """后台查:一次几个号一起读。查完 items = 黑/模糊,errs = 没查成的号,bad = 读不出来的封面几张,exported = 截好的封面数。"""
    step = Signal(str)

    def __init__(self, day: str, parent=None, accounts=None, day2: str = "", st=None):
        super().__init__(parent)
        self.day, self.day2 = day, day2 or day
        self.accounts = accounts if accounts is not None else blackcover.accounts()
        self.st = st
        self.items: list[dict] = []
        self.errs: list[str] = []
        self.bad = 0
        self.exported = 0
        self.stop = False

    def run(self):
        import concurrent.futures as cf

        def one(a):
            return blackcover.scan_one(a, self.day, self.day2, stopped=lambda: self.stop)
        n = 0
        with cf.ThreadPoolExecutor(6) as ex:
            futs = {ex.submit(one, a): a for a in self.accounts}
            for f in cf.as_completed(futs):
                n += 1
                self.step.emit(f"查了 {n} / {len(futs)} 个号…")
                try:
                    black, bad = f.result()
                    self.items += black
                    self.bad += bad
                except Exception as e:
                    self.errs.append(f"{futs[f].get('nick')}:{type(e).__name__}")
        self.items.sort(key=lambda x: (x["nick"], x["time"]))
        if not self.stop and self.items:
            st = self.st if self.st is not None else config.Settings()
            self.exported = blackcover.export_covers(
                self.items, st, stopped=lambda: self.stop, step=self.step.emit)


class CoverExportWorker(QThread):
    """给已经查出来的清单补截清晰封面(比如从今天卡片缓存点进来,还没截到文件夹里)。"""
    step = Signal(str)

    def __init__(self, items: list[dict], st, parent=None):
        super().__init__(parent)
        self.items = items
        self.st = st
        self.stop = False
        self.exported = 0

    def run(self):
        self.exported = blackcover.export_covers(self.items, self.st, stopped=lambda: self.stop, step=self.step.emit)


class CzgtOpenWorker(QThread):
    """在后台线程里切创作罐头账号、筛日期并搜标题,不卡住界面。"""

    def __init__(self, nick: str, title: str, day: str = "", parent=None):
        super().__init__(parent)
        self.nick = nick
        self.title = title
        self.day = day
        self.msg = ""
        self.err = ""

    def run(self):
        try:
            self.msg = blackcover.open_in_czgt(self.nick, self.title, day=self.day)
        except Exception as e:
            self.err = str(e)


class BlackDialog(QDialog):
    def __init__(self, day: str, parent=None, items: list[dict] | None = None, on_scan=None, st=None):
        """day = 「2026-11-06」;items 给了就先摆着不查(自动查过的);on_scan(day, items):查完告诉主窗口(卡片跟着变)。"""
        super().__init__(parent)
        self.on_scan = on_scan
        self.st = st if st is not None else (getattr(parent, "st", None) or config.Settings())
        self.w: BlackWorker | None = None
        self._cov_w: CoverExportWorker | None = None
        self._nav_w: CzgtOpenWorker | None = None
        self.setWindowTitle("黑封面 / 模糊封面")
        self.resize(960, 560)
        v = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("查哪天:"))
        self.d = QDateEdit()
        self.d.setCalendarPopup(True)
        self.d.setDisplayFormat("M.d")
        y, m, dd = (int(x) for x in day.split("-"))
        self.d.setDate(QDate(y, m, dd))
        top.addWidget(self.d)
        self.b_scan = QPushButton("查")
        self.b_scan.clicked.connect(self.start)
        top.addWidget(self.b_scan)
        top.addStretch(1)
        v.addLayout(top)
        self.lab = QLabel("只是去企鹅号读一下封面,不发、不删。纯黑、只有很小的字幕算黑封面;画面主体糊成一团算模糊封面。双击某一行会自动在创作罐头里搜出这条视频,你点修改就能换封面。")
        self.lab.setObjectName("muted")
        self.lab.setWordWrap(True)
        v.addWidget(self.lab)
        self.t = QTableWidget(0, 5)
        self.t.setHorizontalHeaderLabels(["号", "标题", "问题", "发布时间", "新封面"])
        self.t.verticalHeader().setVisible(False)
        self.t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.t.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.t.cellDoubleClicked.connect(lambda r, _c: self.open_row(r))
        v.addWidget(self.t, 1)
        h = QHBoxLayout()
        self.lab_done = QLabel("")
        h.addWidget(self.lab_done, 1)
        self.b_dir = QPushButton("打开封面文件夹")
        self.b_dir.clicked.connect(self.open_cover_dir)
        h.addWidget(self.b_dir)
        self.b_copy = QPushButton("复制这些标题")
        self.b_copy.clicked.connect(self.copy)
        h.addWidget(self.b_copy)
        b = QPushButton("关闭")
        b.clicked.connect(self.close)
        h.addWidget(b)
        v.addLayout(h)
        self.items: list[dict] = []
        if items is None:
            self.start()
        else:
            self.fill(items)
            self._maybe_export_cached()

    def _cover_dir(self) -> str:
        return str(self.st.get("bad_cover_dir") or r"E:\图片\企鹅号").strip()

    def _maybe_export_cached(self):
        if not self.items or not self.st.get("bad_cover_auto", True):
            return
        need = any(not (x.get("cover_file") and os.path.isfile(x["cover_file"])) for x in self.items)
        if not need:
            return
        self._cov_w = CoverExportWorker(self.items, self.st, self)
        self._cov_w.step.connect(self.lab_done.setText)
        self._cov_w.finished.connect(self._cov_done)
        self._cov_w.start()

    def _cov_done(self):
        self.fill(self.items)
        if self.on_scan:
            self.on_scan(self.d.date().toString("yyyy-MM-dd"), self.items)

    def fill(self, items: list[dict]):
        self.items = items
        auto_on = bool(self.st.get("bad_cover_auto", True))
        out_dir = self._cover_dir()
        self.t.setRowCount(len(items))
        n_cov = 0
        for r, x in enumerate(items):
            cf = x.get("cover_file") or ""
            has_cov = bool(cf and os.path.isfile(cf))
            if has_cov:
                n_cov += 1
            cov_txt = "已放到文件夹" if has_cov else ("自己找(设置关了)" if not auto_on else "没找到原视频")
            for c, s in enumerate((x["nick"], x["title"], x.get("kind") or "黑封面", x["time"][5:16], cov_txt)):
                it = QTableWidgetItem(s)
                if c == 4 and has_cov:
                    it.setToolTip(cf)
                self.t.setItem(r, c, it)
        if not items:
            self.lab_done.setText("没有黑封面 / 模糊封面")
        elif auto_on and out_dir:
            self.lab_done.setText(f"{blackcover.summary_text(items)};{n_cov} 张清晰封面已放到 {out_dir}(双击去罐头搜)")
        else:
            self.lab_done.setText(f"{blackcover.summary_text(items)}(双击去罐头搜)")
        self.b_copy.setEnabled(bool(items))

    def start(self):
        if self.w and self.w.isRunning():
            return
        self.b_scan.setEnabled(False)
        self.lab_done.setText("正在查…")
        d = self.d.date().toString("yyyy-MM-dd")
        self.w = BlackWorker(d, self, st=self.st)
        self.w.step.connect(self.lab_done.setText)
        self.w.finished.connect(lambda w=self.w, d=d: self._done(w, d))
        self.w.start()

    def _done(self, w: BlackWorker, day: str):
        self.b_scan.setEnabled(True)
        self.fill(w.items)
        more = [f"{len(w.errs)} 个号没查成({w.errs[0]})"] if w.errs else []
        more += [f"{w.bad} 张封面读不出来"] if w.bad else []
        if more:
            self.lab_done.setText(self.lab_done.text() + ";" + ";".join(more))
        if self.on_scan:
            self.on_scan(day, w.items)

    def open_row(self, r: int):
        if not (0 <= r < len(self.items)):
            return
        if self._nav_w and self._nav_w.isRunning():
            return
        x = self.items[r]
        day = (x.get("time") or "")[:10]
        if len(day) != 10 or day[4] != "-":
            day = self.d.date().toString("yyyy-MM-dd")
        self.lab_done.setText(f"正在打开创作罐头并搜索「{x['title'][:20]}」…")
        w = CzgtOpenWorker(x.get("nick") or "", x.get("title") or "", day=day, parent=self)
        w.finished.connect(lambda w=w: self._nav_done(w))
        self._nav_w = w
        w.start()

    def _nav_done(self, w: CzgtOpenWorker):
        if w.err:
            self.lab_done.setText(f"去罐头搜索没成:{w.err}")
            QMessageBox.warning(self, "去创作罐头搜视频", w.err)
        else:
            self.lab_done.setText(f"{w.msg}(点视频旁边的「修改」就能换封面)")

    def open_cover_dir(self):
        d = self._cover_dir()
        if not d:
            return
        os.makedirs(d, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(d))

    def copy(self):
        QGuiApplication.clipboard().setText("\n".join(f"{x['nick']}\t{x['title']}" for x in self.items))
        self.lab_done.setText(f"复制了 {len(self.items)} 条")

    def _stop_workers(self):
        for w in (self.w, self._cov_w):
            if w and w.isRunning():
                w.stop = True
                w.wait(3000)
        if self._nav_w and self._nav_w.isRunning():
            self._nav_w.wait(3000)

    def closeEvent(self, e):
        self._stop_workers()
        super().closeEvent(e)

    def done(self, r: int):
        self._stop_workers()
        super().done(r)
