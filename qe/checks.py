"""接口发之前,每条视频看三样(用户 2026-10-15 说的):
1. 是不是竖屏 —— 横的标出来,能一键转竖(vertical.py);
2. 标题里有没有别的平台的名字 —— 只标出来,用户自己改或删;
3. 话题是不是只有一个 —— 多的用 AI 挑一个留下(topic.py,和 ainame 一样)。
高级检查(用户 2026-10-16)再加:4. 有没有别的平台的水印 / 广告图标(watermark.py,结果记在 wmstore)。
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


def at_hits(title: str) -> list[str]:
    """标题里的「@某某 / @某平台」(用户 2026-10-18:删掉再发,见 titleclean)。"""
    from .titleclean import at_runs
    return at_runs(title)


def check_one(v, words=None, ffmpeg: str = "") -> dict:
    """填 v.checks:{"w","h","landscape","platform":[..],"tags":[..],"bad_read":bool},返回它。"""
    info = vertical.probe(v.path, ffmpeg)
    tags = topic.split_topics(v.title)["tags"]
    v.checks = {"w": info["w"], "h": info["h"], "dur": info["dur"], "landscape": vertical.is_landscape(info),
                "squarish": vertical.is_squarish(info),
                "bad_read": not info["w"], "platform": platform_hits(v.title, words), "tags": tags}
    return v.checks


def needs_vertical(c: dict) -> bool:
    """要转成标准竖屏的:横屏,或者竖着但偏方(3:4 / 正方形)。"""
    return bool((c or {}).get("landscape") or (c or {}).get("squarish"))


def problems(v) -> list[str]:
    """给界面看的:这条还有哪些问题(空 = 能发)。"""
    c = v.checks or {}
    out = []
    if c.get("bad_read"):
        out.append("视频读不出来")
    elif c.get("landscape"):
        out.append("横屏")
    elif c.get("squarish"):
        out.append("偏方要转竖屏")
    if c.get("platform"):
        out.append("标题有「" + "、".join(c["platform"]) + "」")
    from . import titleclean                         # 下面两样不放进 checks(缓存):改了标题马上重算
    junk = titleclean.dirty(v.title)
    if junk:
        out.append("标题有「" + "、".join(x[:12] for x in junk[:2]) + "」要删(点「整理标题」)")
    ad = titleclean.ad_problem(getattr(v, "account", ""), v.title)
    if ad:
        out.append(ad)
    if len(c.get("tags") or []) > 1:
        out.append(f"{len(c['tags'])} 个话题")
    elif topic.bad_format(v.title) and format_kind(v.title) != "结尾多了空格":   # 一个话题但写成「# 话题」「##话题」:平台可能不认成话题
        out.append(format_kind(v.title))             # 只是结尾多个空格:发的时候自己去掉,不算要处理(新员工试用 2026-10-21)
    from . import gamecheck                          # 标题像别的游戏的(用户 2026-10-20:和平精英传成了 PUBG)
    g = gamecheck.alien(getattr(v, "account", ""), v.title)
    if g:
        out.append(f"标题像是《{g}》的")
    if wm_blocks(c.get("wm")):                       # 高级检查查到水印、人还没说「没水印」
        out.append(wm_text(c["wm"]))
    if wm_blocks(c.get("ads")):                      # 查到口播广告、人还没说「不是广告」
        from .ads import label
        out.append(label(c["ads"]["hits"]))
    return out


def wm_blocks(wm) -> bool:
    return bool(wm and wm.get("hits") and not wm.get("ok"))


def wm_text(wm) -> str:
    """「B站水印(右上角)」这种;查水印的模块改了也不影响这里。"""
    try:
        from .watermark import label_of
        return label_of(wm) or "疑似水印"
    except Exception:
        return "疑似水印"


def format_kind(title: str) -> str:
    """写法问题分两种说(审查:只是结尾多个空格也叫「话题写法不对」,看着吓人):「结尾多了空格」/「话题写法不对」。"""
    t = topic.tidy(title)
    return "结尾多了空格" if t is not None and t == title.rstrip() else "话题写法不对"
