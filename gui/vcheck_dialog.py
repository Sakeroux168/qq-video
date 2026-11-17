"""罐头页右键「去企鹅号查选中的 N 条」(用户 2026-11-09:「再来一个功能去企鹅号查 选中的视频有没有发上去」)。

用这个号「只查」的钥匙(或者 16 个号的钥匙)读企鹅号后台列表,按标题对,一条一行说结果。只读,不发、不删。
对不上的能改(默认不勾,人自己勾):
- 软件记已发、企鹅号上没有 / 打回 / 删了 →「改回还没发」(Records.undo_sent,和右键「不算已发」一样)
- 软件记没发、企鹅号上其实有 →「标成已发」(发布时间用企鹅号上的)
"""
from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout)

from qe import apiacc, verify

NO_KEY = "这个号还没取钥匙,查不了(左下角「设置」→「登录取钥匙…」选这个号,扫一次码)"


class VCheckWorker(QThread):
    one = Signal(str, list)        # 号, [结果](verify.check_videos 的;查不了的每条 kind="err")
    step = Signal(str)

    def __init__(self, groups: dict, today: str, parent=None):
        super().__init__(parent)
        self.groups, self.today = groups, today
        self.stop = False

    def run(self):
        from qe import omapi
        keys = {a.get("nick"): a for a in apiacc.check_accounts()}
        for k, (nick, items) in enumerate(self.groups.items()):
            if self.stop:
                return
            self.step.emit(f"正在查「{nick}」({k + 1} / {len(self.groups)},要翻几页后台列表,稍等)…")
            a = keys.get(nick)
            if a is None:
                self.one.emit(nick, [dict(it, kind="err", text=NO_KEY, fix="") for it in items])
                continue
            try:
                cl = omapi.Client(a["client_id"], apiacc.unseal(a["secret"]))
                res = verify.check_videos(cl, items, self.today, stopped=lambda: self.stop, nick=nick)
            except Exception as e:
                why = omapi.redact(str(e))[:80] if hasattr(omapi, "redact") else str(e)[:80]
                res = [dict(it, kind="err", text=f"查不了:{why}", fix="") for it in items]
            if not self.stop:
                self.one.emit(nick, res)


class VCheckDialog(QDialog):
    def __init__(self, rec, vids: list, items: list[dict], today: str, parent=None):
        """vids[i] 对应 items[i](items 里 i 是下标)。changed:改过记录,关了以后罐头页要刷新。"""
        super().__init__(parent)
        self.rec, self.vids, self.changed = rec, vids, False
        self.setWindowTitle(f"去企鹅号查 · {'、'.join(dict.fromkeys(v.account for v in vids))} · 选中的 {len(vids)} 条")
        self.resize(980, 560)
        v = QVBoxLayout(self)
        self.head = QLabel(f"正在去企鹅号查 {len(vids)} 条…")
        self.head.setObjectName("heroBig")
        self.head.setStyleSheet("font-size:18px;")
        self.head.setWordWrap(True)
        v.addWidget(self.head)
        sub = QLabel("只是读一下企鹅号后台,不发、不删。按标题对;对不上的能改(要你自己勾上)。")
        sub.setObjectName("muted")
        sub.setWordWrap(True)
        v.addWidget(sub)
        self.t = QTableWidget(len(vids), 4)
        self.t.setHorizontalHeaderLabels(["改", "标题", "软件里", "企鹅号上"])
        self.t.verticalHeader().setVisible(False)
        self.t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        hh = self.t.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.t.setColumnWidth(0, 150)
        self.t.setColumnWidth(2, 80)
        self.t.setWordWrap(True)
        self.t.setTextElideMode(Qt.TextElideMode.ElideNone)   # 长标题折行显示全,不在末尾变「…」
        hh.sectionResized.connect(lambda *_: self._fit())   # 窗口宽度定了 / 拉宽以后,折行的标题不被截掉
        self.rows = {}                                   # 下标 -> 结果
        for k, it in enumerate(items):
            self.rows[it["i"]] = dict(it, kind="", text="查中…", fix="")
            self._row(k)
        v.addWidget(self.t, 1)
        h = QHBoxLayout()
        self.lab = QLabel("")
        self.lab.setWordWrap(True)
        h.addWidget(self.lab, 1)
        self.b_unsend = QPushButton("改回还没发")
        self.b_unsend.setToolTip("勾上的「软件记已发、企鹅号上没有」的:软件里改回还没发(之后还会摆),不动文件")
        self.b_unsend.clicked.connect(lambda: self.apply("unsend"))
        self.b_mark = QPushButton("标成已发")
        self.b_mark.setToolTip("勾上的「软件记没发、企鹅号上其实有」的:记成已发,发布时间用企鹅号上的")
        self.b_mark.clicked.connect(lambda: self.apply("mark"))
        for b in (self.b_unsend, self.b_mark):
            b.setEnabled(False)
            h.addWidget(b)
        b = QPushButton("关闭")
        b.clicked.connect(self.close)
        h.addWidget(b)
        v.addLayout(h)
        self.t.itemChanged.connect(self._buttons)
        groups = {}
        for it in items:
            groups.setdefault(it["account"], []).append(it)
        self.w = VCheckWorker(groups, today, self)
        self.w.step.connect(self.lab.setText)
        self.w.one.connect(self._one)
        self.w.finished.connect(self._end)
        self.w.start()

    def _order(self) -> list[int]:
        return list(self.rows)

    def _row(self, k: int):
        from gui.theme import cur
        from PySide6.QtGui import QBrush, QColor
        i = self._order()[k]
        r = self.rows[i]
        self.t.blockSignals(True)
        fix = r.get("fix") or ""
        c0 = QTableWidgetItem({"unsend": "改回还没发", "mark": "标成已发"}.get(fix, ""))
        if fix and not r.get("done"):
            c0.setFlags(c0.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            c0.setCheckState(Qt.CheckState.Unchecked)
        elif r.get("done"):
            c0.setText("✓ " + r["done"])
        c0.setData(Qt.ItemDataRole.UserRole, i)
        soft = "已发" if r.get("sent_day") else "还没发"
        if r.get("done"):
            soft = {"unsend": "还没发", "mark": "已发"}[fix]
        cells = [c0, QTableWidgetItem(r["title"]), QTableWidgetItem(soft), QTableWidgetItem(r["text"])]
        cells[3].setToolTip(r["text"])
        cells[1].setToolTip(f"{r['account']} · {r['title']}")
        color = {"on": "", "wait": "", "bad": "red", "none": "yellow", "err": "yellow"}.get(r.get("kind") or "", "")
        if fix and not r.get("done"):
            color = "red" if fix == "unsend" else "yellow"
        for c, it in enumerate(cells):
            if color:
                it.setBackground(QBrush(QColor(cur()["rows"][color])))
            self.t.setItem(k, c, it)
        self.t.blockSignals(False)
        self._fit()

    def _fit(self):
        """按内容定行高,再多留一点(主题给格子加了内边距,Qt 算行高时没算进去,三行的标题会被截掉)。"""
        self.t.resizeRowsToContents()
        for k in range(self.t.rowCount()):
            self.t.setRowHeight(k, self.t.rowHeight(k) + 22)

    def showEvent(self, e):
        super().showEvent(e)
        self._fit()

    def _one(self, nick: str, res: list):
        if self.sender() is not self.w:
            return
        for r in res:
            self.rows[r["i"]] = r
            self._row(self._order().index(r["i"]))

    def _end(self):
        rs = list(self.rows.values())
        on = sum(1 for r in rs if r.get("kind") in ("on", "wait"))
        un = sum(1 for r in rs if r.get("fix") == "unsend")
        mk = sum(1 for r in rs if r.get("fix") == "mark")
        err = sum(1 for r in rs if r.get("kind") == "err")
        if not (un or mk or err):
            self.head.setText(f"对上了:{on} 条企鹅号上有" + (f",{len(rs) - on} 条还没发、企鹅号上也没有" if len(rs) > on else "") + " ✓")
        else:
            parts = [f"{on} 条企鹅号上有"]
            if un:
                parts.append(f"{un} 条软件记已发、企鹅号上没有 / 没发上")
            if mk:
                parts.append(f"{mk} 条软件记没发、企鹅号上其实有")
            if err:
                parts.append(f"{err} 条查不了")
            self.head.setText("查完了:" + ",".join(parts))
        self.lab.setText("对不上的要改就勾上,再点右边的按钮;不确定的先去企鹅号后台看一眼。" if un or mk else "")
        self._buttons()

    def _checked(self, fix: str) -> list[int]:
        out = []
        for k in range(self.t.rowCount()):
            it = self.t.item(k, 0)
            if it is None or it.checkState() != Qt.CheckState.Checked:
                continue
            i = it.data(Qt.ItemDataRole.UserRole)
            r = self.rows.get(i) or {}
            if r.get("fix") == fix and not r.get("done"):
                out.append(i)
        return out

    def _buttons(self, *_):
        if self.w.isRunning():
            return
        for fix, b, name in (("unsend", self.b_unsend, "改回还没发"), ("mark", self.b_mark, "标成已发")):
            n = len(self._checked(fix))
            b.setText(f"{name}(勾上的 {n} 条)" if n else name)
            b.setEnabled(bool(n))

    def apply(self, fix: str):
        import gui.api_tab as A
        ids = self._checked(fix)
        if not ids:
            return
        what = "改回还没发" if fix == "unsend" else "标成已发"
        why = ("软件里改回还没发:之后还会摆它们,每天的已发数跟着减。不动文件、不碰企鹅号。" if fix == "unsend" else
               "记成已发,发布时间用企鹅号上的:之后不会再摆它们。")
        if not A.ask(self, what, f"这 {len(ids)} 条{what}?\n\n" + "\n".join(f"· {self.rows[i]['title'][:30]}" for i in ids[:8]) +
                     ("\n…" if len(ids) > 8 else "") + "\n\n" + why, what, "先不", default_no=True):
            return
        for i in ids:
            v = self.vids[i]
            r = self.rows[i]
            if fix == "unsend":
                self.rec.undo_sent(v.path, "(去企鹅号查了没有,人改回没发)")
            elif self.rec.status_of(v.path) != "已发":
                self.rec.manual_published(v, "去企鹅号查到发出去了,人标成已发", at=r.get("at") or "")
            r["done"] = what
            self._row(self._order().index(i))
        self.changed = True
        self.lab.setText(f"{what}:{len(ids)} 条")
        self._buttons()

    def _stop(self):
        if self.w.isRunning():
            self.w.stop = True
            self.w.wait(3000)

    def closeEvent(self, e):
        self._stop()
        super().closeEvent(e)

    def reject(self):
        self._stop()
        super().reject()
