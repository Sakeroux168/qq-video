"""封面:用横的还是竖的、裁剪框要对准哪。

用户定的规矩(2026-10-14):
- 默认传横封面(.png);裁剪时人必须在框中间(要拖一下框)。
- 画面里有两个人以上、裁的时候会把人切掉 / 切一半 → 直接用竖封面(.jpg)。
认人用本机的 OpenCV YuNet 人脸模型(models/face_detection_yunet_2023mar.onnx,不联网)。
实测 31 张:正脸都认得准;背对镜头、人很远很小的认不出来 → 标黄让人看一眼。

企鹅号的裁剪依次有 3:4 / 9:16 / 2.35:1 / 公众号小图(方)四个框,最窄的是 9:16。
「认出来的人都装得进 9:16 的框」→ 用横封面,框对准他们中间;装不下 → 用竖封面。
"""
import os

import numpy as np

MIN_FACE = 0.02        # 脸宽不到图宽 2% 的不算(拼图里远处的小人 0.013~0.015;拍球的小孩 0.026~0.032 要算)
SCORE = 0.7
NARROW = 9 / 16        # 最窄的那个框(9:16)


_DET = None


def _detector():
    global _DET
    if _DET is None:
        import cv2
        from .config import model_file
        m = model_file()
        if not m:
            raise RuntimeError("找不到人脸模型文件 models\\face_detection_yunet_2023mar.onnx")
        # 先读进内存再给 OpenCV:它打不开带中文的路径(软件就放在「企鹅号发布助手」文件夹里)
        buf = np.fromfile(m, dtype=np.uint8)
        _DET = cv2.FaceDetectorYN.create("onnx", buf, np.array([], dtype=np.uint8), (320, 320), SCORE, 0.3, 5000)
    return _DET


def read_image(path: str):
    import cv2
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)


def faces_in(path: str) -> tuple[list[tuple[float, float, float, float]], tuple[int, int]]:
    """图里的脸:[(左, 上, 宽, 高)],都按图的宽高算成 0~1。返回 (脸, (图宽, 图高))。"""
    import cv2
    img = read_image(path)
    if img is None:
        return [], (0, 0)
    h, w = img.shape[:2]
    s = 960 / max(w, h)
    small = cv2.resize(img, (max(1, int(w * s)), max(1, int(h * s)))) if s < 1 else img
    sh, sw = small.shape[:2]
    det = _detector()
    det.setInputSize((sw, sh))
    _, fs = det.detect(small)
    out = []
    for f in (fs if fs is not None else []):
        x, y, fw, fh = float(f[0]) / sw, float(f[1]) / sh, float(f[2]) / sw, float(f[3]) / sh
        if fw >= MIN_FACE:
            out.append((max(0.0, x), max(0.0, y), fw, fh))
    return out, (w, h)


def focus_of(faces) -> dict:
    """这些脸要一起框进去:返回 {cx, cy, x0, x1}(0~1)。cy 用脸往下一点(带上脖子肩膀)。"""
    x0 = min(f[0] - f[2] * 0.35 for f in faces)
    x1 = max(f[0] + f[2] * 1.35 for f in faces)
    y0 = min(f[1] for f in faces)
    y1 = max(f[1] + f[3] for f in faces)
    return {"cx": (x0 + x1) / 2, "cy": (y0 + y1) / 2 + (y1 - y0) * 0.3, "x0": max(0.0, x0), "x1": min(1.0, x1)}


def decide(v) -> None:
    """给一条视频定封面:填 v.cover / cover_kind / cover_why / plan / warn。"""
    v.warn = False
    if not v.png and not v.jpg:
        v.cover, v.cover_kind, v.cover_why, v.plan, v.warn = "", "", "没有封面图", {}, True
        return
    if not v.png:
        _use_jpg(v, "没有横封面")
        return
    try:
        faces, (w, h) = faces_in(v.png)
    except Exception as e:
        v.cover, v.cover_kind, v.cover_why, v.plan, v.warn = v.png, "横", f"认人出错({type(e).__name__}),框放中间", {}, True
        return
    if not faces:
        v.cover, v.cover_kind, v.cover_why, v.plan, v.warn = v.png, "横", "没认出人,框放中间(看一眼)", {}, True
        return
    f = focus_of(faces)
    narrow_w = (h * NARROW) / w if w else 1.0          # 9:16 框占图宽的几成
    span = max(x[0] + x[2] for x in faces) - min(x[0] for x in faces)      # 几张脸从最左到最右(只算脸)
    if len(faces) == 1 or span <= narrow_w * 0.9:       # 一个人(脸再大也是他一个)一律横的;几个人挨得近也横的
        v.cover, v.cover_kind, v.plan = v.png, "横", f
        v.cover_why = "1 个人,框对准他" if len(faces) == 1 else f"{len(faces)} 个人挨得近,框得下"
        return
    if v.jpg:
        _use_jpg(v, f"{len(faces)} 个人,横的裁会切掉人")
    else:
        v.cover, v.cover_kind, v.plan, v.warn = v.png, "横", f, True
        v.cover_why = f"{len(faces)} 个人分得开,但没有竖封面(看一眼)"


def _use_jpg(v, why: str):
    v.cover, v.cover_kind, v.cover_why = v.jpg, "竖", why
    try:
        faces, _ = faces_in(v.jpg)
        v.plan = focus_of(faces) if faces else {}
    except Exception:
        v.plan = {}


def set_kind(v, kind: str) -> None:
    """人在界面上手动改横 / 竖。"""
    if kind == "竖" and v.jpg:
        _use_jpg(v, "手动选的竖封面")
        v.warn = False
    elif kind == "横" and v.png:
        try:
            faces, _ = faces_in(v.png)
        except Exception:
            faces = []
        v.cover, v.cover_kind, v.cover_why, v.warn = v.png, "横", "手动选的横封面", False
        v.plan = focus_of(faces) if faces else {}


# ---------------- 裁剪框要拖多远 ----------------
def box_drag(canvas: dict, img_w: int, img_h: int, ratio: float, plan: dict) -> tuple[float, float, float, float]:
    """裁剪弹框里:canvas = 画布在页面上的位置 {left, top, width, height};图按比例缩进画布、居中;
    这个比例的框默认在图正中间、尽量大。返回 (从哪按下 x, y, 拖到 x, y)。plan 空 = 不用拖(起点终点一样)。
    实测:3:4 / 9:16 / 方 框都是图那么高、宽度按比例;2.35:1 框是图那么宽。"""
    cw, ch = canvas["width"], canvas["height"]
    s = min(cw / img_w, ch / img_h)
    dw, dh = img_w * s, img_h * s
    ix, iy = canvas["left"] + (cw - dw) / 2, canvas["top"] + (ch - dh) / 2
    if ratio <= dw / dh:
        bh, bw = dh, dh * ratio
    else:
        bw, bh = dw, dw / ratio
    bx, by = ix + (dw - bw) / 2, iy + (dh - bh) / 2          # 默认位置(居中)
    sx, sy = bx + bw / 2, by + bh / 2
    if not plan:
        return sx, sy, sx, sy
    tx = ix + plan["cx"] * dw - bw / 2
    ty = iy + plan["cy"] * dh - bh * 0.45                     # 脸放在框里偏上一点(2.35:1 下面有「标题区域」)
    tx = min(max(tx, ix), ix + dw - bw)
    ty = min(max(ty, iy), iy + dh - bh)
    return sx, sy, sx + (tx - bx), sy + (ty - by)


def ratio_of(tag: str) -> float:
    """裁剪弹框左边每个选项上的比例字样 → 数字(3:4 → 0.75)。认不出当方的。"""
    t = (tag or "").replace("：", ":").strip()
    try:
        a, b = t.split(":")
        return float(a) / float(b)
    except (ValueError, ZeroDivisionError):
        return 1.0


MIN_SHORT = 540         # 企鹅号嫌小:270×480、270×360 的竖封面传上去提示「封面图尺寸过小」;360×640 收(实测)
UP_SHORT = 720


def upload_file(path: str) -> str:
    """要传的封面图:短边不到 540 就放大到 720 存一份(放在数据目录里,原图不动),返回要传的那个文件。"""
    from PIL import Image
    from .config import data_dir
    with Image.open(path) as im:
        w, h = im.size
        if min(w, h) >= MIN_SHORT:
            return path
        k = UP_SHORT / min(w, h)
        big = im.convert("RGB").resize((round(w * k), round(h * k)), Image.LANCZOS)
    d = data_dir() / "放大的封面"
    d.mkdir(parents=True, exist_ok=True)
    out = d / (os.path.splitext(os.path.basename(path))[0][:60] + f"_{round(w * k)}x{round(h * k)}.jpg")
    big.save(out, quality=93)
    return str(out)


def image_size(path: str) -> tuple[int, int]:
    from PIL import Image
    with Image.open(path) as im:
        return im.size


def exists(p: str) -> bool:
    return bool(p) and os.path.isfile(p)
