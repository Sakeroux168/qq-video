"""界面小部件:大数字卡片、左边导航栏(用户 2026-10-15 选的「抖音创作者中心」那种:白卡片、大数字、红粉色强调)。
颜色都在 gui/theme.py 的 QSS 里按 objectName 配(#stat / #statVal / #sidebar / #nav …),这里只管摆。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout,
                               QWidget)


class StatCards(QWidget):
    """一排大数字卡片:StatCards([("all", "今日待发"), ("ok", "能发"), ...]);set(all=51, ok=43, ...)。
    tone:"" 普通 / "good" 绿 / "warn" 红(要处理)/ "muted" 灰。"""

    def __init__(self, items: list[tuple[str, str]], parent=None):
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
            h.addWidget(card, 1)
            self.vals[key], self.subs[key] = val, sub

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
