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
from gui.widgets import StatCards


class DailyTab(QWidget):
    def __init__(self, st, rec, parent=None):
        super().__init__(parent)
        self.st, self.rec = st, rec
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 16, 20, 12)
        v.setSpacing(10)
        title = QLabel("每日汇总 · 每个号今天发够了没有")
        title.setObjectName("pageTitle")
        v.addWidget(title)

        top = QHBoxLayout()
        top.addWidget(QLabel("哪天:"))
        self.d = QDateEdit()
        self.d.setCalendarPopup(True)
        self.d.setDisplayFormat("yyyy-MM-dd")
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
        tip.setStyleSheet("color:#8a8b91")
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

        self.cards = StatCards([("游戏", "游戏"), ("教育", "教育"), ("动漫", "动漫"), ("总", "总发布量")])
        v.addWidget(self.cards)
        self.hint = QLabel("")
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        v.addWidget(self.hint)

        self.t = QTableWidget(0, 5)
        self.t.setHorizontalHeaderLabels(["品类", "号", "规定条数", "这天发了", "还差"])
        self.t.verticalHeader().setVisible(False)
        self.t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        hh = self.t.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for i, wd in ((0, 90), (2, 90), (3, 90), (4, 90)):
            self.t.setColumnWidth(i, wd)
        v.addWidget(self.t, 1)
        foot = QLabel("说明:只数用这个软件发出去的(旧软件发的、自己在后台手动发的不算);教育每个号各多少还没定,只看两个号加起来够不够 106。")
        foot.setStyleSheet("color:#8a8b91")
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
            self.cards.set(**{key: (f"{a} / {q}", "good" if a >= q else ("warn" if a else "")),
                              f"{key}_sub": "够了 √" if a >= q else f"还差 {q - a} 条"})
        tq, ta = s["total"]
        self.cards.set(总=(f"{ta} / {tq}", "good" if ta >= tq else ("warn" if ta else "")),
                       总_sub="都够了 √" if ta >= tq else f"还差 {tq - ta} 条")
        short = plan.short_list(s)
        if short:
            names = "、".join(f"{n} 差 {q - a}" for n, q, a in short[:6]) + (f" … 共 {len(short)} 个号" if len(short) > 6 else "")
            self.hint.setText(f"还没发够的号:{names}")
            self.hint.show()
        else:
            self.hint.setText("有规定的号都发够了 √")
            self.hint.show()
        accs = s["accounts"]
        self.t.setRowCount(len(accs))
        red, green = QBrush(QColor("#ffe7eb")), QBrush(QColor("#e6f7ec"))
        for i, (cat, n, q, a) in enumerate(accs):
            diff = "" if not q else ("√" if a >= q else str(q - a))
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
