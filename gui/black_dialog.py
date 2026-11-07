"""「查黑封面」窗口(用户 2026-11-06:发完后检查黑屏封面的视频,我好去修改)。只读,不发不删;接口改不了封面,要去后台改。"""
from PySide6.QtCore import QDate, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QDateEdit, QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout)

from qe import blackcover


class BlackWorker(QThread):
    """后台查:一次几个号一起读。查完 items = 黑的,errs = 没查成的号,bad = 读不出来的封面几张。"""
    step = Signal(str)

    def __init__(self, day: str, parent=None, accounts=None, day2: str = ""):
        super().__init__(parent)
        self.day, self.day2 = day, day2 or day
        self.accounts = accounts if accounts is not None else blackcover.accounts()
        self.items: list[dict] = []
        self.errs: list[str] = []
        self.bad = 0
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


class BlackDialog(QDialog):
    def __init__(self, day: str, parent=None, items: list[dict] | None = None, on_scan=None):
        """day = 「2026-11-06」;items 给了就先摆着不查(自动查过的);on_scan(day, items):查完告诉主窗口(卡片跟着变)。"""
        super().__init__(parent)
        self.on_scan = on_scan
        self.w: BlackWorker | None = None
        self.setWindowTitle("黑封面")
        self.resize(820, 560)
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
        self.lab = QLabel("只是去企鹅号读一下封面,不发、不删。纯黑、只有很小的字幕的都算黑;软件改不了平台上的封面,要去后台改。")
        self.lab.setObjectName("muted")
        self.lab.setWordWrap(True)
        v.addWidget(self.lab)
        self.t = QTableWidget(0, 3)
        self.t.setHorizontalHeaderLabels(["号", "标题", "发布时间"])
        self.t.verticalHeader().setVisible(False)
        self.t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.t.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.t.cellDoubleClicked.connect(lambda r, _c: self.open_row(r))
        v.addWidget(self.t, 1)
        h = QHBoxLayout()
        self.lab_done = QLabel("")
        h.addWidget(self.lab_done, 1)
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

    def fill(self, items: list[dict]):
        self.items = items
        self.t.setRowCount(len(items))
        for r, x in enumerate(items):
            for c, s in enumerate((x["nick"], x["title"], x["time"][5:16])):
                self.t.setItem(r, c, QTableWidgetItem(s))
        self.lab_done.setText(f"{len(items)} 条黑封面(双击打开文章)" if items else "没有黑封面")
        self.b_copy.setEnabled(bool(items))

    def start(self):
        if self.w and self.w.isRunning():
            return
        self.b_scan.setEnabled(False)
        self.lab_done.setText("正在查…")
        d = self.d.date().toString("yyyy-MM-dd")
        self.w = BlackWorker(d, self)
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
        url = self.items[r].get("url") if 0 <= r < len(self.items) else ""
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def copy(self):
        QGuiApplication.clipboard().setText("\n".join(f"{x['nick']}\t{x['title']}" for x in self.items))
        self.lab_done.setText(f"复制了 {len(self.items)} 条")

    def closeEvent(self, e):
        if self.w and self.w.isRunning():
            self.w.stop = True
            self.w.wait(3000)
        super().closeEvent(e)
