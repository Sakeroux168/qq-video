"""封面预览:看每个比例的框放在哪;不满意就在大图上拖框。(只用无字的 png,jpg 有字不能用)

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
        self.title_zone = False          # 2.35:1:框下面 26% 是企鹅号的「标题区域」(会压上标题字)
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
        if self.title_zone:
            from qe.cover import TITLE_SAFE
            tz = QRectF(box.left(), box.top() + box.height() * TITLE_SAFE, box.width(), box.height() * (1 - TITLE_SAFE))
            p.fillRect(tz, QColor(30, 30, 30, 170))
            p.setPen(QColor("#ffffff"))
            p.drawText(tz, Qt.AlignmentFlag.AlignCenter, "标 题 区 域(字会压在这)")
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
        self.lab_why.setObjectName("muted")
        v.addWidget(self.lab_why)
        self.lab_src = QLabel()                          # 这张封面是哪个视频的、在哪(用户:好对一下有没有配错)
        self.lab_src.setWordWrap(True)
        self.lab_src.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        v.addWidget(self.lab_src)
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
        self.b_ai = QPushButton("2.35:1 用 AI 扩图")
        self.b_ai.setCheckable(True)
        self.b_ai.setToolTip("大头照:2.35:1 下面的标题区会挡脸。按下 = 用 AI 把画面往两边、下面扩出来(脸在标题区上面);"
                             "不按 = 切掉一点头顶。AI 一张几毛钱,偶尔会画歪,不满意点「重新扩一张」。")
        self.b_ai.clicked.connect(self.toggle_ai)
        self.b_again = QPushButton("重新扩一张")
        self.b_again.clicked.connect(self.ai_again)
        self.b_pick = QPushButton("更换封面…")
        self.b_pick.setToolTip("封面配错了:自己选一张图换上(png / jpg)。软件记着,摆的时候用你选的")
        self.b_pick.clicked.connect(self.pick_cover)
        self.b_unpick = QPushButton("用回自动配的")
        self.b_unpick.clicked.connect(lambda: self.set_cover(""))
        self.b_auto = QPushButton("恢复自动")
        self.b_auto.setToolTip("框的位置按软件自己认的来")
        self.b_auto.clicked.connect(self.reset)
        self.b_prev = QPushButton("← 上一条")
        self.b_prev.clicked.connect(lambda: self.go(-1))
        self.b_next = QPushButton("下一条 →")
        self.b_next.clicked.connect(lambda: self.go(1))
        b_ok = QPushButton("关闭")
        b_ok.clicked.connect(self.accept)
        bar.addWidget(self.b_pick)
        bar.addWidget(self.b_unpick)
        bar.addWidget(self.b_ai)
        bar.addWidget(self.b_again)
        bar.addWidget(self.b_auto)
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
        self._vpm = QPixmap(v.vcover) if getattr(v, "vcover", "") else QPixmap()     # 竖的比例用的竖屏图
        self._wide = None
        self.canvas.set_image(self.pm)
        self.lab_title.setText(f"{self.i + 1}/{len(self.videos)}  视频:{v.title}")
        self.lab_why.setText(v.cover_why)
        self.b_unpick.setVisible(bool(self.adj.own_cover(v.path)))
        self.b_prev.setEnabled(self.i > 0)
        self.b_next.setEnabled(self.i < len(self.videos) - 1)
        self.refresh()

    def pix_for(self, k) -> QPixmap:
        """这个比例用哪张图:竖的比例有竖屏图用竖屏图;2.35:1 要专用图就用专用图;别的用横图。"""
        _tag, r = C.RATIOS[k]
        if r < 1 and not self._vpm.isNull():
            return self._vpm
        if r >= 2 and not self.pm.isNull() and C.needs_wide(self.pm.width(), self.pm.height(), self.v.plan):
            if self._wide is None:
                from PySide6.QtWidgets import QApplication, QMessageBox
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                try:
                    self._wide = QPixmap(C.wide_cover(self.v.cover, self.v.plan))
                except Exception as e:
                    self._wide = QPixmap()
                    QApplication.restoreOverrideCursor()
                    QMessageBox.warning(self, "AI 扩图", f"AI 扩图没成:{e}。先用原图显示;摆的时候会改成切掉一点头顶。")
                else:
                    QApplication.restoreOverrideCursor()
            if not self._wide.isNull():
                return self._wide
        return self.pm

    @staticmethod
    def cover_title(path: str) -> str:
        """封面的「标题」:封面工具出的图(横屏16x9.png / 竖屏9x16.png / 修改 (1).png)看它所在的文件夹名,别的看文件名。"""
        import os
        import re
        stem = os.path.splitext(os.path.basename(path))[0]
        if re.match(r"^(横屏|竖屏|修改|原图)", stem):
            return os.path.basename(os.path.dirname(path))
        return stem

    def show_src(self):
        """标题下面:这个比例用的是哪张图、那张图叫什么、在哪;名字和视频标题对不上标红。"""
        import html
        from qe.folders import norm_name
        v = self.v
        if not v.cover:
            self.lab_src.setText("<span style='color:#c00'>这条没有封面</span>(点「更换封面…」自己选一张)")
            return
        _tag, r = C.RATIOS[self.ratio_i]
        pm = self.pix_for(self.ratio_i)
        if pm is self._vpm:
            path, what = v.vcover, "竖图"
        elif pm is not self.pm:
            path, what = v.cover, "AI 扩图,底图"
        else:
            path, what = v.cover, "图"
        t = self.cover_title(path)
        bad = norm_name(t) != norm_name(v.title)
        own = self.adj.own_cover(v.path)
        self.lab_src.setText(
            f"封面({what}):<b style='color:{'#c00' if bad else '#1a7f37'}'>{html.escape(t)}</b>"
            + (" <span style='color:#c00'>⚠ 和视频标题对不上,看一眼是不是配错了</span>" if bad and not own else "")
            + (" <span style='color:#1a7f37'>(你自己换的)</span>" if own else "")
            + f"<br><span style='color:#666'>位置:{html.escape(path)}</span>")

    def pick_cover(self):
        import os
        from PySide6.QtWidgets import QFileDialog
        start = os.path.dirname(self.v.cover or self.v.path)
        p, _ = QFileDialog.getOpenFileName(self, f"给「{self.v.title[:30]}」换封面", start, "图片 (*.png *.jpg *.jpeg *.webp)")
        if p:
            self.set_cover(os.path.normpath(p))

    def set_cover(self, path: str):
        """换成人选的图(空 = 用回自动配的),重新定框。"""
        v = self.v
        self.adj.use_own(v)                             # 先记下自动配的那张
        self.adj.set_own_cover(v.path, path)
        v.cover_kind = ""
        self.adj.use_own(v)                             # 换上人选的 / 用回自动的
        C.decide(v)
        self.adj.apply(v)
        C.note_wide(v)
        self.show_video()
        self.changed.emit(self.i)

    def rect_for(self, k):
        _tag, r = C.RATIOS[k]
        pm = self.pix_for(k)
        if pm is self._vpm:
            return C.crop_rect(pm.width() or 1, pm.height() or 1, r, self.v.vplan)
        if pm is not self.pm:
            return (0.0, 0.0, float(pm.width()), float(pm.height()))      # 专用图就是 2.35:1,框 = 整张图
        return C.crop_rect(self.pm.width() or 1, self.pm.height() or 1, r, self.v.plan)

    def refresh(self):
        for k, b in enumerate(self.r_btns):
            tag, _r = C.RATIOS[k]
            b.setChecked(k == self.ratio_i)
            b.setText(tag + ("  ✎" if C.rkey(_r) in (self.v.plan or {}).get("manual", {}) else ""))
            if not self.pm.isNull():
                x, y, w, h = self.rect_for(k)
                th = self.pix_for(k).copy(int(x), int(y), int(w), int(h)).scaled(150, 110, Qt.AspectRatioMode.KeepAspectRatio,
                                                                          Qt.TransformationMode.SmoothTransformation)
                b.setIcon(th)
                b.setIconSize(th.size())
        if not self.pm.isNull():
            pm = self.pix_for(self.ratio_i)
            if pm is not self.canvas.pm:
                self.canvas.set_image(pm)
            self.canvas.title_zone = C.RATIOS[self.ratio_i][1] >= 2
            self.canvas.set_rect(self.rect_for(self.ratio_i))
            wide = pm is not self.pm and pm is not self._vpm
            self.canvas.setEnabled(not wide)
            self.lab_why.setText(self.v.cover_why)
        mode = C.wide_mode(self.pm.width() or 1, self.pm.height() or 1, self.v.plan)[0] if not self.pm.isNull() else "none"
        has_face = bool((self.v.plan or {}).get("faces"))
        self.b_ai.setEnabled(has_face and mode != "manual")
        self.b_ai.setChecked(mode == "ai")
        self.b_again.setEnabled(mode == "ai")
        self.show_src()

    def pick_ratio(self, k):
        self.ratio_i = k
        self.refresh()

    # ---- 改 ----
    def _dragged(self):
        pm = self.canvas.pm
        if pm.isNull() or (pm is not self.pm and pm is not self._vpm):
            return
        x, y, w, h = self.canvas.rect_img
        cx, cy = (x + w / 2) / pm.width(), (y + h / 2) / pm.height()
        _tag, r = C.RATIOS[self.ratio_i]
        v = self.v
        vert = pm is self._vpm
        self.adj.set_box(v.path, v.vcover if vert else v.cover, C.rkey(r), cx, cy)
        key = "vplan" if vert else "plan"
        man = dict((getattr(v, key) or {}).get("manual", {}))
        man[C.rkey(r)] = [cx, cy]
        setattr(v, key, dict(getattr(v, key) or {}, manual=man))
        v.warn = False
        if "手动" not in v.cover_why:
            v.cover_why += "(框手动调过)"
        self.lab_why.setText(v.cover_why)
        self.refresh()
        self.changed.emit(self.i)

    def toggle_ai(self, on: bool):
        v = self.v
        self.adj.set_ai235(v.path, bool(on))
        self.adj.apply(v)
        C.note_wide(v)
        self._wide = None
        self.pick_ratio(2)                          # 跳到 2.35:1 看效果
        self.changed.emit(self.i)

    def ai_again(self):
        """AI 扩的不满意:删掉这张,再扩一张。"""
        try:
            C.cache_file("2.35专用封面", self.v.cover, "_2.35_AI.jpg").unlink(missing_ok=True)
        except OSError:
            pass
        self._wide = None
        self.pick_ratio(2)

    def reset(self):
        v = self.v
        self.adj.reset(v.path)
        v.cover_kind = ""
        C.decide(v)
        C.note_wide(v)
        self.show_video()
        self.changed.emit(self.i)

    def go(self, d):
        self.i = min(max(self.i + d, 0), len(self.videos) - 1)
        self.show_video()
