"""「今天」页(用户 2026-10-18):打开软件先看总的 —— 今天还差多少条没发、游戏 / 教育 / 动漫各发了多少(圆环)、
下一步该干什么(点一下跳过去)、今天已经发了哪几批。

用户说的用法:周一到周六一般分好几批发;周末一般定时 → 周末「下一步」第一条是定时。
这一页只看、只跳转,不发任何东西。"""
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy,
                               QVBoxLayout, QWidget)

from qe import plan
from qe.config import bj_now
from gui.widgets import Bar, GLYPH, ICON_FONT, Ring, fade_in, glyph_label, roll, tok

WEEK = "一二三四五六日"
CAT_ICON = {"游戏": ("game", "acc"), "教育": ("school", "green"), "动漫": ("movie", "orange")}


class TodayTab(QWidget):
    def __init__(self, st, rec, main, parent=None):
        super().__init__(parent)
        self.st, self.rec, self.main = st, rec, main
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(sa)
        body = QWidget()
        body.setObjectName("page")
        sa.setWidget(body)
        v = QVBoxLayout(body)
        v.setContentsMargins(32, 26, 32, 20)
        v.setSpacing(14)

        self.lab_day = QLabel("")
        self.lab_day.setObjectName("heroMeta")
        v.addWidget(self.lab_day)
        self.big = QLabel("")
        self.big.setObjectName("heroBig")
        self.big.setStyleSheet("font-size:34px;")
        self.big.setTextFormat(Qt.TextFormat.RichText)
        v.addWidget(self.big)
        self.bar = Bar(10)
        v.addWidget(self.bar)
        row = QHBoxLayout()
        self.lab_sent = QLabel("")
        self.lab_sent.setObjectName("heroSub")
        row.addWidget(self.lab_sent)
        row.addStretch(1)
        self.lab_eta = QLabel("")
        self.lab_eta.setObjectName("heroSub")
        row.addWidget(self.lab_eta)
        v.addLayout(row)

        # 三个圆环:游戏 / 教育 / 动漫,点了去「每日汇总」
        self.rings_w = QWidget()
        rl = QHBoxLayout(self.rings_w)
        rl.setContentsMargins(0, 4, 0, 0)
        rl.setSpacing(12)
        self.rings: dict[str, tuple] = {}
        for cat in ("游戏", "教育", "动漫"):
            icon, colkey = CAT_ICON[cat]
            card = QPushButton()
            card.setObjectName("ringCard")
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card.setToolTip("点这里:去「每日汇总」看每个号")
            card.setMinimumHeight(92)
            card.setStyleSheet(f"QPushButton#ringCard{{background:{tok()['card']};border:1px solid {tok()['line']};border-radius:16px;"
                               f"text-align:left;}} QPushButton#ringCard:hover{{border-color:{tok()['acc']};}}")
            card.clicked.connect(lambda: self.main.goto("daily"))
            h = QHBoxLayout(card)
            h.setContentsMargins(16, 12, 16, 12)
            h.setSpacing(14)
            ring = Ring(60, 7, tok()[colkey])
            ring.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            h.addWidget(ring)
            tv = QVBoxLayout()
            tv.setSpacing(0)
            name = QLabel(f"{GLYPH[icon]}")
            t1 = QHBoxLayout()
            t1.setSpacing(6)
            ic = glyph_label(icon, tok()[colkey], 15)
            t1.addWidget(ic)
            name = QLabel(cat)
            name.setObjectName("secTitle")
            t1.addWidget(name)
            t1.addStretch(1)
            tv.addLayout(t1)
            num = QLabel("")
            num.setStyleSheet("font-size:24px;font-weight:bold;")
            num.setTextFormat(Qt.TextFormat.RichText)
            tv.addWidget(num)
            left = QLabel("")
            left.setObjectName("heroSub")
            tv.addWidget(left)
            h.addLayout(tv, 1)
            for w in (ic, name, num, left):
                w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            rl.addWidget(card, 1)
            self.rings[cat] = (ring, num, left, card)
        v.addWidget(self.rings_w)

        two = QHBoxLayout()
        two.setSpacing(12)
        self.box_next, self.next_v = self._box("bulb", tok()["orange"], "下一步")
        self.box_hist, self.hist_v = self._box("history", tok()["acc"], "今天发了这几批")
        two.addWidget(self.box_next, 6)
        two.addWidget(self.box_hist, 5)
        v.addLayout(two)
        v.addStretch(1)
        self._first = True

    def _box(self, icon, color, title):
        f = QFrame()
        f.setObjectName("panel")
        f.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        bv = QVBoxLayout(f)
        bv.setContentsMargins(16, 14, 16, 14)
        bv.setSpacing(6)
        h = QHBoxLayout()
        h.setSpacing(8)
        h.addWidget(glyph_label(icon, color, 16))
        t = QLabel(title)
        t.setObjectName("secTitle")
        h.addWidget(t)
        h.addStretch(1)
        bv.addLayout(h)
        inner = QVBoxLayout()
        inner.setSpacing(2)
        bv.addLayout(inner)
        bv.addStretch(1)
        return f, inner

    @staticmethod
    def _clear(lay):
        while lay.count():
            it = lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
            elif it.layout() is not None:
                TodayTab._clear(it.layout())

    # ---------------- 数据 ----------------
    def refresh(self, animate_: bool = True):
        t = tok()
        now = bj_now()
        day = plan.today()
        weekend = now.weekday() >= 5
        self.lab_day.setText(f"{now.month} 月 {now.day} 日 · 星期{WEEK[now.weekday()]} · "
                             + ("周末一般用定时" if weekend else "平日分批发"))
        s = plan.summary(self.rec, self.st, day)
        tq, ta = s["total"]
        left = max(0, tq - ta)
        acc = t["acc"]
        fmt = (f"今天还差 <span style='color:{acc}'>{{}}</span> 条没发" if left else "今天的都发够了 √")
        if left:
            if animate_:
                roll(self.big, left, fmt, 1100, frm=tq)
            else:
                self.big.setText(fmt.format(left))
        else:
            self.big.setText(fmt)
        self.bar.set_value(ta / tq if tq else 0, animate_)
        self.lab_sent.setText(f"今天已发 {ta} / {tq} 条(按发出去的时间算)")
        cats = {g["cat"]: (q, a) for g, (_lab, q, a) in zip(plan.plan(self.st), s["rows"])}
        for cat, (ring, num, lab, _card) in self.rings.items():
            q, a = cats.get(cat, (0, 0))
            ring.set_value(a / q if q else 0, animate_)
            num.setText(f"{a}<span style='font-size:13px;font-weight:normal;color:{t['mu']}'> / {q}</span>")
            lab.setText("够了 √" if q and a >= q else f"还差 {q - a} 条" if q else "没有规定条数")
        self._fill_next(weekend)
        eta = self._fill_hist(day)
        self.lab_eta.setText(eta)
        if animate_:
            for k, w in enumerate((self.rings_w, self.box_next, self.box_hist)):
                fade_in(w, 420, 80 + k * 90)

    def _next_row(self, icon, color, bg, title, sub, fn, btn: str = ""):
        t = tok()
        b = QPushButton()
        b.setObjectName("nextBtn")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setMinimumHeight(52)
        b.clicked.connect(fn)
        h = QHBoxLayout(b)
        h.setContentsMargins(8, 6, 8, 6)
        h.setSpacing(10)
        ic = QLabel(GLYPH[icon])
        ic.setFixedSize(32, 32)
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet(f"background:{bg};color:{color};border-radius:9px;font-family:'{ICON_FONT}';font-size:15px;")
        h.addWidget(ic)
        tv = QVBoxLayout()
        tv.setSpacing(0)
        a = QLabel(title)
        a.setObjectName("secTitle")
        tv.addWidget(a)
        if sub:
            c = QLabel(sub)
            c.setObjectName("heroSub")
            tv.addWidget(c)
        h.addLayout(tv, 1)
        if btn:
            go = QLabel(btn)
            go.setStyleSheet(f"background:{t['acc']};color:#ffffff;border-radius:14px;padding:5px 14px;font-weight:bold;")
            h.addWidget(go)
        else:
            go = QLabel(GLYPH["right"])
            go.setStyleSheet(f"font-family:'{ICON_FONT}';font-size:12px;color:{t['mu']};")
            h.addWidget(go)
        for w in b.findChildren(QLabel):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.next_v.addWidget(b)

    def _fill_next(self, weekend: bool):
        t = tok()
        self._clear(self.next_v)
        m = self.main
        api = m.api_tab
        rows = []
        # 教育号:摆好了等人去罐头点发布 → 最要紧
        if m.batch_id:
            acc = m.batch_videos[0].account if m.batch_videos else ""
            rows.append(("school", t["green"], t["ok_bg"], f"教育号:「{acc}」这批摆好了",
                         "去罐头点「发布 → 全部发布」,回来点「这批发好了」", lambda: m.goto("edu"), "去看看"))
        # 16 个号
        n_ok = n_bad = 0
        if api.videos:
            for i in range(len(api.videos)):
                if api._sent(i):
                    continue
                if api._can_send(i):
                    n_ok += 1
                elif api.videos[i].checks:
                    from qe import checks
                    if checks.problems(api.videos[i]):
                        n_bad += 1
        d = api.day()
        tag = f"16 个号({d})" if d else "16 个号"
        lab = api.sched.label() if hasattr(api, "sched") else ""
        if lab:
            rows.append(("clock", t["acc"], t["acc_bg"], f"{tag}:定好时间了", lab.lstrip("⏰ "), lambda: m.goto("api"), ""))
        elif n_ok:
            if weekend:
                rows.append(("clock", t["acc"], t["acc_bg"], f"{tag}:定好时间,到点自动发", f"{n_ok} 条能发 · 周末一般用定时",
                             lambda: (m.goto("api"), api.schedule_clicked()), "定时…"))
            else:
                rows.append(("send", t["acc"], t["acc_bg"], f"{tag}:接着发下一批", f"{n_ok} 条能发 → 点「现在发布」",
                             lambda: m.goto("api"), "去发"))
        elif not d:
            rows.append(("game", t["acc"], t["acc_bg"], "16 个号:先选要发哪天的", "", lambda: m.goto("api"), ""))
        if n_bad:
            rows.append(("warn", t["orange"], t["warn_bg"], f"{tag}:{n_bad} 条有点小问题", "横屏 / 话题 / 水印 … 处理完能多发",
                         lambda: (m.goto("api"), api.k_bad.setChecked(True)), ""))
        # 教育号:下一批
        if not m.batch_id:
            if not m.c_date.currentData():
                rows.append(("school", t["green"], t["ok_bg"], "教育号:先选要发哪天的", "再勾上要发的员工", lambda: m.goto("edu"), ""))
            else:
                acc, vids = m.next_batch()
                if vids:
                    rows.append(("school", t["green"], t["ok_bg"],
                                 f"教育号:" + ("摆好并定时发出" if weekend else f"摆「{acc}」{len(vids)} 条"),
                                 f"「{acc}」{len(vids)} 条等着摆" if weekend else "摆好停在发布前,发布你自己点",
                                 lambda: m.goto("edu"), ""))
                elif not m.videos:
                    rows.append(("school", t["green"], t["ok_bg"], "教育号:勾上要发的员工", "", lambda: m.goto("edu"), ""))
        if not rows:
            rows.append(("done", t["ok"], t["ok_bg"], "现在没有要做的", "去「每日汇总」看看哪个号还没发够",
                         lambda: m.goto("daily"), ""))
        for r in rows[:4]:
            self._next_row(*r)

    def _fill_hist(self, day: str) -> str:
        """今天发了这几批:按时间排,两条之间隔了 20 分钟以上 / 换了「教育号 ↔ 16 个号」就算新的一批。返回右上角那句。"""
        t = tok()
        self._clear(self.hist_v)
        rows = self.rec.published_on(day)
        batches = []
        for r in rows:
            kind = "16 个号" if r["employee"] == "接口" else "教育号"
            at = str(r["published_at"] or "")
            hm = at[11:16]
            mins = int(hm[:2]) * 60 + int(hm[3:5]) if len(hm) == 5 and hm[:2].isdigit() and hm[3:5].isdigit() else -1
            if batches and batches[-1]["kind"] == kind and mins >= 0 and mins - batches[-1]["last"] <= 20:
                b = batches[-1]
            else:
                b = {"kind": kind, "start": hm, "end": hm, "ok": 0, "fail": 0, "last": mins}
                batches.append(b)
            b["end"], b["last"] = hm, mins
            b["ok" if r["status"] == "已发" else "fail"] += 1
        items = []
        for k, b in enumerate(batches, 1):
            when = b["start"] + (f"–{b['end']}" if b["end"] != b["start"] else "")
            sub = f"{b['kind']} {b['ok']} 条" + (f" · {b['fail']} 条没发成" if b["fail"] else "")
            items.append((t["ok"] if not b["fail"] else t["orange"], f"{when} 第 {k} 批", sub, "done" if not b["fail"] else "warn"))
        api = self.main.api_tab
        lab = api.sched.label() if hasattr(api, "sched") else ""
        if lab:
            items.append((t["acc"], "定时中", "16 个号 · " + lab.lstrip("⏰ "), "clock"))
        if not items:
            items.append((t["line"], "今天还没发", "发了以后这里一批一批记着", ""))
        for col, title, sub, icon in items[-6:]:
            h = QHBoxLayout()
            h.setSpacing(10)
            dot = QLabel()
            dot.setFixedSize(12, 12)
            dot.setStyleSheet(f"background:{col};border-radius:6px;")
            h.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)
            tv = QVBoxLayout()
            tv.setSpacing(0)
            a = QLabel(title)
            a.setObjectName("secTitle")
            tv.addWidget(a)
            c = QLabel(sub)
            c.setObjectName("heroSub")
            tv.addWidget(c)
            h.addLayout(tv, 1)
            if icon:
                h.addWidget(glyph_label(icon, col, 16))
            wrap = QWidget()
            wrap.setLayout(h)
            h.setContentsMargins(4, 5, 4, 5)
            self.hist_v.addWidget(wrap)
        n = sum(b["ok"] for b in batches)
        return f"今天发了 {len(batches)} 批 · {n} 条" if batches else ""

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, lambda: self.refresh(animate_=True))
