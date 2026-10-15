"""接口发之前,每条视频看三样(用户 2026-10-15 说的):
1. 是不是竖屏 —— 横的标出来,能一键转竖(vertical.py);
2. 标题里有没有别的平台的名字 —— 只标出来,用户自己改或删;
3. 话题是不是只有一个 —— 多的用 AI 挑一个留下(topic.py,和 ainame 一样)。
"""
from . import topic, vertical

# 别的平台的名字(设置里能改:api_platform_words)。企鹅号是腾讯的,「腾讯视频」「QQ」不算。
PLATFORM_WORDS = ["抖音", "抖音号", "快手", "小红书", "B站", "b站", "哔哩哔哩", "bilibili", "西瓜视频", "今日头条",
                  "头条号", "百家号", "好看视频", "视频号", "微信视频号", "知乎", "微博", "虎牙", "斗鱼", "微视",
                  "火山小视频", "皮皮虾", "爱奇艺", "优酷", "芒果TV", "YouTube", "youtube", "TikTok", "tiktok",
                  "douyin", "kuaishou", "dy", "ks"]
# 太短的英文缩写只在单独出现时才算(「dy」「ks」不能把「body」「books」也算进去)
_SHORT = {"dy", "ks"}


def platform_hits(title: str, words=None) -> list[str]:
    import re
    t = str(title or "")
    low = t.lower()
    hits = []
    for w in words or PLATFORM_WORDS:
        w = str(w).strip()
        if not w:
            continue
        if w.lower() in _SHORT:
            ok = re.search(rf"(?<![a-z]){re.escape(w.lower())}(?![a-z])", low) is not None
        else:
            ok = w.lower() in low
        if ok and not any(w.lower() in h.lower() for h in hits):
            hits = [h for h in hits if h.lower() not in w.lower()] + [w]
    return hits


def check_one(v, words=None, ffmpeg: str = "") -> dict:
    """填 v.checks:{"w","h","landscape","platform":[..],"tags":[..],"bad_read":bool},返回它。"""
    info = vertical.probe(v.path, ffmpeg)
    tags = topic.split_topics(v.title)["tags"]
    v.checks = {"w": info["w"], "h": info["h"], "dur": info["dur"], "landscape": vertical.is_landscape(info),
                "bad_read": not info["w"], "platform": platform_hits(v.title, words), "tags": tags}
    return v.checks


def problems(v) -> list[str]:
    """给界面看的:这条还有哪些问题(空 = 能发)。"""
    c = v.checks or {}
    out = []
    if c.get("bad_read"):
        out.append("视频读不出来")
    elif c.get("landscape"):
        out.append("横屏")
    if c.get("platform"):
        out.append("标题有「" + "、".join(c["platform"]) + "」")
    if len(c.get("tags") or []) > 1:
        out.append(f"{len(c['tags'])} 个话题")
    return out
