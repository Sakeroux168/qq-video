"""员工没放封面的,软件自己挑一帧当封面(用户 2026-10-26:「有些账号员工没放封面,平台就拿第一帧当封面,
但很多第一帧都是黑屏」→ 选了「全自动」)。

从视频里截几个时间点(第 1 / 2 / 3 秒,视频 10% ~ 50% 的位置),太黑、太白、几乎纯色(黑屏 / 白屏 / 转场)、糊的不要,
挑最清楚的一张(对比度 × 清晰度最高的)。截的图放在 数据目录\\自动封面\\ 里,**不往素材文件夹里放东西**。
「换一帧」= 用排第二、第三…的那张(记在 自动封面\\选的.json 里,发的时候用它)。都太黑 → 给 "",还是让平台自己截。
"""
import hashlib
import json
import os
import subprocess
import time

import numpy as np

from .config import data_dir

POINTS = (1.0, 2.0, 3.0, 0.1, 0.2, 0.3, 0.4, 0.5)    # 大于等于 1 的是秒,小于 1 的是视频长度的几成
DARK, BRIGHT, FLAT = 35, 235, 18                     # 平均亮度低于 35 = 黑;高于 235 = 白;亮度起伏小于 18 = 几乎纯色
KEEP_DAYS = 7
_NOWIN = 0x08000000 if os.name == "nt" else 0


def cache_dir() -> str:
    d = data_dir() / "自动封面"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


def _key(path: str) -> str:
    try:
        s = os.stat(path)
        sig = f"{os.path.normcase(os.path.abspath(path))}|{s.st_size}|{int(s.st_mtime)}"
    except OSError:
        sig = os.path.normcase(os.path.abspath(path))
    return hashlib.md5(sig.encode("utf-8")).hexdigest()[:16]


def _chosen_file() -> str:
    return os.path.join(cache_dir(), "选的.json")


def _load_chosen() -> dict:
    try:
        with open(_chosen_file(), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_chosen(d: dict) -> None:
    tmp = _chosen_file() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, _chosen_file())


def _frame(ffmpeg: str, path: str, t: float, width: int = 0) -> bytes:
    """截 t 秒那一帧(png 字节);width > 0 缩到这个宽(打分用小图,快)。截不到给 b""。"""
    vf = ["-vf", f"scale={width}:-2"] if width else []
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1", *vf,
           "-f", "image2pipe", "-vcodec", "png", "-"]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=30, creationflags=_NOWIN)
        return p.stdout or b""
    except (OSError, subprocess.SubprocessError):
        return b""


def score(png: bytes) -> float:
    """这一帧当封面好不好:太黑 / 太白 / 几乎纯色 → -1;不然 = 亮度起伏 × 清晰度(越大越好)。"""
    import cv2
    if not png:
        return -1.0
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return -1.0
    m, s = float(img.mean()), float(img.std())
    if m < DARK or m > BRIGHT or s < FLAT:
        return -1.0
    sharp = float(cv2.Laplacian(img, cv2.CV_64F).var())
    return s * (sharp ** 0.5)


def candidates(path: str, ffmpeg: str = "", dur: float | None = None) -> list[tuple[float, float]]:
    """能当封面的时间点,好的在前:[(分数, 秒)]。"""
    from .vertical import ffmpeg_path, probe
    ff = ffmpeg or ffmpeg_path()
    if not ff:
        return []
    if dur is None:
        dur = float(probe(path, ff).get("dur") or 0)
    ts = []
    for x in POINTS:
        t = x if x >= 1 else x * dur
        if dur and t > dur - 0.2:
            continue
        if all(abs(t - y) > 0.5 for y in ts):
            ts.append(t)
    got = [(score(_frame(ff, path, t, 360)), t) for t in ts]
    return sorted([g for g in got if g[0] > 0], reverse=True)


def _prune() -> None:
    cut = time.time() - KEEP_DAYS * 86400
    try:
        for n in os.listdir(cache_dir()):
            p = os.path.join(cache_dir(), n)
            if n.endswith(".jpg") and os.path.getmtime(p) < cut:
                os.remove(p)
    except OSError:
        pass


def pick(path: str, ffmpeg: str = "", nth: int | None = None) -> str:
    """给这条视频挑一张封面(jpg,在 自动封面\\ 里);nth = 用排第几的(0 = 最好的;不给就用上次「换一帧」选的)。
    挑不出来(全是黑屏 / 截不到)给 ""。同一条视频挑过就直接用(视频改过会重挑)。"""
    from .vertical import ffmpeg_path
    ff = ffmpeg or ffmpeg_path()
    if not ff or not os.path.isfile(path):
        return ""
    k = _key(path)
    chosen = _load_chosen()
    if nth is None:
        nth = int((chosen.get(k) or {}).get("nth", 0))
    out = os.path.join(cache_dir(), f"{k}_{nth}.jpg")
    if os.path.isfile(out) and os.path.getsize(out) > 0:
        return out
    _prune()
    cands = candidates(path, ff)
    if not cands:
        return ""
    nth = nth % len(cands)
    out = os.path.join(cache_dir(), f"{k}_{nth}.jpg")
    t = cands[nth][1]
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1", "-q:v", "2", out]
    try:
        subprocess.run(cmd, capture_output=True, timeout=60, creationflags=_NOWIN)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out if os.path.isfile(out) and os.path.getsize(out) > 0 else ""


def next_frame(path: str, ffmpeg: str = "") -> str:
    """「换一帧」:用排下一名的那张,记下来(发的时候就用它)。返回新的图;没有别的可换就还是原来那张。"""
    k = _key(path)
    chosen = _load_chosen()
    n = int((chosen.get(k) or {}).get("nth", 0)) + 1
    got = pick(path, ffmpeg, n)
    if got:
        chosen[k] = {"nth": int(os.path.basename(got).rsplit("_", 1)[1].split(".")[0]), "path": path}
        _save_chosen(chosen)
    return got
