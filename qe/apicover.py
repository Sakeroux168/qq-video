"""接口发的封面(用户 2026-10-16:「文件夹里面是什么封面就放什么吧 或者可以自行设置 什么比例的」)。

视频旁边同名的图片(xxx.mp4 + xxx.jpg / .png)→ 传给这条视频(/video/clientvideopic:每条一张,
平台建议 3:4,不超过 20MB,jpg / png)。没有同名图片 → 不传,平台自己从视频里截一帧(和以前一样)。
设置「封面比例」:原样 = 文件夹里什么样就传什么样;选了比例 = 从中间裁成那个比例再传(原图不动,裁好的放临时文件夹)。
"""
import os
import tempfile
import uuid

CHOICES = ["原样", "3:4", "9:16", "16:9", "4:3", "1:1", "不传"]
RATIOS = {"3:4": (3, 4), "9:16": (9, 16), "16:9": (16, 9), "4:3": (4, 3), "1:1": (1, 1)}
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")
MAX_BYTES = 20 * 1024 * 1024


def find(video_path: str) -> str:
    """视频旁边同名的封面图;没有给 ""。jpg 优先,其次 png / webp(大小写都认;先精准匹配,再忽略末尾空格)。"""
    d, base = os.path.split(video_path)
    stem = os.path.splitext(base)[0]
    try:
        names = os.listdir(d or ".")
    except OSError:
        return ""
    exact, stripped = {}, {}
    for n in names:
        s, e = os.path.splitext(n)
        el = e.lower()
        if el not in IMG_EXT:
            continue
        if s == stem:
            exact.setdefault(el, n)
        elif s.strip() == stem.strip():
            stripped.setdefault(el, n)
    for bucket in (exact, stripped):
        for e in IMG_EXT:
            if e in bucket:
                return os.path.join(d, bucket[e])
    return ""


def find_all(video_path: str) -> list[str]:
    """视频旁边所有同名封面图(含末尾空格差异、多后缀如同时有 .jpg 和 .png),发完一并挪走不留残余。"""
    d, base = os.path.split(video_path)
    stem = os.path.splitext(base)[0].strip()
    if not stem:
        return []
    try:
        names = os.listdir(d or ".")
    except OSError:
        return []
    out = []
    for n in names:
        s, e = os.path.splitext(n)
        if e.lower() in IMG_EXT and s.strip() == stem and os.path.isfile(os.path.join(d or ".", n)):
            out.append(os.path.join(d or ".", n))
    return out


def crop_box(w: int, h: int, ratio) -> tuple[int, int, int, int]:
    """从中间裁成 ratio=(宽, 高) 的框 (左, 上, 右, 下)。"""
    a, b = ratio
    if w * b > h * a:                       # 太宽:裁左右
        nw = max(1, round(h * a / b))
        x = (w - nw) // 2
        return x, 0, x + nw, h
    nh = max(1, round(w * b / a))           # 太高:裁上下
    y = (h - nh) // 2
    return 0, y, w, y + nh


def _border_box(img: str):
    """这张图去黑边以后留哪块(和教育号用同一个判断);没黑边 / 读不出来 → None。"""
    try:
        import numpy as np
        from PIL import Image
        from .cover import border_box, borders_of
        with Image.open(img) as im:
            g = np.asarray(im.convert("L"))
        return border_box(g.shape[1], g.shape[0], borders_of(g))
    except Exception:
        return None


def _tmp_dir() -> str:
    d = os.path.join(tempfile.gettempdir(), "企鹅号助手封面")
    os.makedirs(d, exist_ok=True)
    return d


def prepare(img: str, mode: str = "原样") -> str:
    """要传的那张图:原样且平台收(jpg/png、不超过 20MB)→ 原图;否则裁 / 转成 jpg 放临时文件夹。
    mode「不传」或没图 → ""。原图永远不动。"""
    if not img or mode == "不传":
        return ""
    ratio = RATIOS.get(mode)
    ext = os.path.splitext(img)[1].lower()
    box = _border_box(img)                         # 封面带黑边:去掉再传(用户 2026-10-22)
    if ratio is None and box is None and ext in (".jpg", ".jpeg", ".png") and os.path.getsize(img) <= MAX_BYTES:
        return img
    from PIL import Image
    with Image.open(img) as im:
        im = im.convert("RGB")
        if box:
            im = im.crop(box)
        if ratio:
            im = im.crop(crop_box(im.width, im.height, ratio))
        out = os.path.join(_tmp_dir(), uuid.uuid4().hex[:12] + ".jpg")
        q = 92
        while True:
            im.save(out, "JPEG", quality=q)
            if os.path.getsize(out) <= MAX_BYTES or q <= 50:
                break
            q -= 15
        if os.path.getsize(out) > MAX_BYTES:    # 还是太大(超大图):缩一半
            im.resize((im.width // 2, im.height // 2)).save(out, "JPEG", quality=85)
    return out


def cleanup(path: str, original: str):
    """传完删掉临时裁的那张(原图不删)。"""
    if path and path != original and os.path.dirname(path) == _tmp_dir():
        try:
            os.remove(path)
        except OSError:
            pass
