"""登录取钥匙(用户 2026-10-16:「可以做」):号的接口钥匙(client_id / client_secret)坏了,不用再开旧软件。

照旧软件「企鹅号批量发布」的做法(逆向看到的):开一个专用浏览器 → 人在里面扫码登录企鹅号 →
在已登录的页面里请求 https://om.qq.com/marticle/getOauthList → 从回话里读出 clientID / clientSecret。

**旧软件请求时带了 relogin=1,我们不带**:不知道它会不会让平台重新发一把钥匙(那样旧软件 / 别处在用的钥匙就作废了)。
只读列表,读不到就停下告诉人,不擅自重置。
- 浏览器:Edge(没有就 Chrome),每个号一个独立的登录目录(数据目录\\浏览器登录\\号名),登录一次以后再取就不用扫码。
- 只认企鹅号自己的页面(om.qq.com);读到的钥匙不打印、不写日志,直接加密存。
"""
import json
import os
import re
import shutil
import socket
import subprocess
import time
import urllib.request

from .cdp import CdpError, Page
from .config import data_dir

OAUTH_LIST = "https://om.qq.com/marticle/getOauthList?status=0"
LOGIN_URL = "https://om.qq.com/"
_NOWIN = 0x08000000 if os.name == "nt" else 0


def browser_path() -> str:
    for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"):
        if os.path.isfile(p):
            return p
    return shutil.which("msedge") or shutil.which("chrome") or ""


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def profile_dir(nick: str) -> str:
    safe = re.sub(r'[<>:"/\\|?*\s]', "_", nick) or "号"
    d = data_dir() / "浏览器登录" / safe
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


def launch(nick: str):
    """开一个这个号专用的浏览器,打开企鹅号首页让人登录。返回 (进程, 调试端口)。"""
    exe = browser_path()
    if not exe:
        raise RuntimeError("这台电脑上没找到 Edge / Chrome 浏览器")
    port = _free_port()
    proc = subprocess.Popen([exe, f"--remote-debugging-port={port}", f"--user-data-dir={profile_dir(nick)}",
                             "--no-first-run", "--no-default-browser-check", "--new-window", LOGIN_URL],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=_NOWIN)
    return proc, port


def _pages(port: int) -> list[dict]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=3) as r:
            return [t for t in json.loads(r.read().decode("utf-8")) if t.get("type") == "page"]
    except Exception:
        return []


_ID_KEYS = ("clientid", "client_id", "appid", "app_id")
_SEC_KEYS = ("clientsecret", "client_secret", "secret", "appsecret", "app_secret")
_NAME_KEYS = ("medianame", "media_name", "nick", "nickname", "name", "sourcename", "source_name", "title")
_MID_KEYS = ("mediaid", "media_id", "sourceid", "source_id", "omid", "uin")


def extract(obj) -> list[dict]:
    """回话里找钥匙:任何一层里同时有 client id 和 secret 的那个对象。返回 [{client_id, secret, name, media_id}]。"""
    out = []

    def pick(d: dict, keys) -> str:
        low = {str(k).lower(): v for k, v in d.items()}
        for k in keys:
            if k in low and isinstance(low[k], (str, int)) and str(low[k]).strip():
                return str(low[k]).strip()
        return ""

    def walk(x, parent_name="", parent_mid=""):
        if isinstance(x, dict):
            name = pick(x, _NAME_KEYS) or parent_name
            mid = pick(x, _MID_KEYS) or parent_mid
            cid, sec = pick(x, _ID_KEYS), pick(x, _SEC_KEYS)
            if cid and sec:
                out.append({"client_id": cid, "secret": sec, "name": name, "media_id": mid})
            for v in x.values():
                walk(v, name, mid)
        elif isinstance(x, list):
            for v in x:
                walk(v, parent_name, parent_mid)
    walk(obj)
    return out


def shape(obj, depth: int = 0) -> str:
    """回话长什么样(只有字段名,没有值):读不到钥匙时写进日志给做软件的人看。"""
    if depth > 3:
        return "…"
    if isinstance(obj, dict):
        return "{" + ", ".join(f"{k}: {shape(v, depth + 1)}" for k, v in list(obj.items())[:12]) + "}"
    if isinstance(obj, list):
        return f"[{shape(obj[0], depth + 1) if obj else ''}]×{len(obj)}"
    return type(obj).__name__


def try_read(port: int) -> tuple[str, list[dict], str]:
    """在已打开的企鹅号页面里读一次钥匙列表。返回 (状态, 钥匙列表, 回话结构)。
    状态:「没页面」/「没登录」/「读到了」/「读不到」。"""
    pages = [t for t in _pages(port) if "om.qq.com" in (t.get("url") or "")]
    if not pages:
        return "没页面", [], ""
    p = None
    try:
        p = Page(pages[0], timeout=10)
        js = ("fetch(%s, {credentials: 'include'}).then(r => r.text()).catch(e => 'ERR ' + e)" % json.dumps(OAUTH_LIST))
        txt = p.ev(js, timeout=20) or ""
    except CdpError:
        return "没页面", [], ""
    finally:
        if p:
            p.close()
    if txt.startswith("ERR"):
        return "没登录", [], ""
    try:
        data = json.loads(txt)
    except ValueError:
        return "没登录", [], ""                       # 没登录时一般回登录页 html
    keys = extract(data)
    if keys:
        return "读到了", keys, shape(data)
    if isinstance(data, dict) and str(data.get("response", {}).get("code", data.get("code", ""))) not in ("0", ""):
        return "没登录", [], shape(data)
    return "读不到", [], shape(data)


def wait_keys(port: int, stopped=None, timeout: float = 600, on_tick=None) -> tuple[str, list[dict], str]:
    """等人扫码登录,登录好了就读钥匙。返回 (状态, 钥匙列表, 回话结构)。"""
    end = time.time() + timeout
    last = ("没页面", [], "")
    while time.time() < end:
        if stopped and stopped():
            return "停下了", [], ""
        last = try_read(port)
        if last[0] in ("读到了", "读不到"):
            return last
        if on_tick:
            on_tick(last[0])
        time.sleep(3)
    return ("超时",) + last[1:]


def match(keys: list[dict], nick: str, source_id: str = "", old_client_id: str = "") -> dict | None:
    """一个账号下面可能有好几个号:按 client_id / 号 ID / 名字挑出要的那个;只有一个就是它。"""
    for k in keys:
        if old_client_id and k["client_id"] == old_client_id:
            return k
    for k in keys:
        if source_id and k.get("media_id") == str(source_id):
            return k
    for k in keys:
        if nick and k.get("name") and (k["name"] == nick or nick in k["name"] or k["name"] in nick):
            return k
    return keys[0] if len(keys) == 1 else None
