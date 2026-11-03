"""AI 第二轮看封面(用户 2026-11-03:「软件第一轮自动调整裁剪,AI 再看第二轮,前期我看第三轮;
觉得 AI 搞得没问题,以后就不需要第三轮我自己看了」)。

做法:把一条视频的封面原图 + 几个比例裁出来的样子拼成一张图,给千问看图模型(阿里百炼,和别处同一个 Key),
只问一件事:裁出来的哪个比例要调、为什么(头 / 脸被切、主角不在框里、主体被切掉一大块、重要的字被切断)。
不让它挪框(先看它挑得准不准)。结果按「封面图 + 框」记在 数据目录\\AI看封面.json,框没变就不再问(省钱)。
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
# 11-03 实测:问「哪个比例有毛病」,AI 会硬挑(20 张好的挑出 18 张「脸被切掉一半」,其实都好好的);
# 改成一张一张如实描述(脸在不在、完不完整),要不要调由软件按描述判断
PROMPT = ("第 1 张是短视频封面的原图,后面几张是从原图上按不同比例裁出来的(比例写在每张前面)。\n"
          "先看原图里最主要的那个人是谁(最大、最显眼的);原图里没有人就看最主要的东西。\n"
          "然后对后面每一张裁出来的图,如实回答:\n"
          "- main:这个主要人物(或主要的东西)在不在这张图里:在 / 不在;\n"
          "- face:他的两只眼睛、鼻子、嘴是不是都在这张图里看得见:都在 / 缺了(缺了指被图片边缘切出去,不是侧脸、"
          "戴眼镜、低头这种);没有人就写 没有人。\n"
          '只回一个 JSON 数组,不要别的字,例如 [{"ratio": "3:4", "main": "在", "face": "都在"}]')
_lock = threading.Lock()


def _key_of(v) -> str:
    """封面图 + 框 → 一个编号:框或图变了就要重新看。"""
    raw = json.dumps([v.cover, v.plan, getattr(v, "vcover", ""), getattr(v, "vplan", {})], ensure_ascii=False, sort_keys=True)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _store_path():
    return data_dir() / "AI看封面.json"


def _load() -> dict:
    try:
        d = json.loads(_store_path().read_text("utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def cached(v) -> dict | None:
    """看过、框没变:{"ok": bool, "why": str};没看过 None。"""
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


def sheet(v, h: int = 360) -> list[tuple[str, bytes]]:
    """[(「原图」/ 比例, JPEG)]:原图 + 每个比例裁出来的样子(和「快速过封面」同一个算框的办法),一张一张给 AI
    (11-03 试过拼成一张横条:AI 分不清哪块是哪块,20 张全说要调)。"""
    from PIL import Image
    base = Image.open(v.cover).convert("RGB")
    parts = [("原图", base)]
    vimg = Image.open(v.vcover).convert("RGB") if getattr(v, "vcover", "") else None
    for tag, r in C.RATIOS:
        img, plan = (vimg, v.vplan) if (r < 1 and vimg is not None) else (base, v.plan)
        x, y, w, hh = C.crop_rect(img.width, img.height, r, plan or {})
        parts.append((tag, img.crop((int(x), int(y), int(x + w), int(y + hh)))))
    out = []
    for tag, im in parts:
        k = h / max(1, im.height)
        buf = io.BytesIO()
        im.resize((max(1, int(im.width * k)), h)).save(buf, "JPEG", quality=85)
        out.append((tag, buf.getvalue()))
    return out


def parse(raw: str) -> dict:
    """AI 回的话 → {"ok": bool, "why": str}。读不出来抛 ValueError。"""
    m = re.search(r"\[.*\]", raw or "", re.S)
    try:
        arr = json.loads(m.group(0)) if m else None
    except ValueError:
        arr = None
    if not isinstance(arr, list) or not arr:
        raise ValueError("AI 回的读不出来")
    bad = []
    for b in arr:
        if not isinstance(b, dict):
            continue
        tag, main, face = str(b.get("ratio") or "").strip(), str(b.get("main") or ""), str(b.get("face") or "")
        if "不在" in main:
            bad.append(f"{tag} 主角不在框里")
        elif "缺" in face:
            bad.append(f"{tag} 脸被切了")
    return {"ok": not bad, "why": ";".join(bad)[:80]}


def ask(imgs: list[tuple[str, bytes]], key: str, model: str = MODEL, timeout: int = 60) -> str:
    """把原图和几个比例的图给千问看,返回它回的原话。出错抛 RuntimeError。"""
    import requests
    if not key:
        raise RuntimeError("要 AI 看封面,先在「设置」里填阿里百炼 Key")
    content = []
    for k, (tag, b) in enumerate(imgs):
        content.append({"type": "text", "text": f"第 {k + 1} 张:{tag}"})
        content.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(b).decode("ascii")}})
    content.append({"type": "text", "text": PROMPT})
    body = {"model": model, "temperature": 0, "max_tokens": 300, "enable_thinking": False,
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


def review(v, key: str, asker=None) -> dict:
    """看一条:先查记过的;没看过就问 AI、记下来。返回 {"ok": bool, "why": str}。出错抛 RuntimeError。
    asker(图) → 原话:测试里换掉,绝不真问 AI。"""
    got = cached(v)
    if got is not None:
        return got
    try:
        img = sheet(v)
    except Exception as e:
        raise RuntimeError(f"封面图读不出来({type(e).__name__})")
    raw = (asker or (lambda b: ask(b, key)))(img)
    try:
        res = parse(raw)
    except ValueError:
        raise RuntimeError("AI 回的读不出来")
    _save(v, res)
    return res
