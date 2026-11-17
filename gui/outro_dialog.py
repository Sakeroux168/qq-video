"""「剪掉结尾」剪前预览框(用户 2026-11-16:软件把结尾那几秒剪掉，照样发，剪前给我看，原片留底)。

每条视频一行：
- 左边图：保留到这一帧（start - 0.25s）；
- 右边图：从这一帧剪掉（start + 0.35s）；
- 右边可勾要不要剪、微调从第几秒开始剪（-0.5秒 / +0.5秒 或直接改秒数），也能直接点「这不是求关注,放行」。
点「剪掉选中的 N 条」返回 [(row, start_sec), ...]。
"""
import os
import threading

from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QCheckBox, QDialog, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from qe import outrocheck, vertical
from gui import theme


def _to_pixmap(im, max_w: int = 128, max_h: int = 160) -> QPixmap:
    if im is None:
        return QPixmap()
    im = im.convert("RGB")
    im.thumbnail((max_w * 2, max_h * 2))
    data = im.tobytes("raw", "RGB")
    qim = QImage(data, im.width, im.height, im.width * 3, QImage.Format.Format_RGB888).copy()
    return QPixmap.fromImage(qim).scaled(max_w, max_h, Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation)


class _ThumbWorker(QThread):
    """按请求队列在后台取帧，关闭对话框时立刻停下。"""
    got = Signal(int, float, object, object)        # row, start, left_pm, right_pm

    def __init__(self, grab_fn, parent=None):
        super().__init__(parent)
        self._grab = grab_fn
        self._cv = threading.Condition()
        self._pending: dict[int, tuple[str, float, float]] = {}
        self._order: list[int] = []
        self._stop = False

    def request(self, idx: int, path: str, start: float, dur: float):
        with self._cv:
            self._pending[idx] = (path, start, dur)
            if idx not in self._order:
                self._order.append(idx)
            self._cv.notify()

    def stop(self):
        with self._cv:
            self._stop = True
            self._pending.clear()
            self._order.clear()
            self._cv.notify_all()

    def run(self):
        ff = "" if self._grab else vertical.ffmpeg_path()
        grab = self._grab or (lambda p, t: outrocheck.grab_frame(ff, p, t))
        while True:
            with self._cv:
                while not self._order and not self._stop:
                    self._cv.wait(0.2)
                if self._stop:
                    return
                idx = self._order.pop(0)
                item = self._pending.pop(idx, None)
            if not item:
                continue
            path, start, dur = item
            keep_t = max(0.0, start - 0.25)
            cut_t = min(max(0.0, dur - 0.08), start + 0.35) if dur > 0 else start + 0.35
            try:
                im1 = grab(path, keep_t)
                im2 = grab(path, cut_t)
            except Exception:
                im1 = im2 = None
            with self._cv:
                if self._stop:
                    return
                if idx in self._pending:             # 人又调了秒数:这一帧过时了,不刷
                    continue
            self.got.emit(idx, start, _to_pixmap(im1), _to_pixmap(im2))


class OutroDialog(QDialog):
    def __init__(self, items: list[dict], parent=None, on_ok=None, grab_fn=None):
        """items: [{"row", "title", "account", "path", "start", "dur", "kind", "reason", "shot"}, ...]。"""
        super().__init__(parent)
        self.items = [dict(x) for x in items]
        self.on_ok = on_ok
        self._cards: list[dict] = []
        self.setWindowTitle(f"剪掉求关注结尾({len(items)} 条)")
        self.resize(840, min(720, max(440, 180 + len(items) * 210)))
        v = QVBoxLayout(self)
        v.setSpacing(10)

        tip = QLabel("下面这些视频在最后几秒查到求关注 / 别人账号 / 二维码。\n"
                     "左边是保留的最后一帧（绿框），右边是要剪掉的开头（红框）。确认没切到正片再点「剪掉」；原片会留在旁边的「结尾原片」文件夹里，不删。")
        tip.setObjectName("muted")
        tip.setWordWrap(True)
        v.addWidget(tip)

        sa = QScrollArea()
        sa.setWidgetResizable(True)
        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setSpacing(10)
        t = theme.cur()

        self._worker = _ThumbWorker(grab_fn, self)
        self._worker.got.connect(self._on_thumbs)
        self._worker.start()

        for idx, x in enumerate(self.items):
            card = QFrame()
            card.setObjectName("panel")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(12, 10, 12, 10)
            cl.setSpacing(8)

            top = QHBoxLayout()
            chk = QCheckBox(f"【{x['account']}】{x['title']}")
            chk.setChecked(True)
            chk.setStyleSheet("font-weight:bold;")
            chk.toggled.connect(self._update_btn)
            top.addWidget(chk, 1)
            why = x.get("kind") or "求关注"
            if x.get("reason"):
                why += f" · {x['reason']}"
            lab_why = QLabel(why)
            lab_why.setObjectName("muted")
            top.addWidget(lab_why)
            cl.addLayout(top)

            mid = QHBoxLayout()
            mid.setSpacing(12)

            def _pic_col(title_txt: str, border_color: str):
                box = QVBoxLayout()
                box.setSpacing(3)
                pic = QLabel("载入中…")
                pic.setFixedSize(134, 166)
                pic.setAlignment(Qt.AlignmentFlag.AlignCenter)
                pic.setStyleSheet(f"border:2px solid {border_color};border-radius:8px;background:{t['soft']};")
                cap = QLabel(title_txt)
                cap.setObjectName("muted")
                cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
                box.addWidget(pic)
                box.addWidget(cap)
                return box, pic, cap

            b_left, p_left, c_left = _pic_col(f"保留到 {outrocheck.fmt_time(max(0.0, x['start'] - 0.25))}", t["ok"])
            b_right, p_right, c_right = _pic_col(f"剪掉 {outrocheck.fmt_time(x['start'])}", t["bad"])
            mid.addLayout(b_left)
            arr = QLabel("→")
            arr.setStyleSheet("font-size:18px;font-weight:bold;")
            mid.addWidget(arr)
            mid.addLayout(b_right)

            ctrl = QVBoxLayout()
            ctrl.setSpacing(8)
            lab_cut = QLabel("")
            lab_cut.setStyleSheet("font-weight:bold;font-size:14px;")
            lab_cut.setWordWrap(True)
            ctrl.addWidget(lab_cut)

            row_adj = QHBoxLayout()
            row_adj.addWidget(QLabel("从第"))
            sp = QDoubleSpinBox()
            dur = float(x.get("dur") or 0)
            sp.setDecimals(2)
            sp.setSingleStep(0.25)
            sp.setRange(0.35, max(0.5, dur - 0.15) if dur > 0.5 else 9999.0)
            sp.setValue(float(x["start"]))
            sp.setSuffix(" 秒")
            row_adj.addWidget(sp)
            b_m = QPushButton("-0.5秒")
            b_p = QPushButton("+0.5秒")
            row_adj.addWidget(b_m)
            row_adj.addWidget(b_p)
            row_adj.addStretch(1)
            ctrl.addLayout(row_adj)

            acts = QHBoxLayout()
            b_open = QPushButton("看原视频")
            b_open.clicked.connect(lambda _c=False, p=x["path"]: os.startfile(p) if os.path.isfile(p) else None)
            b_ok = QPushButton("这不是求关注,放行")
            acts.addWidget(b_open)
            acts.addWidget(b_ok)
            acts.addStretch(1)
            ctrl.addLayout(acts)
            ctrl.addStretch(1)
            mid.addLayout(ctrl, 1)
            cl.addLayout(mid)
            wl.addWidget(card)

            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(180)
            rec = {"idx": idx, "item": x, "chk": chk, "sp": sp, "lab_cut": lab_cut,
                   "p_left": p_left, "p_right": p_right, "c_left": c_left, "c_right": c_right,
                   "timer": timer, "released": False, "b_ok": b_ok, "card": card}
            self._cards.append(rec)

            def _refresh_text(r=rec):
                s = r["sp"].value()
                d0 = float(r["item"].get("dur") or 0)
                gone = max(0.0, d0 - s) if d0 > 0 else 0.0
                r["lab_cut"].setText(f"从 {outrocheck.fmt_time(s)} 剪到最后" + (f"（剪掉 {gone:.1f} 秒）" if gone else ""))
                r["c_left"].setText(f"保留到 {outrocheck.fmt_time(max(0.0, s - 0.25))}")
                r["c_right"].setText(f"剪掉 {outrocheck.fmt_time(s)}")

            def _changed(_v=0.0, r=rec, rf=_refresh_text):
                rf()
                r["timer"].start()

            def _req(r=rec):
                self._worker.request(r["idx"], r["item"]["path"], r["sp"].value(), float(r["item"].get("dur") or 0))

            def _release(_c=False, r=rec):
                if self.on_ok:
                    self.on_ok(r["item"]["row"])
                r["released"] = True
                r["chk"].setChecked(False)
                r["chk"].setEnabled(False)
                r["sp"].setEnabled(False)
                r["b_ok"].setEnabled(False)
                r["b_ok"].setText("已放行")
                r["lab_cut"].setText("已标为「结尾没问题」，这次不剪")
                self._update_btn()

            sp.valueChanged.connect(_changed)
            timer.timeout.connect(_req)
            b_m.clicked.connect(lambda _c=False, s=sp: s.setValue(s.value() - 0.5))
            b_p.clicked.connect(lambda _c=False, s=sp: s.setValue(s.value() + 0.5))
            b_ok.clicked.connect(_release)
            _refresh_text()
            self._worker.request(idx, x["path"], float(x["start"]), dur)

        wl.addStretch(1)
        sa.setWidget(wrap)
        v.addWidget(sa, 1)

        bot = QHBoxLayout()
        self.lab_sel = QLabel("")
        self.lab_sel.setObjectName("muted")
        bot.addWidget(self.lab_sel, 1)
        b_all = QPushButton("全选 / 全不选")
        b_all.clicked.connect(self._toggle_all)
        b_no = QPushButton("先不剪")
        b_no.clicked.connect(self.reject)
        self.b_go = QPushButton("剪掉")
        self.b_go.setObjectName("danger")
        self.b_go.clicked.connect(self.accept)
        bot.addWidget(b_all)
        bot.addWidget(b_no)
        bot.addWidget(self.b_go)
        v.addLayout(bot)
        self._update_btn()

    def _on_thumbs(self, idx: int, _start: float, pm1: QPixmap, pm2: QPixmap):
        if not (0 <= idx < len(self._cards)):
            return
        r = self._cards[idx]
        r["p_left"].setPixmap(pm1) if not pm1.isNull() else r["p_left"].setText("读不出")
        r["p_right"].setPixmap(pm2) if not pm2.isNull() else r["p_right"].setText("读不出")

    def _toggle_all(self):
        act = [r for r in self._cards if not r["released"]]
        want = not all(r["chk"].isChecked() for r in act)
        for r in act:
            r["chk"].setChecked(want)

    def _update_btn(self):
        n = sum(1 for r in self._cards if not r["released"] and r["chk"].isChecked())
        tot = sum(1 for r in self._cards if not r["released"])
        self.lab_sel.setText(f"选中了 {n} / {tot} 条")
        self.b_go.setText(f"剪掉选中的 {n} 条")
        self.b_go.setEnabled(n > 0)

    def chosen(self) -> list[tuple[int, float]]:
        return [(r["item"]["row"], round(float(r["sp"].value()), 2))
                for r in self._cards if not r["released"] and r["chk"].isChecked()]

    def _stop_worker(self):
        if getattr(self, "_worker", None):
            self._worker.stop()
            self._worker.wait(2000)

    def closeEvent(self, e):
        self._stop_worker()
        super().closeEvent(e)

    def done(self, r):
        self._stop_worker()
        super().done(r)
