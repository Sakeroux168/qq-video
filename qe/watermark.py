"""查水印(高级检查,用户 2026-10-16:「内置几个热门平台的水印 logo,软件会飞速看到并标记他」)。

查到的后面会被**自动模糊掉** → 框要准、误报要少(误报 = 好视频白白糊一块)。宁可漏一点,也别乱报。

做法(第二版,子 agent 2026-10-16 重写):
1. 整条按每秒 1 帧解码(灰度,缩到画布 720×1280 / 横的 1280×720),边读边算「亮的细笔画」(白顶帽);
2. 相邻 3 帧取最小值 = 「不动的图」(会动的画面被抹掉,水印、固定的字留下),每秒一张(窗口挪 1 帧);
3. 在不动的图里找「候选块」(亮笔画连成的一小块),同一位置连着几秒的串成一条「轨迹」;
4. 每条轨迹只拿代表的那张图去比 logo 库(按块的高矮直接算缩放,只比 3 个大小)→ 很快,logo 多了也不爆;
   比上了,再在每一秒那个位置复查一下 → 知道水印在哪几段出现(spans,模糊只糊这几段);
5. 认字:像一行字的轨迹,切下来只做「识别」(不做全图检测,快),只认水印的写法:
   「抖音号:xxx」「快手号:xxx」「小红书号:xxx」这种带「号」的,或者整块就是平台名 / bilibili(不能夹在一句话里),
   字要小(水印字小)。游戏里玩家名字叫「抖音熊二大王」、台词里说「快手」都不算。
6. 一直不动的不认识的小图案(find_still)默认关 —— 游戏的血条 / 小地图也一直不动,误报太多。

logo 样子:qe/assets/logos/<名字>/*.png(画布大小下的白顶帽图,make_logo 生成)+ meta.json
({"th": 门槛} 或按文件名 {"文件名": {"th": ..}});数据目录\\水印库\\<名字>\\*.png 是用户自己加的。
"""
import hashlib
import json
import os
import re
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
SCALES = (0.6, 0.75, 0.9, 1.0, 1.15, 1.35, 1.6)   # 没有候选块可用时(整条画面都不动)全图找用
DEFAULT_TH = 0.75                  # logo 匹配分数(0~1)超过这个算找到;样子自己可以在 meta.json 里另设
TB = 22                            # 「不动的图」里亮过这个算笔画
_K = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
_KJOIN = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 5))   # 把一个 logo / 一行字的笔画连成一块
MAX_TRACKS_OCR = 40                # 认字最多认这么多块(一块十几毫秒)
MAX_HITS = 6

# 认字:画面里出现这些字 → 哪家的水印 / 广告(大小写不敏感)
TEXT_WORDS = {
    "抖音": ["抖音", "douyin", "tiktok"],
    "快手": ["快手", "kuaishou"],
    "小红书": ["小红书", "xiaohongshu"],
    "B站": ["bilibili", "哔哩哔哩", "b站"],
    "西瓜视频": ["西瓜视频"],
    "微博": ["微博", "微博视频"],
    "视频号": ["视频号"],
    "好看视频": ["好看视频"],
    "得物": ["得物"],
    "转转": ["转转"],
    "闲鱼": ["闲鱼"],
    "拼多多": ["拼多多"],
}
# 带「号」的写法:抖音号:xxx / 快手号 xxx / 小红书号:xxx / 微博号(视频号本身就带号,按平台名认)
_ID_RE = re.compile(r"(抖音|快手|小红书|西瓜视频|好看视频|微博|b站|bilibili)号|^(视频号)")
# 「抖音|悦策电影」「快手 @xxx」这种:平台名打头,后面跟竖线 / @ 再接作者名
_SEP_RE = re.compile(r"^\s*(抖音|快手|小红书|西瓜视频|好看视频|微博|视频号|b站|bilibili|哔哩哔哩)\s*[|丨｜/@＠]")
_PUNCT = re.compile(r"[\s:：·.,，。、|丨_\-—~!！?？'\"“”‘’()（）\[\]【】<>《》]+")


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


LONG = 300                         # 超过 5 分钟的只解关键帧(快好几倍;关键帧一般 2~10 秒一个,够用)


def read_frames(path: str, ffmpeg: str, w: int, h: int, dur: float, stop=None, on_frame=None) -> tuple[list, list]:
    """整条按每秒 1 帧读(太长的均匀取 MAX_FRAMES 帧),灰度,缩到画布大小。返回 (帧列表, 每帧的秒数)。
    on_frame(帧):每读到一帧就调一下(边解码边算白顶帽,省时间)。
    解码跳过不被参考的帧(-skip_frame noref,快 20~30%);超过 LONG 秒的只解关键帧,重复的帧去掉。"""
    cw, ch = canvas_of(w, h)
    fps = 1.0 if dur <= MAX_FRAMES else MAX_FRAMES / max(dur, 1.0)
    vf = (f"fps={fps:.5f},scale={cw}:{ch}:force_original_aspect_ratio=decrease,"
          f"pad={cw}:{ch}:(ow-iw)/2:(oh-ih)/2,format=gray")
    longv = dur > LONG
    for skip in (["-skip_frame", "nokey"] if longv else ["-skip_frame", "noref"], []):
        frames, times = _decode(ffmpeg, path, vf, cw, ch, fps, skip, stop, on_frame, dedupe=bool(skip) and longv)
        if frames or (stop and stop()) or not skip:
            return frames, times
    return [], []


def _decode(ffmpeg, path, vf, cw, ch, fps, skip, stop, on_frame, dedupe=False):
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", *skip, "-i", path, "-an", "-sn", "-dn", "-vf", vf,
           "-f", "rawvideo", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=_NOWIN)
    frames, times, n, k, last = [], [], cw * ch, -1, None
    try:
        while True:
            if stop and stop():
                break
            buf = p.stdout.read(n)
            if len(buf) < n:
                break
            k += 1
            if dedupe and last is not None and buf == last:      # 关键帧之间 fps 补的重复帧
                continue
            last = buf
            f = np.frombuffer(buf, np.uint8).reshape(ch, cw)
            frames.append(f)
            times.append(k / fps)
            if on_frame:
                on_frame(f)
    finally:
        try:
            p.kill()
        except OSError:
            pass
        p.wait()
    return frames, times


def tophat(g: np.ndarray) -> np.ndarray:
    """亮的细笔画(半透明白水印就是这样)。"""
    return cv2.morphologyEx(g, cv2.MORPH_TOPHAT, _K)


def still_maps(frames: list, step: int = 1, ths: list | None = None) -> list[tuple[int, np.ndarray]]:
    """相邻 WIN 帧的白顶帽取最小值:会动的画面被抹掉,不动的(水印、固定字)留下。返回 [(起始帧号, 图)]。
    窗口每次挪 step 帧(默认 1:每秒一张,水印出现在哪几秒更准)。视频很短(帧不够 WIN)就用全部帧。"""
    if ths is None:
        ths = [tophat(f) for f in frames]
    if not ths:
        return []
    if len(ths) < WIN:
        return [(0, np.min(np.stack(ths), axis=0))]
    pair = [cv2.min(ths[i], ths[i + 1]) for i in range(len(ths) - 1)]
    out = []
    for i in range(0, len(ths) - WIN + 1, max(1, step)):
        m = pair[i]
        for k in range(i + 2, i + WIN):
            m = cv2.min(m, ths[k])
        out.append((i, m))
    return out


class _StillMaker:
    """边解码边做「不动的图」:只留最近 WIN 张白顶帽(省内存:不用把每帧的白顶帽都存着)。
    结果和 still_maps(frames) 一样。"""

    def __init__(self):
        self.last: list = []
        self.out: list = []
        self.n = 0

    def add(self, f: np.ndarray):
        self.last.append(tophat(f))
        if len(self.last) > WIN:
            self.last.pop(0)
        if len(self.last) == WIN:
            m = self.last[0]
            for t in self.last[1:]:
                m = cv2.min(m, t)
            self.out.append((self.n - WIN + 1, m))
        self.n += 1

    def maps(self) -> list:
        if not self.out and self.last:                  # 不够 WIN 帧:用全部帧
            m = self.last[0]
            for t in self.last[1:]:
                m = cv2.min(m, t)
            return [(0, m)]
        return self.out


# ---------------- logo 库 ----------------
class Logo:
    """一个水印样子。th = 门槛;min_h = 比的时候最小多高(画布像素,太小的细节没了,乱像);
    小于 small_h 的门槛再加 small_pen(小的更容易撞上游戏图标)。"""

    def __init__(self, label: str, img: np.ndarray, th: float, src: str, min_h: int = 12, small_h: int = 22,
                 small_pen: float = 0.06):
        self.label, self.img, self.th, self.src = label, img.astype(np.float32), th, src
        self.min_h, self.small_h, self.small_pen = min_h, small_h, small_pen
        self.h, self.w = self.img.shape[:2]
        self._cache: dict = {}

    def th_at(self, h: int) -> float:
        return self.th + (self.small_pen if h < self.small_h else 0.0)

    def at(self, s: float) -> np.ndarray:
        """缩放到 s 倍(按 0.02 取整缓存)。"""
        k = round(s / 0.02)
        t = self._cache.get(k)
        if t is None:
            s2 = k * 0.02
            t = cv2.resize(self.img, (max(4, int(round(self.w * s2))), max(4, int(round(self.h * s2)))),
                           interpolation=cv2.INTER_AREA if s2 < 1 else cv2.INTER_LINEAR)
            self._cache[k] = t
        return t


_logos_cache: dict = {}
_logos_lock = threading.Lock()


def load_logos(force: bool = False) -> list[Logo]:
    """内置的 + 用户加的。样子是画布大小下截的白顶帽图(亮笔画)。meta.json 可设 {"th": 0.7}。"""
    with _logos_lock:
        key = tuple(sorted(str(p) + str(p.stat().st_mtime) for d in (ASSET_DIR, user_dir()) if d.is_dir()
                           for p in d.rglob("*")))
        if not force and _logos_cache.get("key") == key:
            return _logos_cache["logos"]
        out = []
        for root in (ASSET_DIR, user_dir()):
            if not root.is_dir():
                continue
            for sub in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("_")):  # _开头的不是样子
                meta = {}
                try:
                    meta = json.loads((sub / "meta.json").read_text("utf-8"))
                except (OSError, ValueError):
                    pass
                for f in sorted(sub.glob("*.png")):
                    img = cv2.imdecode(np.fromfile(str(f), np.uint8), cv2.IMREAD_GRAYSCALE)
                    if img is None or min(img.shape) < 6 or float(img.std()) < 1:
                        continue
                    one = meta.get(f.stem) if isinstance(meta.get(f.stem), dict) else {}
                    g = lambda k, d: one.get(k, meta.get(k, d))   # noqa: E731  按文件 > 整个文件夹 > 默认
                    try:
                        out.append(Logo(sub.name, img, float(g("th", DEFAULT_TH)), str(f), int(g("min_h", 12)),
                                        int(g("small_h", 22)), float(g("small_pen", 0.06))))
                    except (TypeError, ValueError):
                        continue
        _logos_cache.update(key=key, logos=out)
        return out


def make_logo(crops: list[np.ndarray]) -> np.ndarray:
    """从几张截下来的水印(灰度,同一位置不同帧)做样子:白顶帽取最小值(和查的时候「不动的图」一样:
    背景在变、水印不变),再切到笔画那一块。只有 1~2 张就直接用。"""
    st = np.stack([tophat(c).astype(np.float32) for c in crops])
    med = st.min(axis=0) if len(crops) >= 3 else np.median(st, axis=0)
    m = med > max(float(TB) * 0.6, med.max() * 0.35)
    ys, xs = np.where(m)
    if not len(xs):
        return med.astype(np.uint8)
    y0, y1 = max(0, ys.min() - 2), min(med.shape[0], ys.max() + 3)
    x0, x1 = max(0, xs.min() - 2), min(med.shape[1], xs.max() + 3)
    t = med[y0:y1, x0:x1]
    return np.clip(t * 255.0 / max(1.0, float(t.max())), 0, 255).astype(np.uint8)


# ---------------- 候选块 / 轨迹 ----------------
def blobs(m: np.ndarray, rect: tuple) -> tuple[list, float]:
    """不动的图里的候选块 [(x, y, w, h)](已去掉连块时多出来的边),和画面里亮笔画占多少(太多 = 这几秒画面没动)。"""
    x, y, w, h = rect
    sub = np.ascontiguousarray(m[y:y + h, x:x + w])
    if not sub.size:
        return [], 0.0
    _, b = cv2.threshold(sub, TB - 1, 1, cv2.THRESH_BINARY)          # 只算画面里(黑边不算)
    frac = cv2.countNonZero(b) / float(b.size)
    if frac > 0.12:                                                  # 这几秒画面没动,不用再找块
        return [], frac
    d = cv2.dilate(b, _KJOIN)
    n, _lab, st, _ = cv2.connectedComponentsWithStats(d, connectivity=8)
    out = []
    for k in range(1, n):
        bx, by, bw, bh, _a = (int(v) for v in st[k])
        bx, by, bw, bh = bx + 4 + x, by + 2 + y, bw - 8, bh - 4
        if bw < 10 or bh < 7 or bw > w * 0.6 or bh > max(40, h * 0.13):
            continue
        out.append((bx, by, bw, bh))
    return out, frac


def _iou(a, b) -> float:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    i = (x1 - x0) * (y1 - y0)
    return i / float(a[2] * a[3] + b[2] * b[3] - i)


def tracks_of(maps: list, rect: tuple) -> list[dict]:
    """把每一秒的候选块按位置串起来:{"box", "wins": [窗口序号], "boxes": {窗口序号: 块}}。
    这几秒整个画面没动(亮笔画占 > 12%)的窗口不要(什么都「不动」,块全连在一起,只会添乱)。"""
    tracks: list = []
    active: list = []
    for wi, (_i, m) in enumerate(maps):
        bl, frac = blobs(m, rect)
        if frac > 0.12:
            continue
        nxt = []
        for bb in bl:
            best, bs = None, 0.45
            for t in active:
                s = _iou(t["box"], bb)
                if s > bs:
                    best, bs = t, s
            if best is None:
                best = {"box": bb, "wins": [], "boxes": {}}
                tracks.append(best)
            if best["wins"] and best["wins"][-1] == wi:
                continue
            best["wins"].append(wi)
            best["boxes"][wi] = bb
            best["box"] = bb
            nxt.append(best)
        # 隔一个窗口没出现的也留着(水印偶尔被亮背景盖住一秒)
        active = nxt + [t for t in active if t not in nxt and t["wins"] and wi - t["wins"][-1] <= 2]
    return tracks


def _rep(track: dict) -> int:
    """轨迹的代表窗口:中间那个。"""
    w = track["wins"]
    return w[len(w) // 2]


def _roi(m: np.ndarray, box: tuple, pad: int) -> tuple[np.ndarray, int, int]:
    x, y, w, h = box
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(m.shape[1], x + w + pad), min(m.shape[0], y + h + pad)
    return m[y0:y1, x0:x1], x0, y0


def _match_in(mf: np.ndarray, t: np.ndarray) -> tuple[float, tuple]:
    if mf.shape[0] < t.shape[0] or mf.shape[1] < t.shape[1] or float(t.std()) < 1e-3:
        return 0.0, (0, 0)
    r = cv2.matchTemplate(mf, t, cv2.TM_CCOEFF_NORMED)
    _, mx, _, loc = cv2.minMaxLoc(r)
    return float(mx) if np.isfinite(mx) else 0.0, loc


def _best_logo(m: np.ndarray, box: tuple, logos: list) -> dict | None:
    """一块候选和 logo 库比:按块的高矮算缩放(块可能比 logo 宽:logo 旁边连着名字)。"""
    bx, by, bw, bh = box
    roi, x0, y0 = _roi(m, box, 6)
    roi = roi.astype(np.float32)
    best = None
    for lg in logos:
        s0 = bh / lg.h
        for f in (0.86, 0.93, 1.0, 1.08):
            s = s0 * f
            if s < 0.35 or s > 3.0:
                continue
            if lg.h * s < lg.min_h:
                continue
            t = lg.at(s)
            if t.shape[1] > roi.shape[1] or t.shape[0] > roi.shape[0] or t.shape[1] < 10 or t.shape[0] < lg.min_h:
                continue
            if bw > max(t.shape[1] * 4, t.shape[1] + 60):           # 块比 logo 宽太多(一长行字):不是它
                continue
            sc, loc = _match_in(roi, t)
            th = lg.th_at(t.shape[0])
            if best is None or sc - th > best["score"] - best["th"]:
                best = {"logo": lg, "s": s, "score": sc, "th": th,
                        "box": [x0 + loc[0], y0 + loc[1], int(t.shape[1]), int(t.shape[0])]}
    return best


def _grow(m: np.ndarray, box: list, rect: tuple) -> list:
    """logo 旁边同一行连着的字(UP 主名字、抖音号)一起框上:同一行、高矮差不多、隔得不远的候选块并进来。"""
    x, y, w, h = (int(v) for v in box)
    gap = max(8, int(h * 0.8))
    lim = max(w * 5, int(rect[2] * 0.6))
    bl, _ = blobs(m, rect)
    cur = [x, y, x + w, y + h]
    changed = True
    while changed:
        changed = False
        for bx, by, bw, bh in bl:
            if not (0.4 * h <= bh <= 1.5 * h):
                continue
            ov = min(cur[3], by + bh) - max(cur[1], by)            # 竖着叠多少
            if ov < 0.6 * min(h, bh):
                continue
            if bx > cur[2] + gap or bx + bw < cur[0] - gap:          # 隔太远
                continue
            nx0, nx1 = min(cur[0], bx), max(cur[2], bx + bw)
            if (nx0, nx1) == (cur[0], cur[2]) or nx1 - nx0 > lim:
                continue
            cur[0], cur[2] = nx0, nx1
            changed = True
    return [int(cur[0]), y, int(cur[2] - cur[0]), h]


def _grow_many(maps: list, wins: list, box: list, rect: tuple) -> list:
    """在出现的几个窗口里各扩一次(名字不一定每秒都在),取「至少两次扩到的」最大范围。"""
    pick = [wins[int(k)] for k in np.linspace(0, len(wins) - 1, min(7, len(wins)))]
    gs = [_grow(maps[wi][1], box, rect) for wi in dict.fromkeys(pick)]
    if len(gs) == 1:
        return gs[0]
    x0 = sorted(g[0] for g in gs)[1]
    x1 = sorted((g[0] + g[2] for g in gs), reverse=True)[1]
    x0, x1 = min(x0, box[0]), max(x1, box[0] + box[2])
    return [int(x0), int(box[1]), int(x1 - x0), int(box[3])]


def match_logos(maps: list, logos: list[Logo], times: list, rect: tuple | None = None,
                tracks: list | None = None) -> list[dict]:
    """在「不动的图」里找 logo。每条轨迹只拿代表窗口比一次,比上了再逐秒复查出现在哪几段。
    返回 [{"label","kind":"logo","score","box","t","frame","wins":[窗口序号]}](同一家不同位置分开报)。"""
    if not maps or not logos:
        return []
    if rect is None:
        rect = (0, 0, maps[0][1].shape[1], maps[0][1].shape[0])
    if tracks is None:
        tracks = tracks_of(maps, rect)

    def mf(wi):
        return maps[wi][1]

    found = []
    for tr in tracks:
        wi = _rep(tr)
        c = _best_logo(mf(wi), tr["boxes"][wi], logos)
        if c and c["score"] < c["th"] and c["score"] > c["th"] - 0.12 and len(tr["wins"]) > 2:
            for w2 in (tr["wins"][0], tr["wins"][-1]):           # 差一点的:换两个窗口再看看(那一秒可能被亮背景盖了)
                c2 = _best_logo(mf(w2), tr["boxes"][w2], logos)
                if c2 and c2["score"] - c2["th"] > c["score"] - c["th"]:
                    c = c2
        if not c:
            continue
        if c["score"] < c["th"]:
            continue
        found.append(c)
    if not found and all(blobs(m, rect)[1] > 0.12 for _i, m in maps[:: max(1, len(maps) // 5)]):
        found = _whole_frame(maps, logos)                   # 整条画面都不动(PPT、静态图):全图找
    hits: list = []
    for c in sorted(found, key=lambda z: -(z["score"] - z["th"])):
        if any(h["label"] == c["logo"].label and _iou(h["box"], c["box"]) > 0.2 for h in hits):
            continue
        t = c["logo"].at(c["s"])
        wins, best_w, best_s = [], 0, 0.0
        for wi in range(len(maps)):
            roi, _x0, _y0 = _roi(maps[wi][1], tuple(c["box"]), 5)
            sc, _ = _match_in(roi.astype(np.float32), t)
            if sc >= max(0.5, c["th"] - 0.1):
                wins.append(wi)
            if sc > best_s:
                best_w, best_s = wi, sc
        if not wins:
            continue
        fr = maps[best_w][0] + WIN // 2
        hits.append({"label": c["logo"].label, "kind": "logo", "score": round(max(c["score"], best_s), 3),
                     "box": [int(v) for v in c["box"]], "t": round(times[min(fr, len(times) - 1)], 1),
                     "frame": min(fr, len(times) - 1), "wins": wins, "src": os.path.basename(c["logo"].src),
                     "_grow": _grow_many(maps, wins, c["box"], rect)})
    return hits


def _whole_frame(maps: list, logos: list) -> list:
    """画面一直不动时的退路:挑 3 张不动的图,半分辨率粗找 + 原大小细找(老办法)。"""
    out = []
    picks = sorted({0, len(maps) // 2, len(maps) - 1})
    for wi in picks:
        mfl = maps[wi][1].astype(np.float32)
        small = cv2.resize(mfl, (mfl.shape[1] // 2, mfl.shape[0] // 2), interpolation=cv2.INTER_AREA)
        for lg in logos:
            for s in SCALES:
                t = lg.at(s)
                th_, tw = t.shape
                if th_ < 8 or tw < 8 or th_ >= mfl.shape[0] or tw >= mfl.shape[1]:
                    continue
                ts = cv2.resize(t, (max(4, tw // 2), max(4, th_ // 2)), interpolation=cv2.INTER_AREA)
                sc, loc = _match_in(small, ts)
                if sc < lg.th - 0.12:
                    continue
                roi, x0, y0 = _roi(mfl, (loc[0] * 2, loc[1] * 2, tw, th_), 8)
                sc2, loc2 = _match_in(roi, t)
                if sc2 >= lg.th_at(th_) and th_ >= lg.min_h:
                    out.append({"logo": lg, "s": s, "score": sc2, "th": lg.th_at(th_),
                                "box": [x0 + loc2[0], y0 + loc2[1], tw, th_]})
    return out


# ---------------- 认字 ----------------
_ocr = None
_ocr_lock = threading.Lock()


def ocr_engine():
    """RapidOCR;没装返回 None(就不认字,只用 logo 库)。"""
    global _ocr
    with _ocr_lock:
        if _ocr is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                _ocr = RapidOCR()
            except Exception:
                _ocr = False
        return _ocr or None


def text_label(txt: str) -> str:
    """认出来的一块字是不是水印的写法,是的话返回哪家,不是返回 ""。
    算:「抖音号:xxx」这种带号的;整块就是平台名(「抖音」「bilibili」「得物」,前后最多多 2 个零碎字符)。
    不算:夹在一句话里的(「开局不到30秒抖音直接上线」「抖音熊二大王」)。"""
    m = _SEP_RE.match(str(txt).lower())
    if m:
        k = m.group(1)
        for label, words in TEXT_WORDS.items():
            if k in [w.lower() for w in words]:
                return label
    low = _PUNCT.sub("", str(txt).lower())
    if not low:
        return ""
    m = _ID_RE.search(low)
    if m:
        k = m.group(1) or m.group(2)
        for label, words in TEXT_WORDS.items():
            if k in [w.lower() for w in words]:
                return label
    low2 = low.lstrip("@").replace("@", "")
    for label, words in TEXT_WORDS.items():
        for w in words:
            w = w.lower()
            if w in low2 and len(low2) <= len(w) + 2 and (low2.startswith(w) or low2.endswith(w)):
                if len(w) == 2 and len(low2) > 3:             # 两个字的(抖音 / 快手 / 得物 / 转转)要几乎正好
                    continue
                return label
    return ""


def _rec(eng, crops: list) -> list:
    """只做识别(不做检测):一块块切好的字。返回 [(字, 分)]。"""
    rec = getattr(eng, "text_recognizer", None)
    if rec is not None:
        res, _ = rec(crops)
        return [(str(r[0]), float(r[1])) for r in res]
    out = []
    for c in crops:                                         # 别的版本:整张当一行认
        r, _ = eng(c)
        out.append((str(r[0][1]), float(r[0][2])) if r else ("", 0.0))
    return out


def find_text_tracks(frames: list, maps: list, tracks: list, rect: tuple, times: list,
                     taken: list | None = None) -> list[dict]:
    """像一行字的轨迹切下来认字(只识别),是水印写法的报出来。taken = logo 已经框到的地方(不重复认)。"""
    eng = ocr_engine()
    if not eng or not tracks:
        return []
    ch = frames[0].shape[0]
    cands = []
    for tr in tracks:
        bx, by, bw, bh = tr["box"]
        if bh < 9 or bh > max(48, ch * 0.05) or bw < bh * 1.3:     # 水印的字小,一行
            continue
        if len(tr["wins"]) < min(2, len(maps)):                  # 水印至少待 4 秒;一闪而过的字幕不认
            continue
        if taken and any(_iou(t, tr["box"]) > 0.3 for t in taken):
            continue
        cands.append(tr)
    cands.sort(key=lambda t: -len(t["wins"]))
    cands = cands[:MAX_TRACKS_OCR]
    if not cands:
        return []
    crops = []
    for tr in cands:
        wi = _rep(tr)
        fi = min(len(frames) - 1, maps[wi][0] + WIN // 2)
        g, _x0, _y0 = _roi(frames[fi], tr["boxes"][wi], 4)
        crops.append(cv2.cvtColor(np.ascontiguousarray(g), cv2.COLOR_GRAY2BGR))
    try:
        with _ocr_lock:
            got = _rec(eng, crops)
    except Exception:
        return []
    hits = []
    for tr, (txt, sc) in zip(cands, got):
        if sc < 0.75:
            continue
        lab = text_label(txt)
        if not lab:
            continue
        wi = _rep(tr)
        fi = min(len(frames) - 1, maps[wi][0] + WIN // 2)
        hits.append({"label": lab, "kind": "text", "text": txt, "score": round(sc, 3),
                     "box": [int(v) for v in tr["box"]], "t": round(times[fi], 1), "frame": fi,
                     "wins": list(tr["wins"])})
    return hits


def find_text(frames: list, times: list, picks: int = 4) -> list[dict]:
    """(老办法,detect 不再用)挑几帧整张认字,只报水印写法的。"""
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
            lab = text_label(txt)
            if not lab or lab in hits:
                continue
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            hits[lab] = {"label": lab, "kind": "text", "text": str(txt), "score": round(float(sc), 3),
                         "box": [int(min(xs)), int(min(ys)), int(max(xs) - min(xs)), int(max(ys) - min(ys))],
                         "t": round(times[i], 1), "frame": i}
    return list(hits.values())


# ---------------- 一直不动的小图案(不认识的水印)----------------
def find_still(maps: list, frames: list, rect: tuple, times: list) -> list[dict]:
    """画面里(不算黑边)上下边上一直不动的小块亮图案,在好几段里都有。只报最明显的一处,说「疑似水印」。"""
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
    region[y:y + my, x:x + w] = 1
    region[y + h - my:y + h, x:x + w] = 1
    cand = persist & region
    cand = cv2.dilate(cand, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 5)))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(cand)
    best = None
    for k in range(1, n):
        bx, by, bw, bh, area = stats[k]
        if area < 120 or bw > w * 0.6 or bh > h * 0.12 or bw / max(1, bh) > 12:
            continue
        if best is None or area > best[4]:
            best = (bx, by, bw, bh, area)
    if not best:
        return []
    bx, by, bw, bh, _a = best
    return [{"label": "疑似水印", "kind": "still", "score": 0.0, "box": [int(bx), int(by), int(bw), int(bh)],
             "t": 0.0, "frame": len(frames) // 2, "wins": list(range(len(maps)))}]


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
    """画布上的框 → 原视频画面里的比例坐标(0~1),模糊的时候用。框伸到黑边里的部分切掉。"""
    x, y, w, h = rect
    x0, y0 = max(float(x), box[0]), max(float(y), box[1])
    x1, y1 = min(float(x + w), box[0] + box[2]), min(float(y + h), box[1] + box[3])
    x1, y1 = max(x1, x0), max(y1, y0)
    return [round(min(1.0, (x0 - x) / w), 4), round(min(1.0, (y0 - y) / h), 4),
            round(min(1.0, (x1 - x0) / w), 4), round(min(1.0, (y1 - y0) / h), 4)]


def spans_of(wins: list, maps: list, times: list, dur: float, pad: float = 1.0) -> list:
    """出现的窗口 → 时间段 [[开始秒, 结束秒], ...]:一个窗口管它那几帧,相邻的并起来,前后各留 pad 秒。
    差不多整条都有(≥ 95%)就是 [[0, 时长]]。"""
    if not wins or not times:
        return []
    dur = float(dur or 0) or (times[-1] + 1.0)
    n = len(times)
    segs = []
    for wi in sorted(set(wins)):
        i = maps[wi][0]
        j = min(n - 1, i + WIN - 1)
        # 抽得稀(长视频、只解关键帧)时,往前后各放到上一张 / 下一张抽到的帧:那中间什么时候出现的不知道,宁可多糊
        a = min(times[i] - pad, times[i - 1] if i > 0 else 0.0)
        b = max(times[j] + 0.5 + pad, times[j + 1] if j + 1 < n else dur)
        a, b = max(0.0, a), min(dur, b)
        if segs and a <= segs[-1][1]:
            segs[-1][1] = max(segs[-1][1], b)
        else:
            segs.append([a, b])
    tot = sum(b - a for a, b in segs)
    if tot >= dur * 0.95:
        return [[0.0, round(dur, 2)]]
    return [[round(a, 2), round(b, 2)] for a, b in segs]


def background(maps: list):
    """整条一直不动的东西(取均匀几张不动图的最小值);没有就返回 None。"""
    if len(maps) < 8:
        return None
    idx = np.linspace(0, len(maps) - 1, 6).astype(int)
    p = maps[idx[0]][1]
    for k in idx[1:]:
        p = cv2.min(p, maps[k][1])
    if float((p >= TB * 0.6).mean()) < 0.0005:
        return None
    return cv2.dilate(p, np.ones((3, 3), np.uint8))


def detect(path: str, ffmpeg: str, info: dict, stop=None, use_ocr: bool = True, use_still: bool = False,
           logos: list | None = None) -> dict:
    """查一条。info = vertical.probe 的结果。返回
    {"hits": [{"label","kind","score","box"(画布),"ratio"(原画面比例),"where","t","spans"}], "shot": 截图路径,
     "frames": 看了几帧}。没查到 hits 为空。
    spans:这个水印在哪几段出现(秒),模糊只糊这几段;同一家在不同位置(抖音左上 / 右下来回跳)拆成几条。"""
    w, h, dur = info.get("w", 0), info.get("h", 0), float(info.get("dur") or 0)
    sm = _StillMaker()
    frames, times = read_frames(path, ffmpeg, w, h, dur, stop=stop, on_frame=sm.add)
    if not frames:
        return {"hits": [], "shot": "", "frames": 0, "error": "视频读不出画面"}
    if stop and stop():
        return {"hits": [], "shot": "", "frames": len(frames), "error": "停了"}
    rect = content_rect(w, h)
    maps = sm.maps()
    lgs = load_logos() if logos is None else logos
    tracks = tracks_of(maps, rect)
    hits = match_logos(maps, lgs, times, rect, tracks)
    bg = background(maps)
    if bg is not None and not (stop and stop()):
        # 一直不动的东西(游戏血条、仪表盘、台标)减掉再找一遍:只出现一段的水印压在它们上面也分得出来
        rmaps = [(i, cv2.subtract(m, bg)) for i, m in maps]
        rtracks = tracks_of(rmaps, rect)
        for x in match_logos(rmaps, lgs, times, rect, rtracks):
            if not any(y["label"] == x["label"] and _iou(y["box"], x["box"]) > 0.2 for y in hits):
                hits.append(x)
        tracks = tracks + [t for t in rtracks if not any(_iou(t["box"], u["box"]) > 0.6 for u in tracks)]
    for x in hits:
        x["box"] = x.pop("_grow", x["box"])
    if use_ocr and not (stop and stop()):
        hits += find_text_tracks(frames, maps, tracks, rect, times, taken=[x["box"] for x in hits])
    if not hits and use_still:                   # 游戏的血条 / 小地图也一直不动,默认不用(误报太多)
        hits = find_still(maps, frames, rect, times)
    hits = _merge(hits)[:MAX_HITS]
    for x in hits:
        x["ratio"] = to_ratio(x["box"], rect)
        x["where"] = where(x["box"], rect)
        x["spans"] = spans_of(x.pop("wins", []), maps, times, dur or len(frames))
    shot = save_shot(path, frames, hits) if hits else ""
    return {"hits": hits, "shot": shot, "frames": len(frames)}


def _merge(hits: list) -> list:
    """同一家、框挨着 / 叠着的(logo 和旁边认出来的字)并成一个框;分数高的在前。"""
    out: list = []
    for x in sorted(hits, key=lambda z: (z["kind"] != "logo", -z["score"])):
        for y in out:
            if y["label"] != x["label"]:
                continue
            a, b = y["box"], x["box"]
            near = (abs((a[1] + a[3] / 2) - (b[1] + b[3] / 2)) < max(a[3], b[3]) * 1.5 and
                    b[0] < a[0] + a[2] + max(a[3], b[3]) * 2 and a[0] < b[0] + b[2] + max(a[3], b[3]) * 2)
            if near or _iou(a, b) > 0:
                x0, y0 = min(a[0], b[0]), min(a[1], b[1])
                y["box"] = [x0, y0, max(a[0] + a[2], b[0] + b[2]) - x0, max(a[1] + a[3], b[1] + b[3]) - y0]
                y["wins"] = sorted(set(y.get("wins", [])) | set(x.get("wins", [])))
                break
        else:
            out.append(x)
    return out


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
