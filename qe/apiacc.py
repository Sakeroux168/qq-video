"""接口发的 16 个号:从旧软件「企鹅号批量发布」的数据库搬过来,存在 数据目录\\接口账号.json。

client_secret 用 Windows 自带的 DPAPI 加密(只有这台电脑、这个 Windows 用户能解开),文件里没有明文;
界面、日志里都不显示。旧软件的密码 / cookie 用不上,不搬。
"""
import base64
import ctypes
import json
import os
import sqlite3
from ctypes import wintypes

from .config import data_dir

OLD_DB = r"Z:\测试\企鹅号批量发布\data\qepm.db"
CATEGORIES = {1604: "网络游戏", 1600: "手机游戏", 1605: "电竞赛事", 401: "动漫周边"}


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _crypt(data: bytes, protect: bool) -> bytes:
    if os.name != "nt":                          # 测试机不是 Windows 时:不加密(只在测试里用)
        return data
    buf = ctypes.create_string_buffer(data, len(data))
    src = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out = _Blob()
    fn = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
    if not fn(ctypes.byref(src), None, None, None, None, 0, ctypes.byref(out)):
        raise OSError("DPAPI 加解密失败(换了电脑或 Windows 用户?请重新搬一次账号)")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def seal(s: str) -> str:
    return base64.b64encode(_crypt(s.encode("utf-8"), True)).decode("ascii")


def unseal(s: str) -> str:
    return _crypt(base64.b64decode(s or ""), False).decode("utf-8") if s else ""


def store_path():
    return data_dir() / "接口账号.json"


def load() -> list[dict]:
    """[{nick, source_name, source_id, client_id, secret(加密的), category, enabled}]"""
    try:
        return json.loads(store_path().read_text("utf-8"))
    except (OSError, ValueError):
        return []


def save(accs: list[dict]):
    p = store_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(accs, ensure_ascii=False, indent=1), "utf-8")
    os.replace(tmp, p)


def migrate(db: str = OLD_DB) -> int:
    """从旧数据库搬(只读打开)。已经有的号更新,返回搬了几个。"""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute("select nick, source_name, source_id, client_id, client_secret, category, enabled "
                           "from accounts order by sort_order, id").fetchall()
    finally:
        con.close()
    have = {a["nick"]: a for a in load()}
    for nick, sname, sid, cid, sec, cat, en in rows:
        nick = (nick or sname or "").strip()
        if not nick or not cid or not sec:
            continue
        a = have.get(nick, {})
        a.update({"nick": nick, "source_name": sname or "", "source_id": str(sid or ""), "client_id": cid,
                  "secret": seal(sec), "category": int(cat or 0), "enabled": bool(en)})
        have[nick] = a
    save(list(have.values()))
    return len(rows)


def find(nick: str) -> dict | None:
    for a in load():
        if a.get("nick") == nick:
            return a
    return None


def nicks() -> list[str]:
    return [a["nick"] for a in load() if a.get("enabled", True)]
