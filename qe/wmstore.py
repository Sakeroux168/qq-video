"""查水印 / 查口播广告的结果记在硬盘上(数据目录\\水印检查.json、广告检查.json),
关了软件再开、16 个号和教育号两边都认得。

一条视频按路径记,带上(大小, 修改时间):文件变了(转竖屏 / 模糊过 / 剪过 / 员工换了一条)就当没查过。
ok = 人看过说「没水印 / 不是广告,能发」(误报),之后就不拦它。
模块里的 get / put / set_ok / move 是水印的;广告用 ADS.get(...) 这些。
"""
import json
import os
import threading
import time

from .config import data_dir


def _key(path: str) -> str:
    return os.path.normcase(os.path.normpath(path or ""))


def _sig(path: str):
    try:
        s = os.stat(path)
        return [s.st_size, int(s.st_mtime)]
    except OSError:
        return None


def _view(r: dict) -> dict:
    return {"hits": r.get("hits") or [], "shot": r.get("shot") or "", "ok": bool(r.get("ok")),
            "blurred": bool(r.get("blurred"))}


class Store:
    def __init__(self, filename: str):
        self.filename = filename
        self._lock = threading.Lock()
        self._data: dict | None = None

    def _path(self):
        return data_dir() / self.filename

    def _load(self) -> dict:
        if self._data is None:
            try:
                self._data = json.loads(self._path().read_text("utf-8-sig"))
                if not isinstance(self._data, dict):
                    self._data = {}
            except (OSError, ValueError):
                self._data = {}
        return self._data

    def _save(self):
        p = self._path()
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False), "utf-8")
        os.replace(tmp, p)

    def get(self, path: str) -> dict | None:
        """查过、文件没变:{"hits": [...], "shot": "...", "ok": bool, "blurred": bool};没查过 / 文件变了:None。"""
        with self._lock:
            r = self._load().get(_key(path))
            if not r or r.get("sig") != _sig(path):
                return None
            return _view(r)

    def put(self, path: str, res: dict, ok: bool | None = None, blurred: bool = False) -> dict:
        """记下一条的结果(以前点过「没问题」的,同一个文件再查还算数)。返回记下的。
        处理过的(糊过水印 / 剪过广告):blurred=True、ok=True,不再拦。"""
        with self._lock:
            d = self._load()
            old = d.get(_key(path)) or {}
            sig = _sig(path)
            keep_ok = (bool(old.get("ok")) and old.get("sig") == sig) if ok is None else bool(ok)
            d[_key(path)] = {"sig": sig, "hits": res.get("hits") or [], "shot": res.get("shot") or "",
                             "ok": keep_ok, "blurred": bool(blurred), "at": int(time.time())}
            self._save()
            return _view(d[_key(path)])

    def set_ok(self, path: str, ok: bool) -> None:
        """人看过了:ok=True「误报,能发」;False「确实有」。"""
        with self._lock:
            r = self._load().get(_key(path))
            if r:
                r["ok"] = bool(ok)
                self._save()

    def move(self, old: str, new: str) -> None:
        """改名了(整理话题 / 改标题):结果跟着走。"""
        with self._lock:
            d = self._load()
            r = d.pop(_key(old), None)
            if r:
                r["sig"] = _sig(new)
                d[_key(new)] = r
                self._save()


WM = Store("水印检查.json")
ADS = Store("广告检查.json")
get, put, set_ok, move = WM.get, WM.put, WM.set_ok, WM.move


def blocks(res: dict | None) -> bool:
    """这个结果要不要拦着不发:查到了、人还没说没问题。"""
    return bool(res and res.get("hits") and not res.get("ok"))
