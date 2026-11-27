"""内置 AI 助手界面(用户 2026-11-26):
同时提供左侧全屏页与右侧可收起抽屉，共用同一个 AssistantHub（同一份对话历史与后台线程），
切页或收起抽屉都不会丢对话。
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
                               QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from gui import theme as TH
from qe import assistant as A, redo


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


class AssistantHub(QObject):
    """全屏页与右侧抽屉共用的对话中心。"""
    message_added = Signal(dict)
    cleared = Signal()
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

    def is_busy(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def model_label(self) -> str:
        ai = self.agent.ai_config()
        if not ai.key:
            return "未配 AI Key（快捷查仍可用）"
        return f"{ai.who} · {ai.model}"

    def _append(self, role: str, text: str, actions: list[dict] | None = None):
        m = {"role": role, "text": text, "actions": list(actions or [])}
        self.messages.append(m)
        self.message_added.emit(m)

    def _start(self, mode: str, arg, status: str):
        if self.is_busy():
            return
        w = _TaskWorker(self.agent, mode, arg, self)
        w.progress.connect(self.status_changed.emit)
        w.finished_ok.connect(self._on_ok)
        w.finished_err.connect(self._on_err)
        w.finished.connect(self._on_done)
        self._worker = w
        self.busy_changed.emit(True)
        self.status_changed.emit(status)
        w.start()

    def _on_ok(self, res: dict):
        reply = str(res.get("reply") or "").strip()
        actions = list(res.get("actions") or [])
        if reply or actions:
            self._append("assistant", reply or "已完成。", actions)
        if res.get("mutated"):
            self.data_changed.emit()

    def _on_err(self, err: str):
        self._append("assistant", f"出错了：{err}")

    def _on_done(self):
        self.status_changed.emit("")
        self.busy_changed.emit(False)

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

    def trigger_action(self, action: dict):
        if self.is_busy():
            return
        if action.get("kind") == "pull_back" and self.owner is not None:
            busy = redo.busy_reason(self.owner)
            if busy:
                self._append("assistant", f"暂时不能拎回视频：{busy}")
                return
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
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(5000)


class _Bubble(QFrame):
    def __init__(self, msg: dict, on_action, compact: bool, parent=None):
        super().__init__(parent)
        self.msg = msg
        self.on_action = on_action
        self.compact = compact
        self.action_buttons: list[QPushButton] = []
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
        cv.setSpacing(6)

        self.lbl = QLabel(msg.get("text") or "")
        self.lbl.setWordWrap(True)
        self.lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        cv.addWidget(self.lbl)

        actions = list(msg.get("actions") or [])
        if actions:
            af = QWidget()
            al = QVBoxLayout(af) if compact else QHBoxLayout(af)
            al.setContentsMargins(0, 4, 0, 0)
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

    def retheme(self):
        t = TH.cur()
        if self.role == "user":
            self.card.setStyleSheet(
                f"QFrame#aiBubbleUser {{ background:{t['acc_bg']}; border:1px solid {t['line']}; border-radius:12px; }}"
            )
            self.lbl.setStyleSheet(f"color:{t['tx']}; background:transparent; font-size:13px;")
        else:
            self.card.setStyleSheet(
                f"QFrame#aiBubbleBot {{ background:{t['card']}; border:1px solid {t['line']}; border-radius:12px; }}"
            )
            self.lbl.setStyleSheet(f"color:{t['tx']}; background:transparent; font-size:13px;")


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
            for idx, (kind, label, _prompt) in enumerate(A.QUICK_PROMPTS):
                b = QPushButton(label)
                b.setObjectName("pill")
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.clicked.connect(lambda _c=False, k=kind, l=label: self.hub.quick(k, l))
                ql.addWidget(b, idx // 2, idx % 2)
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
        self.hub.status_changed.connect(self._on_status)
        self.hub.busy_changed.connect(self._on_busy)

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
        b = _Bubble(msg, self.hub.trigger_action, self.compact, self._msg_host)
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
        for b in self._bubbles:
            b.retheme()
