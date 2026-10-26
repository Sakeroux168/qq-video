"""「去企鹅号核对」窗口(每日汇总页的按钮;用户 2026-10-23:我自己点就行,查出来哪条没发上,拎回来重发)。

每个 16 个号的号查一遍(后台,只读):软件记的已发 / 企鹅号上有的 / 审核中 / 没发上 / 软件没记的。
「没发上」的打勾,点「拎回来重发」:视频挪回原来的文件夹、记录改成没发成,去「16 个号」点刷新、发布就行。
"""
from PySide6.QtCore import QDate, QThread, Qt, Signal
from PySide6.QtWidgets import (QDateEdit, QDialog, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QListWidget, QListWidgetItem,
                               QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

from qe import apiacc, verify


class VerifyWorker(QThread):
    one = Signal(dict)          # 一个号查完:verify.check_account 的结果,或者 {nick, error}
    step = Signal(str)

    def __init__(self, rec, day: str, accounts: list[dict], parent=None, days: list[str] | None = None):
        """days = 一段日子(批量查询,用户 2026-10-26);不给 = 只查 day 这一天。"""
        super().__init__(parent)
        self.rec, self.day, self.accounts = rec, day, accounts
        self.days = days if days and len(days) > 1 else None
        self.stop = False

    def _range_one(self, a: dict) -> dict:
        """一段日子:这个号后台只翻一遍,一天一天对,再合成一行(by_day 留着导出用)。"""
        from qe import omapi
        nick = a.get("nick") or ""
        try:
            cl = omapi.Client(a["client_id"], apiacc.unseal(a["secret"]))
            per = verify.check_range(cl, self.rec, nick, self.days, edu=bool(a.get("query_only")), stopped=lambda: self.stop)
        except Exception as e:
            return {"nick": nick, "days": self.days, "edu": bool(a.get("query_only")),
                    "error": omapi.redact(str(e))[:80] if hasattr(omapi, "redact") else str(e)[:80]}
        out = {"nick": nick, "by_day": per, "days": self.days, "edu": bool(a.get("query_only")),
               "live": 0, "ours": 0, "ok": 0, "review": 0, "missing": [], "extra": []}
        for d, r in per.items():
            for k in ("live", "ours", "ok", "review"):
                out[k] += r.get(k, r["ok"] + r["review"] if k == "live" else 0)
            out["missing"] += [dict(m, day=d) for m in r.get("missing") or []]
            out["extra"] += r.get("extra") or []
        return out

    def run(self):
        from qe import omapi
        if self.days:                                    # 一段日子:几个号一起翻(一个号要翻上百页)
            import concurrent.futures as cf
            self.step.emit(f"正在查 {len(self.accounts)} 个号 {self.days[0][5:]} ~ {self.days[-1][5:]}(一个号要翻几十上百页,稍等)…")
            n = 0
            with cf.ThreadPoolExecutor(4) as ex:
                futs = [ex.submit(self._range_one, a) for a in self.accounts]
                for f in cf.as_completed(futs):
                    if self.stop:
                        return
                    n += 1
                    self.one.emit(f.result())
                    self.step.emit(f"查完 {n} / {len(self.accounts)} 个号…")
            return
        for k, a in enumerate(self.accounts):
            if self.stop:
                return
            nick = a.get("nick") or ""
            self.step.emit(f"正在查「{nick}」({k + 1} / {len(self.accounts)})…")
            try:
                cl = omapi.Client(a["client_id"], apiacc.unseal(a["secret"]))
                if a.get("query_only"):                    # 教育号:只查不发,按标题对
                    self.one.emit(verify.check_edu(cl, self.rec, nick, self.day))
                else:
                    self.one.emit(verify.check_account(cl, self.rec, nick, self.day))
            except Exception as e:
                self.one.emit({"nick": nick, "error": omapi.redact(str(e))[:80] if hasattr(omapi, "redact") else str(e)[:80]})


class VerifyDialog(QDialog):
    def __init__(self, rec, day: str, parent=None, nicks: list[str] | None = None, st=None):
        """nicks = 只查这几个号(用户 2026-10-23「再加一个指定某某号核对」);不给 = 16 个号全查。st = 设置(算应发几条)。"""
        super().__init__(parent)
        self.rec, self.day, self.st, self.nicks = rec, day, st, nicks
        self.resize(860, 640)
        v = QVBoxLayout(self)
        # 查哪天(用户 2026-10-25:「增加一个可查指定日期的核查数据」)
        top = QHBoxLayout()
        top.addWidget(QLabel("查哪天:"))
        self.d = QDateEdit()
        self.d.setCalendarPopup(True)
        self.d.setDisplayFormat("M.d")
        y0, m0, d0 = (int(x) for x in day.split("-"))
        self.d.setDate(QDate(y0, m0, d0))
        top.addWidget(self.d)
        # 批量查询(用户 2026-10-26:「比如从 10 号查到 25 号,然后导出成表格看」):「到」选成别的日子就是查一段
        top.addWidget(QLabel("到"))
        self.d2 = QDateEdit()
        self.d2.setCalendarPopup(True)
        self.d2.setDisplayFormat("M.d")
        self.d2.setDate(QDate(y0, m0, d0))
        self.d2.setToolTip("只查一天:跟前面选同一天。查一段:选到哪天(最多 31 天),查完能导出成企业微信那张表的样子")
        top.addWidget(self.d2)
        b = QPushButton("查")
        b.clicked.connect(lambda: self.start(self.d.date().toString("yyyy-MM-dd"), self.d2.date().toString("yyyy-MM-dd")))
        top.addWidget(b)
        top.addStretch(1)
        v.addLayout(top)
        edu_n = len(apiacc.qload())
        self.lab = QLabel("只是去企鹅号读一下,不发、不删。" + (f"教育号 {edu_n} 个一起查(按标题对)。" if edu_n else
                          "教育号还没取钥匙,查不了(左下角「设置」→「登录取钥匙…」选教育号,扫一次码就行)。"))
        self.lab.setObjectName("muted")
        self.lab.setWordWrap(True)
        v.addWidget(self.lab)
        self.t = QTableWidget(0, 8)                       # 用户 2026-10-24:改成 应发 / 实发 / 还差,再说哪些是假发成功
        self.t.setHorizontalHeaderLabels(["号", "应发", "实发(企鹅号上)", "还差", "软件记的已发", "假发成功", "审核中 / 定时没到点", "软件没记的"])
        self.t.verticalHeader().setVisible(False)
        self.t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        v.addWidget(self.t, 2)
        v.addWidget(QLabel("假发成功:软件里记成已发、企鹅号这天的列表里没有的(打勾的拎回来重发;「看一眼再决定」的没打勾):"))
        self.miss = QListWidget()
        v.addWidget(self.miss, 2)
        self.lab_extra = QLabel("")
        self.lab_extra.setObjectName("muted")
        self.lab_extra.setWordWrap(True)
        v.addWidget(self.lab_extra)
        h = QHBoxLayout()
        self.lab_done = QLabel("")
        h.addWidget(self.lab_done, 1)
        self.b_back = QPushButton("拎回来重发")
        self.b_back.setObjectName("primary")
        self.b_back.setEnabled(False)
        self.b_back.clicked.connect(self.pull_back)
        h.addWidget(self.b_back)
        self.b_xls = QPushButton("导出表格…")
        self.b_xls.setToolTip("导出成企业微信表那个样子:品类 / 账号名称 / 规定视频条数 / 每天实发(企鹅号上核实的;没查成的号标灰、用软件记录)。\n"
                              "查的是一段日子:每天一列,另外一页列出没发上的视频")
        self.b_xls.setEnabled(False)
        self.b_xls.clicked.connect(self.export)
        h.addWidget(self.b_xls)
        b = QPushButton("关闭")
        b.clicked.connect(self.close)
        h.addWidget(b)
        v.addLayout(h)
        self.w = None
        self.start(day)

    def start(self, day: str, end: str = ""):
        """查这一天;end = 查到哪天(批量查询,含;最多 31 天)。换了日期重新查。"""
        from datetime import date, timedelta
        if self.w is not None:
            self.w.stop = True
            for sig in (self.w.one, self.w.step, self.w.finished):
                try:
                    sig.disconnect()
                except (RuntimeError, TypeError):
                    pass
            self.w.wait(5000)
        end = end or day
        if end < day:
            day, end = end, day
        d0, d1 = date.fromisoformat(day), date.fromisoformat(end)
        if (d1 - d0).days > 30:
            d1 = d0 + timedelta(days=30)
            end = d1.isoformat()
            self.d2.setDate(QDate(d1.year, d1.month, d1.day))
        self.days = [(d0 + timedelta(days=k)).isoformat() for k in range((d1 - d0).days + 1)]
        self.day = day
        self.by_day = {}
        span = f"{day} ~ {end}" if len(self.days) > 1 else day
        self.setWindowTitle(f"去企鹅号核对 · {span}" + (f" · {'、'.join(self.nicks)}" if self.nicks else ""))
        self.t.setRowCount(0)
        self.miss.clear()
        self.lab_extra.setText("")
        self.b_back.setEnabled(False)
        self.b_xls.setEnabled(False)
        self.rows, self.extra, self.results = [], [], {}
        accs = apiacc.check_accounts()                   # 16 个号 + 取了钥匙的教育号(只查不发)
        if self.nicks:
            accs = [a for a in accs if a.get("nick") in self.nicks]
        if not accs:
            self.lab_done.setText("这个号还没有钥匙(教育号:设置里「登录取钥匙…」选它,扫一次码)" if self.nicks else "还没有 16 个号的账号(去设置里搬账号)")
            self.w = None
            return
        self.w = VerifyWorker(self.rec, day, accs, self, days=self.days)
        self.w.step.connect(self.lab_done.setText)
        self.w.one.connect(self._one)
        self.w.finished.connect(self._end)
        self.w.start()

    def export(self):
        """导出成企业微信表那个样子(用户 2026-10-25 截图)。"""
        import os
        from qe import verify
        if self.st is None:
            return
        y, m, d = (int(x) for x in self.day.split("-"))
        many = len(getattr(self, "days", [])) > 1
        name = f"企鹅号发布数据_{m}月{d}日" + (f"-{int(self.days[-1][5:7])}月{int(self.days[-1][8:10])}日" if many else "")
        start = os.path.join(os.path.expanduser("~"), "Desktop", name + ".xlsx")
        p, _ = QFileDialog.getSaveFileName(self, "导出表格", start, "Excel 表格 (*.xlsx)")
        if not p:
            return
        try:
            if many:
                verify.export_range_xlsx(p, self.st, self.rec, self.days, self.by_day)
            else:
                verify.export_xlsx(p, self.st, self.rec, self.day, self.results)
        except OSError as e:
            QMessageBox.warning(self, "导出表格", f"存不了(文件是不是正开着?):{e.strerror or e}")
            return
        self.lab_done.setText(f"导出好了:{p}")

    def _one(self, r: dict):
        s = self.sender()
        if s is not None and s is not self.w:                 # 上一次查询(换了日期)排着队的结果:丢掉
            return
        self.results[r["nick"]] = r
        if r.get("by_day"):
            self.by_day[r["nick"]] = r["by_day"]
        k = self.t.rowCount()
        self.t.insertRow(k)
        q = 0
        if self.st is not None:
            from qe import plan
            q = sum(plan.quota_on(self.st, r["nick"], d) for d in (r.get("days") or [self.day]))
        need = sum(1 for m in r.get("missing") or [] if m.get("sure", True))      # 要补的(打勾的)
        look = len(r.get("missing") or []) - need                                     # 看一眼的 / 已经补发过的
        short = over = 0
        if r.get("error"):
            vals = [r["nick"], str(q or ""), "", "", "", f"查不了:{r['error']}", "", ""]
        else:
            live = r.get("live", r["ok"] + r["review"])
            if self.st is not None and r.get("by_day"):     # 一段日子:一天一天算少发 / 多发再加起来(审查:一天多 5 一天少 5 不能显示 ✓)
                from qe import plan
                for d, x in r["by_day"].items():
                    qd = plan.quota_on(self.st, r["nick"], d)
                    if qd:
                        short += max(0, qd - x.get("live", 0))
                        over += max(0, x.get("live", 0) - qd)
            elif q:
                short, over = max(0, q - live), max(0, live - q)
            diff = ((str(short) if short else "") + (("、" if short else "") + f"多发 {over}" if over else "")) or ("✓" if q else "")
            vals = [r["nick"], str(q) if q else "—", str(live), diff, str(r["ours"]),
                    (str(need) if need else "✓") + (f"(+{look} 看一眼)" if look else ""),
                    str(r["review"]) if r["review"] else "", str(len(r["extra"])) if r["extra"] else ""]
        for c, t in enumerate(vals):
            it = QTableWidgetItem(t)
            if c:
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.t.setItem(k, c, it)
        if need or look or short or r.get("error"):
            from gui.theme import cur
            from PySide6.QtGui import QBrush, QColor
            for c in range(8):
                self.t.item(k, c).setBackground(QBrush(QColor(cur()["rows"]["red" if need or r.get("error") else "yellow"])))
        for m in r.get("missing") or []:
            when = f"{int(m['day'][5:7])}.{int(m['day'][8:10])} · " if m.get("day") else ""
            it = QListWidgetItem(f"{m['account']} · {when}{m['title']} —— {m['why']}")
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if m.get("sure", True) else Qt.CheckState.Unchecked)
            it.setData(Qt.ItemDataRole.UserRole, len(self.rows))
            self.rows.append(m)
            self.miss.addItem(it)
        self.extra += [(r["nick"], e) for e in r.get("extra") or []]

    def _end(self):
        s = self.sender()
        if s is not None and s is not self.w:                 # 上一次查询的「查完了」:不算
            return
        n = len(self.rows)
        sure = sum(1 for m in self.rows if m.get("sure", True))
        self.lab_done.setText((f"查完了:{sure} 条要补(打了勾)" + (f",{n - sure} 条要你看一眼(没打勾)" if n > sure else ""))
                              if n else "查完了:软件记的已发,企鹅号上都有 ✓")
        self.b_back.setText("拎回来重发(打勾的)" if n else "拎回来重发")
        self.b_back.setEnabled(bool(n))
        self.b_xls.setEnabled(self.st is not None)
        if self.extra:
            self.lab_extra.setText(f"企鹅号上{'这段日子' if len(getattr(self, 'days', [])) > 1 else '这天'}还有 {len(self.extra)} 条软件没记的(手动发的 / 别的软件发的,不用管):" +
                                   ";".join(f"{n} · {e['title'][:20]}" for n, e in self.extra[:8]) + ("…" if len(self.extra) > 8 else ""))

    def pull_back(self):
        """打勾的:视频挪回原来的文件夹、记录改成没发成。"""
        from qe import redo
        busy = redo.busy_reason(self)
        if busy:
            QMessageBox.information(self, "拎回来重发", busy)
            return
        done, bad, room, warn = 0, [], 0, []
        for k in range(self.miss.count()):
            it = self.miss.item(k)
            if it.checkState() != Qt.CheckState.Checked or it.data(Qt.ItemDataRole.UserRole + 1):
                continue
            row = self.rows[it.data(Qt.ItemDataRole.UserRole)]
            if self.st is not None:
                # 用「找视频重发」那套,连封面挪回今天的文件夹(用户 2026-10-26:16 个号原来挪回老的日期文件夹,今天的页面看不到):
                # 教育号 = 素材盘今天的日期文件夹(结构照原样);16 个号 = 今天这个号发视频的文件夹(手选过就是手选的那个)
                from qe import redo
                from qe.config import bj_now
                n = bj_now()
                out = {}
                _new, why = redo.pull_back(self.st, self.rec, row, f"{n.month}.{n.day}", out)
                room += out.get("room", 0)                    # 补发不占今天的规定条数(额度在 pull_back 里加,同一条只加一次)
                warn += out.get("warn") or []
            else:
                why = verify.pull_back(self.rec, row)
            if why:
                bad.append(f"{row['title'][:20]}:{why}")
                it.setText(it.text() + f"  ✗ {why}")
            else:
                done += 1
                it.setText("✓ 拎回来了 · " + it.text())
                it.setData(Qt.ItemDataRole.UserRole + 1, True)
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
        self.lab_done.setText(f"拎回来 {done} 条(改成没发成;挪回今天的文件夹)→ 去那页刷新、再发" +
                              (f";{len(bad)} 条没拎回来" if bad else "") +
                              (f";补发的 {room} 条今天另外加了额度,不占今天的规定条数" if room else "") +
                              (";" + ";".join(warn[:3]) if warn else ""))
        self.b_back.setEnabled(False)
        w = self.parent()
        while w is not None and not hasattr(w, "api_tab"):
            w = w.parent()
        if w is not None and done:
            try:
                w.api_tab.load()
                w._load_dates()
            except Exception:
                pass

    def _stop(self):
        if self.w is not None and self.w.isRunning():
            self.w.stop = True
            self.w.wait(3000)

    def closeEvent(self, e):
        self._stop()
        super().closeEvent(e)

    def reject(self):                                      # 按 Esc 关窗口也停下后台查询(审查 2026-10-26:原来接着翻几百页)
        self._stop()
        super().reject()
