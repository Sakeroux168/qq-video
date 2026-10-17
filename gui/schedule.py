"""定时发布(用户 2026-10-17:「明天周末不上班,电脑不关机,到点自动发」)。

教育号、16 个号两页各一个「定时发布…」:选 哪天的素材 + 什么时候开始(北京时间),到点自己发到完为止。
定好的存在设置里(schedules.edu / schedules.api),软件重开还在;到点时软件没开着 → 不补发,打开时说一声、清掉。
定着 / 正在自动发的时候叫电脑别睡(SetThreadExecutionState,只在软件开着时管用,不改系统设置)。
"""
import ctypes
import datetime as dt

from PySide6.QtCore import QObject, QTime, QTimer
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QTimeEdit

from qe.config import bj_now

_AWAKE: set[str] = set()
_ES_CONTINUOUS, _ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001


def keep_awake(reason: str, on: bool) -> None:
    """reason 在就不让电脑睡(屏幕可以黑);都没了恢复。只能在主线程调(这个设置跟着线程走)。"""
    (_AWAKE.add if on else _AWAKE.discard)(reason)
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS | (_ES_SYSTEM_REQUIRED if _AWAKE else 0))
    except Exception:                                  # 不是 Windows(测试机)
        pass


def awake_reasons() -> set[str]:
    return set(_AWAKE)


def now_str() -> str:
    return bj_now().strftime("%Y-%m-%d %H:%M")


def left_text(at: str) -> str:
    """离 at 还有多久:「13 小时 5 分」/「5 分钟」/「马上」。"""
    try:
        t = dt.datetime.strptime(at, "%Y-%m-%d %H:%M")
    except ValueError:
        return ""
    mins = int((t - dt.datetime.strptime(now_str(), "%Y-%m-%d %H:%M")).total_seconds() // 60)
    if mins <= 0:
        return "马上"
    h, m = divmod(mins, 60)
    return (f"{h} 小时 {m} 分" if m else f"{h} 小时") if h else f"{m} 分钟"


def short_at(at: str) -> str:
    """「2026-10-18 09:00」→「明天 09:00」/「10-18 09:00」。"""
    today = bj_now().date()
    try:
        d = dt.datetime.strptime(at, "%Y-%m-%d %H:%M")
    except ValueError:
        return at
    word = {0: "今天", 1: "明天", 2: "后天"}.get((d.date() - today).days)
    return f"{word or d.strftime('%m-%d')} {d.strftime('%H:%M')}"


class Scheduler(QObject):
    """一页一个。fire(date) = 到点了,开始发 date 那天的。changed() = 定了 / 取消了 / 到点了(界面刷新提示)。"""

    def __init__(self, st, key: str, say, fire, changed=lambda: None, parent=None):
        super().__init__(parent)
        self.st, self.key, self.say, self.fire, self.changed = st, key, say, fire, changed
        self.timer = QTimer(self)
        self.timer.setInterval(15000)
        self.timer.timeout.connect(self.tick)
        p = self.pending()
        if p:
            if p["at"] <= now_str():
                self.say(f"⚠ 定时发布({p['date']},{p['at']})到点的时候软件没开着,没发;定时已经取消,要发就重新定")
                self._drop()
            else:
                self._arm()

    def pending(self) -> dict | None:
        p = (self.st.get("schedules") or {}).get(self.key)
        return dict(p) if isinstance(p, dict) and p.get("at") and p.get("date") else None

    def _drop(self):
        s = dict(self.st.get("schedules") or {})
        s.pop(self.key, None)
        self.st["schedules"] = s
        self.st.save()

    def _arm(self):
        self.timer.start()
        keep_awake(f"定时-{self.key}", True)

    def set(self, at: str, date: str):
        s = dict(self.st.get("schedules") or {})
        s[self.key] = {"at": at, "date": date}
        self.st["schedules"] = s
        self.st.save()
        self._arm()
        self.say(f"⏰ 定好了:{short_at(at)}(北京时间)开始发 {date} 的,发到完为止。电脑别关机,软件和创作罐头开着(罐头最小化没关系)")
        self.changed()

    def cancel(self, quiet: bool = False):
        if not self.pending():
            return
        self._drop()
        self.timer.stop()
        keep_awake(f"定时-{self.key}", False)
        if not quiet:
            self.say("定时取消了")
        self.changed()

    def tick(self):
        p = self.pending()
        if not p:
            self.timer.stop()
            keep_awake(f"定时-{self.key}", False)
            return
        if p["at"] > now_str():
            self.changed()                              # 刷新「还有多久」
            return
        self._drop()
        self.timer.stop()
        keep_awake(f"定时-{self.key}", False)
        self.say(f"⏰ 到点了({p['at']}),开始发 {p['date']} 的")
        self.changed()
        self.fire(p["date"])

    def label(self) -> str:
        p = self.pending()
        return f"⏰ {short_at(p['at'])} 开始发 {p['date']} 的(还有 {left_text(p['at'])})" if p else ""


def ask_schedule(parent, title: str, dates: list[str], cur: str, note: str = "") -> tuple[str, str] | None:
    """弹框选:哪天的素材、哪天几点开始(北京时间)。返回 (「YYYY-MM-DD HH:MM」, 素材日期);不定了返回 None。"""
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    f = QFormLayout(dlg)
    c_date = QComboBox()
    c_date.addItems(dates)
    if cur in dates:
        c_date.setCurrentText(cur)
    f.addRow("发哪天的素材:", c_date)
    c_day = QComboBox()
    today = bj_now().date()
    for k, word in ((0, "今天"), (1, "明天"), (2, "后天")):
        d = today + dt.timedelta(days=k)
        c_day.addItem(f"{word}({d.month}月{d.day}日)", d.isoformat())
    c_day.setCurrentIndex(1)
    f.addRow("哪天开始:", c_day)
    e_time = QTimeEdit(QTime(9, 0))
    e_time.setDisplayFormat("HH:mm")
    f.addRow("几点开始(北京时间):", e_time)
    tip = QLabel("到点后软件自己发,发到完为止。\n电脑别关机、别睡眠(软件会叫它别睡);软件和创作罐头都要开着,罐头最小化没关系。" +
                 (f"\n\n{note}" if note else ""))
    tip.setWordWrap(True)
    tip.setStyleSheet("color:#8a8b91")
    f.addRow(tip)
    bb = QDialogButtonBox()
    bb.addButton("定好了", QDialogButtonBox.ButtonRole.AcceptRole)
    bb.addButton("不定了", QDialogButtonBox.ButtonRole.RejectRole)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    f.addRow(bb)
    while dlg.exec() == QDialog.DialogCode.Accepted:
        at = f"{c_day.currentData()} {e_time.time().toString('HH:mm')}"
        if not c_date.currentText():
            continue
        if at <= now_str():
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(parent, title, f"{short_at(at)} 已经过了,选个以后的时间。")
            continue
        return at, c_date.currentText()
    return None
