"""查水印(高级检查,用户 2026-10-16:「内置几个热门平台的水印 logo,软件会飞速看到并标记他」)。

三种办法一起用,结果都是「疑似」,标黄给人看一眼(查到的后面会模糊掉):
① logo 库:B 站 / 抖音 / 快手 / 小红书 / 得物 / 转转 …… 的水印样子(qe/assets/logos/<名字>/*.png 内置,
   数据目录\\水印库\\<名字>\\*.png 是用户自己加的),在画面里找;
② 认字:画面里有「抖音号」「快手号」「小红书号」「bilibili」「得物」「转转」这类字(RapidOCR,没装就跳过);
③ 一直不动的小图案:不认识的水印也抓得到(只说「疑似水印」)。

为什么不像百家号那样只抽 10 帧:真实素材里 B 站水印只在拼进来的那一小段里有(25 秒的视频只有前 2 秒有),
抽得稀就漏了 → 整条按每秒 1 帧过一遍(CPU 解码,2 分钟的视频 5 秒左右)。
水印的特点是「画面在变,它不变」:相邻几帧取「亮的细笔画」(白顶帽)的最小值,会动的画面被抹掉、水印留下 → 再找 logo,
又准又快(要找的图少了好几倍)。
"""
import hashlib
import json
import os
import subprocess
import threading
from pathlib import Path

import cv2
import numpy as np

from .config import data_dir

_NOWIN = 0x08000000 | 0x00004000 if os.name == "nt" else 0   # 不弹黑窗 + 低优先级
ASSET_DIR = Path(__file__).resolve().parent / "assets" / "logos"
CANVAS_V = (720, 1280)             # 竖视频按 720×1280 看(横的 1280×720);logo 样子都按这个大小截
CANVAS_H = (1280, 720)
MAX_FRAMES = 150                   # 很长的视频最多看这么多帧(均匀分开)
WIN = 3                            # 几帧叠一起(取最小值)找不动的东西
SCALES = (0.6, 0.75, 0.9, 1.0, 1.15, 1.35, 1.6)
DEFAULT_TH = 0.62                  # logo 匹配分数(0~1)超过这个算找到;样子自己可以在 meta.json 里另设
_K = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))

# 认字:画面里出现这些字 → 哪家的水印 / 广告(区分大小写不敏感)
TEXT_WORDS = {
    "抖音": ["抖音号", "抖音", "douyin", "tiktok"],
    "快手": ["快手号", "快手", "kuaishou"],
    "小红书": ["小红书号", "小红书", "xiaohongshu"],
    "B站": ["bilibili", "哔哩哔哩", "b站"],
    "西瓜视频": ["西瓜视频"],
    "微博": ["微博"],
    "视频号": ["视频号"],
    "好看视频": ["好看视频"],
    "得物": ["得物"],
    "转转": ["转转"],
    "闲鱼": ["闲鱼"],
    "拼多多": ["拼多多"],
}


def user_dir() -> Path:
    d = data_dir() / "水印库"
    d.mkdir(parents=True, exist_ok=True)
    return d


def shot_dir() -> Path:
    d = data_dir() / "水印截图"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------- 读帧 ----------------
def canvas_of(w: int, h: int) -> tuple[int, int]:
    return CANVAS_H if w > h > 0 else CANVAS_V


def content_rect(w: int, h: int) -> tuple[int, int, int, int]:
    """原视频缩进画布(等比、居中、补黑边)后,画面在画布里的位置 (x, y, 宽, 高)。"""
    cw, ch = canvas_of(w, h)
    if not w or not h:
        return 0, 0, cw, ch
    k = min(cw / w, ch / h)
    sw, sh = max(2, int(round(w * k / 2)) * 2), max(2, int(round(h * k / 2)) * 2)
    return (cw - sw) // 2, (ch - sh) // 2, sw, sh


def read_frames(path: str, ffmpeg: str, w: int, h: int, dur: float, stop=None) -> tuple[list, list]:
    """整条按每秒 1 帧读(太长的均匀取 MAX_FRAMES 帧),灰度,缩到画布大小。返回 (帧列表, 每帧的秒数)。"""
    cw, ch = canvas_of(w, h)
    fps = 1.0 if dur <= MAX_FRAMES else MAX_FRAMES / max(dur, 1.0)
    vf = (f"fps={fps:.5f},scale={cw}:{ch}:force_original_aspect_ratio=decrease,"
          f"pad={cw}:{ch}:(ow-iw)/2:(oh-ih)/2,format=gray")
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", path, "-an", "-sn", "-vf", vf, "-f", "rawvideo", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=_NOWIN)
    frames, n = [], cw * ch
    try:
        while True:
            if stop and stop():
                break
            buf = p.stdout.read(n)
            if len(buf) < n:
                break
            frames.append(np.frombuffer(buf, np.uint8).reshape(ch, cw))
    finally:
        try:
            p.kill()
        except OSError:
            pass
        p.wait()
    return frames, [i / fps for i in range(len(frames))]


def tophat(g: np.ndarray) -> np.ndarray:
    """亮的细笔画(半透明白水印就是这样)。"""
    return cv2.morphologyEx(g, cv2.MORPH_TOPHAT, _K)


def still_maps(frames: list) -> list[tuple[int, np.ndarray]]:
    """相邻 WIN 帧的白顶帽取最小值:会动的画面被抹掉,不动的(水印、固定字)留下。返回 [(起始帧号, 图)]。
    视频很短(帧不够 WIN)就用单帧。"""
    if not frames:
        return []
    ths = [tophat(f) for f in frames]
    if len(ths) < WIN:
        return [(0, np.min(np.stack(ths), axis=0))]
    step = max(1, WIN - 1)
    return [(i, np.min(np.stack(ths[i:i + WIN]), axis=0)) for i in range(0, len(ths) - WIN + 1, step)]


# ---------------- logo 库 ----------------
class Logo:
    def __init__(self, label: str, img: np.ndarray, th: float, src: str):
        self.label, self.img, self.th, self.src = label, img.astype(np.float32), th, src


_logos_cache: dict = {}
_logos_lock = threading.Lock()


def load_logos(force: bool = False) -> list[Logo]:
    """内置的 + 用户加的。样子是画布大小下截的白顶帽图(亮笔画)。meta.json 可设 {"th": 0.7}。"""
    with _logos_lock:
        key = tuple(sorted(str(p) + str(p.stat().st_mtime) for d in (ASSET_DIR, user_dir()) if d.is_dir()
                           for p in d.rglob("*.png")))
        if not force and _logos_cache.get("key") == key:
            return _logos_cache["logos"]
        out = []
        for root in (ASSET_DIR, user_dir()):
            if not root.is_dir():
                continue
            for sub in sorted(p for p in root.iterdir() if p.is_dir()):
                meta = {}
                try:
                    meta = json.loads((sub / "meta.json").read_text("utf-8"))
                except (OSError, ValueError):
                    pass
                for f in sorted(sub.glob("*.png")):
                    img = cv2.imdecode(np.fromfile(str(f), np.uint8), cv2.IMREAD_GRAYSCALE)
                    if img is None or min(img.shape) < 6:
                        continue
                    th = float((meta.get(f.stem) or {}).get("th", meta.get("th", DEFAULT_TH)))
                    out.append(Logo(sub.name, img, th, str(f)))
        _logos_cache.update(key=key, logos=out)
        return out


def make_logo(crops: list[np.ndarray]) -> np.ndarray:
    """从几张截下来的水印(灰度,同一位置不同帧)做样子:白顶帽取中位数,再切到笔画那一块。"""
    med = np.median(np.stack([tophat(c).astype(np.float32) for c in crops]), axis=0)
    m = med > med.max() * 0.35
    ys, xs = np.where(m)
    if not len(xs):
        return med.astype(np.uint8)
    y0, y1 = max(0, ys.min() - 2), min(med.shape[0], ys.max() + 3)
    x0, x1 = max(0, xs.min() - 2), min(med.shape[1], xs.max() + 3)
    t = med[y0:y1, x0:x1]
    return np.clip(t * 255.0 / max(1.0, float(t.max())), 0, 255).astype(np.uint8)


def match_logos(maps: list, logos: list[Logo], times: list) -> list[dict]:
    """在「不动的图」里找 logo。先半分辨率粗找,分数够了再原大小确认。每个 logo 只报最好的一处。"""
    best: dict = {}
    for i, m in maps:
        mf = m.astype(np.float32)
        small = cv2.resize(mf, (mf.shape[1] // 2, mf.shape[0] // 2), interpolation=cv2.INTER_AREA)
        for lg in logos:
            for s in SCALES:
                t = cv2.resize(lg.img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
                th_, tw = t.shape
                if th_ < 8 or tw < 8 or th_ >= mf.shape[0] or tw >= mf.shape[1]:
                    continue
                ts = cv2.resize(t, (max(4, tw // 2), max(4, th_ // 2)), interpolation=cv2.INTER_AREA)
                if float(ts.std()) < 1e-3:
                    continue
                r = cv2.matchTemplate(small, ts, cv2.TM_CCOEFF_NORMED)
                _, mx, _, loc = cv2.minMaxLoc(r)
                if mx < lg.th - 0.12:                 # 粗找差得远,不用细看
                    continue
                x, y = loc[0] * 2, loc[1] * 2         # 原大小下在附近细找
                x0, y0 = max(0, x - 8), max(0, y - 8)
                roi = mf[y0:min(mf.shape[0], y + th_ + 8), x0:min(mf.shape[1], x + tw + 8)]
                if roi.shape[0] < th_ or roi.shape[1] < tw:
                    continue
                r2 = cv2.matchTemplate(roi, t, cv2.TM_CCOEFF_NORMED)
                _, mx2, _, loc2 = cv2.minMaxLoc(r2)
                if mx2 >= lg.th and mx2 > best.get(lg.label, {}).get("score", 0):
                    best[lg.label] = {"label": lg.label, "kind": "logo", "score": round(float(mx2), 3),
                                      "box": [x0 + loc2[0], y0 + loc2[1], tw, th_], "t": round(times[i], 1), "frame": i}
    return list(best.values())


# ---------------- 认字 ----------------
_ocr = None
_ocr_lock = threading.Lock()


def ocr_engine():
    """RapidOCR;没装返回 None(就不认字,只用 logo 库和不动的图案)。"""
    global _ocr
    with _ocr_lock:
        if _ocr is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                _ocr = RapidOCR()
            except Exception:
                _ocr = False
        return _ocr or None


def find_text(frames: list, times: list, picks: int = 4) -> list[dict]:
    """挑几帧认字,有平台名 / 广告名的报出来。"""
    eng = ocr_engine()
    if not eng or not frames:
        return []
    idx = sorted({min(len(frames) - 1, int(len(frames) * k / (picks + 1))) for k in range(1, picks + 1)})
    hits: dict = {}
    for i in idx:
        try:
            with _ocr_lock:
                res, _ = eng(cv2.cvtColor(frames[i], cv2.COLOR_GRAY2BGR))
        except Exception:
            continue
        for box, txt, sc in res or []:
            low = str(txt).lower().replace(" ", "")
            for label, words in TEXT_WORDS.items():
                if label in hits:
                    continue
                if any(w.lower() in low for w in words):
                    xs = [p[0] for p in box]
                    ys = [p[1] for p in box]
                    hits[label] = {"label": label, "kind": "text", "text": str(txt), "score": round(float(sc), 3),
                                   "box": [int(min(xs)), int(min(ys)), int(max(xs) - min(xs)), int(max(ys) - min(ys))],
                                   "t": round(times[i], 1), "frame": i}
    return list(hits.values())


# ---------------- 一直不动的小图案(不认识的水印)----------------
def find_still(maps: list, frames: list, rect: tuple, times: list) -> list[dict]:
    """画面里(不算黑边)角落 / 上下边上一直不动的小块亮图案,在好几段里都有。只报最明显的一处,说「疑似水印」。"""
    if len(maps) < 3:
        return []
    x, y, w, h = rect
    acc = None
    for _i, m in maps:
        b = (m > 40).astype(np.uint8)
        acc = b if acc is None else acc + b
    persist = (acc >= max(3, int(len(maps) * 0.5))).astype(np.uint8)
    region = np.zeros_like(persist)
    my = int(h * 0.16)                                  # 只看上下两条(左右中间字幕、边框多)
    region[y:y + my, x:x + w] = 1                       # 上边一条
    region[y + h - my:y + h, x:x + w] = 1               # 下边一条
    cand = persist & region
    cand = cv2.dilate(cand, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 5)))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(cand)
    best = None
    for k in range(1, n):
        bx, by, bw, bh, area = stats[k]
        if area < 120 or bw > w * 0.6 or bh > h * 0.12 or bw / max(1, bh) > 12:
            continue                                     # 太小 / 太大 / 细长的线(黑边、字幕条的边)
        if best is None or area > best[4]:
            best = (bx, by, bw, bh, area)
    if not best:
        return []
    bx, by, bw, bh, _a = best
    return [{"label": "疑似水印", "kind": "still", "score": 0.0, "box": [int(bx), int(by), int(bw), int(bh)],
             "t": 0.0, "frame": len(frames) // 2}]


# ---------------- 整条 ----------------
def where(box: list, rect: tuple) -> str:
    """框在画面哪儿(给人看):左上角 / 右上 / 中间 …"""
    x, y, w, h = rect
    cx = (box[0] + box[2] / 2 - x) / max(1, w)
    cy = (box[1] + box[3] / 2 - y) / max(1, h)
    v = "上" if cy < 0.33 else ("下" if cy > 0.67 else "中")
    hpos = "左" if cx < 0.33 else ("右" if cx > 0.67 else "中")
    return "正中间" if v == hpos == "中" else (f"{hpos}{v}角" if v != "中" and hpos != "中" else f"{v}边" if hpos == "中" else f"{hpos}边")


def to_ratio(box: list, rect: tuple) -> list:
    """画布上的框 → 原视频画面里的比例坐标(0~1),模糊的时候用。"""
    x, y, w, h = rect
    return [round(max(0.0, (box[0] - x) / w), 4), round(max(0.0, (box[1] - y) / h), 4),
            round(min(1.0, box[2] / w), 4), round(min(1.0, box[3] / h), 4)]


def detect(path: str, ffmpeg: str, info: dict, stop=None, use_ocr: bool = True, use_still: bool = False) -> dict:
    """查一条。info = vertical.probe 的结果。返回
    {"hits": [{"label","kind","score","box"(画布),"ratio"(原画面比例),"where","t"}], "shot": 截图路径, "frames": 看了几帧}。
    没查到 hits 为空。"""
    w, h, dur = info.get("w", 0), info.get("h", 0), float(info.get("dur") or 0)
    frames, times = read_frames(path, ffmpeg, w, h, dur, stop=stop)
    if not frames:
        return {"hits": [], "shot": "", "frames": 0, "error": "视频读不出画面"}
    rect = content_rect(w, h)
    maps = still_maps(frames)
    hits = match_logos(maps, load_logos(), times)
    if use_ocr and not (stop and stop()):
        known = {x["label"] for x in hits}
        hits += [x for x in find_text(frames, times) if x["label"] not in known]
    if not hits and use_still:                   # 游戏的血条 / 小地图也一直不动,默认不用(误报太多)
        hits = find_still(maps, frames, rect, times)
    for x in hits:
        x["ratio"] = to_ratio(x["box"], rect)
        x["where"] = where(x["box"], rect)
    shot = save_shot(path, frames, hits) if hits else ""
    return {"hits": hits, "shot": shot, "frames": len(frames)}


def save_shot(path: str, frames: list, hits: list) -> str:
    """查到的那一帧画上红框存下来(鼠标放上去看)。"""
    i = hits[0].get("frame", 0)
    img = cv2.cvtColor(frames[min(i, len(frames) - 1)], cv2.COLOR_GRAY2BGR)
    for x in hits:
        bx, by, bw, bh = x["box"]
        cv2.rectangle(img, (bx - 4, by - 4), (bx + bw + 4, by + bh + 4), (0, 0, 255), 3)
    out = shot_dir() / (hashlib.md5(os.path.normcase(path).encode("utf-8")).hexdigest()[:16] + ".jpg")
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if ok:
        buf.tofile(str(out))
        return str(out)
    return ""


def label_of(res: dict) -> str:
    """给人看的一句:「B站水印(右上角)」「疑似水印(左下角)」「有「得物」字样」。"""
    hits = (res or {}).get("hits") or []
    if not hits:
        return ""
    parts = []
    for x in hits[:3]:
        if x["kind"] == "still":
            parts.append(f"疑似水印({x['where']})")
        elif x["kind"] == "text":
            parts.append(f"{x['label']}字样({x['where']})")
        else:
            parts.append(f"{x['label']}水印({x['where']})")
    return "、".join(parts)
