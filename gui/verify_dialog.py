"""「去企鹅号核对」窗口(每日汇总页的按钮;用户 2026-10-23:我自己点就行,查出来哪条没发上,拎回来重发)。

每个 16 个号的号查一遍(后台,只读):软件记的已发 / 企鹅号上有的 / 审核中 / 没发上 / 软件没记的。
「没发上」的打勾,点「拎回来重发」:视频挪回原来的文件夹、记录改成没发成,去「16 个号」点刷新、发布就行。
"""
from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QHeaderView, QLabel, QListWidget, QListWidgetItem, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout)

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
    def __init__(self, rec, day: str, parent=None):
        super().__init__(parent)
        self.rec, self.day = rec, day
        self.setWindowTitle(f"去企鹅号核对 · {day}")
        self.resize(820, 620)
        v = QVBoxLayout(self)
        self.lab = QLabel("只是去企鹅号读一下,不发、不删。教育号走创作罐头,查不了。")
        self.lab.setObjectName("muted")
        self.lab.setWordWrap(True)
        v.addWidget(self.lab)
        self.t = QTableWidget(0, 6)
        self.t.setHorizontalHeaderLabels(["号", "软件记的已发", "企鹅号上发布成功", "审核中", "没发上", "软件没记的"])
        self.t.verticalHeader().setVisible(False)
        self.t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        v.addWidget(self.t, 2)
        v.addWidget(QLabel("软件里记成已发、企鹅号上其实没有的(打勾的拎回来重发):"))
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
        b = QPushButton("关闭")
        b.clicked.connect(self.close)
        h.addWidget(b)
        v.addLayout(h)
        self.rows, self.extra = [], []
        accs = [a for a in apiacc.load() if a.get("enabled", True) and a.get("client_id")]
        if not accs:
            self.lab_done.setText("还没有 16 个号的账号(去设置里搬账号)")
            self.w = None
            return
        self.w = VerifyWorker(rec, day, accs, self)
        self.w.step.connect(self.lab_done.setText)
        self.w.one.connect(self._one)
        self.w.finished.connect(self._end)
        self.w.start()

    def _one(self, r: dict):
        k = self.t.rowCount()
        self.t.insertRow(k)
        if r.get("error"):
            vals = [r["nick"], "", "", "", f"查不了:{r['error']}", ""]
        else:
            vals = [r["nick"], str(r["ours"]), str(r["ok"]), str(r["review"]) if r["review"] else "",
                    str(len(r["missing"])) if r["missing"] else "✓", str(len(r["extra"])) if r["extra"] else ""]
        for c, t in enumerate(vals):
            it = QTableWidgetItem(t)
            if c:
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.t.setItem(k, c, it)
        if r.get("missing"):
            from gui.theme import cur
            from PySide6.QtGui import QBrush, QColor
            for c in range(6):
                self.t.item(k, c).setBackground(QBrush(QColor(cur()["rows"]["red"])))
        for m in r.get("missing") or []:
            it = QListWidgetItem(f"{m['account']} · {m['title']} —— {m['why']}")
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked)
            it.setData(Qt.ItemDataRole.UserRole, len(self.rows))
            self.rows.append(m)
            self.miss.addItem(it)
        self.extra += [(r["nick"], e) for e in r.get("extra") or []]

    def _end(self):
        n = len(self.rows)
        self.lab_done.setText(f"查完了:{n} 条软件记成已发、企鹅号上没有" if n else "查完了:软件记的已发,企鹅号上都有 ✓")
        self.b_back.setText(f"拎回来重发({n} 条)" if n else "拎回来重发")
        self.b_back.setEnabled(bool(n))
        if self.extra:
            self.lab_extra.setText(f"企鹅号上今天还有 {len(self.extra)} 条软件没记的(手动发的 / 别的软件发的,不用管):" +
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
