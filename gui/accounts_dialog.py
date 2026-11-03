"""账号管理窗口(用户 2026-11-03):一张表看全部的号 —— 分组、每天规定几条、素材文件夹、有没有钥匙;
新增账号、改分组、改条数、去掉不用的号。数据怎么改见 qe/accounts.py。"""
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from qe import accounts as A
from qe import plan as P

HOW = {"游戏": "接口发", "动漫": "接口发", "教育": "罐头里发", "影视": "罐头里发"}
FILM_ROOT = r"X:\2企鹅号视频\高热剧集二创"


class AddDialog(QDialog):
    """新增一个号:号名、分组、每天几条,再按分组填文件夹。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新增账号")
        self.setMinimumWidth(520)
        v = QVBoxLayout(self)
        f = QFormLayout()
        self.e_nick = QLineEdit()
        self.e_nick.setPlaceholderText("和企鹅号上的号名一模一样,比如 光影叙集")
        self.c_cat = QComboBox()
        self.c_cat.addItems(list(A.CATS))
        self.sp = QSpinBox()
        self.sp.setRange(0, 999)
        self.sp.setValue(20)
        self.lab_folder = QLabel("")
        self.e_folder = QLineEdit()
        self.b_pick = QPushButton("选文件夹…")
        self.b_pick.clicked.connect(self._pick)
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(self.e_folder, 1)
        h.addWidget(self.b_pick)
        self.note = QLabel("")
        self.note.setObjectName("muted")
        self.note.setWordWrap(True)
        f.addRow("号名", self.e_nick)
        f.addRow("分组", self.c_cat)
        f.addRow("每天规定几条", self.sp)
        f.addRow(self.lab_folder, row)
        v.addLayout(f)
        v.addWidget(self.note)
        bb = QDialogButtonBox()
        bb.addButton("加上", QDialogButtonBox.ButtonRole.AcceptRole)
        bb.addButton("不加了", QDialogButtonBox.ButtonRole.RejectRole)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self.c_cat.currentTextChanged.connect(self._cat_changed)
        self._cat_changed(self.c_cat.currentText())

    def _cat_changed(self, cat: str):
        film = cat == "影视"
        self.b_pick.setVisible(film)
        self.e_folder.clear()
        if cat in ("游戏", "动漫"):
            self.lab_folder.setText("游戏名" if cat == "游戏" else "动漫名")
            self.e_folder.setPlaceholderText("比如 CSGO(发完按它分子文件夹)")
            self.note.setText(f"{cat}号用接口发。素材文件夹照老规矩叫「游戏名--号名」,只有一个横杠「…-号名」的也认;\n"
                              "文件夹里写的名字和号名不一样的,这里直接填完整的文件夹名。\n"
                              "加上以后要扫码取钥匙(用手机登录这个号的企鹅号),取到钥匙才能发。")
        elif cat == "教育":
            self.lab_folder.setText("文件夹缩写")
            self.e_folder.setPlaceholderText("日期文件夹下面这个号的文件夹叫什么,比如 研习社(几个用顿号隔开)")
            self.note.setText("教育号在创作罐头里发:素材放在「小学生教育\\日期\\缩写\\员工」下面。\n"
                              "罐头里要先登录好这个号。")
        else:
            self.lab_folder.setText("素材文件夹")
            self.e_folder.setPlaceholderText("这个号自己的文件夹(下面是 11.3 这种日期文件夹)")
            self.note.setText("影视号在创作罐头里发(和教育号一样摆好、调封面、人点发布)。\n"
                              "素材放在「这个号的文件夹\\日期」下面,比如 高热剧集二创\\光影叙集\\11.3。罐头里要先登录好这个号。")

    def _pick(self):
        nick = self.e_nick.text().strip()
        start = os.path.join(FILM_ROOT, nick) if nick and os.path.isdir(os.path.join(FILM_ROOT, nick)) else FILM_ROOT
        d = QFileDialog.getExistingDirectory(self, "选这个影视号的素材文件夹", start if os.path.isdir(start) else "")
        if d:
            self.e_folder.setText(os.path.normpath(d))

    def values(self) -> tuple[str, str, int, str]:
        return self.e_nick.text().strip(), self.c_cat.currentText(), self.sp.value(), self.e_folder.text().strip()


class AccountsDialog(QDialog):
    def __init__(self, st, parent=None, on_key=None):
        """on_key(parent):新加的接口号要扫码取钥匙时调(登录取钥匙)。"""
        super().__init__(parent)
        self.st, self.on_key = st, on_key
        self.changed = False
        self.setWindowTitle("账号管理")
        self.resize(820, 600)
        v = QVBoxLayout(self)
        head = QLabel("全部的号。分组、每天几条直接在表里改,改了马上存。")
        head.setObjectName("secTitle")
        v.addWidget(head)
        self.t = QTableWidget(0, 6)
        self.t.setHorizontalHeaderLabels(["号", "分组", "怎么发", "每天几条", "素材文件夹", "钥匙"])
        self.t.verticalHeader().hide()
        self.t.verticalHeader().setDefaultSectionSize(44)   # 格子里放下拉框 / 数字框,矮了字会被挤扁
        self.t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.t.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        hh = self.t.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        for col, wd in ((1, 104), (3, 96)):               # 下拉框 / 数字框那两列给够宽,「游戏」两个字别被切
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            self.t.setColumnWidth(col, wd)
        self.t.cellDoubleClicked.connect(self._dbl)
        v.addWidget(self.t, 1)
        tip = QLabel("双击号名改名字;双击素材文件夹改文件夹。")
        tip.setObjectName("muted")
        v.addWidget(tip)
        btns = QHBoxLayout()
        b_add = QPushButton("新增账号…")
        b_add.setObjectName("primary")
        b_add.clicked.connect(self.add)
        b_key = QPushButton("扫码取钥匙…")
        b_key.setToolTip("游戏 / 动漫号:用手机扫码登录这个号的企鹅号,软件读出接口钥匙存上(钥匙一栏写「没有」的要取)")
        b_key.clicked.connect(self._key)
        b_key.setVisible(on_key is not None)
        b_del = QPushButton("去掉选中的号")
        b_del.clicked.connect(self.remove)
        btns.addWidget(b_add)
        btns.addWidget(b_key)
        btns.addStretch(1)
        btns.addWidget(b_del)
        b_close = QPushButton("关闭")
        b_close.clicked.connect(self.accept)
        btns.addWidget(b_close)
        v.addLayout(btns)
        self.fill()

    def fill(self):
        rows = A.rows(self.st)
        order = {c: k for k, c in enumerate(A.CATS)}
        rows.sort(key=lambda r: (order.get(r["cat"], 9), r["nick"]))
        self.t.setRowCount(len(rows))
        for i, r in enumerate(rows):
            it = QTableWidgetItem(r["nick"])
            it.setData(Qt.ItemDataRole.UserRole, r["nick"])
            self.t.setItem(i, 0, it)
            c = QComboBox()
            c.addItems(list(A.CATS))
            c.setCurrentText(r["cat"])
            c.currentTextChanged.connect(lambda cat, n=r["nick"], old=r["cat"]: self._set_cat(n, cat, old))
            self.t.setCellWidget(i, 1, c)
            self.t.setItem(i, 2, QTableWidgetItem(HOW.get(r["cat"], "")))
            sp = QSpinBox()
            sp.setRange(0, 999)
            sp.setValue(r["quota"])
            sp.editingFinished.connect(lambda n=r["nick"], s=sp: self._set_quota(n, s.value()))
            self.t.setCellWidget(i, 3, sp)
            self.t.setItem(i, 4, QTableWidgetItem(r["folder"]))
            self.t.setItem(i, 5, QTableWidgetItem("" if r["key"] is None else "有" if r["key"] else "没有(要扫码取)"))

    def _dbl(self, row: int, col: int):
        """双击号名:改名字(用户 2026-11-03:打错了懒得删了重加);双击素材文件夹:改文件夹。"""
        from PySide6.QtWidgets import QInputDialog
        it = self.t.item(row, 0)
        nick = it.data(Qt.ItemDataRole.UserRole) if it else ""
        if not nick:
            return
        r = next((x for x in A.rows(self.st) if x["nick"] == nick), None)
        if r is None:
            return
        try:
            if col == 0:
                new, ok = QInputDialog.getText(self, "改号名", "号名(和企鹅号上的一模一样):", text=nick)
                if ok and new.strip() and new.strip() != nick:
                    A.rename(self.st, nick, new)
                    self.changed = True
            elif col == 4:
                if r["cat"] == "影视":
                    d = QFileDialog.getExistingDirectory(self, f"「{nick}」的素材文件夹", r["folder"] or FILM_ROOT)
                    new, ok = (os.path.normpath(d), True) if d else ("", False)
                else:
                    what = {"教育": "日期文件夹下面的缩写(几个用顿号隔开):"}.get(
                        r["cat"], "游戏名,或者这个号完整的素材文件夹名(号名和文件夹里写的不一样时填文件夹名):")
                    new, ok = QInputDialog.getText(self, "改素材文件夹", what, text=r["folder"])
                if ok and new.strip() != r["folder"]:
                    A.set_folder(self.st, nick, new)
                    self.changed = True
        except ValueError as e:
            QMessageBox.warning(self, "账号管理", str(e))
        self.fill()

    def _nick(self) -> str:
        r = self.t.currentRow()
        it = self.t.item(r, 0) if r >= 0 else None
        return it.data(Qt.ItemDataRole.UserRole) if it else ""

    def _set_cat(self, nick: str, cat: str, old: str):
        try:
            A.set_cat(self.st, nick, cat)
            self.changed = True
        except ValueError as e:
            QMessageBox.warning(self, "改分组", str(e))
        self.fill()

    def _set_quota(self, nick: str, n: int):
        if P.quota_of(self.st, nick) != n:
            P.set_quota(self.st, nick, n)
            self.changed = True

    def add(self):
        d = AddDialog(self)
        while d.exec():
            nick, cat, q, folder = d.values()
            try:
                A.add(self.st, nick, cat, q, folder)
            except ValueError as e:
                QMessageBox.warning(self, "新增账号", str(e))
                continue
            self.changed = True
            self.fill()
            if not A.czgt(cat) and self.on_key and QMessageBox.question(
                    self, "新增账号", f"「{nick}」加上了。现在扫码取它的接口钥匙吗?(取到钥匙才能发)\n\n"
                                      f"会打开一个浏览器,用手机扫码登录「{nick}」的企鹅号。",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                self._key()
            elif A.czgt(cat):
                QMessageBox.information(self, "新增账号", f"「{nick}」加上了({cat},在罐头里发)。罐头里要登录好这个号。")
            break

    def _key(self):
        if self.on_key:
            self.on_key(self)
            self.fill()

    def remove(self):
        nick = self._nick()
        if not nick:
            QMessageBox.information(self, "去掉号", "先在表里点一下要去掉的号。")
            return
        if QMessageBox.question(self, "去掉号", f"软件里不再管「{nick}」?\n\n"
                                "每天规定、分组里去掉它;接口号的钥匙也删掉(以后再加要重新扫码)。\n"
                                "企鹅号上的文章、素材文件夹都不动。",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        A.remove(self.st, nick)
        self.changed = True
        self.fill()
