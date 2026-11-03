"""AI 第二轮看封面(用户 2026-11-03:「软件第一轮自动调整裁剪,AI 再看第二轮,前期我看第三轮;
觉得 AI 搞得没问题,以后就不需要第三轮我自己看了」;同一天又说:「AI 来判断框的行不行,不行的话他再动手微调」)。

一条视频最多问千问看图模型(阿里百炼,和别处同一个 Key)三回:
1. 判断:原图 + 每个比例裁出来的样子,一张张如实说「主体完不完整、有没有字」(11-03 实测:问「哪个有毛病」它会硬挑);
2. 有不完整的、软件没认出脸的(东西、背对镜头的人):单问原图「主体在哪」(给框,0~1000),软件把那几个比例的框挪过去
   (记在 plan["ai"],人拖过的框优先);认出了脸还切到人的多半是框太窄,不挪,标黄;
3. 挪过的再判断一回,还不行的标黄留给人(多半是框太窄装不下)。有字的标黄「要去豆包去字」。
结果按「封面图 + 软件第一轮的框」记在 数据目录\\AI看封面2.json,没变就不再问(省钱)。
"""
import base64
import hashlib
import io
import json
import re
import threading

from . import cover as C
from .config import data_dir

MODEL = "qwen3-vl-plus"           # 11-03 实测这个 Key 只开了它(qwen-vl-max / plus 报「模型不存在」)
URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
WHAT = ("画面的主体:有人就是人(最大最显眼的那一个,几个人挨在一起就是这几个;背对镜头、侧着也算人);"
        "没人就是画面里最吸引眼球的那一样东西(比如一盘菜、一口锅、正在出水的水龙头),"
        "不是整个桌面、台面、房间这种背景。")
# 原来问「在 / 不在」:切掉一半也算「在」,11-03 用户截图里锅、蛋卷、水龙头切了一半 AI 都说没问题 → 改问完不完整
JUDGE = ("第 1 张是短视频封面的原图,后面几张是从原图上按不同比例裁出来的(比例写在每张前面)。\n"
         "先看原图," + WHAT + "\n"
         "然后对后面每一张裁出来的图,如实回答:\n"
         "- whole:主体在这张图里完不完整:完整 / 切掉一部分 / 不在。人的话只看头:头和脸整个在图里就算完整"
         "(身子被切掉、头顶切掉一点点都不算;背对镜头、侧脸、低头也不算);东西的话看它大半在不在;\n"
         "- text:这张图上有没有后期加上去的字或者大标题字:标题、字幕、花字、水印字、舞台背景板上的大标题都算;"
         "画面里东西上本来就有的字(地图、书本、纸张、海报、包装、衣服、招牌)不算:有 / 没有。\n"
         '只回一个 JSON 数组,不要别的字,例如 [{"ratio": "3:4", "whole": "完整", "text": "没有"}]')
LOCATE = ("这是一张短视频封面图。" + WHAT + "\n"
          "框出这个主体完整的样子,给 [x1, y1, x2, y2](0~1000 的相对坐标)。\n"
          '只回 JSON,不要别的字,例如 {"what": "一盘菜", "box": [300, 200, 700, 900]}')
_lock = threading.Lock()


def _strip(p: dict) -> dict:
    return {k: v for k, v in (p or {}).items() if k != "ai"}


def _key_of(v) -> str:
    """封面图 + 软件第一轮的框 → 一个编号:图或框变了就要重新看(AI 自己挪的不算)。"""
    raw = json.dumps(["v2", v.cover, _strip(v.plan), getattr(v, "vcover", ""), _strip(getattr(v, "vplan", {}))],
                     ensure_ascii=False, sort_keys=True)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _store_path():
    return data_dir() / "AI看封面2.json"


def _load() -> dict:
    try:
        d = json.loads(_store_path().read_text("utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def cached(v) -> dict | None:
    """看过、框没变:review 的结果;没看过 None。"""
    if not v.cover:
        return None
    return _load().get(_key_of(v))


def _save(v, res: dict):
    with _lock:
        d = _load()
        d[_key_of(v)] = res
        p = _store_path()
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False), "utf-8")
        tmp.replace(p)


def _jpeg(im, h: int = 360) -> bytes:
    k = h / max(1, im.height)
    buf = io.BytesIO()
    im.resize((max(1, int(im.width * k)), h)).save(buf, "JPEG", quality=85)
    return buf.getvalue()


def _src(v, r: float):
    """这个比例从哪张图、按哪个框裁:(「plan」/「vplan」, 图路径)。"""
    if r < 1 and getattr(v, "vcover", ""):
        return "vplan", v.vcover
    return "plan", v.cover


def sheet(v, tags=None) -> list[tuple[str, bytes]]:
    """[(「原图」/ 比例, JPEG)]:原图 + 每个比例裁出来的样子(和摆的时候同一个算框的办法),一张一张给 AI
    (11-03 试过拼成一张横条:AI 分不清哪块是哪块)。tags = 只要这几个比例。"""
    from PIL import Image
    imgs = {}

    def load(p):
        if p not in imgs:
            imgs[p] = Image.open(p).convert("RGB")
        return imgs[p]
    out = [("原图", _jpeg(load(v.cover)))]
    for tag, r in C.RATIOS:
        if tags is not None and tag not in tags:
            continue
        which, p = _src(v, r)
        img = load(p)
        x, y, w, hh = C.crop_rect(img.width, img.height, r, getattr(v, which) or {})
        out.append((tag, _jpeg(img.crop((int(x), int(y), int(x + w), int(y + hh))))))
    return out


def parse(raw: str) -> dict:
    """判断那回 AI 回的话 → {比例: {"whole": 完整 / 切了 / 不在, "text": bool}}。读不出来抛 ValueError。"""
    m = re.search(r"\[.*\]", raw or "", re.S)
    try:
        arr = json.loads(m.group(0)) if m else None
    except ValueError:
        arr = None
    if not isinstance(arr, list) or not arr:
        raise ValueError("AI 回的读不出来")
    out = {}
    for b in arr:
        if not isinstance(b, dict):
            continue
        tag, whole, text = str(b.get("ratio") or "").strip(), str(b.get("whole") or ""), str(b.get("text") or "")
        if not tag:
            continue
        out[tag] = {"whole": "不在" if "不在" in whole else ("切了" if ("切" in whole or "不完整" in whole) else "完整"),
                    "text": text.strip().startswith("有")}
    if not out:
        raise ValueError("AI 回的读不出来")
    return out


def parse_box(raw: str) -> tuple[float, float, float, float]:
    """「主体在哪」那回 → (左, 上, 右, 下) 占图几成。读不出来抛 ValueError。"""
    m = re.search(r"\{.*\}", raw or "", re.S)
    try:
        b = json.loads(m.group(0))["box"] if m else None
        x1, y1, x2, y2 = (min(max(float(t) / 1000, 0.0), 1.0) for t in b)
    except (ValueError, TypeError, KeyError):
        raise ValueError("AI 回的框读不出来")
    if x2 - x1 < 0.01 or y2 - y1 < 0.01:
        raise ValueError("AI 回的框读不出来")
    return x1, y1, x2, y2


def aim(img_w: float, img_h: float, r: float, box) -> list[float]:
    """把这个比例的框对准主体:返回框中心占图几成(和人手动拖的记法一样,crop_rect 会收到图里面)。
    装得下:主体放框正中(2.35:1 放上面那 72%,下面是标题区);装不下:左右对准中间,上下保住上沿(人头、锅沿)。"""
    x1, y1, x2, y2 = box
    bw, bh = C.crop_rect(img_w, img_h, r, {})[2:]
    fw, fh = bw / img_w, bh / img_h                       # 框占图几成
    cx = (x1 + x2) / 2
    room = fh * (C.TITLE_SAFE if r >= 2 else 1.0)          # 主体能放的高度
    if y2 - y1 <= room:
        top = (y1 + y2) / 2 - room / 2
    else:
        top = y1 - fh * 0.02                               # 太高放不下:上沿留一点,切下面
    return [round(cx, 4), round(top + fh / 2, 4)]


def _ask_raw(key: str, imgs: list[tuple[str, bytes]], prompt: str, timeout: int = 60) -> str:
    import requests
    if not key:
        raise RuntimeError("要 AI 看封面,先在「设置」里填阿里百炼 Key")
    content = []
    for k, (tag, b) in enumerate(imgs):
        if len(imgs) > 1:
            content.append({"type": "text", "text": f"第 {k + 1} 张:{tag}"})
        content.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(b).decode("ascii")}})
    content.append({"type": "text", "text": prompt})
    body = {"model": MODEL, "temperature": 0, "max_tokens": 300, "enable_thinking": False,
            "messages": [{"role": "user", "content": content}]}
    try:
        r = requests.post(URL, json=body, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                          timeout=timeout)
    except requests.RequestException:
        raise RuntimeError("连不上阿里百炼(网络?)")
    try:
        return r.json()["choices"][0]["message"]["content"]
    except Exception:
        raise RuntimeError(f"AI 没回话:HTTP {r.status_code}")


def ask(imgs: list[tuple[str, bytes]], prompt: str, key: str) -> str:
    """把图给千问看,返回它回的原话。出错抛 RuntimeError。"""
    return _ask_raw(key, imgs, prompt)


def _movable(v, tag: str, r: float) -> bool:
    """这个比例 AI 能不能挪:软件认出了脸的不挪 —— 脸框得准,切到人多半是框太窄装不下(11-03 试 40 张:
    两个人的 1:1 让 AI 挪,反而切掉一个),标黄留给人;认不出脸的(东西、背对镜头的人)才挪。
    2.35:1 有人脸的连「切了」都不算:软件专门算过躲标题区(会故意切点头顶),只看字。"""
    which, _p = _src(v, r)
    return not (getattr(v, which) or {}).get("faces")


def review(v, key: str, asker=None) -> dict:
    """看一条(先查记过的)。返回 {"ok", "why", "ai": {"plan": {比例: 框中心}, "vplan": {…}}, "moved": [比例], "text": [比例]}。
    出错抛 RuntimeError。asker(图, 问的话) → 原话:测试里换掉,绝不真问 AI。"""
    got = cached(v)
    if got is not None:
        return got
    asker = asker or (lambda imgs, prompt: ask(imgs, prompt, key))
    rmap = dict(C.RATIOS)

    def judge(tags=None):
        try:
            imgs = sheet(v, tags)
        except Exception as e:
            raise RuntimeError(f"封面图读不出来({type(e).__name__})")
        try:
            return parse(asker(imgs, JUDGE))
        except ValueError:
            raise RuntimeError("AI 回的读不出来")
    first = judge()
    for tag, r in C.RATIOS:                              # 2.35:1 有人脸的:软件专门算过躲标题区(会故意切点头顶),只看字
        if tag in first and r >= 2 and not _movable(v, tag, r):
            first[tag] = dict(first[tag], whole="完整")
    bad = [t for t, _r in C.RATIOS if first.get(t, {}).get("whole", "完整") != "完整"]
    final = dict(first)
    ai = {"plan": {}, "vplan": {}}
    moved = []
    boxes = {}
    for tag in bad:
        r = rmap[tag]
        if not _movable(v, tag, r):
            continue
        which, p = _src(v, r)
        if p not in boxes:
            try:
                from PIL import Image
                im = Image.open(p).convert("RGB")
                boxes[p] = (parse_box(asker([("原图", _jpeg(im, 720))], LOCATE)), im.width, im.height)
            except Exception:
                boxes[p] = None
        if not boxes[p]:
            continue
        box, w, h = boxes[p]
        ai[which][C.rkey(r)] = aim(w, h, r, box)
        moved.append(tag)
    if moved:
        apply(v, {"ai": ai})
        final.update(judge(moved))
    probs = []
    for tag, _r in C.RATIOS:
        res = final.get(tag)
        if not res:
            continue
        if res["whole"] != "完整":
            probs.append(f"{tag} " + ("主体不在框里" if res["whole"] == "不在" else
                                     ("挪了框还是装不下整个主体" if tag in moved else "主体被切了")))
    texts = [t for t, _r in C.RATIOS if final.get(t, {}).get("text")]
    if texts:
        probs.append(f"{'、'.join(texts)} 有字,要去豆包去字")
    res = {"ok": not probs, "why": ";".join(probs)[:120], "ai": ai, "moved": moved, "text": texts}
    _save(v, res)
    return res


def apply(v, res: dict) -> None:
    """把 AI 挪的框套到这条视频上(plan["ai"] / vplan["ai"];人拖过的框 crop_rect 里优先)。"""
    for which in ("plan", "vplan"):
        got = ((res or {}).get("ai") or {}).get(which) or {}
        if got:
            setattr(v, which, dict(getattr(v, which) or {}, ai=dict(got)))


def reapply(v) -> None:
    """重新自动配封面以后(「恢复自动」):AI 记过的框套回去,不再问 AI。"""
    got = cached(v) if getattr(v, "cover", "") else None
    if got:
        apply(v, got)
