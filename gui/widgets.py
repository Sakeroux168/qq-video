"""界面小部件(用户 2026-10-18 选的「G 一键驾驶舱」):
大字区 Hero(一句话 + 一个大按钮,明细收起时大、展开时缩成一条)、问题卡片 ProbCard(点了就处理)、
「全部 / 要处理 / 能发 / 已发」Segmented、进度圆环 Ring、数字滚动 roll、明细展开收起 slide、
列表里的彩色状态胶囊 PillDelegate、左边导航(图标 + 文字 + 红点数字)、开场动画 Splash。
颜色在 gui/theme.py(QSS 按 objectName 配;自己画的用 theme.cur()),这里只管摆和动。"""
from PySide6.QtCore import (QEasingCurve, QEvent, QPointF, QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QFrame, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QLabel, QMenu,
                               QPushButton, QSizePolicy, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QVBoxLayout,
                               QWidget)

# Windows 自带的图标字体(Segoe MDL2 Assets)里的图标
GLYPH = {"today": "", "school": "", "game": "", "chart": "", "table": "", "bulb": "",
         "warn": "", "done": "", "check": "", "history": "", "clock": "", "calendar": "",
         "send": "", "settings": "", "refresh": "", "search": "", "down": "", "up": "",
         "right": "", "more": "", "folder": "", "video": "", "rotate": "", "tag": "",
         "scan": "", "stop": "", "error": "", "help": "", "movie": "", "eye": ""}
ICON_FONT = "Segoe MDL2 Assets"


def tok() -> dict:
    from gui import theme
    return theme.cur()


def glyph_label(name: str, color: str = "", px: int = 18) -> QLabel:
    lab = QLabel(GLYPH.get(name, name))
    lab.setStyleSheet(f"font-family:'{ICON_FONT}';font-size:{px}px;" + (f"color:{color};" if color else ""))
    lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lab


def glyph_pixmap(name: str, color: str, px: int = 16) -> QPixmap:
    pm = QPixmap(px * 2, px * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    f = QFont(ICON_FONT)
    f.setPixelSize(px)
    p.setFont(f)
    p.setPen(QColor(color))
    p.drawText(QRectF(0, 0, px, px), Qt.AlignmentFlag.AlignCenter, GLYPH.get(name, name))
    p.end()
    return pm


def glyph_icon(name: str, color: str, on_color: str = "", px: int = 16) -> QIcon:
    ic = QIcon()
    ic.addPixmap(glyph_pixmap(name, color, px), QIcon.Mode.Normal, QIcon.State.Off)
    ic.addPixmap(glyph_pixmap(name, on_color or color, px), QIcon.Mode.Normal, QIcon.State.On)
    ic.addPixmap(glyph_pixmap(name, tok()["dim"], px), QIcon.Mode.Disabled, QIcon.State.Off)
    return ic


def repolish(w, **props):
    """改了动态属性(tone / open …)以后让 QSS 重新套一遍。"""
    changed = False
    for k, v in props.items():
        if w.property(k) != v:
            w.setProperty(k, v)
            changed = True
    if changed:
        w.style().unpolish(w)
        w.style().polish(w)


def fill_dates(combo, dates: list[str], cur: str = "", blank: str = "", empty=()) -> None:
    """两页的「要发哪天的」下拉(审查 15:两页顺序不一样):最新的在上面,今天标出来,没视频的灰掉。
    dates = 日期文件夹名(新的在前);empty = 这天没视频的。每项的数据 = 日期本身(文字可能多了「(今天)」)。"""
    from PySide6.QtGui import QBrush
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
            combo.setItemData(i, QBrush(QColor(tok()["dim"])), Qt.ItemDataRole.ForegroundRole)
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
    tone:"" 普通 / "good" 绿 / "warn" 橙(要处理)。
    icons={"sent": ("check", "ok")}:卡片左边一个带颜色的小方块图标;rings={"游戏": "acc"}:左边一个圆环(set_ring 设多满)。"""

    clicked = Signal(str)                                # 点了哪张卡片(只有 clickable 里的才发)

    def __init__(self, items: list[tuple[str, str]], parent=None, clickable: tuple = (), icons: dict | None = None,
                 rings: dict | None = None):
        super().__init__(parent)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(12)
        self.vals: dict[str, QLabel] = {}
        self.subs: dict[str, QLabel] = {}
        self.rings: dict[str, "Ring"] = {}
        t = tok()
        for key, label in items:
            card = QFrame()
            card.setObjectName("stat")
            row = QHBoxLayout(card)
            row.setContentsMargins(16, 12, 16, 12)
            row.setSpacing(14)
            if rings and key in rings:
                ring = Ring(56, 7, t.get(rings[key], rings[key]))
                row.addWidget(ring)
                self.rings[key] = ring
            elif icons and key in icons:
                name, ck = icons[key]
                ic = QLabel(GLYPH.get(name, name))
                ic.setFixedSize(40, 40)
                ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
                fg, bg = t.get(ck, ck), t.get(ck + "_bg", t["soft"])
                ic.setStyleSheet(f"font-family:'{ICON_FONT}';font-size:18px;color:{fg};background:{bg};border-radius:12px;")
                row.addWidget(ic)
            v = QVBoxLayout()
            v.setSpacing(1)
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
            row.addLayout(v, 1)
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

    def set_ring(self, key: str, frac: float, animate_: bool = True):
        r = self.rings.get(key)
        if r is not None:
            r.set_value(frac, animate_)

    def set(self, **kw):
        for k, x in kw.items():
            if k.endswith("_sub"):
                lab = self.subs.get(k[:-4])
                if lab is not None:
                    lab.setText(str(x))
                    lab.setVisible(bool(str(x)))
                continue
            val = self.vals.get(k)
            if val is None:
                continue
            if isinstance(x, tuple):                      # (数字, 色调)
                x, tone = x
            else:
                tone = ""
            val.setText(str(x))
            repolish(val, tone=tone)


# ---------------- 动画小工具 ----------------
def _keep(owner, anim):
    """动画对象挂在部件上,免得被回收;同一个部件上的同名动画先停掉。"""
    old = getattr(owner, "_anims", None)
    if old is None:
        old = owner._anims = {}
    name = anim.objectName()
    if name in old:
        old[name].stop()
    old[name] = anim
    return anim


def animate(owner, name: str, start, end, ms: int, on_value, on_done=None, curve=QEasingCurve.Type.OutCubic):
    a = QVariantAnimation(owner)
    a.setObjectName(name)
    a.setStartValue(start)
    a.setEndValue(end)
    a.setDuration(ms)
    a.setEasingCurve(curve)
    a.valueChanged.connect(on_value)
    if on_done:
        a.finished.connect(on_done)
    _keep(owner, a).start()
    return a


def roll(label: QLabel, to: int, fmt: str = "{}", ms: int = 900, frm: int | None = None):
    """数字滚动到 to(用户 2026-10-18:「再活泼一点」)。label 上记着现在的数。"""
    start = label.property("num") if frm is None else frm
    label.setProperty("num", to)
    if start is None or start == to or not label.isVisible():
        label.setText(fmt.format(to))
        return
    animate(label, "roll", int(start), int(to), ms, lambda v: label.setText(fmt.format(int(v))))


def fade_in(w: QWidget, ms: int = 380, delay: int = 0, dy: int = 0):
    """淡入(开场、换页时一块一块出来)。"""
    eff = QGraphicsOpacityEffect(w)
    eff.setOpacity(0.0)
    w.setGraphicsEffect(eff)

    def go():
        def val(v):
            try:
                eff.setOpacity(v)
            except RuntimeError:
                pass
        animate(w, "fade", 0.0, 1.0, ms, val, lambda: w.setGraphicsEffect(None))
    QTimer.singleShot(delay, go) if delay else go()


def slide(w: QWidget, show: bool, ms: int = 380, full: int = 0):
    """明细展开 / 收起:高度从 0 慢慢拉开(用户 2026-10-18:「丝滑的一个动画」)。"""
    MAX = 16777215
    if show:
        w.setMaximumHeight(0)
        w.show()
        target = full or max(200, (w.parentWidget().height() if w.parentWidget() else 600))
        animate(w, "slide", 0, target, ms, lambda v: w.setMaximumHeight(int(v)), lambda: w.setMaximumHeight(MAX))
    else:
        h = w.height()
        animate(w, "slide", h, 0, int(ms * 0.8), lambda v: w.setMaximumHeight(int(v)),
                lambda: (w.hide(), w.setMaximumHeight(MAX)), QEasingCurve.Type.InOutCubic)


# ---------------- 大字区 ----------------
class Hero(QFrame):
    """每页最上面:一句大字 + 一行说明 + 按钮。
    open=False:明细收起时,大字居中、更大,没有底框(像 G 草图);open=True:明细展开时缩成一条卡片,按钮在右边。
    用法:h = Hero(); h.meta.addWidget(…); h.acts.addWidget(…); h.set("37 条可以发了", "还有 14 条…", tone)。"""

    BIG = (52, 26)                                       # 收起时 / 展开时大字多大

    def __init__(self, parent=None, open_: bool = True):
        super().__init__(parent)
        self.setObjectName("hero")
        self._meta_w = QWidget()
        self.meta = QHBoxLayout(self._meta_w)
        self.meta.setContentsMargins(0, 0, 0, 0)
        self.meta.setSpacing(8)
        self.big = QLabel("")
        self.big.setObjectName("heroBig")
        self.big.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.sub = QLabel("")
        self.sub.setObjectName("heroSub")
        self._extra_w = QWidget()                        # 大字下面多放一块(发布进度条)
        self.extra = QVBoxLayout(self._extra_w)
        self.extra.setContentsMargins(0, 8, 0, 4)
        self._extra_w.hide()
        self._acts_w = QWidget()
        self.acts = QHBoxLayout(self._acts_w)
        self.acts.setContentsMargins(0, 0, 0, 0)
        self.acts.setSpacing(8)
        self.grid = QGridLayout(self)
        self.grid.setHorizontalSpacing(18)
        self.grid.setVerticalSpacing(4)
        self._open = None
        self.set_open(open_, animate_=False)

    def set(self, big: str, sub: str = "", tone: str = ""):
        if self.big.text() != big:
            self.big.setText(big)
        if self.sub.text() != sub:
            self.sub.setText(sub)
        self.sub.setVisible(bool(sub))
        repolish(self.big, tone=tone)

    def _px(self, px):
        self.big.setStyleSheet(f"font-size:{int(px)}px;")

    def set_open(self, on: bool, animate_: bool = True):
        if self._open == on:
            return
        old = self._open
        self._open = on
        for w in (self._meta_w, self.big, self.sub, self._extra_w, self._acts_w):
            self.grid.removeWidget(w)
        L, C, R = Qt.AlignmentFlag.AlignLeft, Qt.AlignmentFlag.AlignHCenter, Qt.AlignmentFlag.AlignRight
        V = Qt.AlignmentFlag.AlignVCenter
        if on:
            self.grid.setContentsMargins(20, 14, 20, 14)
            self.grid.addWidget(self._meta_w, 0, 0, L | V)
            self.grid.addWidget(self.big, 1, 0, L | V)
            self.grid.addWidget(self.sub, 2, 0, L | V)
            self.grid.addWidget(self._acts_w, 0, 1, 3, 1, R | V)
            self.grid.addWidget(self._extra_w, 3, 0, 1, 2)
            self.grid.setColumnStretch(0, 1)
            self.sub.setAlignment(L)
        else:
            self.grid.setContentsMargins(20, 26, 20, 18)
            self.grid.addWidget(self._meta_w, 0, 0, C)
            self.grid.addWidget(self.big, 1, 0, C)
            self.grid.addWidget(self.sub, 2, 0, C)
            self.grid.addWidget(self._extra_w, 3, 0)
            self.grid.addWidget(self._acts_w, 4, 0, C)
            self.grid.setColumnStretch(0, 1)
            self.grid.setColumnStretch(1, 0)
            self.sub.setAlignment(C)
        self.grid.setVerticalSpacing(4 if on else 8)
        self._acts_w.setContentsMargins(0, 0 if on else 18, 0, 0)    # 收起时按钮和大字之间多留点空
        self._meta_w.setContentsMargins(0, 0, 0, 0 if on else 6)
        repolish(self, open="true" if on else "false")
        for w in self.findChildren(QWidget):              # 里面的按钮 / 下拉跟着换大小(QSS 按 hero 的 open 配)
            w.style().unpolish(w)
            w.style().polish(w)
        a, b = (self.BIG[0], self.BIG[1]) if on else (self.BIG[1], self.BIG[0])
        if animate_ and old is not None and self.isVisible():
            animate(self, "font", a, b, 360, self._px)
            fade_in(self, 320)
        else:
            self._px(b)


# ---------------- 问题卡片 ----------------
class ProbCard(QFrame):
    """「8 条横屏 → 转标准竖屏」:图标 + 一句话 + 处理按钮(就是原来那个按钮,搬进卡片里)。点卡片空白处 = 点第一个按钮。"""

    def __init__(self, icon: str, title: str, buttons: list, parent=None, color: str = ""):
        super().__init__(parent)
        self.setObjectName("probCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        h = QHBoxLayout(self)
        h.setContentsMargins(16, 14, 16, 14)
        h.setSpacing(14)
        self._icon_name = icon
        self.icon = glyph_label(icon, color or tok()["orange"], 18)
        self.icon.setFixedSize(40, 40)                   # 图标放进带颜色的小方块里
        h.addWidget(self.icon)
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        sh = QGraphicsDropShadowEffect(self)             # 淡淡的阴影,卡片浮起来一点
        sh.setBlurRadius(28)
        sh.setOffset(0, 4)
        sh.setColor(QColor(16, 24, 40, 18))
        self.setGraphicsEffect(sh)
        v = QVBoxLayout()
        v.setSpacing(1)
        self.title = QLabel(title)
        self.title.setObjectName("probTitle")
        v.addWidget(self.title)
        row = QHBoxLayout()
        row.setSpacing(14)
        self.buttons = buttons
        for b in buttons:
            b.setObjectName("cardBtn")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            row.addWidget(b)
        row.addStretch(1)
        v.addLayout(row)
        h.addLayout(v, 1)

    def set(self, title: str, tone: str = ""):
        self.title.setText(title)
        repolish(self, tone=tone)
        repolish(self.title, tone=tone)
        t = tok()
        name = "done" if tone == "done" else self._icon_name
        col, bg = ((t["ok"], t["ok_bg"]) if tone == "done" else (t["orange"], t["warn_bg"]) if tone == "warn"
                   else (t["acc"], t["acc_bg"]))
        self.icon.setText(GLYPH.get(name, name))
        self.icon.setStyleSheet(f"font-family:'{ICON_FONT}';font-size:18px;color:{col};background:{bg};border-radius:12px;")

    def mouseReleaseEvent(self, e):
        b = self.buttons[0] if self.buttons else None
        if b is not None and b.isEnabled() and e.button() == Qt.MouseButton.LeftButton:
            b.showMenu() if b.menu() else b.click()
        super().mouseReleaseEvent(e)


# ---------------- 全部 / 要处理 / 能发 / 已发 ----------------
class Segmented(QFrame):
    changed = Signal(str)

    def __init__(self, items: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.setObjectName("seg")
        h = QHBoxLayout(self)
        h.setContentsMargins(3, 3, 3, 3)
        h.setSpacing(2)
        self.group = QButtonGroup(self)
        self.btns: dict[str, QPushButton] = {}
        for k, label in items:
            b = QPushButton(label)
            b.setObjectName("segBtn")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, k=k: self.changed.emit(k))
            self.group.addButton(b)
            h.addWidget(b)
            self.btns[k] = b
        self.btns[items[0][0]].setChecked(True)

    def key(self) -> str:
        return next((k for k, b in self.btns.items() if b.isChecked()), "")

    def select(self, k: str):
        if k in self.btns:
            self.btns[k].setChecked(True)

    def set_text(self, k: str, text: str):
        if k in self.btns and self.btns[k].text() != text:
            self.btns[k].setText(text)


# ---------------- 进度圆环 ----------------
class Ring(QWidget):
    """圆环:value 0~1,变的时候转过去。"""

    def __init__(self, size: int = 52, width: int = 6, color: str = "", parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._w, self._v, self.color = width, 0.0, color

    def set_value(self, v: float, animate_: bool = True):
        v = max(0.0, min(1.0, float(v)))
        if animate_ and self.isVisible():
            animate(self, "ring", self._v, v, 1100, self._set)
        else:
            self._set(v)

    def _set(self, v):
        self._v = float(v)
        self.update()

    def paintEvent(self, _e):
        t = tok()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self._w / 2 + 1, self._w / 2 + 1, self.width() - self._w - 2, self.height() - self._w - 2)
        pen = QPen(QColor(t["soft"]), self._w)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(r, 0, 360 * 16)
        if self._v > 0:
            pen.setColor(QColor(self.color or t["acc"]))
            p.setPen(pen)
            p.drawArc(r, 90 * 16, -int(360 * 16 * self._v))
        p.end()


class Bar(QWidget):
    """横的进度条(今天发了多少 / 正在发到第几条)。"""

    def __init__(self, height: int = 8, parent=None):
        super().__init__(parent)
        self.setFixedHeight(height)
        self._v = 0.0

    def set_value(self, v: float, animate_: bool = True):
        v = max(0.0, min(1.0, float(v)))
        if animate_ and self.isVisible():
            animate(self, "bar", self._v, v, 1100, self._set)
        else:
            self._set(v)

    def _set(self, v):
        self._v = float(v)
        self.update()

    def paintEvent(self, _e):
        t = tok()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        r = self.height() / 2
        p.setBrush(QColor(t["soft"]))
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), r, r)
        if self._v > 0:
            p.setBrush(QColor(t["acc"]))
            p.drawRoundedRect(QRectF(0, 0, max(self.height(), self.width() * self._v), self.height()), r, r)
        p.end()


# ---------------- 列表里的彩色状态胶囊 ----------------
def tone_of(text: str) -> str:
    """状态文字 → 颜色:bad 红 / warn 橙 / ok 绿 / acc 蓝 / done 灰 / "" 普通。"""
    s = (text or "").strip()
    if not s:
        return ""
    if s.startswith(("没发成", "没发:", "转竖屏失败", "没摆成", "失败", "出错")):
        return "bad"
    if s.startswith(("不确定", "结果不明", "要处理", "不发:", "有水印", "跳过", "有问题", "还差")):
        return "warn"
    if s.startswith(("已发", "发完")):
        return "done"
    if s.startswith(("能发", "够了")):
        return "ok"
    if s.startswith(("摆好", "正在", "发布中", "排队", "等", "检查中", "转")):
        return "acc"
    return "plain"


class PillDelegate(QStyledItemDelegate):
    """把某一列的状态画成彩色小胶囊(「能发」绿、「要处理」橙、「没发成」红、「已发」灰)。有子项的行(号那一行)照常画字。"""

    def __init__(self, col: int, parent=None):
        super().__init__(parent)
        self.col = col

    def paint(self, painter, option, index):
        from PySide6.QtWidgets import QTreeView
        if index.column() != self.col or (isinstance(option.widget, QTreeView) and not index.parent().isValid()):
            return super().paint(painter, option, index)     # 树上号那一行:照常写字
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        tone = tone_of(text)
        if not tone:
            return super().paint(painter, option, index)
        opt.text = ""
        w = opt.widget
        style = w.style() if w else None
        if style:
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, w)
        t = tok()
        bg, fg = {"bad": (t["bad_bg"], t["bad"]), "warn": (t["warn_bg"], t["warn"]), "ok": (t["ok_bg"], t["ok"]),
                  "acc": (t["acc_bg"], t["acc"]), "done": (t["soft"], t["mu"]), "plain": (t["soft"], t["tx2"])}[tone]
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        f = QFont(opt.font)
        f.setPixelSize(12)
        f.setBold(tone in ("bad", "warn"))
        painter.setFont(f)
        fm = painter.fontMetrics()
        r = option.rect
        maxw = r.width() - 12
        shown = fm.elidedText(text, Qt.TextElideMode.ElideRight, max(10, maxw - 18))
        pw = min(maxw, fm.horizontalAdvance(shown) + 18)
        ph = 22
        pr = QRectF(r.left() + 6, r.top() + (r.height() - ph) / 2, pw, ph)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(bg))
        painter.drawRoundedRect(pr, ph / 2, ph / 2)
        painter.setPen(QColor(fg))
        painter.drawText(pr, Qt.AlignmentFlag.AlignCenter, shown)
        painter.restore()

    def sizeHint(self, option, index):
        s = super().sizeHint(option, index)
        return QSize(s.width() + 18, max(s.height(), 32))


# ---------------- 左边导航 + 右边一页一页换 ----------------
def shell(pages: list[tuple[str, str, QWidget]], on_settings, version: str = "") -> tuple[QWidget, "QButtonGroup", object]:
    """左边导航 + 右边一页一页换(QStackedWidget)。pages = [(图标名, 名字, 页面)]。
    返回 (整个外壳, 导航按钮组, stack)。group.badges[k] = 那个导航后面的小红点数字(setText;空就藏起来)。"""
    from PySide6.QtWidgets import QStackedWidget
    t = tok()
    root = QWidget()
    root.setObjectName("shell")
    h = QHBoxLayout(root)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(0)
    side = QFrame()
    side.setObjectName("sidebar")
    side.setFixedWidth(176)
    sv = QVBoxLayout(side)
    sv.setContentsMargins(12, 18, 12, 14)
    sv.setSpacing(3)
    top = QHBoxLayout()
    top.setSpacing(8)
    logo = QLabel(GLYPH["send"])
    logo.setFixedSize(28, 28)
    logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    logo.setStyleSheet(f"background:{t['acc']};color:#ffffff;border-radius:8px;font-family:'{ICON_FONT}';font-size:15px;")
    top.addWidget(logo)
    brand = QLabel("企鹅号助手")
    brand.setObjectName("brand")
    top.addWidget(brand, 1)
    sv.addLayout(top)
    tag = QLabel("教育 · 游戏 · 动漫")
    tag.setObjectName("brandSub")
    tag.setContentsMargins(36, 0, 0, 0)
    sv.addWidget(tag)
    sv.addSpacing(16)
    stack = QStackedWidget()
    group = QButtonGroup(root)
    group.setExclusive(True)
    group.badges = {}
    for k, (icon, name, page) in enumerate(pages):
        b = QPushButton(name)
        b.setObjectName("nav")
        b.setCheckable(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        if icon in GLYPH:
            b.setIcon(glyph_icon(icon, t["mu"], t["acc"], 16))
            b.setIconSize(QSize(16, 16))
        bl = QHBoxLayout(b)
        bl.setContentsMargins(0, 0, 8, 0)
        bl.addStretch(1)
        badge = QLabel("")
        badge.setObjectName("navBadge")
        badge.setFixedHeight(18)
        badge.setMinimumWidth(18)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        badge.hide()
        bl.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)
        group.badges[k] = badge
        group.addButton(b, k)
        sv.addWidget(b)
        stack.addWidget(page)
    group.idClicked.connect(stack.setCurrentIndex)
    stack.currentChanged.connect(lambda i: group.button(i).setChecked(True))
    group.button(0).setChecked(True)
    sv.addStretch(1)
    b = QPushButton("设置")
    b.setObjectName("nav")
    b.setIcon(glyph_icon("settings", t["mu"], t["acc"], 16))
    b.setIconSize(QSize(16, 16))
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.clicked.connect(on_settings)
    sv.addWidget(b)
    if version:
        ver = QLabel(version)
        ver.setObjectName("brandSub")
        ver.setContentsMargins(12, 4, 0, 0)
        sv.addWidget(ver)
    h.addWidget(side)
    body = QWidget()
    body.setObjectName("page")
    bv = QVBoxLayout(body)
    bv.setContentsMargins(0, 0, 0, 0)
    bv.addWidget(stack)
    h.addWidget(body, 1)
    return root, group, stack


def set_badge(group, k: int, text: str):
    b = getattr(group, "badges", {}).get(k)
    if b is not None:
        b.setText(text)
        b.setVisible(bool(text))


# ---------------- 开场动画 ----------------
class Splash(QWidget):
    """打开软件:「Hi,欢迎使用本工作台」淡入,一秒多以后淡出,露出「今天」页(用户 2026-10-18)。点一下就跳过。"""

    done = Signal()

    def __init__(self, parent: QWidget, sub: str = ""):
        super().__init__(parent)
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"background:{tok()['bg']};")
        v = QVBoxLayout(self)
        v.addStretch(3)
        t = tok()
        self.logo = QLabel(GLYPH["send"])
        self.logo.setFixedSize(64, 64)
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo.setStyleSheet(f"background:{t['acc']};color:#ffffff;border-radius:18px;font-family:'{ICON_FONT}';font-size:30px;")
        v.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignHCenter)
        v.addSpacing(18)
        self.hi = QLabel("Hi,欢迎使用本工作台")
        self.hi.setStyleSheet(f"font-size:32px;font-weight:bold;color:{t['tx']};background:transparent;")
        v.addWidget(self.hi, 0, Qt.AlignmentFlag.AlignHCenter)
        self.sub = QLabel(sub)
        self.sub.setStyleSheet(f"font-size:15px;color:{t['mu']};background:transparent;")
        v.addWidget(self.sub, 0, Qt.AlignmentFlag.AlignHCenter)
        v.addStretch(4)
        self._gone = False

    def play(self, hold_ms: int = 1300):
        self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.show()
        fade_in(self.logo, 450)
        fade_in(self.hi, 500, 180)
        fade_in(self.sub, 500, 380)
        QTimer.singleShot(hold_ms, self.finish)

    def finish(self):
        if self._gone:
            return
        self._gone = True
        eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(eff)
        self.done.emit()
        animate(self, "out", 1.0, 0.0, 450, lambda v: eff.setOpacity(v), self.deleteLater)

    def mousePressEvent(self, _e):
        self.finish()

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.Resize and not self._gone:
            self.setGeometry(obj.rect())
        return False


# ---------------- 列表的画法(用户 2026-10-18 看过草图:头像、标签、进度条、封面小图、两行字) ----------------
def _cell_bg(painter, option, index) -> QRectF:
    """先照常画底色 / 选中 / 勾选框(不画字),返回该写字的那块地方。"""
    opt = QStyleOptionViewItem(option)
    QStyledItemDelegate().initStyleOption(opt, index)
    opt.text = ""
    w = opt.widget
    style = w.style() if w else None
    if style:
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, w)
        return QRectF(style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, opt, w))
    return QRectF(option.rect)


_TONES = {"bad": ("bad_bg", "bad"), "warn": ("warn_bg", "warn"), "ok": ("ok_bg", "ok"), "acc": ("acc_bg", "acc"),
          "done": ("soft", "mu"), "plain": ("soft", "tx2")}


def draw_pill(painter, x: float, cy: float, text: str, tone: str, maxw: float = 999, px: int = 12, h: int = 22,
              radius: float | None = None) -> float:
    """画一个彩色小胶囊,返回画了多宽。"""
    t = tok()
    bg, fg = _TONES.get(tone, _TONES["plain"])
    f = QFont(painter.font())
    f.setPixelSize(px)
    f.setBold(tone in ("bad", "warn", "ok"))
    painter.setFont(f)
    fm = painter.fontMetrics()
    shown = fm.elidedText(text, Qt.TextElideMode.ElideRight, int(max(10, maxw - 18)))
    w = min(maxw, fm.horizontalAdvance(shown) + 18)
    r = QRectF(x, cy - h / 2, w, h)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(t[bg]))
    rr = h / 2 if radius is None else radius
    painter.drawRoundedRect(r, rr, rr)
    painter.setPen(QColor(t[fg]))
    painter.drawText(r, Qt.AlignmentFlag.AlignCenter, shown)
    return w


def draw_bar(painter, x: float, cy: float, w: float, frac: float, color: str, h: int = 6):
    t = tok()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(t["soft"]))
    painter.drawRoundedRect(QRectF(x, cy - h / 2, w, h), h / 2, h / 2)
    if frac > 0:
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(QRectF(x, cy - h / 2, max(h, w * min(1.0, frac)), h), h / 2, h / 2)


def avatar_colors(name: str) -> tuple[str, str]:
    t = tok()
    pairs = [(t["acc_bg"], t["acc"]), (t["ok_bg"], t["ok"]), (t["warn_bg"], t["warn"]), (t["bad_bg"], t["bad"])]
    return pairs[sum(map(ord, name or "?")) % len(pairs)]


def draw_avatar(painter, x: float, cy: float, name: str, d: int = 26, grey: bool = False):
    t = tok()
    bg, fg = (t["soft"], t["mu"]) if grey else avatar_colors(name)
    nm = (name or "?").strip()
    ch = next((c for c in nm if c not in "家长的 "), nm[:1]).upper()   # 「家长研习空间 / 家长小天地」别都是「家」
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(bg))
    painter.drawEllipse(QRectF(x, cy - d / 2, d, d))
    f = QFont(painter.font())
    f.setPixelSize(int(d * 0.46))
    f.setBold(True)
    painter.setFont(f)
    painter.setPen(QColor(fg))
    painter.drawText(QRectF(x, cy - d / 2, d, d), Qt.AlignmentFlag.AlignCenter, ch)


def draw_text(painter, rect: QRectF, text: str, color: str, px: int = 13, bold: bool = False,
              align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter) -> float:
    f = QFont(painter.font())
    f.setPixelSize(px)
    f.setBold(bold)
    painter.setFont(f)
    fm = painter.fontMetrics()
    shown = fm.elidedText(text, Qt.TextElideMode.ElideRight, int(max(0, rect.width())))
    painter.setPen(QColor(color))
    painter.drawText(rect, align, shown)
    return fm.horizontalAdvance(shown)


class ApiTreeDelegate(QStyledItemDelegate):
    """16 个号的明细:号那一行 = 头像 + 号名 + 「5 条要处理」标签 + 今天发了多少的进度条;视频那一行 = 问题小标签 + 状态胶囊。
    文字还是原来那些(测试和右键都按文字),只是换个画法。"""

    NICK = Qt.ItemDataRole.UserRole + 1

    def paint(self, painter, option, index):
        import re
        col = index.column()
        top = not index.parent().isValid()
        if col not in (0, 2, 3) or (col == 0 and not top):
            return super().paint(painter, option, index)
        t = tok()
        text = str(index.data() or "")
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = _cell_bg(painter, option, index)
        cy = r.center().y()
        if top and col == 0:
            nick = str(index.data(self.NICK) or text.split("  ")[0])
            rest = text[len(nick):].strip()
            grey = "没找到视频" in rest
            draw_avatar(painter, r.left() + 2, cy, nick, 28, grey)
            x = r.left() + 40
            wn = draw_text(painter, QRectF(x, r.top(), r.right() - x, r.height()), nick, t["dim"] if grey else t["tx"], 14, True)
            draw_text(painter, QRectF(x + wn + 10, r.top(), r.right() - x - wn - 10, r.height()), rest, t["mu"], 12)
        elif top and col == 2:
            x = r.left() + 2
            for part in [p for p in text.split(" · ") if p]:
                m = re.match(r"(有问题|没发成|结果不明|可能放错了) (\d+)", part)
                if m:
                    label, tone = {"有问题": (f"{m.group(2)} 条要处理", "warn"), "没发成": (f"没发成 {m.group(2)}", "bad"),
                                   "结果不明": (f"结果不明 {m.group(2)}", "warn"),
                                   "可能放错了": ("可能整批放错了", "bad")}[m.group(1)]
                else:
                    label, tone = part, "plain"
                x += draw_pill(painter, x, cy, label, tone, r.right() - x) + 6
                if x > r.right() - 20:
                    break
        elif top and col == 3:
            parts = [p for p in text.split(" · ") if p]
            x = r.left() + 2
            q = None
            for p in parts:
                m = re.match(r"今天 (\d+)/(\d+)", p)
                if m:
                    q = (int(m.group(1)), int(m.group(2)))
                    continue
                if p.startswith("今天"):
                    x += draw_text(painter, QRectF(x, r.top(), r.right() - x, r.height()), p, t["mu"], 12) + 8
                    continue
                n = re.match(r"能发 (\d+)", p)
                tone = "ok" if n and int(n.group(1)) else "done" if p.startswith("发完") else "plain"
                x += draw_pill(painter, x, cy, p, tone, r.right() - x) + 10
            if q:
                a, qq = q
                bw = max(30, min(70, r.right() - x - 54))
                draw_bar(painter, x, cy, bw, a / qq if qq else 0, t["green"] if a >= qq else t["acc"])
                draw_text(painter, QRectF(x + bw + 8, r.top(), r.right() - x - bw - 8, r.height()), f"{a}/{qq}",
                          t["ok"] if a >= qq else t["mu"], 12, a >= qq)
        elif col == 2:                                        # 视频那一行:问题写成灰色小标签
            x = r.left() + 2
            for part in [p for p in text.split("、") if p]:
                if x > r.right() - 30:
                    draw_text(painter, QRectF(x, r.top(), 20, r.height()), "…", t["mu"], 12)
                    break
                x += draw_pill(painter, x, cy, part, "plain", r.right() - x, 12, 20, 6) + 5
        else:                                                 # 视频那一行的状态:彩色胶囊
            if text:
                draw_pill(painter, r.left() + 2, cy, text, tone_of(text), r.width() - 4)
        painter.restore()

    def sizeHint(self, option, index):
        s = super().sizeHint(option, index)
        return QSize(s.width(), 46 if not index.parent().isValid() else 36)


class EduTreeDelegate(QStyledItemDelegate):
    """教育号左边:号那一行 = 头像 + 号名;员工那一行的条数写成小标签(发了 2 绿、有不发的橙)。"""

    def paint(self, painter, option, index):
        top = not index.parent().isValid()
        col = index.column()
        text = str(index.data() or "")
        t = tok()
        if top and col == 0 and text != "没读的文件夹":
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            r = _cell_bg(painter, option, index)
            draw_avatar(painter, r.left() + 2, r.center().y(), text, 26)
            draw_text(painter, QRectF(r.left() + 36, r.top(), r.width() - 36, r.height()), text, t["tx"], 14, True)
            painter.restore()
            return
        if not top and col == 1 and text:
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            r = _cell_bg(painter, option, index)
            grey = not (index.flags() & Qt.ItemFlag.ItemIsUserCheckable)
            tone = "done" if grey else "warn" if "不发" in text else "ok" if "发了" in text else "plain"
            draw_pill(painter, r.left() + 2, r.center().y(), text, tone, r.width() - 4)
            painter.restore()
            return
        super().paint(painter, option, index)

    def sizeHint(self, option, index):
        s = super().sizeHint(option, index)
        return QSize(s.width(), 40 if not index.parent().isValid() else 34)


_THUMBS: dict = {}
THUMB = Qt.ItemDataRole.UserRole + 5                   # 表格第一列存封面图的路径(画小图用)


def thumb(path: str, maxw: int = 60, maxh: int = 48):
    """封面小图(读一次记着;文件变了重读)。读不出来返回 None。"""
    import os
    from PySide6.QtGui import QImageReader
    try:
        key = (path, os.path.getmtime(path), maxw, maxh)
    except OSError:
        return None
    pm = _THUMBS.get(key)
    if pm is None:
        rd = QImageReader(path)
        sz = rd.size()
        if not sz.isValid() or sz.width() <= 0:
            _THUMBS[key] = False
            return None
        k = min(maxw / sz.width(), maxh / sz.height()) * 2
        rd.setScaledSize(QSize(max(1, int(sz.width() * k)), max(1, int(sz.height() * k))))
        img = rd.read()
        pm = QPixmap.fromImage(img) if not img.isNull() else False
        if pm:
            pm.setDevicePixelRatio(2)
        if len(_THUMBS) > 600:
            _THUMBS.clear()
        _THUMBS[key] = pm
    return pm or None


class EduTableDelegate(QStyledItemDelegate):
    """教育号右边第一列:封面小图 + 标题(粗)+ 下面一行「号 · 员工」;已发的淡一点。"""

    def paint(self, painter, option, index):
        if index.column() != 0:
            return super().paint(painter, option, index)
        t = tok()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = _cell_bg(painter, option, index)
        model = index.model()
        status = str(model.index(index.row(), 4).data() or "")
        if status.startswith("已发"):
            painter.setOpacity(0.55)
        x, cy = r.left() + 2, r.center().y()
        pm = thumb(str(index.data(THUMB) or ""))
        box = QRectF(x, cy - 24, 60, 48)
        if pm:
            w, h = pm.width() / pm.devicePixelRatio(), pm.height() / pm.devicePixelRatio()
            dst = QRectF(box.center().x() - w / 2, box.center().y() - h / 2, w, h)
            from PySide6.QtGui import QPainterPath
            path = QPainterPath()
            path.addRoundedRect(dst, 6, 6)
            painter.setClipPath(path)
            painter.drawPixmap(dst, pm, QRectF(0, 0, pm.width(), pm.height()))
            painter.setClipping(False)
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(t["soft"]))
            painter.drawRoundedRect(QRectF(x + 12, cy - 18, 36, 36), 8, 8)
            draw_text(painter, QRectF(x + 12, cy - 18, 36, 36), GLYPH["video"], t["dim"], 14,
                      align=Qt.AlignmentFlag.AlignCenter)
        tx = x + 72
        title = str(index.data() or "")
        sub = " · ".join(x for x in (str(model.index(index.row(), 1).data() or ""), str(model.index(index.row(), 2).data() or "")) if x)
        draw_text(painter, QRectF(tx, r.top() + 6, r.right() - tx, r.height() / 2 - 4), title, t["tx"], 13, True,
                  Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        draw_text(painter, QRectF(tx, cy + 2, r.right() - tx, r.height() / 2 - 8), sub, t["mu"], 12, False,
                  Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        painter.restore()

    def sizeHint(self, option, index):
        s = super().sizeHint(option, index)
        return QSize(s.width(), 62)


class DailyDelegate(QStyledItemDelegate):
    """每日汇总的表:品类只在每段第一行写(带颜色点),段和段之间一条线;「这天发了」画进度条;「还差」画胶囊。"""

    CAT = {"游戏": "acc", "教育": "green", "动漫": "orange"}

    def paint(self, painter, option, index):
        t = tok()
        m = index.model()
        row, col = index.row(), index.column()
        cat = str(m.index(row, 0).data() or "")
        first = row == 0 or str(m.index(row - 1, 0).data() or "") != cat
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if col in (0, 3, 4):
            r = _cell_bg(painter, option, index)
        else:
            painter.restore()
            super().paint(painter, option, index)
            painter.save()
            r = QRectF(option.rect)
        cy = r.center().y()
        if col == 0 and first:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(t.get(self.CAT.get(cat, "mu"), t["mu"])))
            painter.drawEllipse(QRectF(r.left() + 2, cy - 4, 8, 8))
            draw_text(painter, QRectF(r.left() + 16, r.top(), r.width() - 16, r.height()), cat, t["tx"], 14, True)
        elif col == 3:
            a = int(str(index.data() or "0") or 0) if str(index.data() or "0").isdigit() else 0
            qs = str(m.index(row, 2).data() or "")
            q = int(qs) if qs.isdigit() else 0
            if q:
                bw = max(40, r.width() - 80)
                draw_bar(painter, r.left() + 4, cy, bw, a / q, t["green"] if a >= q else t["orange"], 8)
                draw_text(painter, QRectF(r.left() + bw + 12, r.top(), 70, r.height()), f"{a} / {q}",
                          t["ok"] if a >= q else t["mu"], 12, a >= q)
            else:
                draw_text(painter, QRectF(r.left() + 4, r.top(), r.width(), r.height()), f"{a} 条", t["mu"], 12)
        elif col == 4:
            txt = str(index.data() or "")
            if txt:
                draw_pill(painter, r.left() + 4, cy, txt, tone_of(txt), r.width() - 8)
        if first and row > 0:
            painter.setPen(QPen(QColor(t["line"]), 1))
            painter.drawLine(option.rect.topLeft(), option.rect.topRight())
        painter.restore()

    def sizeHint(self, option, index):
        s = super().sizeHint(option, index)
        return QSize(s.width(), 38)


class RecDelegate(QStyledItemDelegate):
    """数据记录「每一条」:标题(粗)+ 下面一行「号 · 员工 · 发布时间 · 备注」合成一格(用户 2026-10-18 看草图定的);
    日期淡一点;状态胶囊。号 / 员工 / 时间 / 备注那几列还在(藏着),右键、测试、导出照旧。"""

    def paint(self, painter, option, index):
        col = index.column()
        if col not in (0, 3, 4):
            return super().paint(painter, option, index)
        t = tok()
        m = index.model()
        row = index.row()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = _cell_bg(painter, option, index)
        text = str(index.data() or "")
        if col == 0:
            draw_text(painter, r, text, t["mu"], 12)
        elif col == 4:
            if text:
                draw_pill(painter, r.left() + 2, r.center().y(), text, tone_of(text), r.width() - 4)
        else:
            def cell(c):
                return str(m.index(row, c).data() or "")
            when = cell(6) or (("摆好 " + cell(5)) if cell(5) else "")
            sub = " · ".join(x for x in (cell(1), cell(2), when, cell(7)) if x)
            draw_text(painter, QRectF(r.left(), r.top() + 4, r.width(), r.height() / 2 - 2), text, t["tx"], 13, True,
                      Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
            draw_text(painter, QRectF(r.left(), r.center().y() + 2, r.width(), r.height() / 2 - 6), sub,
                      t["bad"] if cell(4) == "没发成" else t["mu"], 12, False,
                      Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        painter.restore()

    def sizeHint(self, option, index):
        s = super().sizeHint(option, index)
        return QSize(s.width(), 54)


# ---------------- 发布进度(用户 2026-10-19 选的 B:大字看整体进度 + 每秒网速 + 有趣的小字 + 小动画,自己画) ----------------
# 发布时大字下面轮着换的小字(用户 2026-10-19:「生活小科普 / 损人的搞笑段子 / 两个小人在那里对话」)
FUN_TIPS = ["小科普:香蕉其实是浆果,草莓反而不是", "小科普:章鱼有三颗心脏,难怪那么能折腾",
            "小科普:蜂蜜放三千年都不会坏,比你的计划保质期长", "小科普:人一天大约眨眼一万五千次,刚才那下也算",
            "小科普:企鹅的膝盖藏在羽毛里,它们其实一直在半蹲", "小科普:打哈欠会传染,看到这句你可能已经想打了",
            "小科普:长颈鹿一天只睡两小时左右,比打工人还拼", "小科普:水獭睡觉会手拉手,怕自己漂走",
            "小科普:喝水别等渴了再喝,感觉渴的时候身体已经缺水了", "小科普:眼睛盯屏幕 20 分钟,看 6 米外 20 秒,护眼",
            "小科普:蜗牛可以一觉睡三年,别学", "小科普:猫一天能睡十几个小时,它们才是真正的摸鱼大师"]
FUN_ROAST = ["进度条:我在走了,你别催,你催我也不会变快", "网速表示:我已经尽力了,剩下的交给命运",
             "这速度,跟你周一早上起床差不多", "别盯着看了,盯着它也不会快,去喝口水吧",
             "上传中…这点耐心都没有,怎么当运营", "电脑风扇在呼呼转,它也在为你的 KPI 奋斗",
             "发完这批,今天的工作量就能拿出去吹了", "你负责摸鱼,我负责发视频,分工明确",
             "老板路过的话,记得把表情调成「很忙」", "别担心,发不出去的不是你,是网"]
FUN_TALK = [("小企鹅", "这条怎么这么重?", "小飞机", "装的是你今天的 KPI"),
            ("小企鹅", "还有多久到?", "小飞机", "快了,前面在排队检票"),
            ("小企鹅", "你飞慢点,我晕机", "小飞机", "你是企鹅,本来就不会飞"),
            ("小企鹅", "外面网好卡啊", "小飞机", "嘘,别让老板听见"),
            ("小企鹅", "这个标题有点长", "小飞机", "没事,企鹅号装得下"),
            ("小企鹅", "封面带了吗?", "小飞机", "带了带了,还擦了擦"),
            ("小企鹅", "我们发完能下班吗?", "小飞机", "我能,你不行"),
            ("小企鹅", "这一批好多啊", "小飞机", "多好,说明素材管够"),
            ("小企鹅", "要是没发成怎么办?", "小飞机", "再点一下「再发一次没发成的」就好"),
            ("小企鹅", "你说人类在干嘛?", "小飞机", "在等我们,顺便摸鱼")]
_FUN_SEEN: list[str] = []


def fun_line() -> str:
    """随便挑一句(科普 / 段子 / 两个小人对话),最近出现过的先不挑。"""
    import random
    pool = FUN_TIPS + FUN_ROAST + [f"{a}:{x}    {b}:{y}" for a, x, b, y in FUN_TALK]
    left = [x for x in pool if x not in _FUN_SEEN] or pool
    s = random.choice(left)
    _FUN_SEEN.append(s)
    del _FUN_SEEN[:-12]
    return s


class PlaneTrack(QWidget):
    """进度条 + 一架小纸飞机沿着它飞(上下轻轻晃);发完飞机停在终点变绿。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self._v, self._phase, self.running, self.done = 0.0, 0.0, False, False
        self._t = QTimer(self)
        self._t.setInterval(33)
        self._t.timeout.connect(self._tick)

    def set_value(self, v: float):
        v = max(0.0, min(1.0, float(v)))
        if self.isVisible():
            animate(self, "v", self._v, v, 500, self._set)
        else:
            self._set(v)

    def _set(self, v):
        self._v = float(v)
        self.update()

    def set_running(self, on: bool):
        self.running = on
        (self._t.start if on else self._t.stop)()
        self.update()

    def _tick(self):
        self._phase += 0.12
        self.update()

    def paintEvent(self, _e):
        import math
        t = tok()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        h, y = 10, self.height() - 8
        x0, w = 14, self.width() - 28
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(t["soft"]))
        p.drawRoundedRect(QRectF(x0, y - h / 2, w, h), h / 2, h / 2)
        col = QColor(t["green"] if self.done else t["acc"])
        if self._v > 0:
            p.setBrush(col)
            p.drawRoundedRect(QRectF(x0, y - h / 2, max(h, w * self._v), h), h / 2, h / 2)
        if self.running:                                  # 进度条上一道亮光慢慢扫过去
            sx = x0 + (self._phase * 40) % max(1, w * max(self._v, 0.02))
            g = QColor("#ffffff")
            g.setAlpha(70)
            p.setBrush(g)
            p.drawRoundedRect(QRectF(sx, y - h / 2, 26, h), h / 2, h / 2)
        px = x0 + w * self._v
        bob = math.sin(self._phase) * 3 if self.running else 0
        f = QFont(ICON_FONT)
        f.setPixelSize(18)
        p.setFont(f)
        p.setPen(col)
        p.drawText(QRectF(px - 11, y - h / 2 - 26 + bob, 22, 22), Qt.AlignmentFlag.AlignCenter, GLYPH["send"])
        p.end()


class Spark(QWidget):
    """小波浪线:最近十几秒的网速。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(64, 20)
        self.vals: list[float] = []

    def push(self, v: float):
        self.vals = (self.vals + [max(0.0, v)])[-16:]
        self.update()

    def paintEvent(self, _e):
        if len(self.vals) < 2:
            return
        from PySide6.QtGui import QPainterPath
        t = tok()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        top = max(self.vals) or 1
        n = len(self.vals)
        path = QPainterPath()
        for k, v in enumerate(self.vals):
            pt = QPointF(k * (self.width() - 2) / (n - 1) + 1, self.height() - 2 - v / top * (self.height() - 4))
            path.moveTo(pt) if k == 0 else path.lineTo(pt)
        p.setPen(QPen(QColor(t["acc"]), 1.6))
        p.drawPath(path)
        p.end()


class BusyDots(QWidget):
    """三个一跳一跳的小点:正在干活。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(26, 14)
        self._p = 0.0
        self._t = QTimer(self)
        self._t.setInterval(40)
        self._t.timeout.connect(lambda: (setattr(self, "_p", self._p + 0.15), self.update()))

    def showEvent(self, e):
        self._t.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._t.stop()
        super().hideEvent(e)

    def paintEvent(self, _e):
        import math
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QColor(tok()["acc"])
        for k in range(3):
            s = (math.sin(self._p - k * 0.8) + 1) / 2
            c.setAlphaF(0.3 + 0.7 * s)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c)
            p.drawEllipse(QRectF(2 + k * 8, 6 - s * 3, 5, 5))
        p.end()


class Confetti(QWidget):
    """发完撒一把彩带(1.6 秒),盖在大字区上面,不挡鼠标。"""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        import random
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setGeometry(parent.rect())
        t = tok()
        cols = [t["acc"], t["green"], t["orange"], "#f5b800", t["danger"]]
        w = max(1, parent.width())
        self.ps = [(random.uniform(0, w), random.uniform(-40, 0), random.uniform(-40, 40), random.uniform(160, 300),
                    random.uniform(0, 360), random.uniform(-500, 500), cols[k % len(cols)], random.uniform(0, 0.4))
                   for k in range(46)]
        self._k = 0.0
        self.show()
        self.raise_()
        animate(self, "fall", 0.0, 1.0, 1700, self._set, self.deleteLater, QEasingCurve.Type.Linear)

    def _set(self, k):
        self._k = float(k)
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for x, y, vx, vy, rot, vr, col, delay in self.ps:
            k = max(0.0, (self._k - delay) / (1 - delay))
            if k <= 0:
                continue
            c = QColor(col)
            c.setAlphaF(max(0.0, 1 - k * k))
            p.save()
            p.translate(x + vx * k, y + vy * k * 1.6 + 120 * k * k)
            p.rotate(rot + vr * k)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c)
            p.drawRoundedRect(QRectF(-3, -5, 6, 10), 2, 2)
            p.restore()
        p.end()


class PubStrip(QWidget):
    """大字下面那块:纸飞机进度条 + 一排小标签(每秒网速 + 小波浪线 / 正在发哪条 / 成功 / 没发成 / 还要多久)。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        self.track = PlaneTrack()
        v.addWidget(self.track)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.spd_w = QFrame()
        self.spd_w.setObjectName("chip")
        sh = QHBoxLayout(self.spd_w)
        sh.setContentsMargins(12, 3, 12, 3)
        sh.setSpacing(8)
        self.spd = QLabel("↑ — MB/s")
        self.spd.setObjectName("chipText")
        self.spd.setMinimumWidth(96)
        sh.addWidget(self.spd)
        self.spark = Spark()
        sh.addWidget(self.spark)
        row.addWidget(self.spd_w)
        self.cur = self._chip("")
        self.cur.setMaximumWidth(520)
        row.addWidget(self.cur)
        row.addStretch(1)
        self.ok = self._chip("")
        row.addWidget(self.ok)
        self.bad = self._chip("")
        row.addWidget(self.bad)
        self.eta = self._chip("")
        row.addWidget(self.eta)
        v.addLayout(row)

    @staticmethod
    def _chip(text):
        lab = QLabel(text)
        lab.setObjectName("chip")
        lab.setTextFormat(Qt.TextFormat.RichText)
        return lab

    def set_numbers(self, ok: int, bad: int, cur: str = "", eta: str = ""):
        t = tok()
        self.ok.setText(f"成功 <b style='color:{t['ok']}'>{ok}</b>")
        self.bad.setText(f"没发成 <b style='color:{t['bad'] if bad else t['mu']}'>{bad}</b>")
        self.cur.setText(cur)
        self.cur.setVisible(bool(cur))
        self.eta.setText(eta)
        self.eta.setVisible(bool(eta))

    def set_speed(self, mbps: float | None):
        if mbps is None:
            self.spd.setText("↑ — MB/s")
            return
        self.spd.setText(f"↑ {mbps:.1f} MB/s" if mbps >= 0.1 else f"↑ {mbps * 1024:.0f} KB/s")
        self.spark.push(mbps)
