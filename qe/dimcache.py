"""视频多大(宽 × 高)记在硬盘上:教育号页一勾员工就看出哪些是横屏 / 偏方(用户 2026-10-25「教育类的也要跟 16 个号一样
识别视频有没有横屏的或偏方的,然后我才好去处理」)。网络盘上一条条读要零点几秒,读过、文件没变的不再读。
按 路径 + 大小 + 修改时间 认;转了竖屏文件变了就重新读。"""
import json
import os
import threading

from .config import data_dir

_LOCK = threading.Lock()
_D = None


def _path() -> str:
    return str(data_dir() / "视频尺寸.json")


def _load() -> dict:
    global _D
    if _D is None:
        try:
            with open(_path(), encoding="utf-8") as f:
                _D = json.load(f)
        except (OSError, ValueError):
            _D = {}
    return _D


def _key(path: str) -> str:
    st = os.stat(path)
    return f"{os.path.normcase(path)}|{st.st_size}|{int(st.st_mtime)}"


def get(path: str):
    """(宽, 高) 或 None(没读过 / 文件变了)。"""
    try:
        k = _key(path)
    except OSError:
        return None
    with _LOCK:
        v = _load().get(k)
    return tuple(v) if v else None


def put(path: str, w: int, h: int) -> None:
    try:
        k = _key(path)
    except OSError:
        return
    with _LOCK:
        d = _load()
        d[k] = [int(w), int(h)]
        if len(d) > 20000:                                 # 太多了清掉老的一半
            for x in list(d)[:10000]:
                d.pop(x, None)


def save() -> None:
    with _LOCK:
        d = _load()
        tmp = _path() + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False)
            os.replace(tmp, _path())
        except OSError:
            pass


def shape(w: int, h: int) -> str:
    """「横屏」/「偏方」/ ""(标准竖屏)。和 16 个号同一个判断(vertical.is_landscape / is_squarish)。"""
    from .vertical import is_landscape, is_squarish
    info = {"w": w, "h": h}
    return "横屏" if is_landscape(info) else "偏方" if is_squarish(info) else ""
