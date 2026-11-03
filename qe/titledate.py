"""标题里写了日期的(用户 2026-11-03:「标题里面明确了日期的,如果不是今天那就不能要这个视频」;
「将来的日期也不要,最多允许时效性落后一天」):日期只能是今天或昨天(北京时间),别的都不发。
视频一读进来就查(不用点「检查」)。认错了(「3号选手」这种)右键「日期没问题,能发」放行。

认的写法:11月27日 / 11月27号 / 27号 / 27日 / 11.27 / 11/27。只写「27号」没写月份的按几号比。
"""
import re
from datetime import datetime, timedelta

from .config import bj_now, data_dir
from .titleclean import AdOk

_CN = "零一二三四五六七八九十"
# 「号 / 日」后面跟着这些字的不是日期:「1号位」「3号选手」「7号球衣」「2号服」「3日游」「7日内」
_NOT_DATE = ("位", "选手", "球衣", "玩家", "种子", "机位", "楼", "线", "房", "桌", "队", "车", "门", "球员", "英雄", "角色",
             "技能", "地图", "服", "区", "游", "内", "后", "前", "连", "签", "店", "仓", "包", "窗", "口", "床", "键", "坑")
_MD = re.compile(r"(?<![0-9A-Za-z.])(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?")
_DOT = re.compile(r"(?<![0-9A-Za-z.:/vV])(\d{1,2})[./](\d{1,2})(?![0-9.%/倍版分级:])")
_DAY = re.compile(r"(?<![0-9A-Za-z.月第])(\d{1,2})\s*[日号]")


def dates_in(title: str) -> list[tuple[int | None, int, str]]:
    """标题里的日期:[(月 或 None, 日, 原文)]。"""
    s = str(title or "")
    out, used = [], []
    for m in _MD.finditer(s):
        mo, d = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            out.append((mo, d, m.group(0).strip()))
            used.append(m.span())
    for m in _DOT.finditer(s):
        mo, d = int(m.group(1)), int(m.group(2))
        if s[max(0, m.start() - 2):m.start()].rstrip().endswith(("版本", "版", "本", "第")):
            continue                                     # 「版本3.5」「第1.2期」不是日期
        if 1 <= mo <= 12 and 1 <= d <= 31 and not any(a <= m.start() < b for a, b in used):
            out.append((mo, d, m.group(0)))
            used.append(m.span())
    for m in _DAY.finditer(s):
        if any(a <= m.start() < b for a, b in used):
            continue
        d = int(m.group(1))
        rest = s[m.end():m.end() + 2]
        if 1 <= d <= 31 and not rest.startswith(_NOT_DATE):
            out.append((None, d, m.group(0).strip()))
    return out


def _ok_days(today=None) -> list:
    """今天、昨天(北京时间)。today 可以给 date / datetime(测试用)。"""
    t = today or bj_now()
    if isinstance(t, datetime):
        t = t.date()
    return [t, t - timedelta(days=1)]


def bad_dates(title: str, today=None) -> list[str]:
    """标题里不是今天 / 昨天的日期(原文)。"""
    ok = _ok_days(today)
    bad = []
    for mo, d, txt in dates_in(title):
        hit = any(x.day == d and (mo is None or x.month == mo) for x in ok)
        if not hit:
            bad.append(txt)
    return bad


def _store() -> AdOk:
    global _S
    p = str(data_dir() / "标题日期放行.json")
    if _S is None or _S.path != p:
        _S = AdOk(p)
    return _S


_S = None


def store() -> AdOk:
    """人右键「日期没问题,能发」的:号 + 标题。"""
    return _store()


def problem(account: str, title: str, today=None) -> str:
    """标题日期不是今天 / 昨天、人也没放行 → 一句话;否则 ""。"""
    bad = bad_dates(title, today)
    if not bad or store().ok(account, title):
        return ""
    return f"标题日期过期「{'、'.join(bad[:2])}」(只发今天 / 昨天的;不是日期就右键「日期没问题」)"
