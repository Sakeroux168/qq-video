"""「每日汇总」页:每天规定发多少 / 实际发了多少(按发出去的时间算),一键复制贴进企业微信表「彭超」页。

用户 2026-10-16:「这是每个账号每天必须要达到的量 / 图二是我每天都要记录的」「没有我就要去找对应的那个人」。
企业微信文档的接口要公司管理员建自建应用才能用 → 先「复制 → 粘贴」,以后有了权限再改成自动写。
"""
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QDateEdit, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
                               QMenu, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from qe import plan
from qe.config import bj_now
from gui.widgets import StatCards, repolish


class DailyTab(QWidget):
    def __init__(self, st, rec, parent=None):
        super().__init__(parent)
        self.st, self.rec = st, rec
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 18, 24, 14)
        v.setSpacing(10)
        title = QLabel("每日汇总")
        title.setObjectName("pageTitle")
        v.addWidget(title)
        sub = QLabel("每个号今天发够了没有")
        sub.setObjectName("heroSub")
        v.addWidget(sub)

        top = QHBoxLayout()
        top.addWidget(QLabel("哪天:"))
        self.d = QDateEdit()
        self.d.setCalendarPopup(True)
        self.d.setDisplayFormat("M.d")                  # 审查 21:和别的页一样写 10.19(原来 2026-10-19)
        self.d.setMinimumWidth(90)
        n = bj_now()
        self.d.setDate(QDate(n.year, n.month, n.day))
        self.d.dateChanged.connect(lambda _d: self.refresh())
        b = QPushButton("‹ 前一天")
        b.setObjectName("link")
        b.clicked.connect(lambda: self.d.setDate(self.d.date().addDays(-1)))
        top.addWidget(b)
        top.addWidget(self.d)
        b = QPushButton("后一天 ›")
        b.setObjectName("link")
        b.clicked.connect(lambda: self.d.setDate(self.d.date().addDays(1)))
        top.addWidget(b)
        b = QPushButton("今天")
        b.clicked.connect(self._today)
        top.addWidget(b)
        b = QPushButton("刷新")
        b.clicked.connect(self.refresh)
        top.addWidget(b)
        tip = QLabel("按「哪天发出去的」算,不看素材文件夹的日期")
        tip.setObjectName("muted")
        top.addWidget(tip, 1)
        self.b_copy = QPushButton("复制,贴到企业微信表")
        self.b_copy.setObjectName("primary")
        self.b_copy.setToolTip("复制这天的「游戏 / 教育 / 动漫 / 总发布量」四行(日期、工作内容、品类、规定、实际)。\n"
                               "到企业微信表「彭超」页,点一下要放的那一格(日期那一列),Ctrl+V 就填好了。")
        self.b_copy.clicked.connect(self.copy_day)
        top.addWidget(self.b_copy)
        b = QPushButton("复制没达标的号")
        b.setToolTip("复制还没发够的号和差几条,发给对应的人")
        b.clicked.connect(self.copy_short)
        top.addWidget(b)
        b = QPushButton("去企鹅号核对")
        b.setToolTip("16 个号:去企鹅号读一下这天每个号真发了几条,和软件记的对一对(只读,不发不删)。\n"
                     "软件记成已发、企鹅号上其实没有的,能「拎回来重发」。教育号查不了。\n只查一个号:表里右键那个号「去企鹅号核对…」")
        b.clicked.connect(lambda: self.verify())
        top.addWidget(b)
        v.addLayout(top)

        self.cards = StatCards([("游戏", "游戏"), ("教育", "教育"), ("动漫", "动漫"), ("总", "总发布量")],
                               rings={"游戏": "acc", "教育": "green", "动漫": "orange", "总": "acc"})
        v.addWidget(self.cards)
        hr = QHBoxLayout()
        self.hint = QLabel("")                          # 草图 ③:一个小标签「12 个号还没发够」,鼠标放上去看是哪些
        self.hint.setObjectName("warnPill")
        hr.addWidget(self.hint)
        self.hint_more = QLabel("鼠标放上去看是哪些")
        self.hint_more.setObjectName("muted")
        hr.addWidget(self.hint_more)
        hr.addStretch(1)
        how = QLabel("双击一个号 = 改它每天规定几条")
        how.setObjectName("muted")
        hr.addWidget(how)
        v.addLayout(hr)

        self.t = QTableWidget(0, 5)
        self.t.setHorizontalHeaderLabels(["品类", "号", "规定条数", "这天发了", "还差"])
        self.t.verticalHeader().setVisible(False)
        self.t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.t.setShowGrid(False)
        self.t.verticalHeader().setDefaultSectionSize(38)
        self.t.setAlternatingRowColors(False)
        from gui.widgets import DailyDelegate
        self.t.setItemDelegate(DailyDelegate(self.t))     # 品类分段、这天发了画进度条、还差画胶囊
        hh = self.t.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for i, wd in ((0, 90), (2, 90), (3, 300), (4, 110)):
            self.t.setColumnWidth(i, wd)
        self.t.setColumnHidden(2, True)                   # 规定条数写在进度条旁边了(列还在,复制用)
        self.t.cellDoubleClicked.connect(lambda r, _c: self.edit_quota(r))
        self.t.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.t.customContextMenuRequested.connect(self._menu)
        self.t.setToolTip("双击一个号:改它每天规定发几条")
        self.t.setHorizontalHeaderLabels(["品类", "号", "规定条数", "这天发了 / 规定", "还差"])
        v.addWidget(self.t, 1)
        foot = QLabel("说明:只数用这个软件发出去的(旧软件发的、自己在后台手动发的不算)。")
        foot.setObjectName("muted")
        foot.setWordWrap(True)
        v.addWidget(foot)
        self.refresh()

    def day(self) -> str:
        return self.d.date().toString("yyyy-MM-dd")

    def _menu(self, pos):
        r = self.t.rowAt(pos.y())
        if r < 0:
            return
        m = QMenu(self)
        nick = self.t.item(r, 1).text()
        m.addAction(f"改「{nick}」每天规定几条…", lambda: self.edit_quota(r))
        from qe import apiacc
        if nick in apiacc.nicks() or apiacc.qfind(nick):      # 教育号取了钥匙(只查不发)的也能单查
            m.addAction(f"去企鹅号核对「{nick}」这天发了几条", lambda: self.verify([nick]))
        w = self.window()
        if hasattr(w, "add_extra") and self.day() == plan.today():
            m.addAction(f"「{nick}」今天临时多发几条…(只管今天)", lambda: (w.add_extra(nick), self.refresh()))
        m.exec(self.t.viewport().mapToGlobal(pos))

    def edit_quota(self, row: int):
        """改这个号每天规定几条(用户 2026-10-22)。改完马上按新数算:还差几条、发够就停、多的挪到明天。"""
        it = self.t.item(row, 1)
        if it is None:
            return
        nick = it.text()
        q = plan.quota_of(self.st, nick)
        n, ok = QInputDialog.getInt(self, "每天规定条数", f"「{nick}」每天规定发几条?\n(改完今天马上按新数算:发够就停,多的挪到明天)",
                                    q, 0, 5000, 1)
        if not ok or n == q:
            return
        plan.set_quota(self.st, nick, n)
        self.refresh()
        w = self.window()
        for name in ("today", "api_tab"):              # 别的页也按新数算
            tab = getattr(w, name, None)
            try:
                if name == "today":
                    tab.refresh(animate_=False)
                elif tab is not None:
                    tab._update_sum()
            except Exception:
                pass

    def verify(self, nicks: list[str] | None = None):
        """去企鹅号核对:不给号 = 16 个号全查;给了 = 只查这几个(右键一个号)。"""
        from gui.verify_dialog import VerifyDialog
        VerifyDialog(self.rec, self.day(), self, nicks=nicks or None, st=self.st).exec()
        self.refresh()

    def _today(self):
        n = bj_now()
        self.d.setDate(QDate(n.year, n.month, n.day))
        self.refresh()

    def refresh(self):
        s = plan.summary(self.rec, self.st, self.day())
        self._s = s
        for lab, q, a in s["rows"]:
            key = lab.replace("总发布量", "")
            self.cards.set(**{key: (f"{a} / {q}", "warn" if q and a > q else "good" if a >= q else ""),
                              f"{key}_sub": f"多发 {a - q} 条" if q and a > q else "够了 √" if a >= q else f"还差 {q - a} 条"})
            self.cards.set_ring(key, a / q if q else 0)
        tq, ta = s["total"]
        self.cards.set(总=(f"{ta} / {tq}", "good" if ta >= tq else ""),
                       总_sub="都够了 √" if ta >= tq else f"还差 {tq - ta} 条")
        self.cards.set_ring("总", ta / tq if tq else 0)
        short = plan.short_list(s)
        if short:
            self.hint.setText(f"{len(short)} 个号还没发够")
            tip = "还没发够的号:\n" + "\n".join(f"{n}:差 {q - a}" for n, q, a in short)
            self.hint.setToolTip(tip)
            self.hint_more.setToolTip(tip)
            self.hint_more.show()
            repolish(self.hint, tone="warn")
        else:
            self.hint.setText("有规定的号都发够了 √")
            self.hint.setToolTip("")
            self.hint_more.hide()
            repolish(self.hint, tone="good")
        # 同一个品类里:没发够的排前面(差得多的在上)、再多发的、再够了的(老板试用:没发够的散在 18 行里要往下滚)
        order = {c: k for k, c in enumerate(dict.fromkeys(x[0] for x in s["accounts"]))}
        accs = sorted(s["accounts"], key=lambda x: (order[x[0]], 0 if x[2] and x[3] < x[2] else 1 if x[2] and x[3] > x[2] else 2,
                                                     -(x[2] - x[3]) if x[2] else 0))
        self.t.setRowCount(len(accs))
        from gui.theme import cur
        red, green = QBrush(QColor(cur()["rows"]["red"])), QBrush(QColor(cur()["rows"]["green"]))
        yellow = QBrush(QColor(cur()["rows"]["yellow"]))
        for i, (cat, n, q, a) in enumerate(accs):
            diff = "" if not q else (f"多发 {a - q}" if a > q else "够了 √" if a >= q else f"还差 {q - a}")
            for c, txt in enumerate([cat, n, str(q) if q else "—", str(a), diff]):
                it = QTableWidgetItem(txt)
                if c >= 2:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if q:
                    it.setBackground(yellow if a > q else green if a >= q else red)
                self.t.setItem(i, c, it)

    def copy_day(self):
        QApplication.clipboard().setText(plan.as_tsv(self._s))
        self.b_copy.setText("复制好了 → 去企业微信表 Ctrl+V")

    def copy_short(self):
        short = plan.short_list(self._s)
        txt = (f"{plan.short_day(self.day())} 企鹅号还没发够的号:\n" + "\n".join(f"{n}:规定 {q},发了 {a},还差 {q - a}" for n, q, a in short)
               if short else f"{plan.short_day(self.day())} 企鹅号有规定的号都发够了")
        QApplication.clipboard().setText(txt)
