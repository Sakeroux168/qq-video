"""查水印的结果记在硬盘上(数据目录\\水印检查.json),关了软件再开、16 个号和教育号两边都认得。

一条视频按路径记,带上(大小, 修改时间):文件变了(转竖屏 / 模糊过 / 员工换了一条)就当没查过。
ok = 人看过截图说「没水印,能发」(误报),之后就不拦它。
"""
import json
import os
import threading
import time

from .config import data_dir

_lock = threading.Lock()
_data: dict | None = None


def _path():
    return data_dir() / "水印检查.json"


def _key(path: str) -> str:
    return os.path.normcase(os.path.normpath(path or ""))


def _sig(path: str):
    try:
        s = os.stat(path)
        return [s.st_size, int(s.st_mtime)]
    except OSError:
        return None


def _load() -> dict:
    global _data
    if _data is None:
        try:
            _data = json.loads(_path().read_text("utf-8-sig"))
            if not isinstance(_data, dict):
                _data = {}
        except (OSError, ValueError):
            _data = {}
    return _data


def _save():
    p = _path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(_data, ensure_ascii=False), "utf-8")
    os.replace(tmp, p)


def get(path: str) -> dict | None:
    """查过、文件没变:{"hits": [...], "shot": "...", "ok": bool};没查过 / 文件变了:None。"""
    with _lock:
        r = _load().get(_key(path))
        if not r or r.get("sig") != _sig(path):
            return None
        return _view(r)


def put(path: str, res: dict, ok: bool | None = None, blurred: bool = False) -> dict:
    """记下一条的查水印结果(以前点过「没水印」的,同一个文件再查还算数)。返回记下的。
    模糊过的:blurred=True、ok=True(查到的那些已经糊掉了,不再拦)。"""
    with _lock:
        d = _load()
        old = d.get(_key(path)) or {}
        sig = _sig(path)
        keep_ok = (bool(old.get("ok")) and old.get("sig") == sig) if ok is None else bool(ok)
        d[_key(path)] = {"sig": sig, "hits": res.get("hits") or [], "shot": res.get("shot") or "",
                         "ok": keep_ok, "blurred": bool(blurred), "at": int(time.time())}
        _save()
        return _view(d[_key(path)])


def _view(r: dict) -> dict:
    return {"hits": r.get("hits") or [], "shot": r.get("shot") or "", "ok": bool(r.get("ok")), "blurred": bool(r.get("blurred"))}


def set_ok(path: str, ok: bool) -> None:
    """人看过了:ok=True「没水印 / 不用管,能发」;False「确实有水印」。"""
    with _lock:
        r = _load().get(_key(path))
        if r:
            r["ok"] = bool(ok)
            _save()


def move(old: str, new: str) -> None:
    """改名了(整理话题 / 改标题):结果跟着走。"""
    with _lock:
        d = _load()
        r = d.pop(_key(old), None)
        if r:
            r["sig"] = _sig(new)
            d[_key(new)] = r
            _save()


def blocks(res: dict | None) -> bool:
    """这个结果要不要拦着不发:查到了、人还没说没问题。"""
    return bool(res and res.get("hits") and not res.get("ok"))
