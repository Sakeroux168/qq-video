"""内置 AI 助手界面(用户 2026-11-26):
同时提供左侧全屏页与右侧可收起抽屉，共用同一个 AssistantHub（同一份对话历史与后台线程），
切页或收起抽屉都不会丢对话。
"""
from __future__ import annotations

import time

from PySide6.QtCore import QEvent, QObject, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from gui import theme as TH
from qe import aplog, assistant as A, redo


class _TaskWorker(QThread):
    progress = Signal(str)
    finished_ok = Signal(dict)
    finished_err = Signal(str)

    def __init__(self, agent: A.AssistantAgent, mode: str, arg, parent=None):
        super().__init__(parent)
        self.agent = agent
        self.mode = mode
        self.arg = arg
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            cb = lambda msg: self.progress.emit(str(msg))
            st = lambda: self._stop
            if self.mode == "ask":
                res = self.agent.ask(self.arg, on_progress=cb, stopped=st)
            elif self.mode == "quick":
                res = self.agent.run_quick(self.arg, on_progress=cb, stopped=st)
            elif self.mode == "action":
                res = self.agent.execute_action(self.arg, on_progress=cb, stopped=st)
            else:
                res = {"reply": "不支持的模式", "actions": [], "mutated": False}
            self.finished_ok.emit(res)
        except Exception as e:
            self.finished_err.emit(str(e))


class AutopilotLogDialog(QDialog):
    """全自动运行留痕查看窗口：按日期浏览每一步执行时间与结果，支持一键筛选只看异常/失败/跳过。"""

    def __init__(self, day_iso: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("全自动留痕日志")
        self.resize(860, 560)
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(QLabel("日期："))
        self.c_day = QComboBox()
        days = aplog.list_days(30)
        want_day = (day_iso or "").strip() or (days[0] if days else aplog.log_path().stem)
        if want_day and want_day not in days:
            days = [want_day] + days
        for d in days:
            self.c_day.addItem(d, d)
        idx = self.c_day.findData(want_day)
        if idx >= 0:
            self.c_day.setCurrentIndex(idx)
        self.c_day.currentIndexChanged.connect(lambda _i: self.reload())
        top.addWidget(self.c_day)

        self.k_err = QCheckBox("只看异常 / 失败 / 跳过")
        self.k_err.toggled.connect(lambda _c: self.reload())
        top.addWidget(self.k_err)

        self.ed_acc = QLineEdit()
        self.ed_acc.setPlaceholderText("按账号或关键词筛选…")
        self.ed_acc.setFixedWidth(180)
        self.ed_acc.textChanged.connect(lambda _t: self.reload())
        top.addWidget(self.ed_acc)
        top.addStretch(1)

        self.k_live = QCheckBox("实时刷新")
        self.k_live.setChecked(True)
        self.k_live.toggled.connect(self._toggle_live)
        top.addWidget(self.k_live)

        b_ref = QPushButton("刷新")
        b_ref.clicked.connect(lambda: self.reload(force=True))
        top.addWidget(b_ref)
        b_open = QPushButton("打开原文件")
        b_open.clicked.connect(self._open_file)
        top.addWidget(b_open)
        v.addLayout(top)

        self.ed_log = QPlainTextEdit()
        self.ed_log.setReadOnly(True)
        self.ed_log.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        v.addWidget(self.ed_log, 1)

        bot = QHBoxLayout()
        self.lab_info = QLabel("")
        self.lab_info.setObjectName("muted")
        self.lab_info.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        bot.addWidget(self.lab_info, 1)
        b_close = QPushButton("关闭")
        b_close.setObjectName("primary")
        b_close.clicked.connect(self.accept)
        bot.addWidget(b_close)
        v.addLayout(bot)
        self._last_sig = None
        self._live_timer = QTimer(self)
        self._live_timer.setInterval(1500)
        self._live_timer.timeout.connect(lambda: self.reload(force=False))
        self._live_timer.start()
        self.reload(force=True)

    def _toggle_live(self, on: bool):
        if on:
            self._live_timer.start()
        else:
            self._live_timer.stop()

    def closeEvent(self, e):
        if self._live_timer.isActive():
            self._live_timer.stop()
        super().closeEvent(e)

    def reload(self, force: bool = True):
        day = str(self.c_day.currentData() or "")
        err_on = self.k_err.isChecked()
        acc_q = self.ed_acc.text().strip()
        res = aplog.read(day, errors_only=err_on, account=acc_q, limit=1500)
        sig = (day, err_on, acc_q, res["total_lines"], len(res["lines"]))
        if not force and sig == self._last_sig:
            return
        self._last_sig = sig
        self._cur_path = res["path"]
        if res["text"]:
            self.ed_log.setPlainText(res["text"])
            sb = self.ed_log.verticalScrollBar()
            sb.setValue(sb.maximum())
        else:
            self.ed_log.setPlainText(
                "这一天还没有异常/跳过记录。" if err_on and res["total_lines"] else "这一天还没有全自动运行留痕记录。"
            )
        self.lab_info.setText(f"共 {res['total_lines']} 行，当前显示 {len(res['lines'])} 行 · {res['path']}")

    def _open_file(self):
        import os
        p = getattr(self, "_cur_path", "")
        if p and os.path.isfile(p):
            try:
                os.startfile(p)
            except OSError:
                pass


_STAGE_MAP = {"①": 1, "②": 2, "③": 3, "④": 4, "⑤": 5, "⑥": 6}


class AssistantHub(QObject):
    """全屏页与右侧抽屉共用的对话中心。"""
    message_added = Signal(object)
    cleared = Signal()
    card_updated = Signal()
    watch_status_changed = Signal(object)
    live_changed = Signal(object)
    _live_log_sig = Signal(str, str)
    key_alert = Signal(str)
    status_changed = Signal(str)
    busy_changed = Signal(bool)
    data_changed = Signal()

    def __init__(self, st, rec, owner: QWidget | None = None, chat_fn=None, deps: dict | None = None):
        super().__init__(owner)
        self.st = st
        self.rec = rec
        self.owner = owner
        self.agent = A.AssistantAgent(st, rec, chat_fn=chat_fn, deps=deps)
        self.messages: list[dict] = []
        self._worker: _TaskWorker | None = None
        self._next_tick_at: float = 0.0
        self._live_active: bool = False
        self._live_stage: int = 0
        self._live_headline: str = ""
        self._live_lines: list[str] = []
        self._live_log_sig.connect(self._on_live_log)
        self._watch_timer = QTimer(self)
        self._watch_timer.setInterval(1000)
        self._watch_timer.timeout.connect(self._on_watch_second)

    def _aplog_listener(self, line: str, stage: str, _level: str, _acc: str, _msg: str):
        if self._live_active:
            self._live_log_sig.emit(line, stage)

    def _stage_from_text(self, text: str) -> int:
        for ch, idx in _STAGE_MAP.items():
            if ch in (text or ""):
                return idx
        return 0

    def _on_live_log(self, line: str, stage: str):
        if not self._live_active:
            return
        st_i = self._stage_from_text(stage)
        if st_i:
            self._live_stage = max(self._live_stage, st_i)
        self._live_lines.append(line)
        if len(self._live_lines) > 8:
            self._live_lines = self._live_lines[-8:]
        self.live_changed.emit(self.live_info())

    def _on_worker_progress(self, text: str):
        self.status_changed.emit(text)
        if self._live_active:
            st_i = self._stage_from_text(text)
            if st_i:
                self._live_stage = st_i
            self._live_headline = text
            self.live_changed.emit(self.live_info())

    def live_info(self) -> dict:
        return {
            "active": self._live_active,
            "stage": self._live_stage,
            "headline": self._live_headline,
            "lines": list(self._live_lines),
        }

    def is_busy(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def is_watching(self) -> bool:
        w = self.agent.watch
        return w is not None and w.active

    def watch_info(self) -> dict:
        w = self.agent.watch
        if w is None or not w.active:
            return {"active": False}
        rem = max(0, int(round(self._next_tick_at - time.time()))) if self._next_tick_at else 0
        snap = w.snapshot(self.st, self.rec)
        snap["next_in_sec"] = rem
        snap["busy"] = self.is_busy()
        return snap

    def _sync_watch_timer(self, reset_cd: bool = False):
        if self.is_watching():
            if reset_cd or self._next_tick_at <= 0:
                self._next_tick_at = time.time() + max(60, int(self.agent.watch.interval_min) * 60)
            if not self._watch_timer.isActive():
                self._watch_timer.start()
        else:
            self._next_tick_at = 0.0
            if self._watch_timer.isActive():
                self._watch_timer.stop()
        self.watch_status_changed.emit(self.watch_info())

    def _on_watch_second(self):
        if not self.is_watching():
            self._sync_watch_timer()
            return
        if not self.is_busy() and self._next_tick_at > 0 and time.time() >= self._next_tick_at:
            if self.owner is not None and redo.busy_reason(self.owner):
                # 你正好在「16 个号」页手动干活：顺延 1 分钟，绝不抢活
                self._next_tick_at = time.time() + 60
            else:
                self.watch_tick_now()
                return
        self.watch_status_changed.emit(self.watch_info())

    def watch_tick_now(self):
        if not self.is_watching() or self.is_busy():
            return
        if self.owner is not None and redo.busy_reason(self.owner):
            self._next_tick_at = time.time() + 60
            self.watch_status_changed.emit(self.watch_info())
            return
        self._start("action", {"kind": "watch_tick", "label": "全天值守巡检"}, "值守巡检中…")

    def open_log_dialog(self, day_iso: str = "", parent: QWidget | None = None):
        d = AutopilotLogDialog(day_iso=day_iso, parent=parent or self.owner)
        d.exec()

    def stop_watch(self):
        w = self.agent.watch
        if w is not None and w.active:
            w.active = False
            aplog.write("值守结束", f"用户手动结束全天值守（累计巡检 {w.rounds} 轮，自动发布 {w.total_published} 条）", level="INFO", day_iso=w.day_iso)
            self._append("assistant", f"已结束今日全天值守（累计巡检 {w.rounds} 轮，自动发布 {w.total_published} 条）。")
        self._sync_watch_timer()

    def model_label(self) -> str:
        ai = self.agent.ai_config()
        if not ai.key:
            return "未配 AI Key（快捷查仍可用）"
        return f"{ai.who} · {ai.model}"

    def _append(self, role: str, text: str, actions: list[dict] | None = None, card: dict | None = None):
        m = {"role": role, "text": text, "actions": list(actions or []), "card": card}
        self.messages.append(m)
        self.message_added.emit(m)

    def _start(self, mode: str, arg, status: str):
        if self.is_busy():
            return
        is_ap = (mode == "action" and isinstance(arg, dict) and arg.get("kind") in ("run_autopilot", "watch_tick"))
        if is_ap:
            self._live_active = True
            self._live_stage = 1
            self._live_headline = status
            self._live_lines = []
            aplog.add_listener(self._aplog_listener)
            self.live_changed.emit(self.live_info())
        w = _TaskWorker(self.agent, mode, arg, self)
        w.progress.connect(self._on_worker_progress)
        w.finished_ok.connect(self._on_ok)
        w.finished_err.connect(self._on_err)
        w.finished.connect(self._on_done)
        self._worker = w
        self.busy_changed.emit(True)
        self.status_changed.emit(status)
        w.start()

    def _on_ok(self, res: dict):
        if not res.get("quiet"):
            reply = str(res.get("reply") or "").strip()
            actions = list(res.get("actions") or [])
            card = res.get("card")
            if reply or actions or card:
                self._append("assistant", reply or "已完成。", actions, card=card)
        key_errs = list(res.get("key_errors") or [])
        if key_errs:
            detail = "；".join(f"{e.get('account')}（{e.get('error', '')[:40]}）" for e in key_errs)
            alert_msg = f"⚠ 账号密钥失效提醒：{detail}\n请到「设置 / 账号管理」重新搬账号或更新钥匙。"
            self._append("assistant", alert_msg)
            self.key_alert.emit(alert_msg)
        if res.get("mutated"):
            self.data_changed.emit()
        if res.get("watch_changed"):
            self._sync_watch_timer(reset_cd=True)
        if res.get("trigger_tick") and self.is_watching():
            QTimer.singleShot(80, self.watch_tick_now)

    def _on_err(self, err: str):
        self._append("assistant", f"出错了：{err}")

    def _on_done(self):
        if self._live_active:
            aplog.remove_listener(self._aplog_listener)
            self._live_active = False
            self._live_stage = 0
            self._live_headline = ""
            self.live_changed.emit(self.live_info())
        self.status_changed.emit("")
        self.busy_changed.emit(False)
        if self.is_watching():
            self.watch_status_changed.emit(self.watch_info())

    def send(self, text: str):
        t = (text or "").strip()
        if not t or self.is_busy():
            return
        self._append("user", t)
        self._start("ask", t, "正在请 AI 分析你的问题…")

    def quick(self, kind: str, label: str):
        if self.is_busy():
            return
        self._append("user", label)
        self._start("quick", kind, f"正在执行「{label}」…")

    def cancel_card(self, card: dict):
        if card.get("state") in ("started", "cancelled"):
            return
        card["state"] = "cancelled"
        self.card_updated.emit()

    def trigger_action(self, action: dict, card: dict | None = None):
        kind = str(action.get("kind") or "")
        if kind == "goto_page":
            page = str((action.get("payload") or {}).get("page") or "")
            if self.owner is not None and hasattr(self.owner, "goto") and page:
                self.owner.goto(page)
            return
        if kind == "open_aplog":
            day = str((action.get("payload") or {}).get("day") or "")
            self.open_log_dialog(day)
            return
        if self.is_busy():
            return
        if kind in ("pull_back", "clean_old_folders", "run_autopilot") and self.owner is not None:
            busy = redo.busy_reason(self.owner)
            if busy:
                self._append("assistant", f"暂时不能启动：{busy}")
                return
        if card is not None:
            if card.get("state") in ("started", "cancelled"):
                return
            card["state"] = "started"
            self.card_updated.emit()
        lbl = str(action.get("label") or "执行操作")
        self._append("user", f"执行：{lbl}")
        self._start("action", action, f"正在{lbl}…")

    def stop(self):
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self.status_changed.emit("正在停止，请稍等…")

    def clear(self):
        if self.is_busy():
            return
        self.messages.clear()
        self.agent.reset()
        self.cleared.emit()

    def shutdown(self):
        aplog.remove_listener(self._aplog_listener)
        self._live_active = False
        if self._watch_timer.isActive():
            self._watch_timer.stop()
        if self.agent.watch is not None:
            self.agent.watch.active = False
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(5000)


def _make_metric_tile(value: str, label: str, tone: str = "normal", tip: str = "") -> tuple[QFrame, QLabel, QLabel, str]:
    box = QFrame()
    box.setObjectName("apMetric")
    if tip:
        box.setToolTip(tip)
    lay = QVBoxLayout(box)
    lay.setContentsMargins(10, 8, 10, 8)
    lay.setSpacing(2)
    v_lbl = QLabel(value)
    v_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    l_lbl = QLabel(label)
    l_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(v_lbl)
    lay.addWidget(l_lbl)
    return box, v_lbl, l_lbl, tone


class _AutopilotConfirmCard(QFrame):
    """简洁一眼看清的「今日 16 个号全自动」确认卡片（不罗嗦、明细可折叠）。"""

    def __init__(self, card: dict, on_confirm, on_cancel, compact: bool, parent=None):
        super().__init__(parent)
        self.card = card
        self.plan = card.get("plan") or {}
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.compact = compact
        self._busy = False
        self._tiles: list[tuple[QFrame, QLabel, QLabel, str]] = []
        self.setObjectName("apCard")

        v = QVBoxLayout(self)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(10)

        # 顶栏：标题 + 日期徽章 + 状态胶囊
        top = QHBoxLayout()
        top.setSpacing(6)
        self.lab_title = QLabel(f"🚀 今日 16 个号全自动")
        top.addWidget(self.lab_title)
        self.lab_date = QLabel(self.plan.get("md") or "")
        self.lab_date.setObjectName("apTag")
        top.addWidget(self.lab_date)
        top.addStretch(1)
        self.lab_state = QLabel("待确认")
        self.lab_state.setObjectName("apState")
        top.addWidget(self.lab_state)
        v.addLayout(top)

        # 3 个核心数字卡片（一眼抓重点）
        chk = self.plan.get("checks") or {}
        en_list = list(chk.get("enabled") or [])
        dis_list = list(chk.get("disabled") or [])
        chk_tip = (
            ("已开启：" + "、".join(en_list) if en_list else "已开启：无")
            + ("\n已关闭（不触发）：" + "、".join(dis_list) if dis_list else "")
        )
        mr = QHBoxLayout()
        mr.setSpacing(8)
        for val, lbl, tone, tip in (
            (f"{self.plan.get('ready_count', 0)} 个", "参与账号", "acc", ""),
            (f"{self.plan.get('total_estimated', 0)} 条", "预计发布", "ok", ""),
            (f"{len(en_list)} 项", "已开检查", "normal", chk_tip),
        ):
            tile = _make_metric_tile(val, lbl, tone, tip)
            self._tiles.append(tile)
            mr.addWidget(tile[0], 1)
        v.addLayout(mr)

        # 一行流程条 + 检查说明
        self.lab_flow = QLabel("转竖屏  →  整理标题  →  自动发布  →  清残留  →  查漏补发(≤1轮)  →  查黑封面")
        self.lab_flow.setWordWrap(True)
        v.addWidget(self.lab_flow)

        chk_txt = (
            "按设置检查：" + " · ".join(en_list) + "（命中跳过不发，最后汇总给你拍板）"
            if en_list else
            "按设置：6 项自动检查已关闭（仍保留防重发、条数闸、违禁词保护）"
        )
        self.lab_checks = QLabel(chk_txt)
        self.lab_checks.setWordWrap(True)
        v.addWidget(self.lab_checks)

        # 准备就绪账号摘要 + 可折叠明细
        ready = list(self.plan.get("ready_accounts") or [])
        self._detail_box = None
        self.b_detail = None
        if ready:
            preview = " · ".join(f"{x['account']}({x['estimated_run']})" for x in ready[:4])
            if len(ready) > 4:
                preview += f" 等 {len(ready)} 个号"
            srow = QHBoxLayout()
            srow.setSpacing(6)
            self.lab_ready = QLabel(preview)
            self.lab_ready.setWordWrap(True)
            srow.addWidget(self.lab_ready, 1)
            self.b_detail = QPushButton("明细 ▾")
            self.b_detail.setObjectName("link")
            self.b_detail.setCursor(Qt.CursorShape.PointingHandCursor)
            self.b_detail.clicked.connect(self._toggle_detail)
            srow.addWidget(self.b_detail, 0, Qt.AlignmentFlag.AlignTop)
            v.addLayout(srow)

            self._detail_box = QLabel(
                "\n".join(
                    f"· {x['account']}：{x['folder_name'] or '今日目录'}（待发 {x['pending_count']} 条，预计发 {x['estimated_run']} 条）"
                    for x in ready
                )
            )
            self._detail_box.setWordWrap(True)
            self._detail_box.hide()
            v.addWidget(self._detail_box)
        else:
            self.lab_ready = None

        # 等待中（如「正在处理」） / 无今日夹 / 已发满（简洁一行）
        waiting = list(self.plan.get("waiting_folders") or [])
        missing = list(self.plan.get("missing_accounts") or [])
        done = list(self.plan.get("done_accounts") or [])
        notes = []
        if waiting:
            show_w = "、".join(f"{x['account']}/{x['folder_name']}" for x in waiting[:3]) + (f" 等 {len(waiting)} 个" if len(waiting) > 3 else "")
            notes.append(f"等待中(先不动)：{show_w}")
        if missing:
            show_m = "、".join(missing[:5]) + (f" 等 {len(missing)} 个" if len(missing) > 5 else "")
            notes.append(f"暂无今日文件夹：{show_m}")
        if done:
            show_d = "、".join(x["account"] for x in done[:5]) + (f" 等 {len(done)} 个" if len(done) > 5 else "")
            notes.append(f"今日已发满(跳过)：{show_d}")
        self.lab_notes = QLabel("\n".join(notes)) if notes else None
        if self.lab_notes is not None:
            self.lab_notes.setWordWrap(True)
            v.addWidget(self.lab_notes)

        # 全天值守开关（清爽单行）
        self.k_watch = QCheckBox("开启全天值守（每 10 分钟巡检新素材，发满或 22:30 自动收工）")
        self.k_watch.setChecked(True)
        self.k_watch.setToolTip("勾上：跑完现在到货的视频后，每 10 分钟安静巡检一次新素材（落稳 30 秒动手、自动读懂「正在处理 / (15)」备注）；\n取消勾选：只跑完此刻盘里已有的这一批就停。")
        self.k_watch.toggled.connect(lambda _c: self.sync_state())
        v.addWidget(self.k_watch)

        # 底部操作行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.b_start = QPushButton("🚀 确认启动全自动")
        self.b_start.setObjectName("primary")
        self.b_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_start.clicked.connect(self._clicked_start)
        self.b_cancel = QPushButton("取消")
        self.b_cancel.setObjectName("link")
        self.b_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_cancel.clicked.connect(lambda: self.on_cancel(self.card))
        btn_row.addWidget(self.b_start, 1 if compact else 0)
        btn_row.addWidget(self.b_cancel, 0)
        if not compact:
            btn_row.addStretch(1)
        v.addLayout(btn_row)

        self.sync_state()
        self.retheme()

    def _toggle_detail(self):
        if self._detail_box is None or self.b_detail is None:
            return
        vis = not self._detail_box.isVisible()
        self._detail_box.setVisible(vis)
        self.b_detail.setText("收起 ▴" if vis else "明细 ▾")

    def _clicked_start(self):
        watch_on = self.k_watch.isChecked()
        act = {
            "label": f"今日全自动{'（全天值守）' if watch_on else ''}（{self.plan.get('md', '')}）",
            "kind": "run_autopilot",
            "payload": {
                "day": self.plan.get("day_iso") or "",
                "accounts": self.plan.get("accounts_filter") or [],
                "watch": watch_on,
                "interval_min": 10,
                "cutoff_hm": "22:30",
            },
        }
        self.on_confirm(act, self.card)

    def set_busy(self, busy: bool):
        self._busy = busy
        self.sync_state()

    def sync_state(self):
        st = self.card.get("state") or "pending"
        watch_on = self.k_watch.isChecked()
        can_start = bool(self.plan.get("can_start")) if watch_on else bool(self.plan.get("can_start_once", self.plan.get("can_start")))
        if st == "started":
            self.lab_state.setText("已启动")
            self.b_start.setText("已启动")
            self.b_start.setEnabled(False)
            self.k_watch.setEnabled(False)
            self.b_cancel.setVisible(False)
        elif st == "cancelled":
            self.lab_state.setText("已取消")
            self.b_start.setEnabled(False)
            self.k_watch.setEnabled(False)
            self.b_cancel.setVisible(False)
        else:
            self.lab_state.setText("待确认" if can_start else "无可发")
            self.b_start.setText("🚀 确认启动全天值守" if watch_on else "🚀 确认启动本次全自动")
            self.b_start.setEnabled(can_start and not self._busy)
            self.k_watch.setEnabled(not self._busy)
            self.b_cancel.setEnabled(not self._busy)
            self.b_cancel.setVisible(bool(self.plan.get("can_start")))
        self.retheme()

    def retheme(self):
        t = TH.cur()
        st = self.card.get("state") or "pending"
        self.setStyleSheet(
            f"QFrame#apCard {{ background:{t['card']}; border:1px solid {t['acc']}; border-radius:14px; }}"
        )
        self.lab_title.setStyleSheet(f"font-size:14px; font-weight:bold; color:{t['tx']}; background:transparent;")
        self.lab_date.setStyleSheet(
            f"background:{t['soft']}; color:{t['tx2']}; border-radius:8px; padding:2px 8px; font-size:12px; font-weight:bold;"
        )
        st_bg, st_fg = (
            (t["ok_bg"], t["ok"]) if st == "started" else
            (t["soft"], t["dim"]) if st == "cancelled" else
            (t["acc_bg"], t["acc"])
        )
        self.lab_state.setStyleSheet(
            f"background:{st_bg}; color:{st_fg}; border-radius:9px; padding:2px 9px; font-size:11px; font-weight:bold;"
        )
        tone_map = {"acc": t["acc"], "ok": t["ok"], "warn": t["warn"], "bad": t["bad"], "normal": t["tx"]}
        for box, v_lbl, l_lbl, tone in self._tiles:
            box.setStyleSheet(f"QFrame#apMetric {{ background:{t['soft']}; border-radius:10px; border:none; }}")
            v_lbl.setStyleSheet(f"font-size:17px; font-weight:bold; color:{tone_map.get(tone, t['tx'])}; background:transparent;")
            l_lbl.setStyleSheet(f"font-size:11px; color:{t['mu']}; background:transparent;")
        self.lab_flow.setStyleSheet(
            f"background:{t['acc_bg']}; color:{t['tx2']}; border-radius:8px; padding:6px 10px; font-size:12px;"
        )
        self.lab_checks.setStyleSheet(f"color:{t['mu']}; font-size:12px; background:transparent;")
        if self.lab_ready is not None:
            self.lab_ready.setStyleSheet(f"color:{t['tx2']}; font-size:12px; background:transparent;")
        if self._detail_box is not None:
            self._detail_box.setStyleSheet(
                f"background:{t['soft']}; color:{t['tx2']}; border-radius:8px; padding:8px 10px; font-size:12px;"
            )
        if self.lab_notes is not None:
            self.lab_notes.setStyleSheet(f"color:{t['dim']}; font-size:12px; background:transparent;")


class _AutopilotLiveCard(QFrame):
    """全自动运行时的实时动态进度卡片：6 步阶段高亮 + 当前动作 + 最新 6 条现场流水。"""
    STEPS = ("①扫描", "②检查", "③预处理", "④发布", "⑤查漏", "⑥封面")

    def __init__(self, on_stop, compact: bool, parent=None):
        super().__init__(parent)
        self.compact = compact
        self._stage = 0
        self.setObjectName("apLiveCard")

        v = QVBoxLayout(self)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(6)
        self.lab_head = QLabel("⚡ 正在执行全自动任务…")
        self.lab_head.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        top.addWidget(self.lab_head, 1)
        self.b_stop = QPushButton("停止")
        self.b_stop.setObjectName("danger")
        self.b_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_stop.clicked.connect(on_stop)
        top.addWidget(self.b_stop, 0)
        v.addLayout(top)

        # 6 步进度胶囊条
        sr = QHBoxLayout()
        sr.setSpacing(4)
        self._step_labs: list[QLabel] = []
        for s in self.STEPS:
            lb = QLabel(s)
            lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sr.addWidget(lb, 1)
            self._step_labs.append(lb)
        v.addLayout(sr)

        # 实时现场流水（最近 6 条，一目了然正在转哪条横屏/发哪条视频）
        self.lab_feed = QLabel("等待首条执行事件…")
        self.lab_feed.setWordWrap(True)
        self.lab_feed.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        v.addWidget(self.lab_feed)

        self.hide()
        self.retheme()

    def update_state(self, info: dict):
        active = bool((info or {}).get("active"))
        self.setVisible(active)
        if not active:
            return
        self._stage = int(info.get("stage") or 1)
        self.lab_head.setText("⚡ " + str(info.get("headline") or "正在执行全自动任务…"))
        lines = list(info.get("lines") or [])[-6:]
        self.lab_feed.setText("\n".join(lines) if lines else "正在启动，马上输出实时步骤…")
        self.retheme()

    def retheme(self):
        t = TH.cur()
        self.setStyleSheet(
            f"QFrame#apLiveCard {{ background:{t['card']}; border:1px solid {t['acc']}; border-radius:12px; }}"
        )
        self.lab_head.setStyleSheet(f"color:{t['tx']}; font-weight:bold; font-size:13px; background:transparent;")
        for idx, lb in enumerate(self._step_labs, 1):
            if idx == self._stage:
                lb.setStyleSheet(f"background:{t['acc']}; color:#ffffff; border-radius:7px; padding:3px 2px; font-size:11px; font-weight:bold;")
            elif idx < self._stage:
                lb.setStyleSheet(f"background:{t['ok_bg']}; color:{t['ok']}; border-radius:7px; padding:3px 2px; font-size:11px; font-weight:bold;")
            else:
                lb.setStyleSheet(f"background:{t['soft']}; color:{t['dim']}; border-radius:7px; padding:3px 2px; font-size:11px;")
        self.lab_feed.setStyleSheet(
            f"background:{t['soft']}; color:{t['tx2']}; border-radius:8px; padding:7px 9px; font-size:11px;"
        )


class _AutopilotReportCard(QFrame):
    """全自动跑完后的最终战报卡片：4 个核心数字 + 自动剪片尾抽检卡片组 + 可折叠待拍板异常清单。"""

    def __init__(self, card: dict, compact: bool, on_action=None, parent=None):
        super().__init__(parent)
        self.rep = card.get("report") or {}
        self.compact = compact
        self.on_action = on_action
        self._tiles: list[tuple[QFrame, QLabel, QLabel, str]] = []
        self._outro_cards: list[tuple[QFrame, QLabel, QLabel]] = []
        self._outro_btns: list[QPushButton] = []
        self.setObjectName("apReport")

        v = QVBoxLayout(self)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(6)
        stopped = bool(self.rep.get("stopped"))
        self.lab_title = QLabel(
            f"{'⏹ 全自动已停止' if stopped else '✅ 全自动战报'} · {self.rep.get('md') or ''}"
        )
        top.addWidget(self.lab_title)
        top.addStretch(1)
        cleaned = int(self.rep.get("cleaned_dirs_count") or 0)
        self.lab_clean = QLabel(f"已清残留夹 {cleaned} 个") if cleaned else None
        if self.lab_clean is not None:
            top.addWidget(self.lab_clean)
        v.addLayout(top)

        pub_n = int(self.rep.get("published_count") or 0)
        ret_n = int(self.rep.get("retried_count") or 0)
        skip_n = int(self.rep.get("skipped_count") or 0) + int(self.rep.get("failed_count") or 0)
        blk_n = len(self.rep.get("black_covers") or [])
        metrics = [
            (str(pub_n), "已发布", "ok"),
            (str(ret_n), "自动补发", "acc"),
            (str(skip_n), "拦下/失败", "warn" if skip_n else "normal"),
            (str(blk_n), "问题封面", "bad" if blk_n else "ok"),
        ]
        if compact:
            mg = QGridLayout()
            mg.setSpacing(6)
            for idx, (val, lbl, tone) in enumerate(metrics):
                tile = _make_metric_tile(val, lbl, tone)
                self._tiles.append(tile)
                mg.addWidget(tile[0], idx // 2, idx % 2)
            v.addLayout(mg)
        else:
            mr = QHBoxLayout()
            mr.setSpacing(8)
            for val, lbl, tone in metrics:
                tile = _make_metric_tile(val, lbl, tone)
                self._tiles.append(tile)
                mr.addWidget(tile[0], 1)
            v.addLayout(mr)

        prep_parts = []
        if self.rep.get("converted_count"):
            prep_parts.append(f"转竖屏 {self.rep['converted_count']} 条")
        if self.rep.get("outro_cut_count"):
            prep_parts.append(f"剪片尾 {self.rep['outro_cut_count']} 条")
        if self.rep.get("renamed_count"):
            prep_parts.append(f"整理标题 {self.rep['renamed_count']} 条")
        if self.rep.get("exported_covers_count"):
            prep_parts.append(f"截清晰封面 {self.rep['exported_covers_count']} 张")
        self.lab_prep = QLabel("顺手处理：" + " · ".join(prep_parts)) if prep_parts else None
        if self.lab_prep is not None:
            self.lab_prep.setWordWrap(True)
            v.addWidget(self.lab_prep)

        # 自动剪过头像片尾的抽检卡片组（方便用户事后抽查，有问题一键定位后台删掉重发）
        outro_items = list(self.rep.get("outro_cut_items") or [])
        self.outro_group = None
        self.lab_outro_head = None
        if outro_items:
            og = QFrame()
            og.setObjectName("apOutroGroup")
            ol = QVBoxLayout(og)
            ol.setContentsMargins(10, 8, 10, 8)
            ol.setSpacing(6)
            self.lab_outro_head = QLabel(f"✂ 自动剪过片尾（{len(outro_items)} 条，建议抽检；有问题可去罐头删掉重发）")
            self.lab_outro_head.setWordWrap(True)
            ol.addWidget(self.lab_outro_head)
            for item in outro_items:
                ic = QFrame()
                ic.setObjectName("apOutroItem")
                il = QHBoxLayout(ic)
                il.setContentsMargins(8, 6, 8, 6)
                il.setSpacing(6)
                tv = QVBoxLayout()
                tv.setSpacing(2)
                lt = QLabel(f"[{item.get('account', '')}] 《{str(item.get('title') or '')[:26]}》")
                lt.setWordWrap(True)
                ls = QLabel(f"剪掉末尾 {float(item.get('cut_sec') or 0):.1f} 秒 · {item.get('reason') or '头像片尾卡片'}")
                ls.setWordWrap(True)
                tv.addWidget(lt)
                tv.addWidget(ls)
                il.addLayout(tv, 1)
                shot_p = str(item.get("shot") or "")
                if shot_p:
                    bs = QPushButton("看截帧")
                    bs.setObjectName("link")
                    bs.setCursor(Qt.CursorShape.PointingHandCursor)
                    bs.clicked.connect(lambda _c=False, sp=shot_p: self._open_shot(sp))
                    il.addWidget(bs, 0)
                if self.on_action is not None:
                    bc = QPushButton("去罐头定位")
                    bc.setObjectName("pill")
                    bc.setCursor(Qt.CursorShape.PointingHandCursor)
                    act = {
                        "label": f"去罐头定位：{item.get('account', '')}",
                        "kind": "open_czgt",
                        "payload": {
                            "account": item.get("account") or "",
                            "title": item.get("title") or "",
                            "day": item.get("day_iso") or self.rep.get("day_iso") or "",
                        },
                    }
                    bc.clicked.connect(lambda _c=False, a=act: self.on_action(a))
                    il.addWidget(bc, 0)
                    self._outro_btns.append(bc)
                self._outro_cards.append((ic, lt, ls))
                ol.addWidget(ic)
            self.outro_group = og
            v.addWidget(og)

        # 待拍板异常清单（前 4 条直接看，多余折叠）
        issue_lines = []
        for x in self.rep.get("skipped_items") or []:
            issue_lines.append(f"· [{x['account']}] 《{x['title'][:22]}》— {'、'.join(x.get('reasons') or [])}")
        for x in self.rep.get("failed_items") or []:
            issue_lines.append(f"· [{x['account']}] 《{x['title'][:22]}》— 发布失败：{x.get('error', '')}")
        self._more_box = None
        self.b_more = None
        self.lab_issues = None
        if issue_lines:
            head_txt = "待拍板 / 失败清单：\n" + "\n".join(issue_lines[:4])
            self.lab_issues = QLabel(head_txt)
            self.lab_issues.setWordWrap(True)
            self.lab_issues.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            v.addWidget(self.lab_issues)
            if len(issue_lines) > 4:
                self.b_more = QPushButton(f"展开其余 {len(issue_lines) - 4} 条 ▾")
                self.b_more.setObjectName("link")
                self.b_more.setCursor(Qt.CursorShape.PointingHandCursor)
                self.b_more.clicked.connect(self._toggle_more)
                v.addWidget(self.b_more, 0, Qt.AlignmentFlag.AlignLeft)
                self._more_box = QLabel("\n".join(issue_lines[4:]))
                self._more_box.setWordWrap(True)
                self._more_box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                self._more_box.hide()
                v.addWidget(self._more_box)

        extra_notes = []
        for cn in self.rep.get("count_notes") or []:
            extra_notes.append(f"数量提示：{cn}")
        unc = self.rep.get("uncertain_missing") or []
        if unc:
            extra_notes.append(f"后台暂未同步 / 待复核 {len(unc)} 条（未自动补发，稍后可点「去后台查漏发」复核）")
        miss = self.rep.get("missing_accounts") or []
        if miss:
            extra_notes.append("无今日文件夹(跳过)：" + "、".join(miss[:5]) + (f" 等 {len(miss)} 个" if len(miss) > 5 else ""))
        self.lab_extra = QLabel("\n".join(extra_notes)) if extra_notes else None
        if self.lab_extra is not None:
            self.lab_extra.setWordWrap(True)
            v.addWidget(self.lab_extra)

        self.retheme()

    def _toggle_more(self):
        if self._more_box is None or self.b_more is None:
            return
        vis = not self._more_box.isVisible()
        self._more_box.setVisible(vis)
        n = len(self._more_box.text().splitlines())
        self.b_more.setText("收起 ▴" if vis else f"展开其余 {n} 条 ▾")

    def _open_shot(self, path: str):
        import os
        if path and os.path.isfile(path):
            try:
                os.startfile(path)
            except OSError:
                pass

    def set_busy(self, busy: bool):
        for b in self._outro_btns:
            b.setEnabled(not busy)

    def sync_state(self):
        pass

    def retheme(self):
        t = TH.cur()
        self.setStyleSheet(
            f"QFrame#apReport {{ background:{t['card']}; border:1px solid {t['line']}; border-radius:14px; }}"
        )
        self.lab_title.setStyleSheet(f"font-size:14px; font-weight:bold; color:{t['tx']}; background:transparent;")
        if self.lab_clean is not None:
            self.lab_clean.setStyleSheet(
                f"background:{t['ok_bg']}; color:{t['ok']}; border-radius:9px; padding:2px 9px; font-size:11px; font-weight:bold;"
            )
        tone_map = {"acc": t["acc"], "ok": t["ok"], "warn": t["warn"], "bad": t["bad"], "normal": t["tx"]}
        for box, v_lbl, l_lbl, tone in self._tiles:
            box.setStyleSheet(f"QFrame#apMetric {{ background:{t['soft']}; border-radius:10px; border:none; }}")
            v_lbl.setStyleSheet(f"font-size:17px; font-weight:bold; color:{tone_map.get(tone, t['tx'])}; background:transparent;")
            l_lbl.setStyleSheet(f"font-size:11px; color:{t['mu']}; background:transparent;")
        if self.lab_prep is not None:
            self.lab_prep.setStyleSheet(f"color:{t['mu']}; font-size:12px; background:transparent;")
        if self.outro_group is not None:
            self.outro_group.setStyleSheet(
                f"QFrame#apOutroGroup {{ background:{t['acc_bg']}; border:1px solid {t['line']}; border-radius:10px; }}"
            )
            self.lab_outro_head.setStyleSheet(f"color:{t['acc']}; font-weight:bold; font-size:12px; background:transparent;")
            for ic, lt, ls in self._outro_cards:
                ic.setStyleSheet(f"QFrame#apOutroItem {{ background:{t['card']}; border:1px solid {t['line2']}; border-radius:8px; }}")
                lt.setStyleSheet(f"color:{t['tx']}; font-size:12px; font-weight:bold; background:transparent;")
                ls.setStyleSheet(f"color:{t['mu']}; font-size:11px; background:transparent;")
        if self.lab_issues is not None:
            self.lab_issues.setStyleSheet(
                f"background:{t['warn_bg']}; color:{t['tx']}; border-radius:8px; padding:8px 10px; font-size:12px;"
            )
        if self._more_box is not None:
            self._more_box.setStyleSheet(
                f"background:{t['soft']}; color:{t['tx2']}; border-radius:8px; padding:8px 10px; font-size:12px;"
            )
        if self.lab_extra is not None:
            self.lab_extra.setStyleSheet(f"color:{t['dim']}; font-size:12px; background:transparent;")


class _Bubble(QFrame):
    def __init__(self, msg: dict, on_action, on_cancel_card, compact: bool, parent=None):
        super().__init__(parent)
        self.msg = msg
        self.on_action = on_action
        self.on_cancel_card = on_cancel_card
        self.compact = compact
        self.action_buttons: list[QPushButton] = []
        self.card_widget = None
        role = msg.get("role") or "assistant"
        self.role = role

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        self.card = QFrame()
        self.card.setObjectName("aiBubbleUser" if role == "user" else "aiBubbleBot")
        cv = QVBoxLayout(self.card)
        cv.setContentsMargins(12, 9, 12, 9)
        cv.setSpacing(8)

        card_data = msg.get("card")
        self._is_rich_card = bool(card_data and card_data.get("kind") in ("autopilot_confirm", "autopilot_report"))
        if self._is_rich_card:
            cv.setContentsMargins(0, 0, 0, 0)
            cv.setSpacing(6)
        self.lbl = QLabel(msg.get("text") or "")
        self.lbl.setWordWrap(True)
        self.lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        # 确认卡片与战报卡片自带清晰标题和数字，避免多余啰嗦文字占空间
        if self._is_rich_card:
            self.lbl.hide()
        else:
            cv.addWidget(self.lbl)

        if card_data:
            ck = card_data.get("kind")
            if ck == "autopilot_confirm":
                self.card_widget = _AutopilotConfirmCard(card_data, self.on_action, self.on_cancel_card, compact, self.card)
                if not compact:
                    self.card_widget.setMinimumWidth(560)
                cv.addWidget(self.card_widget)
            elif ck == "autopilot_report":
                self.card_widget = _AutopilotReportCard(card_data, compact, on_action=self.on_action, parent=self.card)
                if not compact:
                    self.card_widget.setMinimumWidth(560)
                cv.addWidget(self.card_widget)

        actions = list(msg.get("actions") or [])
        if actions:
            af = QWidget()
            al = QVBoxLayout(af) if compact else QHBoxLayout(af)
            al.setContentsMargins(0, 2, 0, 0)
            al.setSpacing(6)
            for act in actions:
                b = QPushButton(str(act.get("label") or "执行"))
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                if act.get("tone") == "primary":
                    b.setObjectName("primary")
                else:
                    b.setObjectName("pill")
                b.clicked.connect(lambda _c=False, a=act: self.on_action(a))
                al.addWidget(b)
                self.action_buttons.append(b)
            if not compact:
                al.addStretch(1)
            cv.addWidget(af)

        if role == "user":
            row.addStretch(1)
            row.addWidget(self.card, 0)
        else:
            row.addWidget(self.card, 1 if compact else 0)
            if not compact:
                row.addStretch(1)
        if not compact:
            self.card.setMaximumWidth(780)
        outer.addLayout(row)
        self.retheme()

    def set_busy(self, busy: bool):
        for b in self.action_buttons:
            b.setEnabled(not busy)
        if self.card_widget is not None:
            self.card_widget.set_busy(busy)

    def sync_card(self):
        if self.card_widget is not None:
            self.card_widget.sync_state()

    def retheme(self):
        t = TH.cur()
        if self.role == "user":
            self.card.setStyleSheet(
                f"QFrame#aiBubbleUser {{ background:{t['acc_bg']}; border:1px solid {t['line']}; border-radius:12px; }}"
            )
            self.lbl.setStyleSheet(f"color:{t['tx']}; background:transparent; font-size:13px;")
        elif getattr(self, "_is_rich_card", False):
            self.card.setStyleSheet("QFrame#aiBubbleBot { background:transparent; border:none; }")
            self.lbl.setStyleSheet(f"color:{t['tx']}; background:transparent; font-size:13px;")
        else:
            self.card.setStyleSheet(
                f"QFrame#aiBubbleBot {{ background:{t['card']}; border:1px solid {t['line']}; border-radius:12px; }}"
            )
            self.lbl.setStyleSheet(f"color:{t['tx']}; background:transparent; font-size:13px;")
        if self.card_widget is not None:
            self.card_widget.retheme()


class AssistantView(QWidget):
    """可作为左侧独立全屏页，也可作为右侧可收起抽屉使用的 AI 助手面板。"""

    def __init__(self, hub: AssistantHub, compact: bool = False, on_close=None, parent=None):
        super().__init__(parent)
        self.hub = hub
        self.compact = compact
        self.on_close = on_close
        self._bubbles: list[_Bubble] = []
        self._quick_btns: list[QPushButton] = []
        self.setObjectName("aiDrawer" if compact else "page")
        self._build()
        self._connect_hub()
        self._rebuild_messages()
        self.retheme()

    def _build(self):
        v = QVBoxLayout(self)
        m = 12 if self.compact else 24
        v.setContentsMargins(m, 14 if self.compact else 18, m, 12)
        v.setSpacing(10)

        # 顶栏
        head = QHBoxLayout()
        head.setSpacing(8)
        title = QLabel("AI 助手")
        title.setObjectName("secTitle" if self.compact else "pageTitle")
        head.addWidget(title)
        self.lab_model = QLabel("")
        self.lab_model.setObjectName("muted")
        self.lab_model.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        head.addWidget(self.lab_model, 1)
        self.b_log = QPushButton("留痕日志")
        self.b_log.setObjectName("link")
        self.b_log.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_log.setToolTip("查看今天和近 30 天全自动运行的完整留痕记录（每一步时间、成功/跳过/出错原因）")
        self.b_log.clicked.connect(lambda: self.hub.open_log_dialog("", self))
        head.addWidget(self.b_log)
        self.b_clear = QPushButton("清空")
        self.b_clear.setObjectName("link")
        self.b_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_clear.clicked.connect(self.hub.clear)
        head.addWidget(self.b_clear)
        if self.on_close is not None:
            self.b_close = QPushButton("收起")
            self.b_close.setObjectName("link")
            self.b_close.setCursor(Qt.CursorShape.PointingHandCursor)
            self.b_close.clicked.connect(self.on_close)
            head.addWidget(self.b_close)
        v.addLayout(head)

        # 快捷提问按钮区
        quick_box = QWidget()
        if self.compact:
            ql = QGridLayout(quick_box)
            ql.setContentsMargins(0, 0, 0, 0)
            ql.setSpacing(6)
            total_q = len(A.QUICK_PROMPTS)
            for idx, (kind, label, _prompt) in enumerate(A.QUICK_PROMPTS):
                b = QPushButton(label)
                b.setObjectName("pill")
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.clicked.connect(lambda _c=False, k=kind, l=label: self.hub.quick(k, l))
                span = 2 if (total_q % 2 == 1 and idx == total_q - 1) else 1
                ql.addWidget(b, idx // 2, idx % 2, 1, span)
                self._quick_btns.append(b)
        else:
            ql = QHBoxLayout(quick_box)
            ql.setContentsMargins(0, 0, 0, 0)
            ql.setSpacing(8)
            for kind, label, _prompt in A.QUICK_PROMPTS:
                b = QPushButton(label)
                b.setObjectName("pill")
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.clicked.connect(lambda _c=False, k=kind, l=label: self.hub.quick(k, l))
                ql.addWidget(b)
                self._quick_btns.append(b)
            ql.addStretch(1)
        v.addWidget(quick_box)

        # 全天值守状态条（开启值守时显示，平时隐藏）
        self.watch_bar = QFrame()
        self.watch_bar.setObjectName("apWatchBar")
        wl = QHBoxLayout(self.watch_bar)
        wl.setContentsMargins(10, 6, 10, 6)
        wl.setSpacing(8)
        self.lab_watch = QLabel("")
        self.lab_watch.setWordWrap(False)
        self.lab_watch.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        wl.addWidget(self.lab_watch, 1)
        self.b_watch_now = QPushButton("立即巡检")
        self.b_watch_now.setObjectName("link")
        self.b_watch_now.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_watch_now.clicked.connect(self.hub.watch_tick_now)
        wl.addWidget(self.b_watch_now)
        self.b_watch_stop = QPushButton("结束值守")
        self.b_watch_stop.setObjectName("link")
        self.b_watch_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_watch_stop.clicked.connect(self.hub.stop_watch)
        wl.addWidget(self.b_watch_stop)
        self.watch_bar.hide()
        v.addWidget(self.watch_bar)

        # 全自动实时执行动态卡片（跑任务时自动展开，实时高亮阶段 + 滚动最近现场流水）
        self.live_card = _AutopilotLiveCard(self.hub.stop, self.compact, self)
        v.addWidget(self.live_card)

        # 对话消息滚动区
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._msg_host = QWidget()
        self._msg_lay = QVBoxLayout(self._msg_host)
        self._msg_lay.setContentsMargins(2, 4, 6, 4)
        self._msg_lay.setSpacing(10)
        self.welcome = QLabel(
            "你可以直接点上面的快捷按钮，或者用大白话让我帮忙：\n"
            "· 查今天各号发完没、后台有没有漏发 / 黑封面\n"
            "· 找「没发但已挪进归档」的视频，并一键拎回今天待发目录\n"
            "· 查游戏 / 动漫目录里的过期文件夹与残留文件，已发过的归档/去重、空夹删除（绝不删未发视频）\n"
            "安全说明：我绝不会自动发布视频，也绝不会删除线上作品。"
        )
        self.welcome.setWordWrap(True)
        self.welcome.setObjectName("hint")
        self._msg_lay.addWidget(self.welcome)
        self._msg_lay.addStretch(1)
        self.scroll.setWidget(self._msg_host)
        v.addWidget(self.scroll, 1)

        # 进度条 / 停止按钮
        self.status_bar = QWidget()
        sh = QHBoxLayout(self.status_bar)
        sh.setContentsMargins(2, 0, 2, 0)
        sh.setSpacing(8)
        self.lab_status = QLabel("")
        self.lab_status.setObjectName("muted")
        self.lab_status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        sh.addWidget(self.lab_status, 1)
        self.b_stop = QPushButton("停止")
        self.b_stop.setObjectName("danger")
        self.b_stop.clicked.connect(self.hub.stop)
        sh.addWidget(self.b_stop)
        self.status_bar.hide()
        v.addWidget(self.status_bar)

        # 输入区
        inp_row = QHBoxLayout()
        inp_row.setSpacing(8)
        self.ed_input = QPlainTextEdit()
        self.ed_input.setPlaceholderText("问点什么，例如：今天有没有没发上但挪到归档里的视频？（Enter 发送，Shift+Enter 换行）")
        self.ed_input.setFixedHeight(64 if self.compact else 72)
        self.ed_input.installEventFilter(self)
        inp_row.addWidget(self.ed_input, 1)
        self.b_send = QPushButton("发送")
        self.b_send.setObjectName("primary")
        self.b_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_send.clicked.connect(self._send_clicked)
        inp_row.addWidget(self.b_send, 0, Qt.AlignmentFlag.AlignBottom)
        v.addLayout(inp_row)

    def _connect_hub(self):
        self.hub.message_added.connect(self._add_bubble)
        self.hub.cleared.connect(self._rebuild_messages)
        self.hub.card_updated.connect(self._sync_cards)
        self.hub.watch_status_changed.connect(self._on_watch_status)
        self.hub.live_changed.connect(self.live_card.update_state)
        self.hub.status_changed.connect(self._on_status)
        self.hub.busy_changed.connect(self._on_busy)

    def _on_watch_status(self, info: dict):
        active = bool((info or {}).get("active"))
        self.watch_bar.setVisible(active)
        if not active:
            return
        rem = int(info.get("next_in_sec") or 0)
        mm, ss = rem // 60, rem % 60
        sent, quota = int(info.get("api_sent") or 0), int(info.get("api_quota") or 0)
        busy = bool(info.get("busy"))
        q_str = f" · 今日 {sent}/{quota}" if quota else (f" · 今日已发 {sent}" if sent else "")
        if busy:
            self.lab_watch.setText(f"🟢 值守巡检中…{q_str}")
        else:
            self.lab_watch.setText(f"🟢 值守中 · 下次巡检 {mm:02d}:{ss:02d}{q_str}")
        self.b_watch_now.setEnabled(not busy)
        self.b_watch_stop.setEnabled(not busy)

    def _sync_cards(self):
        for b in self._bubbles:
            b.sync_card()

    def eventFilter(self, obj, ev):
        if obj is self.ed_input and ev.type() == QEvent.Type.KeyPress:
            if ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (ev.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self._send_clicked()
                return True
        return super().eventFilter(obj, ev)

    def _send_clicked(self):
        txt = self.ed_input.toPlainText().strip()
        if not txt or self.hub.is_busy():
            return
        self.ed_input.clear()
        self.hub.send(txt)

    def _rebuild_messages(self):
        for b in self._bubbles:
            self._msg_lay.removeWidget(b)
            b.deleteLater()
        self._bubbles.clear()
        for m in self.hub.messages:
            self._insert_bubble(m)
        self.welcome.setVisible(len(self._bubbles) == 0)

    def _insert_bubble(self, msg: dict):
        b = _Bubble(msg, self.hub.trigger_action, self.hub.cancel_card, self.compact, self._msg_host)
        b.set_busy(self.hub.is_busy())
        # 插在尾部 stretch 之前
        self._msg_lay.insertWidget(self._msg_lay.count() - 1, b)
        self._bubbles.append(b)
        self.welcome.setVisible(False)
        QTimer.singleShot(0, self._scroll_bottom)

    def _add_bubble(self, msg: dict):
        self._insert_bubble(msg)

    def _scroll_bottom(self):
        sb = self.scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_status(self, txt: str):
        self.lab_status.setText(txt)
        self.status_bar.setVisible(bool(txt) or self.hub.is_busy())

    def _on_busy(self, busy: bool):
        self.b_send.setEnabled(not busy)
        self.b_clear.setEnabled(not busy)
        for b in self._quick_btns:
            b.setEnabled(not busy)
        for bub in self._bubbles:
            bub.set_busy(busy)
        self.status_bar.setVisible(busy or bool(self.lab_status.text()))

    def retheme(self):
        t = TH.cur()
        self.lab_model.setText(self.hub.model_label())
        if self.compact:
            self.setStyleSheet(f"QWidget#aiDrawer {{ background:{t['bg']}; border-left:1px solid {t['line']}; }}")
        self.welcome.setStyleSheet(
            f"background:{t['card']}; color:{t['mu']}; border:1px solid {t['line']}; border-radius:12px; padding:12px; font-size:13px;"
        )
        self.watch_bar.setStyleSheet(
            f"QFrame#apWatchBar {{ background:{t['ok_bg']}; border:1px solid {t['ok']}; border-radius:10px; }}"
        )
        self.lab_watch.setStyleSheet(f"color:{t['ok']}; font-weight:bold; font-size:12px; background:transparent;")
        self._on_watch_status(self.hub.watch_info())
        self.live_card.update_state(self.hub.live_info())
        self.live_card.retheme()
        for b in self._bubbles:
            b.retheme()
