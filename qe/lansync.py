"""多台电脑局域网互通(方案 B:一台当主机开轻量 HTTP 接口,另一台当从机实时连主机共用记录/检查缓存/账号设置)。

设计原则:
- 主机(lan_role='host')用自己本地 SQLite 与 JSON,顺带在后台开 ThreadingHTTPServer;
- 从机(lan_role='client')的所有写操作与发布前查重/额度计数全部直连主机,主机离线直接报错拦住,绝不悄悄回退本地各自写;
- 从机保留一份增量同步过来的本地只读镜像数据库(发布记录_主机镜像.sqlite)与缓存副本,列表渲染 0 毫秒不卡界面;
- 不跨电脑互锁运行中.lock,截图/皮肤/定时各自留在本机。
"""
import base64
import gzip
import hashlib
import hmac
import json
import os
import secrets
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

from .config import APP_VERSION, data_dir

ROLE_OFF = "off"
ROLE_HOST = "host"
ROLE_CLIENT = "client"
DEFAULT_PORT = 18620

LOCAL_ONLY_KEYS = frozenset({
    "lan_role", "lan_port", "lan_host", "lan_token", "lan_merged_at",
    "theme", "splash", "schedules", "sched_notice",
    "last_date", "api_last_date", "api_detail_open",
    "bad_cover_dir", "material_root", "archive_root", "api_roots", "api_archive",
    "api_threads", "api_per_acc",
})

SHARED_SETTING_KEYS = frozenset({
    "accounts", "daily_plan", "quota_extra", "quota_open", "redo_room",
    "api_picked", "api_cover", "api_interval", "api_archive_by_game",
    "batch_size", "topic_model", "outro_check", "sharp_check", "crop_check",
    "ai_cover", "ai_cover_trust", "bad_cover_auto", "game_words",
    "ai_key", "own_ai_url", "own_ai_model", "own_ai_key", "own_ai_vision",
    "api_last_topic",
})

DICT_MERGE_KEYS = frozenset({"daily_plan", "quota_extra", "redo_room"})
NESTED2_MERGE_KEYS = frozenset({"api_picked"})

STORE_FILES = {
    "wm": "水印检查.json",
    "ads": "广告检查.json",
    "crop": "字幕被裁.json",
    "outro": "结尾检查.json",
    "sharp": "清晰度检查.json",
    "gamecheck": "游戏判断.json",
    "titledate": "标题日期放行.json",
    "titleclean": "标题广告处理过.json",
    "dimcache": "视频尺寸.json",
    "adjust": "封面调整.json",
    "aicover": "AI看封面2.json",
    "ledger": "话题改名台账.json",
    "blackcover": "黑封面.json",
}

ALL_KINDS = tuple(STORE_FILES) + ("settings", "apiacc")


class LanError(OSError):
    """局域网主机连不上 / 配对码不对 / 同步失败。从机发布或写入时必须拦住,绝不降级写本地。"""


def gen_pin() -> str:
    return f"{secrets.randbelow(900000) + 100000}"


def parse_addr(addr: str, default_port: int = DEFAULT_PORT) -> tuple[str, int]:
    s = str(addr or "").strip()
    if s.startswith("http://"):
        s = s[7:]
    elif s.startswith("https://"):
        s = s[8:]
    s = s.split("/", 1)[0].strip()
    if ":" in s:
        h, p = s.rsplit(":", 1)
        try:
            return h.strip(), max(1, min(65535, int(p)))
        except ValueError:
            return h.strip(), default_port
    return s, default_port


def host_info() -> tuple[str, list[str]]:
    """返回 (本机电脑名, 局域网 IPv4 列表)。"""
    name = socket.gethostname() or "localhost"
    ips: list[str] = []
    try:
        for af, _, _, _, sa in socket.getaddrinfo(name, None, socket.AF_INET):
            if af == socket.AF_INET and sa and sa[0]:
                ip = sa[0]
                if not ip.startswith(("127.", "169.254.")) and ip not in ips:
                    ips.append(ip)
    except OSError:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith(("127.", "169.254.")) and ip not in ips:
            ips.insert(0, ip)
    except OSError:
        pass
    ips.sort(key=lambda x: (0 if x.startswith(("192.168.", "10.", "172.")) else 1, x))
    return name, ips


def _stream(key: bytes, nonce: bytes, n: int) -> bytes:
    out = bytearray()
    i = 0
    while len(out) < n:
        out += hashlib.sha256(key + nonce + i.to_bytes(4, "big")).digest()
        i += 1
    return bytes(out[:n])


def wrap_secret_payload(token: str, obj) -> str:
    """用局域网配对码派生密钥流加密账号包(避免密钥在局域网报文中明文出现)。"""
    key = hashlib.sha256(("qe-lan-acc:" + str(token or "")).encode("utf-8")).digest()
    raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    nonce = os.urandom(16)
    ks = _stream(key, nonce, len(raw))
    ct = bytes(a ^ b for a, b in zip(raw, ks))
    mac = hmac.new(key, b"LAN1" + nonce + ct, hashlib.sha256).digest()[:16]
    return base64.b64encode(nonce + mac + ct).decode("ascii")


def unwrap_secret_payload(token: str, b64: str):
    key = hashlib.sha256(("qe-lan-acc:" + str(token or "")).encode("utf-8")).digest()
    blob = base64.b64decode(b64)
    if len(blob) < 32:
        raise LanError("同步账号数据损坏")
    nonce, mac, ct = blob[:16], blob[16:32], blob[32:]
    want = hmac.new(key, b"LAN1" + nonce + ct, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(mac, want):
        raise LanError("同步账号校验失败(配对码不一致?)")
    ks = _stream(key, nonce, len(ct))
    return json.loads(bytes(a ^ b for a, b in zip(ct, ks)).decode("utf-8"))


def _gz_b64(raw: bytes) -> str:
    return base64.b64encode(gzip.compress(raw, compresslevel=5)).decode("ascii")


def _ungz_b64(s: str) -> bytes:
    return gzip.decompress(base64.b64decode(s))


def serialize_arg(v):
    if hasattr(v, "path") and hasattr(v, "title") and hasattr(v, "account"):
        return {
            "__video__": 1,
            "date": str(getattr(v, "date", "") or ""),
            "account": str(getattr(v, "account", "") or ""),
            "employee": str(getattr(v, "employee", "") or ""),
            "title": str(getattr(v, "title", "") or ""),
            "path": str(getattr(v, "path", "") or ""),
            "cover_kind": str(getattr(v, "cover_kind", "") or ""),
        }
    return v


def deserialize_arg(v):
    if isinstance(v, dict) and v.get("__video__") == 1:
        return SimpleNamespace(**{k: val for k, val in v.items() if k != "__video__"})
    return v


def merge_settings_patch(disk: dict, patch: dict) -> list[str]:
    """把补丁温和合并到设置字典(按日期/号拆键的字典只按子键合并,不互相覆盖)。返回实际写入的键。"""
    touched = []
    for k, val in patch.items():
        if k not in SHARED_SETTING_KEYS:
            continue
        if k in DICT_MERGE_KEYS and isinstance(val, dict):
            cur = disk.get(k)
            cur = dict(cur) if isinstance(cur, dict) else {}
            cur.update(val)
            disk[k] = cur
        elif k in NESTED2_MERGE_KEYS and isinstance(val, dict):
            cur = disk.get(k)
            cur = dict(cur) if isinstance(cur, dict) else {}
            for sub_k, sub_v in val.items():
                if isinstance(sub_v, dict) and isinstance(cur.get(sub_k), dict):
                    merged = dict(cur[sub_k])
                    merged.update(sub_v)
                    cur[sub_k] = merged
                else:
                    cur[sub_k] = sub_v
            disk[k] = cur
        else:
            disk[k] = val
        touched.append(k)
    return touched


# ---------------- 运行时全局挂钩(按当前 data_dir 隔离,不串单元测试) ----------------
_REG_LOCK = threading.RLock()
_HOST = None
_CLIENT = None
_BOUND_DATA = ""
_TLS = threading.local()


def is_reloading() -> bool:
    return bool(getattr(_TLS, "reloading", False))


def active_host():
    with _REG_LOCK:
        if _HOST is not None and _BOUND_DATA == str(data_dir()):
            return _HOST
        return None


def active_client():
    if getattr(_TLS, "in_host", False):
        return None
    with _REG_LOCK:
        if _CLIENT is not None and _BOUND_DATA == str(data_dir()):
            return _CLIENT
        return None


def bump(kind: str) -> None:
    if getattr(_TLS, "in_host", False):
        h = _HOST
        if h is not None:
            h.bump(kind)
        return
    h = active_host()
    if h is not None:
        h.bump(kind)


def stop() -> None:
    global _HOST, _CLIENT, _BOUND_DATA
    with _REG_LOCK:
        if _HOST is not None:
            try:
                _HOST.stop()
            except Exception:
                pass
            _HOST = None
        if _CLIENT is not None:
            try:
                _CLIENT.close()
            except Exception:
                pass
            _CLIENT = None
        _BOUND_DATA = ""


def _reload_store(kind: str) -> None:
    if kind in ("wm", "ads", "crop", "outro", "sharp"):
        from . import wmstore
        s = wmstore.by_key(kind)
        if s is not None:
            s.reload()
    elif kind == "gamecheck":
        from . import gamecheck
        gamecheck.store().reload()
    elif kind == "titledate":
        from . import titledate
        titledate.store().reload()
    elif kind == "titleclean":
        from . import titleclean
        titleclean.store().reload()
    elif kind == "dimcache":
        from . import dimcache
        dimcache.reload()
    elif kind == "adjust":
        h = active_host()
        c = active_client()
        adj = (h and h.adj) or (c and c.adj)
        if adj is not None and hasattr(adj, "reload"):
            adj.reload()


def _exec_store_op(kind: str, op: str, kw: dict, adj=None):
    """在主机进程里执行各缓存 / 设置仓库的写操作并抬高版本号。"""
    if kind in ("wm", "ads", "crop", "outro", "sharp"):
        from . import wmstore
        st = wmstore.by_key(kind)
        if st is None:
            raise LanError(f"未知仓库:{kind}")
        if op == "put":
            res = dict(kw.get("res") or {})
            shot_b64 = kw.get("shot_b64") or ""
            shot_sub = kw.get("shot_sub") or ""
            shot_name = os.path.basename(kw.get("shot_name") or "")
            if shot_b64 and shot_sub in ("结尾截图", "水印截图") and shot_name:
                d = data_dir() / shot_sub
                d.mkdir(parents=True, exist_ok=True)
                sp = d / shot_name
                tmp = sp.with_suffix(".tmp")
                tmp.write_bytes(base64.b64decode(shot_b64))
                os.replace(tmp, sp)
                res["shot"] = str(sp)
            return st.put(kw["path"], res, ok=kw.get("ok"), blurred=bool(kw.get("blurred", False)))
        if op == "set_ok":
            st.set_ok(kw["path"], bool(kw["ok"]))
            return True
        if op == "move":
            st.move(kw["old"], kw["new"])
            return True
    elif kind == "gamecheck":
        from . import gamecheck
        gs = gamecheck.store()
        if op == "set_ai":
            gs.set_ai(kw["got"])
            return True
        if op == "set_ok":
            gs.set_ok(kw["nick"], kw["title"], bool(kw.get("on", True)))
            return True
        if op == "set_batch_ok":
            gs.set_batch_ok(kw["nick"], kw["day"], bool(kw.get("on", True)))
            return True
    elif kind == "titledate":
        from . import titledate
        titledate.store().set(kw["account"], kw["title"], bool(kw.get("on", True)))
        return True
    elif kind == "titleclean":
        from . import titleclean
        titleclean.store().set(kw["account"], kw["title"], bool(kw.get("on", True)))
        return True
    elif kind == "dimcache":
        from . import dimcache
        entries = kw.get("entries") or {}
        if entries:
            dimcache.merge_remote(entries)
        return True
    elif kind == "adjust":
        from .adjust import Adjustments
        a = adj if adj is not None else Adjustments()
        if adj is None:
            a.reload()
        if op == "set_box":
            a.set_box(kw["video"], kw["cover"], kw["rkey"], kw["cx"], kw["cy"], kw.get("title", ""))
        elif op == "set_ai235":
            a.set_ai235(kw["video"], kw["on"], kw.get("title", ""))
        elif op == "set_own_cover":
            a.set_own_cover(kw["video"], kw["path"])
        elif op == "reset":
            a.reset(kw["video"])
        elif op == "set_ok":
            a.set_ok(kw["video"], kw["cover"], kw.get("title", ""))
        else:
            raise LanError(f"未知调整操作:{op}")
        return True
    elif kind == "aicover":
        from . import aicover
        aicover.put_entry(kw["key"], kw["res"])
        return True
    elif kind == "ledger":
        from .topic import Ledger
        lg = Ledger(data_dir() / "话题改名台账.json")
        if op == "add":
            lg.add(kw["at"], kw["moves"])
        elif op == "save":
            lg._save(kw["data"])
            bump("ledger")
        return True
    elif kind == "blackcover":
        from . import blackcover
        blackcover.save(kw["day"], kw["items"])
        return True
    raise LanError(f"不支持的仓库操作:{kind}.{op}")


_REC_ALLOW = frozenset({
    "prepared", "failed", "mark_batch_published", "manual_published",
    "api_result", "api_begin", "try_begin", "mark_moved", "relink",
    "api_finish", "resolve_unsure", "resolve_found", "note_once", "repath",
    "mark_sent", "mark_failed_published", "drop_batch", "mark_unsent", "undo_sent",
    "unsure_paths", "failed_in_batch", "ready_in_batch", "status_of", "blocked",
    "rows", "sent_on", "published_on", "sent_row", "problems_on", "summary",
    "open_batches", "find_for_cover", "search_title", "status_by_id", "movable_ids_for_keys",
})


class HostServer:
    """主机端内置局域网服务。"""

    def __init__(self, st, rec, adj=None, port: int = DEFAULT_PORT, token: str = "", on_change=None):
        self.st = st
        self.rec = rec
        self.adj = adj
        self.data_root = str(data_dir())
        self.port = DEFAULT_PORT if port is None else int(port)
        self.token = str(token or "")
        self.on_change = on_change
        self._lock = threading.RLock()
        self._revs = {k: 1 for k in ALL_KINDS}
        self._httpd: ThreadingHTTPServer | None = None
        self._thr: threading.Thread | None = None
        self.bound_port = 0

    def bump(self, kind: str) -> int:
        with self._lock:
            if kind in self._revs:
                self._revs[kind] += 1
                v = self._revs[kind]
            else:
                v = 0
        return v

    def revs(self) -> dict[str, int]:
        with self._lock:
            return dict(self._revs)

    def _notify(self, kind: str):
        if self.on_change:
            try:
                self.on_change(kind)
            except Exception:
                pass

    def _read_store_bytes(self, kind: str) -> bytes:
        if kind == "settings":
            with self._lock:
                shared = {k: self.st[k] for k in SHARED_SETTING_KEYS if k in self.st}
                return json.dumps(shared, ensure_ascii=False).encode("utf-8")
        if kind == "apiacc":
            from . import apiacc
            accs = [dict(a, secret=apiacc.unseal(a.get("secret", "")) if a.get("secret") else "")
                    for a in apiacc.load()]
            qaccs = [dict(a, secret=apiacc.unseal(a.get("secret", "")) if a.get("secret") else "")
                     for a in apiacc.qload()]
            wrapped = wrap_secret_payload(self.token, {"api": accs, "q": qaccs})
            return json.dumps({"wrapped": wrapped}, ensure_ascii=False).encode("utf-8")
        fn = STORE_FILES.get(kind)
        if not fn:
            return b"{}"
        p = data_dir() / fn
        if p.is_file():
            return p.read_bytes()
        return b"[]" if kind == "ledger" else b"{}"

    def start(self):
        srv_ref = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, fmt, *args):
                return

            def _auth(self) -> bool:
                if not srv_ref.token:
                    return True
                got = self.headers.get("X-QE-Token", "")
                return hmac.compare_digest(got, srv_ref.token)

            def _json_in(self) -> dict:
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0:
                    return {}
                return json.loads(self.rfile.read(n).decode("utf-8"))

            def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8"):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)

            def _send_json(self, code: int, obj: dict):
                self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

            def do_GET(self):
                if not self._auth():
                    self._send_json(403, {"ok": False, "err": "配对码不对"})
                    return
                from . import config as _cfg
                _TLS.in_host = True
                old_ctx = getattr(_cfg._LOCAL_CTX, "data_dir", "")
                _cfg._LOCAL_CTX.data_dir = srv_ref.data_root
                try:
                    u = urlparse(self.path)
                    qs = parse_qs(u.query)
                    if u.path == "/ping":
                        self._send_json(200, {
                            "ok": True, "host": socket.gethostname(), "app_version": APP_VERSION,
                            "db_rev": srv_ref.rec.current_rev(), "revs": srv_ref.revs(),
                            "posts": srv_ref.rec.count_all(),
                        })
                    elif u.path == "/rec/delta":
                        since = int((qs.get("since") or ["-1"])[0])
                        full = (qs.get("full") or ["0"])[0] == "1"
                        d = srv_ref.rec.delta_since(since, force_full=full)
                        if d["mode"] == "full":
                            raw = json.dumps(d["rows"], ensure_ascii=False).encode("utf-8")
                            self._send_json(200, {"ok": True, "mode": "full", "db_rev": d["db_rev"], "rows_gz": _gz_b64(raw)})
                        else:
                            self._send_json(200, {"ok": True, **d})
                    elif u.path == "/sync/poll":
                        known = json.loads((qs.get("known") or ["{}"])[0])
                        db_since = int(known.get("db") if known.get("db") is not None else -1)
                        db_full = db_since < 0
                        db = srv_ref.rec.delta_since(db_since, force_full=db_full)
                        if db["mode"] == "full":
                            raw = json.dumps(db["rows"], ensure_ascii=False).encode("utf-8")
                            db = {"mode": "full", "db_rev": db["db_rev"], "rows_gz": _gz_b64(raw)}
                        k_stores = known.get("stores") or {}
                        cur_revs = srv_ref.revs()
                        changed = {}
                        for sk, rev in cur_revs.items():
                            if rev > int(k_stores.get(sk) or 0):
                                changed[sk] = {"rev": rev, "gz": _gz_b64(srv_ref._read_store_bytes(sk))}
                        self._send_json(200, {"ok": True, "db": db, "revs": cur_revs, "stores": changed})
                    elif u.path.startswith("/shot/"):
                        parts = [p for p in u.path[6:].split("/") if p]
                        if len(parts) == 2 and parts[0] in ("结尾截图", "水印截图") and ".." not in parts[1]:
                            from urllib.parse import unquote
                            fp = data_dir() / parts[0] / os.path.basename(unquote(parts[1]))
                            if fp.is_file():
                                self._send(200, fp.read_bytes(), "image/jpeg")
                                return
                        self._send_json(404, {"ok": False, "err": "not found"})
                    else:
                        self._send_json(404, {"ok": False, "err": "unknown endpoint"})
                finally:
                    _TLS.in_host = False
                    _cfg._LOCAL_CTX.data_dir = old_ctx

            def do_POST(self):
                if not self._auth():
                    self._send_json(403, {"ok": False, "err": "配对码不对"})
                    return
                from . import config as _cfg
                _TLS.in_host = True
                old_ctx = getattr(_cfg._LOCAL_CTX, "data_dir", "")
                _cfg._LOCAL_CTX.data_dir = srv_ref.data_root
                u = urlparse(self.path)
                try:
                    body = self._json_in()
                    if u.path == "/rec/call":
                        m = body.get("method") or ""
                        if m not in _REC_ALLOW:
                            self._send_json(400, {"ok": False, "err": f"method not allowed: {m}"})
                            return
                        since = int(body.get("since") if body.get("since") is not None else -1)
                        args = [deserialize_arg(a) for a in (body.get("args") or [])]
                        kwargs = {k: deserialize_arg(v) for k, v in (body.get("kwargs") or {}).items()}
                        res = getattr(srv_ref.rec, m)(*args, **kwargs)
                        delta = srv_ref.rec.delta_since(since) if since >= 0 else {"mode": "noop", "db_rev": srv_ref.rec.current_rev()}
                        if delta["mode"] != "noop" or m in (
                            "prepared", "failed", "mark_batch_published", "manual_published", "api_result",
                            "api_begin", "try_begin", "mark_moved", "relink", "api_finish", "resolve_unsure",
                            "resolve_found", "note_once", "repath", "mark_sent", "mark_failed_published",
                            "drop_batch", "mark_unsent", "undo_sent"
                        ):
                            srv_ref._notify("rec")
                        self._send_json(200, {"ok": True, "result": res, "delta": delta})
                    elif u.path == "/rec/merge":
                        rows = body.get("rows") or []
                        merged, skipped = srv_ref.rec.merge_rows(rows)
                        if merged:
                            srv_ref._notify("rec")
                        self._send_json(200, {"ok": True, "merged": merged, "skipped": skipped, "db_rev": srv_ref.rec.current_rev()})
                    elif u.path == "/store/op":
                        kind = body.get("kind") or ""
                        op = body.get("op") or ""
                        kw = body.get("kwargs") or {}
                        res = _exec_store_op(kind, op, kw, adj=srv_ref.adj)
                        rev = srv_ref.bump(kind)
                        srv_ref._notify(kind)
                        self._send_json(200, {"ok": True, "result": res, "rev": rev})
                    elif u.path == "/settings/patch":
                        patch = body.get("patch") or {}
                        with srv_ref._lock:
                            touched = merge_settings_patch(srv_ref.st, patch)
                            for k in touched:
                                srv_ref.st._dirty.add(k)
                            srv_ref.st.save()
                            rev = srv_ref.bump("settings")
                        if touched:
                            srv_ref._notify("settings")
                        self._send_json(200, {"ok": True, "rev": rev})
                    elif u.path == "/accounts/push":
                        from . import apiacc
                        payload = unwrap_secret_payload(srv_ref.token, body.get("wrapped") or "")
                        if "api" in payload:
                            accs = [dict(a, secret=apiacc.seal(a["secret"]) if a.get("secret") else "") for a in payload["api"]]
                            apiacc.save(accs)
                        if "q" in payload:
                            qaccs = [dict(a, secret=apiacc.seal(a["secret"]) if a.get("secret") else "") for a in payload["q"]]
                            apiacc.qsave(qaccs)
                        rev = srv_ref.bump("apiacc")
                        srv_ref._notify("apiacc")
                        self._send_json(200, {"ok": True, "rev": rev})
                    else:
                        self._send_json(404, {"ok": False, "err": "unknown endpoint"})
                except Exception as e:
                    self._send_json(500, {"ok": False, "err": f"{type(e).__name__}: {e}"})
                finally:
                    _TLS.in_host = False
                    _cfg._LOCAL_CTX.data_dir = old_ctx

        class _Server(ThreadingHTTPServer):
            allow_reuse_address = True
            daemon_threads = True

        self._httpd = _Server(("0.0.0.0", self.port), Handler)
        self.bound_port = int(self._httpd.server_address[1])
        self._thr = threading.Thread(target=self._httpd.serve_forever, daemon=True, name="qe-lan-host")
        self._thr.start()
        return self

    def stop(self):
        if self._httpd is not None:
            try:
                self._httpd.shutdown()
            except Exception:
                pass
            try:
                self._httpd.server_close()
            except Exception:
                pass
            self._httpd = None


class LanClient:
    """从机客户端:负责和主机通信,维护增量镜像、缓存拉取与在线状态。"""

    def __init__(self, host_addr: str, token: str, st, adj=None, on_change=None):
        self.host_addr = str(host_addr or "").strip()
        self.token = str(token or "")
        self.st = st
        self.adj = adj
        self.on_change = on_change
        self.online = False
        self.last_err = ""
        self._lock = threading.RLock()
        self._poll_lock = threading.Lock()
        self._known_stores: dict[str, int] = {}
        self.rec = None
        import requests
        self._sess = requests.Session()
        self._sess.trust_env = False     # 绝不走本机代理,直连局域网主机

    def _base(self) -> str:
        h, p = parse_addr(self.host_addr, DEFAULT_PORT)
        if not h:
            raise LanError("设置里还没填主机电脑名字或局域网 IP")
        return f"http://{h}:{p}"

    def _headers(self) -> dict[str, str]:
        return {"X-QE-Token": self.token} if self.token else {}

    def _req(self, method: str, path: str, json_body=None, params=None, timeout=(2.0, 12.0), raw: bool = False):
        url = self._base() + path
        try:
            r = self._sess.request(method, url, json=json_body, params=params, headers=self._headers(), timeout=timeout)
        except Exception as e:
            self.online = False
            self.last_err = f"连不上主机({self.host_addr}):{type(e).__name__}"
            raise LanError(f"连不上主机({self.host_addr}),请确认主机电脑上「企鹅号发布助手」开着、局域网能通") from e
        if r.status_code == 403:
            self.online = False
            self.last_err = "配对码不对"
            raise LanError("主机拒绝连接:配对码不对(去两边「设置」核对一下配对码)")
        if raw:
            if r.status_code != 200:
                raise LanError(f"主机返回异常({r.status_code})")
            self.online = True
            self.last_err = ""
            return r.content
        try:
            data = r.json()
        except Exception as e:
            raise LanError(f"主机返回读不出来({r.status_code})") from e
        if not data.get("ok"):
            raise LanError(data.get("err") or f"主机报错({r.status_code})")
        self.online = True
        self.last_err = ""
        return data

    def ping(self) -> dict:
        return self._req("GET", "/ping", timeout=(2.0, 4.0))

    def rec_call(self, method: str, args: list, kwargs: dict, since: int = -1) -> dict:
        return self._req("POST", "/rec/call", {
            "method": method,
            "args": [serialize_arg(a) for a in args],
            "kwargs": {k: serialize_arg(v) for k, v in kwargs.items()},
            "since": int(since),
        })

    def rec_delta(self, since: int = 0, full: bool = False) -> dict:
        return self._req("GET", "/rec/delta", params={"since": str(int(since)), "full": "1" if full else "0"}, timeout=(2.0, 20.0))

    def rec_merge(self, rows: list[dict]) -> dict:
        return self._req("POST", "/rec/merge", {"rows": rows}, timeout=(2.0, 20.0))

    def store_op(self, kind: str, op: str, **kw):
        res = self._req("POST", "/store/op", {"kind": kind, "op": op, "kwargs": kw})
        if res.get("rev"):
            with self._lock:
                self._known_stores[kind] = max(self._known_stores.get(kind, 0), int(res["rev"]))
        return res.get("result")

    def push_settings(self, patch: dict) -> None:
        if not patch:
            return
        res = self._req("POST", "/settings/patch", {"patch": patch})
        if res.get("rev"):
            with self._lock:
                self._known_stores["settings"] = max(self._known_stores.get("settings", 0), int(res["rev"]))

    def push_accounts(self, accs: list[dict], qaccs: list[dict]) -> None:
        from . import apiacc
        p_api = [dict(a, secret=apiacc.unseal(a.get("secret", "")) if a.get("secret") else "") for a in accs]
        p_q = [dict(a, secret=apiacc.unseal(a.get("secret", "")) if a.get("secret") else "") for a in qaccs]
        wrapped = wrap_secret_payload(self.token, {"api": p_api, "q": p_q})
        res = self._req("POST", "/accounts/push", {"wrapped": wrapped})
        if res.get("rev"):
            with self._lock:
                self._known_stores["apiacc"] = max(self._known_stores.get("apiacc", 0), int(res["rev"]))

    def fetch_shot(self, sub: str, name: str) -> str:
        if sub not in ("结尾截图", "水印截图") or not name:
            return ""
        from urllib.parse import quote
        try:
            raw = self._req("GET", f"/shot/{quote(sub)}/{quote(name)}", timeout=(2.0, 6.0), raw=True)
        except Exception:
            return ""
        d = data_dir() / sub
        d.mkdir(parents=True, exist_ok=True)
        dst = d / os.path.basename(name)
        tmp = dst.with_suffix(".tmp")
        tmp.write_bytes(raw)
        os.replace(tmp, dst)
        return str(dst)

    def _apply_store_bytes(self, kind: str, raw: bytes) -> None:
        _TLS.reloading = True
        try:
            if kind == "settings":
                shared = json.loads(raw.decode("utf-8"))
                changed = False
                for k, v in shared.items():
                    if k in SHARED_SETTING_KEYS and self.st.get(k) != v:
                        self.st[k] = v
                        changed = True
                if changed:
                    self.st.save()
                return
            if kind == "apiacc":
                from . import apiacc
                obj = json.loads(raw.decode("utf-8"))
                payload = unwrap_secret_payload(self.token, obj.get("wrapped") or "")
                accs = [dict(a, secret=apiacc.seal(a["secret"]) if a.get("secret") else "") for a in payload.get("api") or []]
                qaccs = [dict(a, secret=apiacc.seal(a["secret"]) if a.get("secret") else "") for a in payload.get("q") or []]
                apiacc.save(accs)
                apiacc.qsave(qaccs)
                return
            fn = STORE_FILES.get(kind)
            if not fn:
                return
            dst = data_dir() / fn
            tmp = dst.with_suffix(".tmp")
            tmp.write_bytes(raw)
            os.replace(tmp, dst)
            _reload_store(kind)
        finally:
            _TLS.reloading = False

    def sync_poll(self, strict: bool = False) -> list[str]:
        """向主机拉一次新增记录和有变动的检查缓存/设置;返回本次有变动的种类列表。"""
        if not self._poll_lock.acquire(blocking=strict):
            return []
        try:
            db_since = self.rec.mirror_rev() if self.rec is not None else -1
            with self._lock:
                known = {"db": db_since, "stores": dict(self._known_stores)}
            try:
                res = self._req("GET", "/sync/poll", params={"known": json.dumps(known, separators=(",", ":"))},
                                timeout=(2.0, 20.0 if db_since <= 0 else 8.0))
            except LanError:
                if strict:
                    raise
                return []
            changed_kinds = []
            db = res.get("db") or {}
            mode = db.get("mode")
            if mode == "full" and self.rec is not None:
                rows = json.loads(_ungz_b64(db["rows_gz"]).decode("utf-8"))
                self.rec.apply_mirror_full(rows, int(db.get("db_rev") or 0))
                changed_kinds.append("rec")
            elif mode == "delta" and self.rec is not None:
                rows = db.get("rows") or []
                if rows:
                    self.rec.apply_mirror_delta(rows, int(db.get("db_rev") or 0))
                    changed_kinds.append("rec")
                elif db.get("db_rev"):
                    self.rec.set_mirror_rev(int(db["db_rev"]))
            for sk, info in (res.get("stores") or {}).items():
                raw = _ungz_b64(info["gz"])
                self._apply_store_bytes(sk, raw)
                with self._lock:
                    self._known_stores[sk] = max(self._known_stores.get(sk, 0), int(info.get("rev") or 0))
                changed_kinds.append(sk)
            if changed_kinds and self.on_change:
                try:
                    self.on_change(changed_kinds)
                except Exception:
                    pass
            return changed_kinds
        finally:
            self._poll_lock.release()

    def close(self):
        try:
            self._sess.close()
        except Exception:
            pass


def setup(st, rec=None, adj=None, on_change=None):
    """按设置启动主机服务或连接从机,并挂载全局同步钩子。返回要用的 Records 实例。"""
    global _HOST, _CLIENT, _BOUND_DATA
    stop()
    role = str(st.get("lan_role") or ROLE_OFF).strip().lower()
    if role == ROLE_HOST:
        from .records import Records
        r = rec if rec is not None else Records()
        if not str(st.get("lan_token") or "").strip():
            st["lan_token"] = gen_pin()
            st.save()
        port = DEFAULT_PORT if st.get("lan_port") is None else int(st["lan_port"])
        h = HostServer(st, r, adj=adj, port=port, token=str(st.get("lan_token") or ""), on_change=on_change)
        h.start()
        with _REG_LOCK:
            _BOUND_DATA = str(data_dir())
            _HOST = h
        return r
    if role == ROLE_CLIENT:
        from .records import RemoteRecords
        c = LanClient(str(st.get("lan_host") or ""), str(st.get("lan_token") or ""), st, adj=adj, on_change=on_change)
        rr = RemoteRecords(c)
        c.rec = rr
        with _REG_LOCK:
            _BOUND_DATA = str(data_dir())
            _CLIENT = c
        c.sync_poll(strict=False)
        return rr
    from .records import Records
    return rec if rec is not None else Records()


def test_connection(addr: str, token: str) -> dict:
    """设置界面点「测一下连不连得上」用,不改动当前运行角色。"""
    c = LanClient(addr, token, None)
    try:
        return c.ping()
    finally:
        c.close()


def unmerged_local_rows(client: LanClient | None = None) -> list[dict]:
    """从机自己本机旧库(发布记录.sqlite)里还没并入主机镜像的记录(仅在「已发 / 没发成 / 结果不明 / 发布中 / 摆好」里查)。"""
    from .records import Records, pkey
    local_p = data_dir() / "发布记录.sqlite"
    if not local_p.is_file():
        return []
    lr = Records(local_p)
    try:
        lrows = lr.rows()
    finally:
        lr.close()
    c = client or active_client()
    if c is None or c.rec is None or not c.rec.mirror_ready():
        return lrows
    have_sent = set()
    have_key = set()
    for r in c.rec.mirror_rows():
        k = pkey(r.get("path") or "")
        st_ = r.get("status") or ""
        if st_ == "已发":
            have_sent.add(k)
        have_key.add((k, st_, str(r.get("published_at") or "")[:10], str(r.get("title") or "")))
    out = []
    for r in lrows:
        k = pkey(r.get("path") or "")
        st_ = r.get("status") or ""
        if st_ == "已发" and k in have_sent:
            continue
        if (k, st_, str(r.get("published_at") or "")[:10], str(r.get("title") or "")) in have_key:
            continue
        out.append(r)
    return out


def merge_local_to_host(client: LanClient | None = None) -> tuple[int, int]:
    """把本机未同步的记录发给主机去重并入,并立刻拉一次最新记录。"""
    c = client or active_client()
    if c is None or c.rec is None:
        raise LanError("当前不是「局域网从机」模式")
    c.sync_poll(strict=True)
    todo = unmerged_local_rows(c)
    if not todo:
        return 0, 0
    res = c.rec_merge(todo)
    c.sync_poll(strict=True)
    return int(res.get("merged") or 0), int(res.get("skipped") or 0)
