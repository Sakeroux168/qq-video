"""界面小部件:大数字卡片、左边导航栏(用户 2026-10-15 选的「抖音创作者中心」那种:白卡片、大数字、红粉色强调)。
颜色都在 gui/theme.py 的 QSS 里按 objectName 配(#stat / #statVal / #sidebar / #nav …),这里只管摆。"""
from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QSizePolicy, QVBoxLayout,
                               QWidget)


def fill_dates(combo, dates: list[str], cur: str = "", blank: str = "", empty=()) -> None:
    """两页的「要发哪天的」下拉(审查 15:两页顺序不一样):最新的在上面,今天标出来,没视频的灰掉。
    dates = 日期文件夹名(新的在前);empty = 这天没视频的。每项的数据 = 日期本身(文字可能多了「(今天)」)。"""
    from PySide6.QtGui import QBrush, QColor
    from qe.config import bj_now
    from qe.folders import day_of
    today = f"{bj_now().month}.{bj_now().day}"
    combo.blockSignals(True)
    combo.clear()
    combo.addItem(blank, "")
    for d in dates:
        tags = (["今天"] if day_of(d) == today else []) + (["没视频"] if d in empty else [])
        combo.addItem(d + (f"({' · '.join(tags)})" if tags else ""), d)
        if d in empty:
            i = combo.count() - 1
            combo.setItemData(i, QBrush(QColor("#a8a9ae")), Qt.ItemDataRole.ForegroundRole)
            combo.setItemData(i, "这天还没有视频(文件夹是空的 / 还没建)", Qt.ItemDataRole.ToolTipRole)
    i = combo.findData(cur) if cur else -1
    combo.setCurrentIndex(i if i > 0 else 0)
    combo.blockSignals(False)


def newest_first(dates: list[str]) -> list[str]:
    """日期文件夹按 月.日 从新到旧(「10.14（101）」这种改过名的也按开头算);认不出日期的放最后。"""
    from qe.folders import day_of

    def key(d):
        k = day_of(d)
        return (0, -int(k.split(".")[0]), -int(k.split(".")[1]), d) if k else (1, 0, 0, d)
    return sorted(dates, key=key)


class MenuButton(QPushButton):
    """带下拉的按钮:鼠标挪上去停一下就弹出列表(用户 2026-10-16:「鼠标挪到检查 弹出列表」),点也弹。
    b = MenuButton("检查"); b.add("普通检查", fn, "说明")。"""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.menu_ = QMenu(self)
        self.menu_.setToolTipsVisible(True)
        self.setMenu(self.menu_)
        self._t = QTimer(self)
        self._t.setSingleShot(True)
        self._t.setInterval(300)                         # 停 0.3 秒再弹,鼠标只是路过不弹
        self._t.timeout.connect(self._pop)

    def add(self, text: str, fn, tip: str = ""):
        a = self.menu_.addAction(text, fn)
        if tip:
            a.setToolTip(tip)
        return a

    def enterEvent(self, e):
        if self.isEnabled():
            self._t.start()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._t.stop()
        super().leaveEvent(e)

    def _pop(self):
        if self.isEnabled() and self.underMouse() and not self.menu_.isVisible():
            self.showMenu()


class StatCards(QWidget):
    """一排大数字卡片:StatCards([("all", "今日待发"), ("ok", "能发"), ...]);set(all=51, ok=43, ...)。
    tone:"" 普通 / "good" 绿 / "warn" 红(要处理)/ "muted" 灰。"""

    clicked = Signal(str)                                # 点了哪张卡片(只有 clickable 里的才发)

    def __init__(self, items: list[tuple[str, str]], parent=None, clickable: tuple = ()):
        super().__init__(parent)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)
        self.vals: dict[str, QLabel] = {}
        self.subs: dict[str, QLabel] = {}
        for key, label in items:
            card = QFrame()
            card.setObjectName("stat")
            v = QVBoxLayout(card)
            v.setContentsMargins(16, 10, 16, 10)
            v.setSpacing(2)
            lab = QLabel(label)
            lab.setObjectName("statLbl")
            val = QLabel("–")
            val.setObjectName("statVal")
            sub = QLabel("")
            sub.setObjectName("statSub")
            sub.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)   # 小字太长就截,不撑宽窗口
            v.addWidget(lab)
            v.addWidget(val)
            v.addWidget(sub)
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            if key in clickable:
                card.setProperty("click", True)
                card.setProperty("key", key)
                card.setCursor(Qt.CursorShape.PointingHandCursor)
                card.setToolTip({"bad": "点这里:只看要处理的", "ok": "点这里:看全部"}.get(key, ""))
                card.installEventFilter(self)
            h.addWidget(card, 1)
            self.vals[key], self.subs[key] = val, sub

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.MouseButtonRelease and obj.property("key"):
            self.clicked.emit(obj.property("key"))
        return False

    def set(self, **kw):
        for k, x in kw.items():
            if k.endswith("_sub"):
                lab = self.subs.get(k[:-4])
                if lab is not None:
                    lab.setText(str(x))
                continue
            val = self.vals.get(k)
            if val is None:
                continue
            if isinstance(x, tuple):                      # (数字, 色调)
                x, tone = x
            else:
                tone = ""
            val.setText(str(x))
            if val.property("tone") != tone:
                val.setProperty("tone", tone)
                val.style().unpolish(val)
                val.style().polish(val)


def shell(pages: list[tuple[str, str, QWidget]], on_settings, version: str = "") -> tuple[QWidget, "QButtonGroup", object]:
    """左边导航 + 右边一页一页换(QStackedWidget)。pages = [(图标字, 名字, 页面)]。
    返回 (整个外壳, 导航按钮组, stack)。"""
    from PySide6.QtWidgets import QStackedWidget
    root = QWidget()
    root.setObjectName("shell")
    h = QHBoxLayout(root)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(0)
    side = QFrame()
    side.setObjectName("sidebar")
    side.setFixedWidth(168)
    sv = QVBoxLayout(side)
    sv.setContentsMargins(12, 16, 12, 14)
    sv.setSpacing(4)
    brand = QLabel("企鹅号助手")
    brand.setObjectName("brand")
    sv.addWidget(brand)
    tag = QLabel("教育 · 游戏 · 动漫")
    tag.setObjectName("brandSub")
    sv.addWidget(tag)
    sv.addSpacing(14)
    stack = QStackedWidget()
    group = QButtonGroup(root)
    group.setExclusive(True)
    for k, (icon, name, page) in enumerate(pages):
        b = QPushButton(f"{icon}  {name}" if icon else name)
        b.setObjectName("nav")
        b.setCheckable(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        group.addButton(b, k)
        sv.addWidget(b)
        stack.addWidget(page)
    group.idClicked.connect(stack.setCurrentIndex)
    stack.currentChanged.connect(lambda i: group.button(i).setChecked(True))
    group.button(0).setChecked(True)
    sv.addStretch(1)
    b = QPushButton("设置")
    b.setObjectName("nav")
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.clicked.connect(on_settings)
    sv.addWidget(b)
    if version:
        ver = QLabel(version)
        ver.setObjectName("brandSub")
        sv.addWidget(ver)
    h.addWidget(side)
    body = QWidget()
    body.setObjectName("page")
    bv = QVBoxLayout(body)
    bv.setContentsMargins(0, 0, 0, 0)
    bv.addWidget(stack)
    h.addWidget(body, 1)
    return root, group, stack
