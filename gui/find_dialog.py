"""「找视频重发」窗口(用户 2026-10-25):输入标题里的几个字 → 列出发过的 → 选一条:挪回今天 / 明天重发、复制标题、
(16 个号)在企鹅号上删掉。逻辑在 qe/redo.py。"""
import os
from datetime import timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMessageBox, QPushButton, QVBoxLayout)

from qe import redo
from qe.config import bj_now


class FindDialog(QDialog):
    def __init__(self, rec, st, parent=None, after=None):
        """after = 挪回去以后叫一下(刷新教育号 / 16 个号页)。"""
        super().__init__(parent)
        self.rec, self.st, self.after = rec, st, after
        self.setWindowTitle("找视频重发")
        self.resize(820, 560)
        v = QVBoxLayout(self)
        tip = QLabel("输入标题里的几个字,找出发过的视频。选一条:挪回素材盘重发(视频和封面一起,文件夹照原样建好),"
                     "或者复制标题去企鹅号后台删;16 个号还能直接在企鹅号上删掉。")
        tip.setObjectName("muted")
        tip.setWordWrap(True)
        v.addWidget(tip)
        h = QHBoxLayout()
        self.e = QLineEdit()
        self.e.setPlaceholderText("标题里的几个字,比如:幼小衔接必备")
        self.e.returnPressed.connect(self.find)
        h.addWidget(self.e, 1)
        b = QPushButton("找")
        b.clicked.connect(self.find)
        h.addWidget(b)
        v.addLayout(h)
        self.lst = QListWidget()
        self.lst.setWordWrap(True)                          # 归档的位置很长:折行,别横着拖
        self.lst.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lst.setSpacing(3)
        self.lst.currentRowChanged.connect(lambda _r: self._sel())
        v.addWidget(self.lst, 1)
        self.lab = QLabel("")
        self.lab.setWordWrap(True)
        v.addWidget(self.lab)
        a = QHBoxLayout()
        a.addWidget(QLabel("挪回哪天:"))
        self.c_day = QComboBox()
        n = bj_now()
        for k, name in ((0, "今天"), (1, "明天")):
            t = n + timedelta(days=k)
            self.c_day.addItem(f"{name}({t.month}.{t.day})", f"{t.month}.{t.day}")
        a.addWidget(self.c_day)
        a.addStretch(1)
        self.b_copy = QPushButton("复制标题(去后台搜)")
        self.b_copy.clicked.connect(self.copy)
        a.addWidget(self.b_copy)
        self.b_del = QPushButton("在企鹅号上删掉…")
        self.b_del.setObjectName("danger")
        self.b_del.setToolTip("16 个号:软件直接在企鹅号上删掉这条(删了找不回)。教育号走罐头,删不了,去后台手动删")
        self.b_del.clicked.connect(self.delete)
        a.addWidget(self.b_del)
        self.b_back = QPushButton("挪回去重发")
        self.b_back.setObjectName("primary")
        self.b_back.clicked.connect(self.pull_back)
        a.addWidget(self.b_back)
        v.addLayout(a)
        self.rows = []
        self._sel()

    def find(self):
        self.rows = redo.search(self.rec, self.e.text())
        self.lst.clear()
        for r in self.rows:
            where = redo.locate(self.st, r)
            st = {"已发": "已发", "摆好": "摆好没确认", "结果不明": "不确定发没发", "发布中": "不确定发没发", "没发成": "没发成"}.get(r["status"], r["status"])
            when = str(r.get("published_at") or r.get("prepared_at") or "")[5:16]
            it = QListWidgetItem(f"{r['title']}\n    {r['account']} · {r.get('date') or ''} 文件夹 · {st} {when}\n    "
                                 + ("现在在:" + os.path.dirname(where) if where else "视频文件找不到了"))
            it.setToolTip(where or "")
            if not where:
                it.setForeground(Qt.GlobalColor.gray)
            self.lst.addItem(it)
        self.lab.setText(f"找到 {len(self.rows)} 条" if self.rows else ("没找到,换几个字试试" if self.e.text().strip() else ""))
        if self.rows:
            self.lst.setCurrentRow(0)
        self._sel()

    def _cur(self):
        k = self.lst.currentRow()
        return self.rows[k] if 0 <= k < len(self.rows) else None

    def _sel(self):
        r = self._cur()
        self.b_copy.setEnabled(bool(r))
        self.b_back.setEnabled(bool(r) and bool(redo.locate(self.st, r)))
        self.b_del.setEnabled(bool(r) and redo.is_api(r) and r["status"] == "已发")
        self.b_del.setVisible(not r or redo.is_api(r))

    def copy(self):
        r = self._cur()
        if r:
            QApplication.clipboard().setText(r["title"])
            self.lab.setText("标题复制好了:去企鹅号后台「内容管理」搜一下")

    def pull_back(self):
        r = self._cur()
        if not r:
            return
        md = self.c_day.currentData()
        dst = redo.target_dir(self.st, r, md)
        from gui.api_tab import ask
        if not ask(self, "挪回去重发", f"「{r['title'][:40]}」\n\n视频和封面挪到:\n{dst}\n\n记录改成没发,之后在"
                   + ("「16 个号」" if redo.is_api(r) else "「教育号」") + f"页选 {md} 就能再发(不会自己发)。\n"
                   "企鹅号上原来那条要删的话,记得去后台删(或者先点「在企鹅号上删掉」)。", "挪回去", "先不"):
            return
        new, why = redo.pull_back(self.st, self.rec, r, md)
        if why:
            QMessageBox.warning(self, "挪回去重发", why)
            return
        from qe import plan
        room = plan.room_for_redo(self.st, r, plan.md_to_day(md))     # 补发不占那天的规定条数(用户 2026-10-26)
        self.lab.setText(f"挪回去了:{new}" + (f"\n「{r['account']}」{md} 多加了 1 条(补发的这条不占那天的规定条数)" if room else ""))
        if self.after:
            try:
                self.after()
            except Exception:
                pass
        self.find()

    def delete(self):
        r = self._cur()
        if not r or not redo.is_api(r):
            return
        from gui.api_tab import ask
        if not ask(self, "在企鹅号上删掉", f"「{r['title'][:40]}」({r['account']})\n\n在企鹅号上删掉这条?删了找不回来。",
                   "删掉", "先不", default_no=True, danger=True):
            return
        why = redo.delete_on_platform(r)
        if why:
            QMessageBox.warning(self, "在企鹅号上删掉", why)
            return
        self.rec.conn.execute("UPDATE posts SET note=note || ? WHERE id=?", ("(找视频重发:在企鹅号上删掉了)", r["id"]))
        self.rec.conn.commit()
        self.lab.setText("企鹅号上删掉了。要重发就再点「挪回去重发」")
