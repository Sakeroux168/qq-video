"""封面预览:看软件选的横 / 竖封面、每个比例的框放在哪;不满意就在大图上拖框,或者换横 / 竖。

用户:「做一个预览封面 我好看他选的 不行咋滴就让我手动在这个软件里面拖拽裁剪位置」
框的大小和企鹅号一样(尽量大),位置用 qe.cover.crop_rect 算 —— 和摆的时候真去拖的是同一个算法,看到的就是摆出来的。
"""
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from qe import cover as C


class CropCanvas(QWidget):
    """大图 + 一个能拖的框(框外面压暗)。框的位置用图的像素记。"""
    released = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pm = QPixmap()
        self.iw = self.ih = 1
        self.rect_img = (0.0, 0.0, 1.0, 1.0)
        self._drag = None
        self.setMinimumSize(560, 380)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def set_image(self, pm: QPixmap):
        self.pm = pm
        self.iw, self.ih = max(1, pm.width()), max(1, pm.height())
        self.update()

    def set_rect(self, r):
        self.rect_img = tuple(float(x) for x in r)
        self.update()

    def _geom(self):
        s = min(self.width() / self.iw, self.height() / self.ih)
        ox, oy = (self.width() - self.iw * s) / 2, (self.height() - self.ih * s) / 2
        return s, ox, oy

    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#2b2b2b"))
        if self.pm.isNull():
            p.setPen(QColor("#ddd"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "没有封面图")
            return
        s, ox, oy = self._geom()
        img = QRectF(ox, oy, self.iw * s, self.ih * s)
        p.drawPixmap(img, self.pm, QRectF(0, 0, self.iw, self.ih))
        x, y, w, h = self.rect_img
        box = QRectF(ox + x * s, oy + y * s, w * s, h * s)
        dim = QColor(0, 0, 0, 150)
        p.fillRect(QRectF(img.left(), img.top(), img.width(), box.top() - img.top()), dim)
        p.fillRect(QRectF(img.left(), box.bottom(), img.width(), img.bottom() - box.bottom()), dim)
        p.fillRect(QRectF(img.left(), box.top(), box.left() - img.left(), box.height()), dim)
        p.fillRect(QRectF(box.right(), box.top(), img.right() - box.right(), box.height()), dim)
        p.setPen(QPen(QColor("#FFD400"), 3))
        p.drawRect(box)

    def mousePressEvent(self, e):
        s, ox, oy = self._geom()
        self._drag = (e.position(), self.rect_img)
        self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, e):
        if not self._drag:
            return
        s, ox, oy = self._geom()
        start, (x, y, w, h) = self._drag
        d: QPointF = e.position() - start
        nx = min(max(x + d.x() / s, 0.0), self.iw - w)
        ny = min(max(y + d.y() / s, 0.0), self.ih - h)
        self.rect_img = (nx, ny, w, h)
        self.update()

    def mouseReleaseEvent(self, _e):
        if self._drag:
            self._drag = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.released.emit()


class CoverDialog(QDialog):
    """一条一条看封面。changed(下标) 发给主窗口刷新那一行。"""
    changed = Signal(int)

    def __init__(self, videos: list, index: int, adj, parent=None):
        super().__init__(parent)
        self.videos, self.i, self.adj = videos, index, adj
        self.ratio_i = 0
        self.setWindowTitle("封面预览")
        self.resize(1100, 680)
        v = QVBoxLayout(self)
        self.lab_title = QLabel()
        self.lab_title.setWordWrap(True)
        self.lab_title.setStyleSheet("font-size:15px;font-weight:bold")
        v.addWidget(self.lab_title)
        self.lab_why = QLabel()
        self.lab_why.setStyleSheet("color:#666")
        v.addWidget(self.lab_why)
        mid = QHBoxLayout()
        side = QVBoxLayout()
        side.addWidget(QLabel("点一个比例,在右边大图上拖框:"))
        self.r_btns = []
        for k, (tag, _r) in enumerate(C.RATIOS):
            b = QToolButton()
            b.setCheckable(True)
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            b.setMinimumWidth(170)
            b.clicked.connect(lambda _c=False, k=k: self.pick_ratio(k))
            side.addWidget(b)
            self.r_btns.append(b)
        side.addWidget(QLabel("(有的号只用前两个比例)"))
        side.addStretch(1)
        mid.addLayout(side)
        self.canvas = CropCanvas()
        self.canvas.released.connect(self._dragged)
        mid.addWidget(self.canvas, 1)
        v.addLayout(mid, 1)
        bar = QHBoxLayout()
        self.b_h = QPushButton("用横封面")
        self.b_h.clicked.connect(lambda: self.set_kind("横"))
        self.b_v = QPushButton("用竖封面")
        self.b_v.clicked.connect(lambda: self.set_kind("竖"))
        self.b_auto = QPushButton("恢复自动")
        self.b_auto.setToolTip("横竖、框的位置都按软件自己认的来")
        self.b_auto.clicked.connect(self.reset)
        self.b_prev = QPushButton("← 上一条")
        self.b_prev.clicked.connect(lambda: self.go(-1))
        self.b_next = QPushButton("下一条 →")
        self.b_next.clicked.connect(lambda: self.go(1))
        b_ok = QPushButton("关闭")
        b_ok.clicked.connect(self.accept)
        for b in (self.b_h, self.b_v, self.b_auto):
            bar.addWidget(b)
        bar.addStretch(1)
        for b in (self.b_prev, self.b_next, b_ok):
            bar.addWidget(b)
        v.addLayout(bar)
        self.show_video()

    # ---- 显示 ----
    @property
    def v(self):
        return self.videos[self.i]

    def show_video(self):
        v = self.v
        self.pm = QPixmap(v.cover) if v.cover else QPixmap()
        self.canvas.set_image(self.pm)
        self.lab_title.setText(f"{self.i + 1}/{len(self.videos)}  {v.title}")
        self.lab_why.setText(f"{v.cover_kind or '?'}封面:{v.cover_why}" + ("" if v.cover else "(这条没有封面图)"))
        self.b_h.setEnabled(bool(v.png) and v.cover_kind != "横")
        self.b_v.setEnabled(bool(v.jpg) and v.cover_kind != "竖")
        self.b_prev.setEnabled(self.i > 0)
        self.b_next.setEnabled(self.i < len(self.videos) - 1)
        self.refresh()

    def rect_for(self, k):
        _tag, r = C.RATIOS[k]
        return C.crop_rect(self.pm.width() or 1, self.pm.height() or 1, r, self.v.plan)

    def refresh(self):
        for k, b in enumerate(self.r_btns):
            tag, _r = C.RATIOS[k]
            b.setChecked(k == self.ratio_i)
            b.setText(tag + ("  ✎" if C.rkey(_r) in (self.v.plan or {}).get("manual", {}) else ""))
            if not self.pm.isNull():
                x, y, w, h = self.rect_for(k)
                th = self.pm.copy(int(x), int(y), int(w), int(h)).scaled(150, 110, Qt.AspectRatioMode.KeepAspectRatio,
                                                                          Qt.TransformationMode.SmoothTransformation)
                b.setIcon(th)
                b.setIconSize(th.size())
        if not self.pm.isNull():
            self.canvas.set_rect(self.rect_for(self.ratio_i))

    def pick_ratio(self, k):
        self.ratio_i = k
        self.refresh()

    # ---- 改 ----
    def _dragged(self):
        if self.pm.isNull():
            return
        x, y, w, h = self.canvas.rect_img
        cx, cy = (x + w / 2) / self.pm.width(), (y + h / 2) / self.pm.height()
        _tag, r = C.RATIOS[self.ratio_i]
        v = self.v
        self.adj.set_box(v.path, v.cover, C.rkey(r), cx, cy)
        man = dict((v.plan or {}).get("manual", {}))
        man[C.rkey(r)] = [cx, cy]
        v.plan = dict(v.plan or {}, manual=man)
        v.warn = False
        if "手动" not in v.cover_why:
            v.cover_why += "(框手动调过)"
        self.lab_why.setText(f"{v.cover_kind}封面:{v.cover_why}")
        self.refresh()
        self.changed.emit(self.i)

    def set_kind(self, kind):
        v = self.v
        self.adj.set_kind(v.path, kind)
        C.set_kind(v, kind)
        self.adj.apply(v)
        self.show_video()
        self.changed.emit(self.i)

    def reset(self):
        v = self.v
        self.adj.reset(v.path)
        v.cover_kind = ""
        C.decide(v)
        self.show_video()
        self.changed.emit(self.i)

    def go(self, d):
        self.i = min(max(self.i + d, 0), len(self.videos) - 1)
        self.show_video()
