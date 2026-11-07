"""发布前查清晰度(用户 2026-11-06:「发布前检查视频模糊不模糊」)。只提醒,不拦发布。

看两样,每条抽 4 帧,先去掉黑边:
1. 低清放大:resdet(MIT,GitHub 0x09/resdet)看频谱估放大前的尺寸。一帧的分数很吵(11-06 真视频:原片也常有 0.6),
   所以要同一个尺寸在两帧以上都出现、分数 >= 0.56、短边 240~380、放大 1.4 倍以上才算(720 放大到 1080 这种我们自己转竖屏就有,不算)。
   所以画面本身只有 720×406 的抓不到(再低也放大不到 1.4 倍)。
   0.75 倍是压缩留下的假信号(好多原片都报 810),不算。
   11-06 拿没调过门槛的 80 条验:原片标 2 条,放大过的 360p 抓 6 成、270p 抓 9 成(放大版是自己造的,不是真差片)。
2. 整条都糊:缩到短边 540 量边缘,4 帧里最清楚的一帧都不到 100 才算。动漫大色块、暗场分数天然低,所以看最清楚的一帧、门槛放得很低;
   120 条真视频里只标 1 条,只抓得到很糊的。

原生拍虚、只有脸失焦、只有一小段糊的抓不到。试过不用的:FFmpeg blurdetect(软件带的 4.2.2 没有,新版也分不开 360p)、
千问看单帧(故意弄糊的 12 张说 9 张清楚)。
"""
import io
import os
import subprocess
import sys
import tempfile

from . import wmstore
from .config import app_dir

POINTS = (0.2, 0.4, 0.6, 0.8)
SCORE, NEAR = 0.56, 3
LOW_MIN, LOW_MAX = 240, 380
BLUR_EDGE = 100
_NOWIN = 0x08000000 if os.name == "nt" else 0
STORE = wmstore.Store("清晰度检查.json")


def resdet_path() -> str:
    mei = getattr(sys, "_MEIPASS", "")                   # 打包以后在 _internal 里
    for p in (os.environ.get("QE_RESDET", ""), str(app_dir() / "resdet" / "resdet.exe"), os.path.join(mei, "resdet", "resdet.exe") if mei else ""):
        if p and os.path.isfile(p):
            return p
    return ""


def _frame(ff: str, path: str, t: float):
    """t 秒那一帧,灰度 numpy;截不到 None。"""
    import numpy as np
    from PIL import Image
    r = subprocess.run([ff, "-v", "error", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                       capture_output=True, timeout=60, creationflags=_NOWIN)
    if not r.stdout:
        return None
    return np.array(Image.open(io.BytesIO(r.stdout)).convert("L"))


def active(g):
    """去掉四边黑边 / 纯色边,只留有画面的那块;整张都是纯色给 None。"""
    import numpy as np
    rows, cols = np.where(g.std(axis=1) > 6)[0], np.where(g.std(axis=0) > 6)[0]
    if len(rows) < 20 or len(cols) < 20:
        return None
    return g[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]


def edge(g) -> float:
    """缩到短边 540 量边缘,大小不同的视频才能比。"""
    import cv2
    h, w = g.shape
    k = 540 / min(h, w)
    g2 = cv2.resize(g, (max(1, int(w * k)), max(1, int(h * k))), interpolation=cv2.INTER_AREA if k < 1 else cv2.INTER_CUBIC)
    return float(cv2.Laplacian(g2, cv2.CV_64F).var())


def _parse(line: str) -> list[tuple[int, float]]:
    out = []
    for x in line.split():
        a, _s, b = x.partition(":")
        if a.isdigit() and b:
            c = float(b)
            if c >= SCORE:
                out.append((int(a), c))
    return out


def sizes(raw: str, w: int, h: int) -> list[tuple[int, int]]:
    """resdet -v 3 的输出(第一行宽、第二行高)→ 够得上的尺寸:宽高比例一致、放大 1.4 倍以上(0.75 是压缩的假信号,
    681×380 对 720×406 这种几乎没放大的也不算)、短边在范围里。"""
    ls = (raw or "").strip().split("\n")
    if len(ls) < 2:
        return []
    out = []
    for a, _c in _parse(ls[0]):
        for b, _c2 in _parse(ls[1]):
            r = b / h
            if abs(a / w - r) < 0.012 and r < 0.72 and LOW_MIN <= min(a, b) <= LOW_MAX:
                out.append((a, b))
    return out


def agree(frames: list[list[tuple[int, int]]]) -> tuple[int, int] | None:
    """至少两帧都出现的尺寸(差 3 像素算一样);没有 None。"""
    seen = [(a, b, k) for k, f in enumerate(frames) for a, b in f]
    for a, b, _k in seen:
        if len({k for x, y, k in seen if abs(x - a) <= NEAR and abs(y - b) <= NEAR}) >= 2:
            return a, b
    return None


def _resdet(rd: str, g) -> str:
    """一帧(灰度 numpy)给 resdet 看,返回原话。"""
    from PIL import Image
    fd, p = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        Image.fromarray(g).save(p)
        return subprocess.run([rd, "-v", "3", "-x", "0", p], capture_output=True, text=True, encoding="utf-8", errors="ignore",
                              timeout=60, creationflags=_NOWIN).stdout
    finally:
        try:
            os.remove(p)
        except OSError:
            pass


def check(path: str, ff: str, dur: float, stop=None, grab=None, detect=None) -> dict:
    """查一条:{"hits": [{"kind": "low", "w", "h"} 或 {"kind": "blur", "score"}]}。grab(t) / detect(灰度图):测试里换掉。
    resdet 没放进来:只看整条糊不糊。一帧都读不出来抛 OSError(不记成没问题)。"""
    rd = resdet_path()
    grab = grab or (lambda t: _frame(ff, path, t))
    detect = detect or ((lambda g: _resdet(rd, g)) if rd else None)
    best, found = 0.0, []
    n = 0
    for f in POINTS:
        if stop and stop():
            raise OSError("停下了")
        g = grab(dur * f)
        g = active(g) if g is not None else None
        if g is None:
            continue
        n += 1
        best = max(best, edge(g))
        if detect:
            found.append(sizes(detect(g), g.shape[1], g.shape[0]))
    if not n:
        raise OSError("读不出画面")
    hits = []
    low = agree(found)
    if low:
        hits.append({"kind": "low", "w": low[0], "h": low[1]})
    if best < BLUR_EDGE:
        hits.append({"kind": "blur", "score": round(best)})
    return {"hits": hits}


def flagged(res: dict | None) -> bool:
    return bool(res and res.get("hits") and not res.get("ok"))


def text(res: dict | None) -> str:
    """表格里的一句话;没问题、人说过没问题的给 ""。"""
    if not flagged(res):
        return ""
    out = []
    for x in res["hits"]:
        if x.get("kind") == "low":
            out.append(f"疑似低清放大(约 {x['w']}×{x['h']})")
        elif x.get("kind") == "blur":
            out.append("画面可能很糊")
    return "、".join(out) + ",看一眼"
