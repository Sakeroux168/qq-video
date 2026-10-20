"""「每日汇总」页:每天规定发多少 / 实际发了多少(按发出去的时间算),一键复制贴进企业微信表「彭超」页。

用户 2026-10-16:「这是每个账号每天必须要达到的量 / 图二是我每天都要记录的」「没有我就要去找对应的那个人」。
企业微信文档的接口要公司管理员建自建应用才能用 → 先「复制 → 粘贴」,以后有了权限再改成自动写。
"""
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QDateEdit, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

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
        top.addWidget(self.d)
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
        self.t.setHorizontalHeaderLabels(["品类", "号", "规定条数", "这天发了 / 规定", "还差"])
        v.addWidget(self.t, 1)
        foot = QLabel("说明:只数用这个软件发出去的(旧软件发的、自己在后台手动发的不算)。")
        foot.setObjectName("muted")
        foot.setWordWrap(True)
        v.addWidget(foot)
        self.refresh()

    def day(self) -> str:
        return self.d.date().toString("yyyy-MM-dd")

    def _today(self):
        n = bj_now()
        self.d.setDate(QDate(n.year, n.month, n.day))
        self.refresh()

    def refresh(self):
        s = plan.summary(self.rec, self.st, self.day())
        self._s = s
        for lab, q, a in s["rows"]:
            key = lab.replace("总发布量", "")
            self.cards.set(**{key: (f"{a} / {q}", "good" if a >= q else ""),
                              f"{key}_sub": "够了 √" if a >= q else f"还差 {q - a} 条"})
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
        accs = s["accounts"]
        self.t.setRowCount(len(accs))
        from gui.theme import cur
        red, green = QBrush(QColor(cur()["rows"]["red"])), QBrush(QColor(cur()["rows"]["green"]))
        for i, (cat, n, q, a) in enumerate(accs):
            diff = "" if not q else ("够了 √" if a >= q else f"还差 {q - a}")
            for c, txt in enumerate([cat, n, str(q) if q else "—", str(a), diff]):
                it = QTableWidgetItem(txt)
                if c >= 2:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if q:
                    it.setBackground(green if a >= q else red)
                self.t.setItem(i, c, it)

    def copy_day(self):
        QApplication.clipboard().setText(plan.as_tsv(self._s))
        self.b_copy.setText("复制好了 → 去企业微信表 Ctrl+V")

    def copy_short(self):
        short = plan.short_list(self._s)
        txt = (f"{plan.short_day(self.day())} 企鹅号还没发够的号:\n" + "\n".join(f"{n}:规定 {q},发了 {a},还差 {q - a}" for n, q, a in short)
               if short else f"{plan.short_day(self.day())} 企鹅号有规定的号都发够了")
        QApplication.clipboard().setText(txt)
