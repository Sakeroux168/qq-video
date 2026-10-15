"""连创作罐头的调试口(从百家号发布助手 core/czgt.py 抄过来的那部分,自己一份,两个软件互不影响)。

罐头里每个号的页面是 webview:Playwright 看不到,只能直接对每个页面发调试命令(CDP)。
罐头的调试口拒绝带 Origin 头的 websocket,所以自己写了个最小的 websocket。
"""
import base64
import glob
import json
import os
import re
import socket
import struct
import time
import urllib.request


class CdpError(RuntimeError):
    pass


def find_ports() -> list[int]:
    """罐头每次启动调试端口都不一样:数据目录里每个 DevToolsActivePort 文件第一行就是端口。"""
    ports = []
    for f in glob.glob(os.path.join(os.environ.get("APPDATA", ""), "创作罐头", "**", "DevToolsActivePort"), recursive=True):
        try:
            p = int(open(f, encoding="utf-8").readline().strip())
        except (OSError, ValueError):
            continue
        if p not in ports and _alive(p):
            ports.append(p)
    return ports


def _alive(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def targets(port: int) -> list[dict]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=8) as r:
        return [t for t in json.loads(r.read().decode("utf-8")) if t.get("type") in ("page", "webview")]


class Page:
    """对一个页面发调试命令。用完 close()。"""

    def __init__(self, target: dict, timeout: float = 20):
        self.target = target
        self.id = target.get("id", "")
        url = target["webSocketDebuggerUrl"]
        m = re.match(r"ws://([^/:]+):(\d+)(/.*)", url)
        if not m:
            raise CdpError(f"调试地址看不懂:{url}")
        host, port, path = m.group(1), int(m.group(2)), m.group(3)
        self.sock = socket.create_connection((host, port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                           f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise CdpError("调试口握手没回话")
            head += chunk
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise CdpError("调试口拒绝连接:" + head.split(b"\r\n", 1)[0].decode("latin-1"))
        self.buf = head.split(b"\r\n\r\n", 1)[1]
        self._id = 0

    # ---- websocket ----
    def _recv(self, n: int) -> bytes:
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise CdpError("调试口断开了")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def _send(self, obj: dict):
        data = json.dumps(obj).encode()
        hdr = bytearray([0x81])
        n = len(data)
        if n < 126:
            hdr.append(0x80 | n)
        elif n < 65536:
            hdr.append(0x80 | 126)
            hdr += struct.pack(">H", n)
        else:
            hdr.append(0x80 | 127)
            hdr += struct.pack(">Q", n)
        mask = os.urandom(4)
        self.sock.sendall(bytes(hdr) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _read(self) -> dict | None:
        msg = b""
        while True:
            b1, b2 = self._recv(2)
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._recv(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._recv(8))[0]
            payload = self._recv(n)
            op = b1 & 0x0F
            if op == 8:
                return None
            if op in (0, 1, 2):
                msg += payload
                if b1 & 0x80:
                    try:
                        return json.loads(msg.decode("utf-8"))
                    except ValueError:
                        return {}

    def cmd(self, method: str, params: dict | None = None, timeout: float = 20) -> dict:
        self._id += 1
        i = self._id
        self._send({"id": i, "method": method, **({"params": params} if params else {})})
        end = time.time() + timeout
        while time.time() < end:
            self.sock.settimeout(max(0.5, end - time.time()))
            try:
                d = self._read()
            except (OSError, CdpError):
                raise CdpError(f"调试口没回话({method})")
            if d is None:
                raise CdpError("页面关掉了")
            if d.get("id") == i:
                if "error" in d:
                    raise CdpError(f"{method}: {d['error'].get('message')}")
                return d.get("result") or {}
        raise CdpError(f"调试口超时({method})")

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass

    # ---- 常用 ----
    def ev(self, js: str, timeout: float = 20):
        """在页面里跑一段 JS,拿回结果。JS 抛错就抛 CdpError。"""
        r = self.cmd("Runtime.evaluate", {"expression": js, "returnByValue": True, "awaitPromise": True}, timeout)
        if "exceptionDetails" in r:
            d = r["exceptionDetails"]
            raise CdpError("页面脚本出错:" + str((d.get("exception") or {}).get("description") or d.get("text"))[:200])
        return (r.get("result") or {}).get("value")

    def set_files(self, selector: str, files: list[str], index: int = 0):
        """给 <input type=file> 塞文件(等于在选文件窗口里选好点打开)。"""
        doc = self.cmd("DOM.getDocument", {"depth": -1, "pierce": True})
        ids = self.cmd("DOM.querySelectorAll", {"nodeId": doc["root"]["nodeId"], "selector": selector}).get("nodeIds") or []
        if len(ids) <= index:
            raise CdpError(f"页面上找不到上传框({selector})")
        self.cmd("DOM.setFileInputFiles", {"nodeId": ids[index], "files": list(files)})

    def click_xy(self, x: float, y: float):
        for t in ("mouseMoved", "mousePressed", "mouseReleased"):
            p = {"type": t, "x": x, "y": y}
            if t != "mouseMoved":
                p.update(button="left", clickCount=1)
            self.cmd("Input.dispatchMouseEvent", p)

    def drag(self, x0: float, y0: float, x1: float, y1: float, steps: int = 18):
        """真鼠标拖:按下 → 一点点挪 → 松开(裁剪框只认真鼠标)。"""
        self.cmd("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x0, "y": y0})
        self.cmd("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x0, "y": y0, "button": "left", "clickCount": 1})
        for i in range(1, steps + 1):
            self.cmd("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x0 + (x1 - x0) * i / steps,
                                                  "y": y0 + (y1 - y0) * i / steps, "button": "left", "buttons": 1})
            time.sleep(0.02)
        self.cmd("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x1, "y": y1, "button": "left", "clickCount": 1})

    def key(self, key: str, code: int):
        for t in ("keyDown", "keyUp"):
            self.cmd("Input.dispatchKeyEvent", {"type": t, "key": key, "code": key, "windowsVirtualKeyCode": code})

    def shot(self, path: str) -> str:
        try:
            r = self.cmd("Page.captureScreenshot", {"format": "png"}, timeout=15)
        except CdpError:
            return ""
        if r.get("data"):
            with open(path, "wb") as f:
                f.write(base64.b64decode(r["data"]))
            return path
        return ""
