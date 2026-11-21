"""发布前查有没有声音(用户 2026-11-21:有些视频没有声音)。只提醒,不拦发布。

分两种:
1. 没有音轨:在 vertical.probe(检查横竖屏时跑的那次 ffmpeg -i)里顺带就能看出,零额外开销 → 标「没有声音(无音轨)」;
2. 有音轨但整条静音:抽 3 段(50% / 15% / 80%,每段 8 秒;≤24 秒直接量整条)跑 ffmpeg volumedetect。
   先量中间那段,99% 正常视频第一段就测出有声音(>= -50 dB)直接返回,一条 ~0.1 秒;
   只有整条都低于 -50 dB(含 -inf)才标「疑似无声」。读不出来报错,不记成没问题。
结果存在 音频检查.json(按 路径 + 大小 + 修改时间 缓存,并支持局域网主从同步)。
"""
import os
import re
import subprocess

from . import wmstore

POINTS = (0.5, 0.15, 0.8)
WIN = 8.0
SHORT_DUR = 24.0
SILENT_DB = -50.0
_NOWIN = 0x08000000 if os.name == "nt" else 0
STORE = wmstore.Store("音频检查.json")

_MAX_VOL = re.compile(r"max_volume:\s*(-?[\d.]+|-inf)\s*dB", re.I)
_HAS_VID = re.compile(r"Stream #\S+.*?Video:")
_HAS_AUD = re.compile(r"Stream #\S+.*?Audio:")


def _windows(dur: float) -> list[tuple[float, float]]:
    if not dur or dur <= SHORT_DUR:
        return [(0.0, SHORT_DUR)]
    out: list[tuple[float, float]] = []
    for f in POINTS:
        s = round(max(0.0, min(dur - WIN, dur * f)), 2)
        if not any(abs(s - x[0]) < 1.0 for x in out):
            out.append((s, WIN))
    return out


def _probe_vol(ff: str, path: str, start: float, win: float) -> tuple[str, float | None]:
    """量一段的最大音量。返回 ("ok", max_db) / ("none", None)(无音轨) / ("err", None)(读不出来)。"""
    if not ff:
        return "err", None
    cmd = [ff, "-hide_banner", "-nostats", "-ss", f"{start:.2f}", "-t", f"{win:.2f}",
           "-i", path, "-vn", "-af", "volumedetect", "-f", "null", "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=60, creationflags=_NOWIN)
        txt = (r.stderr or b"").decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError):
        return "err", None
    m = _MAX_VOL.search(txt)
    if m:
        raw = m.group(1).lower()
        return "ok", (float("-inf") if raw == "-inf" else float(raw))
    if "does not contain any stream" in txt or (_HAS_VID.search(txt) and not _HAS_AUD.search(txt)):
        return "none", None
    return "err", None


def check(path: str, ff: str, dur: float = 0.0, has_audio: bool | None = None, stop=None, measure=None) -> dict:
    """查一条:{"hits": [{"kind": "none"} 或 {"kind": "silent", "max_db": -91.0}]}。
    has_audio=False(probe 已经发现没音轨):直接返回,不再起 ffmpeg。
    measure(start, win) -> ("ok", db) | ("none", None) | ("err", None):测试里换掉。
    读不出来抛 OSError(不记成没问题)。"""
    if has_audio is False:
        return {"hits": [{"kind": "none"}]}
    measure = measure or (lambda s, w: _probe_vol(ff, path, s, w))
    n_ok = 0
    best_db = float("-inf")
    for s, w in _windows(float(dur or 0)):
        if stop and stop():
            raise OSError("停下了")
        kind, db = measure(s, w)
        if kind == "none":
            return {"hits": [{"kind": "none"}]}
        if kind == "ok" and db is not None:
            n_ok += 1
            if db > best_db:
                best_db = db
            if db >= SILENT_DB:                          # 任一段有正常声音就提前停(99% 视频只跑 1 段)
                return {"hits": []}
    if not n_ok:
        raise OSError("读不出音频")
    hit: dict = {"kind": "silent"}
    if best_db > float("-inf"):
        hit["max_db"] = round(best_db, 1)
    return {"hits": [hit]}


def flagged(res: dict | None) -> bool:
    return bool(res and res.get("hits") and not res.get("ok"))


def text(res: dict | None) -> str:
    """表格备注 / 状态里的一句话;有声音或人说过没问题的给 ""。"""
    if not flagged(res):
        return ""
    h = (res["hits"][0] or {}) if res.get("hits") else {}
    return "没有声音(无音轨)" if h.get("kind") == "none" else "疑似无声"


def detail(res: dict | None) -> str:
    """鼠标悬浮说明。"""
    if not flagged(res):
        return ""
    h = (res["hits"][0] or {}) if res.get("hits") else {}
    if h.get("kind") == "none":
        return "这条视频没有音轨,整条无声"
    db = h.get("max_db")
    if db is not None:
        return f"抽查音量最高只有 {db} dB(低于 {int(SILENT_DB)} dB),疑似整条静音"
    return "抽查音频全是静音信号,疑似整条无声"
