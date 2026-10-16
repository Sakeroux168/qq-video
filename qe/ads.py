"""查口播广告(用户 2026-10-16 同意从百家号那边搬):语音转成文字(qe/asr.py),找广告词,标出第几秒说了哪句。

广告词库在设置里(ad_keywords,逗号 / 顿号 / 空格隔开都行),默认是百家号那边用的一套,加上企鹅号这边常见的
(得物、转转这类 App 广告)。剧情 / 解说里也常说的词(福利、链接、限时 …)单独出现只算「可能」,
同一句里有两个以上广告词、或者有「扫码 / 点击下方 / 小黄车 / 得物」这种一看就是广告的,才算「很像广告」。
"""
import re

DEFAULT_KEYWORDS = ("点击下方,下方链接,小黄车,购物车,评论区,私信,优惠,折扣,领取,加微信,微信号,关注我,进群,链接,下单,"
                    "拼多多,淘宝,京东,抖音小店,福利,免费领,限时,得物,转转,闲鱼,下载,扫码,二维码,优惠券,小程序,应用商店,"
                    "搜索,官方旗舰店,赞助,本期视频由,点击链接,同款")
STRONG = {"点击下方", "下方链接", "小黄车", "购物车", "加微信", "微信号", "进群", "下单", "抖音小店", "免费领", "得物", "转转",
          "闲鱼", "扫码", "二维码", "优惠券", "小程序", "应用商店", "官方旗舰店", "赞助", "本期视频由", "点击链接"}


def split_keywords(s) -> list[str]:
    if isinstance(s, (list, tuple)):
        s = ",".join(str(x) for x in s)
    out = []
    for k in re.split(r"[,，;；、\s]+", str(s or "")):
        k = k.strip()
        if k and k not in out:
            out.append(k)
    return out


def scan(sents: list[dict], keywords: list[str]) -> list[dict]:
    """[{"start","end","text","keywords","strong"}]:strong = 很像广告(有一看就是广告的词,或者一句里两个以上广告词)。"""
    hits = []
    for s in sents or []:
        text = str(s.get("text") or "")
        found = [k for k in keywords if k and k in text]
        if found:
            strong = len(found) >= 2 or any(k in STRONG for k in found)
            hits.append({"start": s.get("start", 0), "end": s.get("end", 0), "text": text, "keywords": found,
                         "strong": strong})
    return hits


def summary(hits: list[dict]) -> str:
    """给人看:「口播广告 2 处(0:41「点击下方链接领取…」)」。"""
    strong = [h for h in hits if h.get("strong")]
    if not strong:
        return ""
    h = strong[0]
    sec = int(h["start"])
    return f"口播广告 {len(strong)} 处({sec // 60}:{sec % 60:02d}「{h['text'][:14]}」)"


def groups(sents: list[dict], keywords: list[str], gap: float = 1.5) -> list[dict]:
    """要剪 / 要拦的广告段:挨着的广告句(间隔不到 gap 秒)连成一段,段里至少有一句「很像广告」才算。
    返回 [{"start","end","text","keywords"}](剪的时候前后再各留一点)。"""
    hits = scan(sents, keywords)
    out, cur = [], None
    for h in hits:
        if cur and h["start"] - cur["end"] <= gap:
            cur["end"] = max(cur["end"], h["end"])
            cur["text"] += h["text"]
            cur["keywords"] += [k for k in h["keywords"] if k not in cur["keywords"]]
            cur["strong"] = cur["strong"] or h["strong"]
        else:
            if cur:
                out.append(cur)
            cur = dict(h, keywords=list(h["keywords"]))
    if cur:
        out.append(cur)
    return [{"start": g["start"], "end": g["end"], "text": g["text"], "keywords": g["keywords"]} for g in out if g["strong"]]


def label(hits: list[dict]) -> str:
    """「口播广告 2 处(0:41「点击下方链接领取…」)」"""
    if not hits:
        return ""
    sec = int(hits[0]["start"])
    return f"口播广告 {len(hits)} 处({sec // 60}:{sec % 60:02d}「{hits[0]['text'][:12]}」)"
