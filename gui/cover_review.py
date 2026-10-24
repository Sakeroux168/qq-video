"""「快速过封面」(用户 2026-10-19 看草图定的):一屏铺开勾上的员工里所有标黄的封面,每张带 4 个比例的小图,
一眼看出人脸在不在框里。回车 = 这张没问题(去黄)跳下一张;← → 换一张;空格 / 点一下 = 打开封面预览拖框;
「剩下的都没问题」一下子全去黄。去黄和「封面都看过了」「这张没问题」一样,记在封面调整里。
软件觉得脸可能被框切掉的,小图描橙边、写「脸好像被切了」,先看这几张。"""
from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout,
                               QWidget)

from qe import cover as C
from gui.widgets import Bar, repolish, tok


def _crops(v):
    """[(比例名, 那张图, 框, 脸会不会被切)]:和封面预览 / 摆的时候同一个算框的办法(2.35:1 不调 AI,只看原图上的框)。"""
    pm = QPixmap(v.cover) if v.cover else QPixmap()
    vpm = QPixmap(v.vcover) if getattr(v, "vcover", "") else QPixmap()
    out = []
    for tag, r in C.RATIOS:
        use_v = r < 1 and not vpm.isNull()
        img, plan = (vpm, v.vplan) if use_v else (pm, v.plan)
        if img.isNull():
            out.append((tag, img, (0, 0, 1, 1), False))
            continue
        x, y, w, h = C.crop_rect(img.width(), img.height(), r, plan or {})
        cut = False
        for f in (plan or {}).get("all") or (plan or {}).get("faces") or []:
            fx, fy, fw, fh = f[0] * img.width(), f[1] * img.height(), f[2] * img.width(), f[3] * img.height()
            ox = max(0.0, min(fx + fw, x + w) - max(fx, x))
            oy = max(0.0, min(fy + fh, y + h) - max(fy, y))
            if fw * fh > 0 and ox * oy / (fw * fh) < 0.85:          # 脸有一成半以上在框外
                cut = True
        out.append((tag, img, (x, y, w, h), cut))
    return out


class Thumb(QWidget):
    """一个比例的小图:框里那块画出来;脸可能被切了描橙边;角上写比例。"""

    def __init__(self, tag, img: QPixmap, rect, cut: bool, h: int = 112, parent=None):
        super().__init__(parent)
        x, y, w, hh = rect
        ratio = w / hh if hh else 1
        self.setFixedSize(max(28, int(h * ratio)) if ratio < 2 else int(h * 1.55), h if ratio < 2 else int(h * 1.55 / ratio))
        self.tag, self.cut = tag, cut
        self.pm = img.copy(int(x), int(y), int(w), int(hh)).scaled(self.width() * 2, self.height() * 2,
                                                                     Qt.AspectRatioMode.IgnoreAspectRatio,
                                                                     Qt.TransformationMode.SmoothTransformation) if not img.isNull() else QPixmap()

    def paintEvent(self, _e):
        from PySide6.QtGui import QPainterPath
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(r, 7, 7)
        p.setClipPath(path)
        if self.pm.isNull():
            p.fillRect(r, QColor(tok()["soft"]))
        else:
            p.drawPixmap(r, self.pm, QRectF(self.pm.rect()))
        p.setClipping(False)
        if self.cut:
            p.setPen(QPen(QColor(tok()["orange"]), 2.5))
            p.drawRoundedRect(r, 7, 7)
        f = p.font()
        f.setPixelSize(11)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(0, 0, 0, 160))
        p.drawText(r.adjusted(5, 0, 0, -3).translated(1, 1), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, self.tag)
        p.setPen(QColor("#ffffff"))
        p.drawText(r.adjusted(5, 0, 0, -3), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, self.tag)
        p.end()


class Card(QFrame):
    clicked = Signal(int)

    def __init__(self, k: int, v, parent=None):
        super().__init__(parent)
        self.k, self.v = k, v
        self.setObjectName("rvCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)
        top = QHBoxLayout()
        self.title = QLabel(v.title)
        self.title.setStyleSheet("font-weight:bold;font-size:13px;")
        self.title.setMinimumWidth(10)
        top.addWidget(self.title, 1)
        self.pill = QLabel("")
        self.pill.setFixedHeight(22)
        top.addWidget(self.pill)
        lay.addLayout(top)
        self.row = QHBoxLayout()
        self.row.setSpacing(6)
        lay.addLayout(self.row)
        self.why = QLabel("")
        self.why.setObjectName("muted")
        self.why.setWordWrap(True)
        lay.addWidget(self.why)
        self.build()

    def build(self):
        while self.row.count():
            it = self.row.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        cs = _crops(self.v)
        for tag, img, rect, cut in cs:
            self.row.addWidget(Thumb(tag, img, rect, cut), 0, Qt.AlignmentFlag.AlignBottom)
        self.row.addStretch(1)
        self.cut = any(c for *_x, c in cs)
        self.update_state("ok" if not self.v.warn else "")

    def update_state(self, state: str):
        t = tok()
        self.state = state
        if state == "ok":
            txt, fg, bg = "没问题 √", t["ok"], t["ok_bg"]
        else:
            txt, fg, bg = "标黄", t["warn"], t["warn_bg"]
        self.pill.setText(txt)
        self.pill.setStyleSheet(f"background:{bg};color:{fg};border-radius:10px;padding:1px 9px;font-weight:bold;font-size:12px;")
        self.why.setText(self.v.cover_why + (f" · <b style='color:{t['warn']}'>脸好像被切了</b>" if self.cut and state != "ok" else ""))
        repolish(self, st=state or "todo")

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.k)
        super().mouseReleaseEvent(e)


class QuickReview(QDialog):
    """changed(视频) 发给主窗口刷新那一行。"""
    changed = Signal(object)

    def __init__(self, videos: list, adj, parent=None):
        super().__init__(parent)
        t = tok()
        self.vs, self.adj, self.cur = videos, adj, 0
        self.setWindowTitle("快速过封面")
        scr = (parent.screen() if parent is not None else None) or self.screen()
        ag = scr.availableGeometry() if scr else None
        self.resize(min(1080, ag.width() - 40) if ag else 1080, min(760, ag.height() - 40) if ag else 760)   # 小屏别顶出屏幕
        self.setStyleSheet(
            f"QFrame#rvCard {{ background:{t['card']}; border:2px solid {t['line2']}; border-radius:14px; }}"
            f" QFrame#rvCard[st='todo'] {{ border-color:{t['line']}; }}"
            f" QFrame#rvCard[on='true'] {{ border-color:{t['acc']}; background:{t['acc_bg']}; }}"
            f" QFrame#rvCard[st='ok'] QLabel {{ color:{t['dim']}; }}"
            f" QLabel#kbd {{ border:1px solid {t['line']}; border-bottom-width:2px; border-radius:5px; padding:0 6px;"
            f" background:{t['card']}; color:{t['tx2']}; font-size:12px; }}")
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 14)
        v.setSpacing(10)
        top = QHBoxLayout()
        title = QLabel("快速过封面")
        title.setObjectName("pageTitle")
        top.addWidget(title)
        sub = QLabel("勾上的员工里标黄的封面")
        sub.setObjectName("muted")
        top.addWidget(sub)
        top.addStretch(1)
        self.bar = Bar(8)
        self.bar.setFixedWidth(240)
        top.addWidget(self.bar)
        self.lab_n = QLabel("")
        self.lab_n.setObjectName("muted")
        top.addWidget(self.lab_n)
        v.addLayout(top)
        keys = QHBoxLayout()
        keys.setSpacing(6)
        for k, txt in (("回车", "没问题,跳下一张"), ("← →", "换一张"), ("空格 / 点一下", "进去拖框")):
            kb = QLabel(k)
            kb.setObjectName("kbd")
            keys.addWidget(kb)
            lab = QLabel(txt)
            lab.setObjectName("muted")
            keys.addWidget(lab)
            keys.addSpacing(10)
        keys.addStretch(1)
        self.b_all = QPushButton("剩下的都没问题")
        self.b_all.setToolTip("还标黄的这些都算看过了、没问题:不再标黄,自动发布 / 定时发布不会再为它们停下来")
        self.b_all.clicked.connect(self.all_ok)
        keys.addWidget(self.b_all)
        b_close = QPushButton("看完了")
        b_close.setObjectName("primary")
        b_close.clicked.connect(self.accept)
        keys.addWidget(b_close)
        for b in (self.b_all, b_close):                  # 按钮不抢键盘:回车 / 空格 / 方向键都归这一页
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setAutoDefault(False)
        v.addLayout(keys)
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.Shape.NoFrame)
        sa.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.sa = sa
        body = QWidget()
        body.setObjectName("page")
        self.grid = QGridLayout(body)
        self.grid.setSpacing(12)
        self.grid.setContentsMargins(2, 2, 2, 2)
        sa.setWidget(body)
        v.addWidget(sa, 1)
        self.tip = QLabel("")
        self.tip.setObjectName("muted")
        self.tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.tip)
        self.cards: list[Card] = []
        self._k = 0
        QTimer.singleShot(0, self._add_more)                 # 小图一张张做,窗口先出来不卡
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _add_more(self):
        """一次做几张卡片(读大图、裁小图要点时间),做完再做下一批。"""
        for _ in range(4):
            if self._k >= len(self.vs):
                break
            c = Card(self._k, self.vs[self._k])
            c.clicked.connect(self.open_one)
            self.grid.addWidget(c, self._k // 2, self._k % 2)
            self.cards.append(c)
            self._k += 1
        self._mark()
        if self._k < len(self.vs):
            QTimer.singleShot(0, self._add_more)

    def _mark(self):
        n = sum(1 for c in self.cards if c.state == "ok") + sum(1 for v in self.vs[len(self.cards):] if not v.warn)
        total = len(self.vs)
        for c in self.cards:
            repolish(c, on="true" if c.k == self.cur else "false")
        self.bar.set_value(n / total if total else 1, animate_=False)
        self.lab_n.setText(f"标黄 {total} 张 · 看过 {n} · 剩 {total - n}")
        self.tip.setText("都看完了:这些不再标黄,自动发布不会再为它们停下来" if total and n == total else
                         "没问题就按回车;脸被切了的点一下进去拖框")
        if 0 <= self.cur < len(self.cards):
            self.sa.ensureWidgetVisible(self.cards[self.cur], 20, 40)

    def _ok(self, k: int):
        v = self.vs[k]
        if v.warn:
            self.adj.set_ok(v.path, v.cover, title=v.title)
            v.warn = False
            if "人看过" not in v.cover_why:
                v.cover_why += "(人看过了)"
            self.changed.emit(v)
        if k < len(self.cards):
            self.cards[k].update_state("ok")

    def _next(self):
        n = len(self.cards)
        for d in range(1, n + 1):
            j = (self.cur + d) % n
            if self.cards[j].state != "ok":
                self.cur = j
                return

    def keyPressEvent(self, e):
        k = e.key()
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.cards:
            self._ok(self.cur)
            self._next()
            self._mark()
        elif k == Qt.Key.Key_Right and self.cards:
            self.cur = min(len(self.cards) - 1, self.cur + 1)
            self._mark()
        elif k == Qt.Key.Key_Left and self.cards:
            self.cur = max(0, self.cur - 1)
            self._mark()
        elif k == Qt.Key.Key_Space and self.cards:
            self.open_one(self.cur)
        else:
            super().keyPressEvent(e)

    def open_one(self, k: int):
        """打开那张的封面预览拖框;关掉回来刷新小图(拖过框的软件会自己去黄)。"""
        self.cur = k
        self._mark()
        from gui.cover_dialog import CoverDialog
        d = CoverDialog(self.vs, k, self.adj, self)
        d.changed.connect(lambda i: self.changed.emit(self.vs[i]))
        d.exec()
        for c in self.cards:                              # 预览里可能翻到别的、拖了别的,都刷新一下
            c.build()
        self._mark()
        self.setFocus()

    def all_ok(self):
        left = [c.k for c in self.cards if c.state != "ok"] + list(range(len(self.cards), len(self.vs)))
        left = [k for k in left if self.vs[k].warn]
        if not left:
            return
        from gui.api_tab import ask
        if not ask(self, "剩下的都没问题", f"还标黄的 {len(left)} 张都算看过了、没问题?\n\n点了以后它们不再标黄,自动发布 / 定时发布不会再为它们停下来。",
                   "都没问题", "我再看看"):
            return
        for k in left:
            self._ok(k)
        self._mark()
