"""黑封面(用户 2026-11-06:「发完后检查黑屏封面的视频,我好去修改」;很小的字幕也算黑)。

11-06 查了 2793 张平台封面:20 张黑的,抽查 8 条,都是员工放的 .jpg 本身就是黑的(截了视频第一帧),软件照着传了。所以两头都管:
- 发之前:放的封面图是黑的就不用,换成软件自己挑的一帧(api_tab 发布那里);
- 发之后:读平台上实际用的封面(文章列表的 article_imgurl,只读),黑的列出来让人去后台改(接口改不了封面)。

算黑:亮度超过 40 的像素不到 3%。纯黑、只有一小行字幕都算;有一块正常画面、黑底大字的不算(3% 是拿 2793 张看出来的)。
"""
import io
import json

from .config import data_dir

BRIGHT, LIMIT = 40, 0.03


def _store_path():
    return data_dir() / "黑封面.json"


def is_black_img(im) -> bool:
    """im = 一张 PIL 图。"""
    import numpy as np
    a = np.asarray(im.convert("L").resize((160, 160)))
    return float((a > BRIGHT).mean()) < LIMIT


def is_black(path: str) -> bool:
    """本地这张图是黑的吗;读不出来算不是(不因为这个换封面)。"""
    from PIL import Image
    try:
        with Image.open(path) as im:
            return is_black_img(im)
    except Exception:
        return False


def _fetch(url: str) -> bytes:
    import requests
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.content


def accounts() -> list[dict]:
    """取过钥匙的号:接口发的 + 只查的(教育 / 影视)。"""
    from . import apiacc
    out = [a for a in apiacc.load() if a.get("client_id") and a.get("secret")]
    have = {a.get("nick") for a in out}
    return out + [a for a in apiacc.qload() if a.get("nick") not in have]


def scan_one(a: dict, start: str, end: str, stopped=None, make_client=None, fetch=None) -> tuple[list[dict], int]:
    """查一个号 start~end(「2026-11-06」)发的:返回 ([黑的], 读不出来的几张)。删掉的不算。"""
    from PIL import Image
    from . import apiacc, omapi, verify
    cl = (make_client or (lambda x: omapi.Client(x["client_id"], apiacc.unseal(x["secret"]))))(a)
    black, bad = [], 0
    for p in verify.platform_between(cl, start, end, stopped=stopped):
        if stopped and stopped():
            break
        if p.get("deleted"):
            continue
        if not p.get("img"):
            bad += 1
            continue
        try:
            with Image.open(io.BytesIO((fetch or _fetch)(p["img"]))) as im:
                if is_black_img(im):
                    black.append({"nick": a.get("nick") or "", "title": p.get("title") or "", "time": p.get("time") or "",
                                  "url": p.get("url") or "", "aid": p.get("aid") or ""})
        except Exception:
            bad += 1
    return black, bad


def save(day: str, items: list[dict]) -> None:
    p = _store_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"day": day, "items": items}, ensure_ascii=False), "utf-8")
    tmp.replace(p)


def load(day: str) -> list[dict]:
    """这天查到的黑封面(软件重开还在);别的天的不算。"""
    try:
        d = json.loads(_store_path().read_text("utf-8"))
    except (OSError, ValueError):
        return []
    return list(d.get("items") or []) if isinstance(d, dict) and d.get("day") == day else []
