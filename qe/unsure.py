"""「结果不明」的软件自己去企鹅号查(用户 2026-10-26:「既然都能核对了,那能不能直接自查看有没有发呢」,选了 B):
- 查到了(按视频编号,找不到再按标题 + 时间)→ 记成已发(发布时间、文章编号用企鹅号上的);
- 查不到、发出去已经 15 分钟了 → 不自动改(怕企鹅号慢,改了会重发一条),只提示「后台没找到,多半没发上」,人双击确认。
只读:/article/clientlist。不发、不删。
"""
import re
from datetime import datetime, timedelta

WAIT_MIN = 15                                    # 发出去过了这么久后台还没有 → 多半没发上(只提示)
MISSING_NOTE = "(软件去企鹅号查过:后台一直没有这条,多半没发上)"


def _vid(note: str) -> str:
    m = re.search(r"vid=(\w+)", note or "")
    return m.group(1) if m else ""


def _key(t: str) -> str:
    from .folders import norm_name
    return norm_name(t)


def _t(s: str) -> datetime | None:
    try:
        return datetime.strptime(str(s)[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def elapsed_min(row: dict, now: datetime) -> float:
    """这条开始发到现在几分钟了(北京时间,不带时区的比)。"""
    t0 = _t(row.get("prepared_at") or row.get("published_at") or "")
    return (now - t0).total_seconds() / 60 if t0 else 0.0


def find(cl, row: dict, max_pages: int = 30) -> dict | None:
    """企鹅号上找这条:视频编号一样的,或者标题一样、发布时间不早于开始发前 10 分钟的。新的在前,翻到比这条早一天的就停。"""
    vid, k = _vid(row.get("note")), _key(row.get("title") or "")
    t0 = _t(row.get("prepared_at") or "")
    lo = (t0 - timedelta(minutes=10)) if t0 else None
    stop = (t0 - timedelta(days=1)) if t0 else None
    for page in range(1, max_pages + 1):
        arts = cl.list_articles(page, 10).get("articles") or []
        if not arts:
            return None
        older = 0
        for a in arts:
            v = str((a.get("article_video_info") or {}).get("vid") or "")
            pt = _t(a.get("article_pub_time") or "")
            if vid and v == vid:
                return a
            if k and _key(a.get("article_title") or "") == k and (lo is None or pt is None or pt >= lo):
                return a
            if stop and pt and pt < stop:
                older += 1
        if older == len(arts):
            return None
    return None
