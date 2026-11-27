"""超过 10 分钟的视频拦截与放行(用户 2026-11-26):
时长 > 600 秒默认标黄先不发;人看过觉得可以发,右键「时长没问题,能发」放行(记在 超长视频放行.json,支持局域网双机同步)。
设置里「查超过 10 分钟的视频」(long_check)取消勾选后不触发。
"""
from .config import data_dir
from .titleclean import AdOk

MAX_SEC = 600.0
ENABLED = True
_S = None


def configure(st) -> None:
    global ENABLED
    ENABLED = bool(st.get("long_check", True)) if hasattr(st, "get") else True


def is_long(dur) -> bool:
    try:
        return float(dur or 0) > MAX_SEC
    except (TypeError, ValueError):
        return False


def fmt_dur(dur) -> str:
    sec = max(0, int(round(float(dur or 0))))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}小时{m:02d}分{s:02d}秒" if h else f"{m}分{s:02d}秒"


def store() -> AdOk:
    global _S
    p = str(data_dir() / "超长视频放行.json")
    if _S is None or _S.path != p:
        _S = AdOk(p)
    return _S


def problem(account: str, title: str, dur) -> str:
    """超过 10 分钟且未放行 → 一句话;否则 ""。"""
    if not ENABLED or not is_long(dur) or store().ok(account, title):
        return ""
    return f"超过10分钟({fmt_dur(dur)})(能发就右键「时长没问题,能发」)"
