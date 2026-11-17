"""问哪个 AI(用户 2026-11-09:百炼欠费了,「试试我自己部署的模型」—— 地址 / 模型 / Key 自己填)。

设置里「自己的模型」三项都填了:
  · 只用文字的活(处理重名改标题、串游戏判断、挑话题)改用它;
  · 要看图的活(AI 看封面、字幕被裁)要它认得图才用 —— 点「试一下」认图对了才记 own_ai_vision = "地址|模型",
    之后改了地址 / 模型就不算了,要再试一下。认不得图的照旧用阿里百炼。
没填 / 没填全:照旧全用阿里百炼。出错照实说是哪边的错,不偷偷换回百炼。
"""
from typing import NamedTuple

DASH = "https://dashscope.aliyuncs.com/compatible-mode/v1"
TEXT_MODEL = "qwen-plus"
VISION_MODEL = "qwen3-vl-plus"


class AI(NamedTuple):
    base: str                 # …/v1(OpenAI 兼容)
    key: str
    model: str
    own: bool = False         # 是用户自己部署的

    @property
    def who(self) -> str:
        return "你自己的模型" if self.own else "阿里百炼"

    def url(self) -> str:
        return self.base.rstrip("/") + "/chat/completions"

    def extra(self) -> dict:
        """百炼的千问要关掉「先想一想」(慢、费钱);别家不认这个参数就不给。"""
        return {"enable_thinking": False} if "dashscope" in self.base else {}


def clean(raw) -> str:
    """有的模型(DeepSeek 这类会先想一想的)把想的过程放在 <think>…</think> 里:去掉,只留回答。"""
    import re
    return re.sub(r"<think>.*?</think>", "", str(raw or ""), flags=re.S).strip()


def tokens(ai: AI, n: int) -> int:
    """自己的模型可能先想一想再回答:给多点字数,免得想到一半就断了。"""
    return max(n, 1500) if ai.own else n


def as_ai(key, model: str, base: str = DASH) -> AI:
    """老的调用传的是 Key 字符串(测试里也是):当成百炼;传 AI 就用它。"""
    if isinstance(key, AI):
        return key
    return AI(base, str(key or ""), model)


def own(st) -> AI | None:
    url, model, key = (str(st.get(k) or "").strip() for k in ("own_ai_url", "own_ai_model", "own_ai_key"))
    return AI(url, key, model, True) if url and model and key else None


def sig(url: str, model: str) -> str:
    return f"{url.strip()}|{model.strip()}"


def text(st, model: str = TEXT_MODEL) -> AI:
    return own(st) or AI(DASH, st.ai_key() if hasattr(st, "ai_key") else "", model)


def vision(st, model: str = VISION_MODEL) -> AI:
    o = own(st)
    if o and st.get("own_ai_vision") == sig(o.base, o.model):
        return o
    return AI(DASH, st.ai_key() if hasattr(st, "ai_key") else "", model)


def _post(ai: AI, content, max_tokens: int = 300, timeout: int = 60) -> str:
    import requests
    from .aierr import why
    body = {"model": ai.model, "temperature": 0, "max_tokens": tokens(ai, max_tokens), "messages": [{"role": "user", "content": content}], **ai.extra()}
    try:
        r = requests.post(ai.url(), json=body, headers={"Authorization": f"Bearer {ai.key}", "Content-Type": "application/json"}, timeout=timeout)
    except UnicodeError:
        raise RuntimeError(f"{ai.who}的 Key 里有中文 / 全角字符,看看是不是复制错了")
    except (requests.RequestException, ValueError) as e:
        raise RuntimeError(f"连不上{ai.who}(地址对吗?服务开着吗?{type(e).__name__})")
    try:
        return clean(r.json()["choices"][0]["message"]["content"])
    except Exception:
        raise RuntimeError(why(r, ai.who) or f"{ai.who}没回话(HTTP {r.status_code}){r.text[:120]}")


def probe(ai: AI, post=None) -> dict:
    """「试一下」:问一句话、给一张红圆圈的图。{"text": (能用, 说明), "image": (认得图, 说明)}。post:测试里换掉。"""
    import base64
    import io
    from PIL import Image, ImageDraw
    post = post or _post
    out = {}
    try:
        a = post(ai, "只回一个字:好", 200, 60).strip()
        out["text"] = (bool(a), f"回了「{a[:20]}」" if a else "回了空话(可能是只想不答的模型,max_tokens 不够)")
    except Exception as e:                                # 什么错都要回话(「试一下」不能一直转圈)
        out["text"] = (False, str(e))
    if not out["text"][0]:
        out["image"] = (False, "没试(先让文字那条能用)")
        return out
    im = Image.new("RGB", (256, 256), "white")
    ImageDraw.Draw(im).ellipse((48, 48, 208, 208), fill=(220, 20, 20))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    pic = [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")}},
           {"type": "text", "text": "图里画的是什么颜色的什么形状?十个字以内回答。"}]
    try:
        a = post(ai, pic, 200, 90).strip()
        hit = "红" in a and ("圆" in a or "球" in a)
        out["image"] = (hit, f"认对了(「{a[:20]}」)" if hit else f"没认对,当它不认图(回的是「{a[:20]}」)")
    except Exception as e:
        out["image"] = (False, f"不认图({str(e)[:60]})")
    return out
