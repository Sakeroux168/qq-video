"""每天规定发多少、实际发了多少(用户 2026-10-16 给的表)。

- 「实际」按**哪天发出去的**算(发布时间的北京日期),不看素材文件夹的日期(那是找视频的人建的,算他的绩效)。
- 教育:用户 2026-10-19 定了 —— 家长小天地每天 54 条,家长研习空间每天 102 条(原来没定,只看两个号合起来够不够 106)。
- 每日记录的格式照用户在企业微信表「彭超」页记的(图二):日期 / 工作内容 / 品类 / 规定视频条数 / 实际发布视频条数。
  先用「复制」贴过去;以后管理员开了企业微信文档接口再改成自动写。
"""
from .config import bj_now

DEFAULT_PLAN = [
    {"cat": "游戏", "label": "游戏总发布量", "accounts": {
        "PUBG突围君": 20, "和平精英上分君": 80, "CSGO战神君": 20, "DNF连招档案馆": 10, "QQ飞车漂移课堂": 10,
        "LOLM峡谷日常": 20, "LOL玩家聚集地": 20, "三角洲密探君": 70, "云顶上分情报局": 10, "暗区突围情报局": 20,
        "光与夜心动剧场": 20, "电竞情报馆": 80}},
    {"cat": "教育", "label": "教育总发布量", "accounts": {"家长研习空间": 102, "家长小天地": 54}},
    {"cat": "动漫", "label": "动漫总发布量", "accounts": {
        "国漫趣谈": 50, "国漫解说馆z": 50, "日漫漫谈社": 50, "日漫解说馆": 50}},
]
WORK = "发布企鹅号视频"


def plan(st) -> list[dict]:
    p = st.get("daily_plan") if hasattr(st, "get") else None
    return p if isinstance(p, list) and p else DEFAULT_PLAN


def quota_of(st, nick: str) -> int:
    """这个号每天规定几条;没规定返回 0。"""
    for g in plan(st):
        if nick in (g.get("accounts") or {}):
            try:
                return int(g["accounts"][nick] or 0)
            except (TypeError, ValueError):
                return 0
    return 0


def cat_total(g: dict) -> int:
    if g.get("total") is not None:
        try:
            return int(g["total"])
        except (TypeError, ValueError):
            pass
    return sum(int(x or 0) for x in (g.get("accounts") or {}).values())


def today() -> str:
    return bj_now().strftime("%Y-%m-%d")


def tomorrow_folder() -> str:
    """明天的日期文件夹名(北京时间),如 10.21:发够规定条数以后多的视频挪进去。"""
    from datetime import timedelta
    t = bj_now() + timedelta(days=1)
    return f"{t.month}.{t.day}"


def left_today(rec, st, nick: str, day: str = "", sent: dict | None = None) -> int | None:
    """这个号这天(默认今天,北京时间)还能发几条 = 规定条数 - 已经发出去的。没规定条数 / 开了闸 = None(不限)。
    用户 2026-10-20:不能发多、也不能发少;开闸(设置里「允许超过每天规定条数」)才能多发。"""
    if st.get("quota_open", False):
        return None
    q = quota_of(st, nick)
    if not q:
        return None
    got = (sent if sent is not None else rec.sent_on(day or today())).get(nick, 0)
    return max(0, q - got)


def move_noclobber(path: str, dst_dir: str) -> str:
    """挪到 dst_dir(没有就建),同名的不盖:后面加 (2)。返回新位置。"""
    import os
    import shutil
    os.makedirs(dst_dir, exist_ok=True)
    stem, ext = os.path.splitext(os.path.basename(path))
    dst = os.path.join(dst_dir, stem + ext)
    k = 2
    while os.path.exists(dst):
        dst = os.path.join(dst_dir, f"{stem} ({k}){ext}")
        k += 1
    shutil.move(path, dst)
    return dst


def day_counts(rec, day: str) -> dict[str, int]:
    """这天(发布时间的北京日期,如 2026-10-16)每个号实际发了几条(同一个视频只算一次)。"""
    return rec.sent_on(day)


def summary(rec, st, day: str) -> dict:
    """{"day", "rows": [(品类标签, 规定, 实际)], "total": (规定, 实际), "accounts": [(品类, 号, 规定, 实际)]}。"""
    got = day_counts(rec, day)
    rows, accs = [], []
    tq = ta = 0
    for g in plan(st):
        q = cat_total(g)
        a = sum(got.get(n, 0) for n in (g.get("accounts") or {}))
        rows.append((g.get("label") or g["cat"], q, a))
        tq += q
        ta += a
        for n, nq in (g.get("accounts") or {}).items():
            accs.append((g["cat"], n, int(nq or 0), got.get(n, 0)))
    return {"day": day, "rows": rows, "total": (tq, ta), "accounts": accs}


def short_day(day: str) -> str:
    """2026-10-16 → 10月16日(和用户表里一样)。"""
    try:
        _y, m, d = day.split("-")
        return f"{int(m)}月{int(d)}日"
    except ValueError:
        return day


def as_tsv(s: dict) -> str:
    """复制到企业微信表的文字:一行一格用 Tab 隔开,贴进去正好占 日期 / 工作内容 / 品类 / 规定 / 实际 五列。"""
    lines = []
    for k, (lab, q, a) in enumerate(s["rows"]):
        lines.append("\t".join([short_day(s["day"]) if k == 0 else "", WORK if k == 0 else "", lab, str(q), str(a)]))
    tq, ta = s["total"]
    lines.append("\t".join(["", "", "总发布量", str(tq), str(ta)]))
    return "\n".join(lines)


def short_list(s: dict) -> list[tuple[str, int, int]]:
    """今天还没到规定条数的号:[(号, 规定, 实际)],差得多的排前面。没规定条数的号不算。"""
    out = [(n, q, a) for _c, n, q, a in s["accounts"] if q and a < q]
    return sorted(out, key=lambda x: x[2] - x[1])
