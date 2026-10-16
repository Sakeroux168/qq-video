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
        eye = (float(f[5]) + float(f[7])) / 2 / sh            # 两只眼睛的高度(YuNet 的关键点)
        if fw >= MIN_FACE:
            out.append((max(0.0, x), max(0.0, y), fw, fh, eye))
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
    """给一条视频定封面:填 v.cover / cover_kind / cover_why / plan / warn(还有 vcover / vplan)。只用无字的。"""
    v.warn = False
    v.vcover, v.vplan = "", {}
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
        v.plan = dict(focus_of(faces), faces=[list(f) for f in faces])
        v.cover_why = "1 个人,框对准他" if len(faces) == 1 else f"{len(faces)} 个人挨得近,框得下"
        return
    big = max(faces, key=lambda x: x[2] * x[3])
    # 用户(2026-10-15 截图):两个人挨着坐,框只对准大人把小孩切了一半 —— 应该框两个人中间。
    # 「all」= 认出来的所有人:每个比例框得下所有人就对准他们中间(crop_rect),框不下的窄比例才对准脸最大的
    v.plan, v.warn = dict(focus_of([big]), faces=[list(big)], all=[list(f) for f in faces]), True
    v.cover_why = f"{len(faces)} 个人:宽的比例框所有人,窄的框不下就对准脸最大的(看一眼)"
    # 用户一开始定的:几个人、裁剪会把人切掉 / 切一半 → 用竖封面。带字的 jpg 不能用,员工「梁」做的 竖屏9x16.png 是无字的 →
    # 竖的比例(3:4、9:16)用它;宽的比例(2.35:1、1:1)横图本来就框得下所有人,还用横图
    if getattr(v, "vpng", "") and exists(v.vpng):
        v.vcover, v.vplan, v.warn = v.vpng, plan_for_image(v.vpng), False
        v.cover_why = f"{len(faces)} 个人:竖的比例用他做的竖屏图,宽的比例框所有人"


def plan_for_image(path: str) -> dict:
    """一张图该对准哪:有人对准人(几个人一起),没人对准画面主体。"""
    try:
        fs, _ = faces_in(path)
    except Exception:
        return {}
    if fs:
        return dict(focus_of(fs), faces=[list(f) for f in fs], all=[list(f) for f in fs])
    try:
        return subject_of(path)
    except Exception:
        return {}


def pick_for(v, ratio: float) -> tuple[str, dict]:
    """这个比例用哪张图、按哪个 plan 裁:竖的比例有竖图就用竖图,别的用横图。(2.35:1 的 AI 专用图另外算)"""
    if ratio < 1 and getattr(v, "vcover", ""):
        return v.vcover, v.vplan
    return v.cover, v.plan


WIDE_NOTE = {"crop": ";2.35:1 切掉一点头顶(不挡脸)", "ai": ";2.35:1 要 AI 扩图(看一眼)"}


def note_wide(v) -> None:
    """说明里补一句 2.35:1 怎么躲标题区(切头顶 / AI 扩图);AI 扩的标黄让人看一眼。"""
    for t in WIDE_NOTE.values():
        v.cover_why = v.cover_why.replace(t, "")
    if not v.cover or not (v.plan or {}).get("faces"):
        return
    try:
        w, h = image_size(v.cover)
    except Exception:
        return
    mode = wide_mode(w, h, v.plan)[0]
    if mode in WIDE_NOTE:
        v.cover_why += WIDE_NOTE[mode]
        if mode == "ai":
            v.warn = True


# ---------------- 裁剪框放哪 ----------------
RATIOS = [("3:4", 3 / 4), ("9:16", 9 / 16), ("2.35:1", 2.35), ("1:1", 1.0)]    # 企鹅号裁剪的几个比例(有的号只有前两个)


def rkey(ratio: float) -> str:
    return f"{ratio:.3f}"


# 2.35:1(公众号推送大图)框的下面 26% 是「标题区域」,会压上标题字(用户:大头照脸上会有字,不行)。
# 实测两张截图:标题区上沿在框高的 0.738、0.758 处 → 按 0.72 算(留点余量)。
TITLE_SAFE = 0.72
TITLE_TEXT = 0.76      # 标题的字在标题区中间偏下:切头顶的时候下巴可以碰到标题区上沿那条暗边,但不能到字那里
WIDE = 2.35


def _face_band(plan: dict, img_h: float):
    """要躲开标题区的那几张脸:从头顶(脸框往上 22%)到下巴(脸框往下 3%),图的像素。没有脸返回 None。"""
    fs = (plan or {}).get("all") or (plan or {}).get("faces") or []      # 2.35:1 框跟图一样宽,所有人都在里面:都要躲开标题区
    if not fs:
        return None
    return min(f[1] - f[3] * 0.22 for f in fs) * img_h, max(f[1] + f[3] * 1.03 for f in fs) * img_h


def title_fit(img_w: float, img_h: float, plan: dict):
    """2.35:1 框上下能挪的范围里,能不能让脸整个在标题区上面。返回 (能不能, 最合适的框上沿 y)。没有脸返回 (True, None)。"""
    band = _face_band(plan, img_h)
    if band is None:
        return True, None
    bh = min(img_h, img_w / WIDE)
    top, bot = band
    lo, hi = max(0.0, bot - TITLE_SAFE * bh), min(img_h - bh, top)
    ideal = (top + bot) / 2 - TITLE_SAFE * bh / 2
    if lo <= hi:
        return True, min(max(ideal, lo), hi)
    return False, min(max(bot - TITLE_SAFE * bh, 0.0), img_h - bh)


def crop_fit(img_w: float, img_h: float, plan: dict):
    """办法一(用户选的):挪框躲不开时,允许切掉一点头顶 —— 下巴刚好在标题区上面。
    最多切到眼睛上面(眼睛往上留脸高的 22%,眉毛额头要在),再多就不行。返回 (行不行, 框上沿 y)。"""
    fs = (plan or {}).get("all") or (plan or {}).get("faces") or []
    if not fs:
        return True, None
    bh = min(img_h, img_w / WIDE)
    chin = max(f[1] + f[3] * 1.03 for f in fs) * img_h
    brow = min((f[4] if len(f) > 4 else f[1] + f[3] * 0.4) - f[3] * 0.22 for f in fs) * img_h
    ty = min(max(chin - TITLE_SAFE * bh, 0.0), img_h - bh)
    return (ty + TITLE_TEXT * bh >= chin - 1 and ty <= brow), ty


def wide_mode(img_w: float, img_h: float, plan: dict) -> tuple[str, float | None]:
    """2.35:1 怎么办:
    "manual" 人手动拖过;"drag" 挪框就躲开标题区;"crop" 切掉一点头顶(办法一);"ai" AI 扩图做专用图(办法三);
    "none" 没脸,不管标题区。人在预览里点了「AI 扩图」(plan["ai235"])就直接 "ai"。返回 (怎么办, 框上沿 y)。"""
    plan = plan or {}
    if plan.get("manual", {}).get(rkey(WIDE)):
        return "manual", None
    if not plan.get("faces"):
        return "none", None
    if plan.get("ai235"):
        return "ai", None
    ok, ty = title_fit(img_w, img_h, plan)
    if ok:
        return "drag", ty
    ok, ty2 = crop_fit(img_w, img_h, plan)
    if ok or plan.get("no_ai"):                           # 人点了「不用 AI」:切头顶能切多少切多少
        return "crop", ty2
    return "ai", None


def needs_wide(img_w: float, img_h: float, plan: dict) -> bool:
    """这条的 2.35:1 要不要换专用图(AI 扩图)。"""
    return wide_mode(img_w, img_h, plan)[0] == "ai"


# ---------------- 办法三:AI 扩图(阿里百炼 qwen-image-2.0,一张约几毛钱、6 秒左右)----------------
# 用户 2026-10-15:两边模糊不行(「那张封面 png 并没有模糊处理」);办法一(切头顶)和办法三(AI 扩)都不错。
# 原图缩小放进 2.35:1 的白底画布(脸在标题区上面),让 AI 把白的地方补成和原图连着的场景;
# 画完把原图原样贴回去 —— 人脸和原画面一个像素都不让 AI 改,AI 只补边(实测它会在边上乱画一只手,提示词里也不让画人)。
AI_KEY = ""                  # 窗口启动时从设置里填
AI_NEGATIVE = "人,手,手臂,手指,胳膊,人脸,身体,文字,字母,水印,logo"
AI_MODEL = "qwen-image-2.0"
AI_PROMPT = ("这张图两边和下面的纯白色区域是空的。把纯白色区域补画出来,和中间原来的画面自然衔接"
             "(同一个场景、同样的光线和色调、线条接得上)。不要画任何人、手、脸或身体的一部分,不要加任何文字和水印。"
             "中间原有的画面和人物一点都不要改动。")


def ai_canvas(img, plan: dict, max_w: int = 1424):
    """原图(缩到 max_w 宽以内)放进 2.35:1 白底画布:脸(头顶到下巴)落在标题区上面。
    脸在原图很靠下时原图要往上推(上面超出画布的部分不要),下面空出来给 AI 补。
    返回 (画布, (原图那块在画布上的 左, 上, 宽, 高, 从原图(缩小后)第几行开始))。"""
    import cv2
    H, W = img.shape[:2]
    if W > max_w:
        img = cv2.resize(img, (max_w, round(H * max_w / W)), interpolation=cv2.INTER_AREA)
        H, W = img.shape[:2]
    top, bot = _face_band(plan, H)
    fs = plan.get("faces") or []
    cx = (min(f[0] for f in fs) + max(f[0] + f[2] for f in fs)) / 2 * W
    s = min(1.0, (TITLE_SAFE - 0.06) * (W / WIDE) / max(1.0, bot - top))   # 画布上原图要缩到几成(画布宽 = 原图宽 / s)
    W2 = round(W / s)
    H2 = round(W2 / WIDE)
    left = int(min(max(W2 / 2 - cx, 0), W2 - W))
    up = int(round(0.03 * H2 - top))                    # 可以是负的:原图往上推
    up = min(up, max(0, H2 - H))                        # 原图比画布矮时别往下放过头
    canvas = np.full((H2, W2, 3), 255, np.uint8)
    y0, y1 = max(0, up), min(H2, up + H)
    canvas[y0:y1, left:left + W] = img[y0 - up:y1 - up]
    return canvas, (left, y0, W, y1 - y0, y0 - up)


def cache_file(folder: str, path: str, suffix: str):
    """数据目录里给这张封面存的东西(AI 扩的 2.35:1 图、放大的图)叫什么。
    按**完整路径**区分(2026-10-16 修:原来只按文件名,封面工具出的图每条都叫「横屏16x9.png」,
    所有视频共用了同一张 AI 扩图 —— A 视频的 2.35:1 封面是 B 视频的画面)。"""
    import hashlib
    from .config import data_dir
    d = data_dir() / folder
    d.mkdir(parents=True, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0][:40]
    h = hashlib.md5(os.path.normcase(os.path.abspath(path)).encode("utf-8")).hexdigest()[:10]
    return d / f"{stem}_{h}{suffix}"


def wide_cover(path: str, plan: dict, log=lambda m: None) -> str:
    """办法三:AI 扩图做 2.35:1 专用图。做过的直接用(存在数据目录)。没填阿里百炼 Key / 调不通抛 RuntimeError。"""
    import base64
    import cv2
    import requests
    out = cache_file("2.35专用封面", path, "_2.35_AI.jpg")
    if out.is_file() and out.stat().st_mtime >= os.path.getmtime(path):
        return str(out)
    if not AI_KEY:
        raise RuntimeError("要用 AI 扩图,先在「设置」里填阿里百炼 Key")
    img = read_image(path)
    canvas, (left, up, w, h, src0) = ai_canvas(img, plan)
    ok, buf = cv2.imencode(".jpg", canvas, [cv2.IMWRITE_JPEG_QUALITY, 92])
    body = {"model": AI_MODEL, "input": {"messages": [{"role": "user", "content": [
        {"image": "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()}, {"text": AI_PROMPT}]}]},
        "parameters": {"n": 1, "watermark": False, "negative_prompt": AI_NEGATIVE}}
    log("  AI 扩图中…(6 秒左右)")
    r = requests.post("https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
                      headers={"Authorization": f"Bearer {AI_KEY}", "Content-Type": "application/json"}, json=body, timeout=180)
    try:
        url = r.json()["output"]["choices"][0]["message"]["content"][0]["image"]
    except Exception:
        raise RuntimeError(f"AI 扩图没成:{r.status_code} {r.text[:150]}")
    gen = cv2.imdecode(np.frombuffer(requests.get(url, timeout=60).content, np.uint8), cv2.IMREAD_COLOR)
    if gen is None:
        raise RuntimeError("AI 扩图的结果下载不下来")
    # 按原图的清晰度拼:画布放大 k 倍(k = 原图宽 / 交给 AI 的那张宽),中间贴全尺寸原图
    # (企鹅号嫌小:交给 AI 的 1424 宽扩出来只有一千多宽,传上去报「封面图尺寸过小」)
    k = img.shape[1] / w
    H2, W2 = round(canvas.shape[0] * k), round(canvas.shape[1] * k)
    left, up, w, h, src_top = round(left * k), round(up * k), img.shape[1], round(h * k), round(src0 * k)
    gen = cv2.resize(gen, (W2, H2), interpolation=cv2.INTER_CUBIC)
    canvas = gen.copy()
    h = min(h, H2 - up, img.shape[0] - src_top)
    canvas[up:up + h, left:left + w] = img[src_top:src_top + h, :w]
    # 原图贴回去:原图那块全用原图;只在和 AI 补的交界处(不贴画布边的那几条边)往里 12 像素渐变
    feather = 12
    mask = np.zeros((H2, W2), np.float32)
    ys = np.ones(h, np.float32)
    xs = np.ones(w, np.float32)
    ramp = np.linspace(0, 1, feather, dtype=np.float32)
    if up > 0:
        ys[:feather] = np.minimum(ys[:feather], ramp)
    if up + h < H2:
        ys[-feather:] = np.minimum(ys[-feather:], ramp[::-1])
    if left > 0:
        xs[:feather] = np.minimum(xs[:feather], ramp)
    if left + w < W2:
        xs[-feather:] = np.minimum(xs[-feather:], ramp[::-1])
    mask[up:up + h, left:left + w] = np.outer(ys, xs)
    m3 = mask[..., None]
    res = (gen.astype(np.float32) * (1 - m3) + canvas.astype(np.float32) * m3).astype(np.uint8)
    cv2.imencode(".jpg", res, [cv2.IMWRITE_JPEG_QUALITY, 93])[1].tofile(str(out))
    return str(out)


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
        group = plan.get("all") or []
        if len(group) > 1:                                   # 几个人:这个框装得下所有人就对准他们中间
            gx0 = min(f[0] - f[2] * 0.3 for f in group) * img_w
            gx1 = max(f[0] + f[2] * 1.3 for f in group) * img_w
            if gx1 - gx0 <= bw:
                tx = (gx0 + gx1) / 2 - bw / 2
        ty = plan["cy"] * img_h - bh * 0.45                   # 脸放在框里偏上一点
        if ratio >= 2 and plan.get("faces"):
            mode, t2 = wide_mode(img_w, img_h, plan)          # 2.35:1:让脸躲开下面的标题区(挪框 / 切掉点头顶)
            if t2 is not None:
                ty = t2
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
    out = cache_file("放大的封面", path, f"_{round(w * k)}x{round(h * k)}.jpg")
    big.save(out, quality=93)
    return str(out)


def image_size(path: str) -> tuple[int, int]:
    from PIL import Image
    with Image.open(path) as im:
        return im.size


def exists(p: str) -> bool:
    return bool(p) and os.path.isfile(p)
