"""「去企鹅号核对」窗口(每日汇总页的按钮;用户 2026-10-23:我自己点就行,查出来哪条没发上,拎回来重发)。

每个 16 个号的号查一遍(后台,只读):软件记的已发 / 企鹅号上有的 / 审核中 / 没发上 / 软件没记的。
「没发上」的打勾,点「拎回来重发」:视频挪回原来的文件夹、记录改成没发成,去「16 个号」点刷新、发布就行。
"""
from PySide6.QtCore import QDate, QThread, Qt, Signal
from PySide6.QtWidgets import (QDateEdit, QDialog, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QListWidget, QListWidgetItem,
                               QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

from qe import apiacc, verify


class VerifyWorker(QThread):
    one = Signal(dict)          # 一个号查完:verify.check_account 的结果,或者 {nick, error}
    step = Signal(str)

    def __init__(self, rec, day: str, accounts: list[dict], parent=None):
        super().__init__(parent)
        self.rec, self.day, self.accounts = rec, day, accounts
        self.stop = False

    def run(self):
        from qe import omapi
        for k, a in enumerate(self.accounts):
            if self.stop:
                return
            nick = a.get("nick") or ""
            self.step.emit(f"正在查「{nick}」({k + 1} / {len(self.accounts)})…")
            try:
                cl = omapi.Client(a["client_id"], apiacc.unseal(a["secret"]))
                self.one.emit(verify.check_account(cl, self.rec, nick, self.day))
            except Exception as e:
                self.one.emit({"nick": nick, "error": omapi.redact(str(e))[:80] if hasattr(omapi, "redact") else str(e)[:80]})


class VerifyDialog(QDialog):
    def __init__(self, rec, day: str, parent=None, nicks: list[str] | None = None, st=None):
        """nicks = 只查这几个号(用户 2026-10-23「再加一个指定某某号核对」);不给 = 16 个号全查。st = 设置(算应发几条)。"""
        super().__init__(parent)
        self.rec, self.day, self.st, self.nicks = rec, day, st, nicks
        self.resize(860, 640)
        v = QVBoxLayout(self)
        # 查哪天(用户 2026-10-25:「增加一个可查指定日期的核查数据」)
        top = QHBoxLayout()
        top.addWidget(QLabel("查哪天:"))
        self.d = QDateEdit()
        self.d.setCalendarPopup(True)
        self.d.setDisplayFormat("M.d")
        y0, m0, d0 = (int(x) for x in day.split("-"))
        self.d.setDate(QDate(y0, m0, d0))
        top.addWidget(self.d)
        b = QPushButton("查")
        b.clicked.connect(lambda: self.start(self.d.date().toString("yyyy-MM-dd")))
        top.addWidget(b)
        top.addStretch(1)
        v.addLayout(top)
        self.lab = QLabel("只是去企鹅号读一下,不发、不删。教育号走创作罐头,查不了。")
        self.lab.setObjectName("muted")
        self.lab.setWordWrap(True)
        v.addWidget(self.lab)
        self.t = QTableWidget(0, 8)                       # 用户 2026-10-24:改成 应发 / 实发 / 还差,再说哪些是假发成功
        self.t.setHorizontalHeaderLabels(["号", "应发", "实发(企鹅号上)", "还差", "软件记的已发", "假发成功", "审核中", "软件没记的"])
        self.t.verticalHeader().setVisible(False)
        self.t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        v.addWidget(self.t, 2)
        v.addWidget(QLabel("假发成功:软件里记成已发、企鹅号这天的列表里没有的(打勾的拎回来重发;「看一眼再决定」的没打勾):"))
        self.miss = QListWidget()
        v.addWidget(self.miss, 2)
        self.lab_extra = QLabel("")
        self.lab_extra.setObjectName("muted")
        self.lab_extra.setWordWrap(True)
        v.addWidget(self.lab_extra)
        h = QHBoxLayout()
        self.lab_done = QLabel("")
        h.addWidget(self.lab_done, 1)
        self.b_back = QPushButton("拎回来重发")
        self.b_back.setObjectName("primary")
        self.b_back.setEnabled(False)
        self.b_back.clicked.connect(self.pull_back)
        h.addWidget(self.b_back)
        self.b_xls = QPushButton("导出表格…")
        self.b_xls.setToolTip("导出成企业微信表那个样子:品类 / 账号名称 / 规定视频条数 / 这天实发(16 个号用企鹅号上的,教育号按软件记录)")
        self.b_xls.setEnabled(False)
        self.b_xls.clicked.connect(self.export)
        h.addWidget(self.b_xls)
        b = QPushButton("关闭")
        b.clicked.connect(self.close)
        h.addWidget(b)
        v.addLayout(h)
        self.w = None
        self.start(day)

    def start(self, day: str):
        """查这一天(换了日期重新查)。"""
        if self.w is not None and self.w.isRunning():
            self.w.stop = True
            self.w.wait(5000)
        self.day = day
        self.setWindowTitle(f"去企鹅号核对 · {day}" + (f" · {'、'.join(self.nicks)}" if self.nicks else ""))
        self.t.setRowCount(0)
        self.miss.clear()
        self.lab_extra.setText("")
        self.b_back.setEnabled(False)
        self.b_xls.setEnabled(False)
        self.rows, self.extra, self.results = [], [], {}
        accs = [a for a in apiacc.load() if a.get("enabled", True) and a.get("client_id")]
        if self.nicks:
            accs = [a for a in accs if a.get("nick") in self.nicks]
        if not accs:
            self.lab_done.setText("这个号不是 16 个号里的(教育号走创作罐头,查不了)" if self.nicks else "还没有 16 个号的账号(去设置里搬账号)")
            self.w = None
            return
        self.w = VerifyWorker(self.rec, day, accs, self)
        self.w.step.connect(self.lab_done.setText)
        self.w.one.connect(self._one)
        self.w.finished.connect(self._end)
        self.w.start()

    def export(self):
        """导出成企业微信表那个样子(用户 2026-10-25 截图)。"""
        import os
        from qe import verify
        if self.st is None:
            return
        y, m, d = (int(x) for x in self.day.split("-"))
        start = os.path.join(os.path.expanduser("~"), "Desktop", f"企鹅号发布数据_{m}月{d}日.xlsx")
        p, _ = QFileDialog.getSaveFileName(self, "导出表格", start, "Excel 表格 (*.xlsx)")
        if not p:
            return
        try:
            verify.export_xlsx(p, self.st, self.rec, self.day, self.results)
        except OSError as e:
            QMessageBox.warning(self, "导出表格", f"存不了(文件是不是正开着?):{e.strerror or e}")
            return
        self.lab_done.setText(f"导出好了:{p}")

    def _one(self, r: dict):
        self.results[r["nick"]] = r
        k = self.t.rowCount()
        self.t.insertRow(k)
        q = 0
        if self.st is not None:
            from qe import plan
            q = plan.quota_on(self.st, r["nick"], self.day)
        if r.get("error"):
            vals = [r["nick"], str(q or ""), "", "", "", f"查不了:{r['error']}", "", ""]
        else:
            live = r.get("live", r["ok"] + r["review"])
            diff = (f"多发 {live - q}" if live > q else str(q - live) if q > live else "✓") if q else ""
            vals = [r["nick"], str(q) if q else "—", str(live), diff, str(r["ours"]),
                    str(len(r["missing"])) if r["missing"] else "✓", str(r["review"]) if r["review"] else "",
                    str(len(r["extra"])) if r["extra"] else ""]
        for c, t in enumerate(vals):
            it = QTableWidgetItem(t)
            if c:
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.t.setItem(k, c, it)
        bad = r.get("missing") or (not r.get("error") and q and r.get("live", 0) < q)
        if bad or r.get("error"):
            from gui.theme import cur
            from PySide6.QtGui import QBrush, QColor
            for c in range(8):
                self.t.item(k, c).setBackground(QBrush(QColor(cur()["rows"]["red" if r.get("missing") or r.get("error") else "yellow"])))
        for m in r.get("missing") or []:
            it = QListWidgetItem(f"{m['account']} · {m['title']} —— {m['why']}")
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if m.get("sure", True) else Qt.CheckState.Unchecked)
            it.setData(Qt.ItemDataRole.UserRole, len(self.rows))
            self.rows.append(m)
            self.miss.addItem(it)
        self.extra += [(r["nick"], e) for e in r.get("extra") or []]

    def _end(self):
        n = len(self.rows)
        sure = sum(1 for m in self.rows if m.get("sure", True))
        self.lab_done.setText((f"查完了:{n} 条假发成功(软件记成已发、企鹅号这天的列表里没有)" + (f",其中 {n - sure} 条要你看一眼" if n > sure else ""))
                              if n else "查完了:软件记的已发,企鹅号上都有 ✓")
        self.b_back.setText("拎回来重发(打勾的)" if n else "拎回来重发")
        self.b_back.setEnabled(bool(n))
        self.b_xls.setEnabled(self.st is not None)
        if self.extra:
            self.lab_extra.setText(f"企鹅号上这天还有 {len(self.extra)} 条软件没记的(手动发的 / 别的软件发的,不用管):" +
                                   ";".join(f"{n} · {e['title'][:20]}" for n, e in self.extra[:8]) + ("…" if len(self.extra) > 8 else ""))

    def pull_back(self):
        """打勾的:视频挪回原来的文件夹、记录改成没发成。"""
        done, bad = 0, []
        for k in range(self.miss.count()):
            it = self.miss.item(k)
            if it.checkState() != Qt.CheckState.Checked or it.data(Qt.ItemDataRole.UserRole + 1):
                continue
            row = self.rows[it.data(Qt.ItemDataRole.UserRole)]
            why = verify.pull_back(self.rec, row)
            if why:
                bad.append(f"{row['title'][:20]}:{why}")
                it.setText(it.text() + f"  ✗ {why}")
            else:
                done += 1
                it.setText("✓ 拎回来了 · " + it.text())
                it.setData(Qt.ItemDataRole.UserRole + 1, True)
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
        self.lab_done.setText(f"拎回来 {done} 条(挪回原来的文件夹、改成没发成)→ 去「16 个号」点刷新、发布" +
                              (f";{len(bad)} 条没拎回来" if bad else ""))
        self.b_back.setEnabled(False)
        w = self.parent()
        while w is not None and not hasattr(w, "api_tab"):
            w = w.parent()
        if w is not None and done:
            try:
                w.api_tab.load()
            except Exception:
                pass

    def closeEvent(self, e):
        if self.w is not None and self.w.isRunning():
            self.w.stop = True
            self.w.wait(3000)
        super().closeEvent(e)
