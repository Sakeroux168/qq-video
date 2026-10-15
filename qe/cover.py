"""封面:裁剪框要对准哪。

用户定的规矩:
- 封面只用 .png(组长 2026-10-15:「jpg 是原封面不能要,上面有字,所以才 p 了一下导出的 png 无字版本」)。
  以前「几个人分得开就用竖的 jpg」作废;没有 png 的标黄,不拿 jpg 顶。
- 裁剪时人必须在框中间(要拖一下框);没有人的,框对准画面主体。
认人用本机的 OpenCV YuNet 人脸模型(models/face_detection_yunet_2023mar.onnx,不联网)。

企鹅号的裁剪依次有 3:4 / 9:16 / 2.35:1 / 公众号小图(方)四个框(有的号只有前两个),最窄的是 9:16。
几个人都装得进 9:16 的框 → 框对准他们中间;装不下 → 框对准脸最大的那个(一般是主角),标黄让人在「封面预览」里看一眼。
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


def subject_of(path: str) -> dict:
    """没人的封面:找画面主体(用户:「没有人 那就以这个物的主体为中心」)。
    频率调谐显著性(Achanta 2009):每个点的颜色离整张图的平均颜色有多远(Lab),主体一般和背景差得多;
    再往画面中间压一点(边上多半是桌面、墙)。取最显眼的 15% 的重心。返回 {cx, cy}(0~1),读不出来返回 {}。
    实测今天 8 张没人的:背影写作业的小孩、一盘鸡块、零食、书桌、手表、湖边远处的人都框得准。"""
    import cv2
    img = read_image(path)
    if img is None:
        return {}
    h, w = img.shape[:2]
    s = 640 / w
    img = cv2.resize(img, (640, max(1, int(h * s))))
    lab = cv2.cvtColor(cv2.GaussianBlur(img, (5, 5), 0), cv2.COLOR_BGR2LAB).astype(np.float32)
    sal = np.linalg.norm(lab - lab.reshape(-1, 3).mean(0), axis=2)
    sal = cv2.GaussianBlur(sal, (0, 0), 6)
    hh, ww = sal.shape
    yy, xx = np.mgrid[0:hh, 0:ww]
    prior = np.exp(-(((xx / ww - 0.5) / 0.45) ** 2 + ((yy / hh - 0.5) / 0.55) ** 2))
    sal = sal * (0.6 + 0.4 * prior)
    thr = np.quantile(sal, 0.85)
    m = np.where(sal >= thr, sal - thr, 0)
    tot = float(m.sum())
    if tot <= 0:
        return {}
    return {"cx": float((m * xx).sum() / tot / ww), "cy": float((m * yy).sum() / tot / hh), "subject": True}


def decide(v) -> None:
    """给一条视频定封面:填 v.cover / cover_kind / cover_why / plan / warn。只用 png。"""
    v.warn = False
    if not v.png:
        v.cover, v.cover_kind, v.plan, v.warn = "", "", {}, True
        v.cover_why = "没有无字封面(png)" + (",jpg 有字不能用" if v.jpg else "")
        return
    v.cover, v.cover_kind = v.png, "横"
    try:
        faces, (w, h) = faces_in(v.png)
    except Exception as e:
        v.cover_why, v.plan, v.warn = f"认人出错({type(e).__name__}),框放中间", {}, True
        return
    if not faces:
        try:
            plan = subject_of(v.png)
        except Exception:
            plan = {}
        v.plan = plan
        v.cover_why, v.warn = ("没人,框对准画面主体", False) if plan else ("没认出人,框放中间(看一眼)", True)
        return
    narrow_w = (h * NARROW) / w if w else 1.0          # 9:16 框占图宽的几成
    span = max(x[0] + x[2] for x in faces) - min(x[0] for x in faces)      # 几张脸从最左到最右(只算脸)
    if len(faces) == 1 or span <= narrow_w * 0.9:       # 一个人(脸再大也是他一个);几个人挨得近也框得下
        v.plan = focus_of(faces)
        v.cover_why = "1 个人,框对准他" if len(faces) == 1 else f"{len(faces)} 个人挨得近,框得下"
        return
    big = max(faces, key=lambda x: x[2] * x[3])
    v.plan, v.warn = focus_of([big]), True
    v.cover_why = f"{len(faces)} 个人分得开,框对准脸最大的(看一眼)"


# ---------------- 裁剪框放哪 ----------------
RATIOS = [("3:4", 3 / 4), ("9:16", 9 / 16), ("2.35:1", 2.35), ("1:1", 1.0)]    # 企鹅号裁剪的几个比例(有的号只有前两个)


def rkey(ratio: float) -> str:
    return f"{ratio:.3f}"


def crop_rect(img_w: float, img_h: float, ratio: float, plan: dict) -> tuple[float, float, float, float]:
    """这个比例的框在图上放哪:返回 (左, 上, 宽, 高)(图的像素)。框尽量大(企鹅号就是这样)。
    放哪:人手动拖过的(plan["manual"][比例] = 框中心占图的几成)> 自动的(plan 的 cx, cy,脸放框里偏上一点)> 正中间。
    预览窗口画的、摆的时候真去拖的,都用这一个算法,所以看到的就是摆出来的。"""
    if ratio <= img_w / img_h:
        bh, bw = img_h, img_h * ratio
    else:
        bw, bh = img_w, img_w / ratio
    man = (plan or {}).get("manual", {}).get(rkey(ratio))
    if man:
        tx, ty = man[0] * img_w - bw / 2, man[1] * img_h - bh / 2
    elif plan and "cx" in plan:
        tx = plan["cx"] * img_w - bw / 2
        ty = plan["cy"] * img_h - bh * 0.45                   # 脸放在框里偏上一点(2.35:1 下面有「标题区域」)
    else:
        tx, ty = (img_w - bw) / 2, (img_h - bh) / 2
    tx = min(max(tx, 0.0), img_w - bw)
    ty = min(max(ty, 0.0), img_h - bh)
    return tx, ty, bw, bh


def box_drag(canvas: dict, img_w: int, img_h: int, ratio: float, plan: dict) -> tuple[float, float, float, float]:
    """裁剪弹框里:canvas = 画布在页面上的位置 {left, top, width, height};图按比例缩进画布、居中;
    这个比例的框默认在图正中间、尽量大。返回 (从哪按下 x, y, 拖到 x, y)。
    实测:3:4 / 9:16 / 方 框都是图那么高、宽度按比例;2.35:1 框是图那么宽。"""
    cw, ch = canvas["width"], canvas["height"]
    s = min(cw / img_w, ch / img_h)
    ix, iy = canvas["left"] + (cw - img_w * s) / 2, canvas["top"] + (ch - img_h * s) / 2
    dx, dy, bw, bh = crop_rect(img_w, img_h, ratio, {})              # 默认(居中)
    tx, ty, _w, _h = crop_rect(img_w, img_h, ratio, plan)
    sx, sy = ix + (dx + bw / 2) * s, iy + (dy + bh / 2) * s
    return sx, sy, sx + (tx - dx) * s, sy + (ty - dy) * s


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
