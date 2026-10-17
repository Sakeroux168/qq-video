"""接口发的 16 个号(游戏 / 动漫)的素材在哪(2026-10-15 用户说的 + 实地看过):

    X:\\知乎视频\\游戏视频\\<游戏名>--<号的昵称>\\<日期文件夹>\\*.mp4
    X:\\知乎视频\\动漫视频\\<号的昵称>\\<日期文件夹>\\*.mp4

- 日期文件夹叫法很杂:「10.14（星期三）」「10.15」「10.15(20)」「10.15（20）」 —— 只认开头的「月.日」。
- 号的文件夹里还有「不能用」「脏话」「不行」「已发」「游戏资讯」「1」之类,一概不碰(不是日期开头的都不碰)。
- 「2电竞赛事（腾讯系相关游戏赛事）」= 电竞情报馆,视频直接放在最外面(没有日期文件夹)—— 用「给号选文件夹」(picked)。
- 发完挪到 X:\\知乎视频\\内容查看\\<月>月发布视频\\企鹅号\\企鹅号软件发布\\(平铺;用户 2026-10-15 定的,设置里能改)。
"""
import os
import re
from dataclasses import dataclass, field

# 只认「10.15」「10.15(20)」「10.15（20）」「10.14（星期三）」:日期后面只能跟空白或一对括号(2026-10-16 挖 bug:
# 原来只看开头,「10.15已发」「10.15不能用」「10.15 脏话」会被当成 10.15 的素材一起发)
DATE_RE = re.compile(r"^\s*(\d{1,2})\s*[.．]\s*(\d{1,2})(?![\d.．])\s*(?:[（(][^）)]*[）)])?\s*$")
VIDEO_EXTS = (".mp4", ".mov", ".m4v", ".avi", ".mkv", ".flv", ".wmv")

DEFAULT_ROOTS = [r"X:\知乎视频\游戏视频", r"X:\知乎视频\动漫视频"]
DEFAULT_ARCHIVE = r"X:\知乎视频\内容查看\{month}月发布视频\企鹅号\企鹅号软件发布"


@dataclass
class ApiVideo:
    path: str
    title: str                  # = 文件名(不带后缀),旧软件就是这么发的(标题、简介都用它)
    account: str                # 号的昵称
    date: str                   # 「10.15」
    folder: str                 # 日期文件夹
    checks: dict = field(default_factory=dict)   # 发前检查的结果(checks.py 填)


def natural_key(s: str):
    """按数字大小排:「第2条」在「第10条」前面(审查:原来按字排,第10 跑到第1 后面、第2 前面)。"""
    return [(0, int(t), "") if t.isdigit() else (1, 0, t.lower()) for t in re.split(r"(\d+)", str(s or "")) if t]


def date_key(name: str) -> str:
    """「10.14（星期三）」→「10.14」;不是日期开头的返回 ""。"""
    m = DATE_RE.match(name or "")
    return f"{int(m.group(1))}.{int(m.group(2))}" if m else ""


def nick_of_folder(name: str) -> str:
    """「CSGO--CSGO战神君」→「CSGO战神君」;「国漫解说馆z」→ 原样。"""
    return name.split("--")[-1].strip() if "--" in name else name.strip()


def account_folders(roots, known=None) -> dict[str, str]:
    """{号的昵称: 号的(第一个)文件夹}。要全部的用 account_folder_list。"""
    return {k: v[0] for k, v in account_folder_list(roots, known).items()}


def account_folder_list(roots, known=None) -> dict[str, list[str]]:
    """{号的昵称: [号的文件夹, …]}。根目录下名字带「--」的、或者下面有日期文件夹的,算一个号。
    known = 搬过来的号的昵称:给了就只认这些(「1疑似脏话」这种不是号的文件夹就不会混进来)。
    同一个号有两个文件夹(「CSGO--X」「CS2--X」/ 两个根目录各一个)都算,不悄悄丢一个。"""
    out: dict[str, list[str]] = {}
    for root in roots or []:
        try:
            names = sorted(os.listdir(root))
        except OSError:
            continue
        for n in names:
            p = os.path.join(root, n)
            if not os.path.isdir(p):
                continue
            nick = nick_of_folder(n)
            if known is not None:
                if nick in known:
                    out.setdefault(nick, []).append(p)
            elif "--" in n or any(date_key(x) for x in _subdirs(p)):
                out.setdefault(nick, []).append(p)
    return out


def _subdirs(p: str) -> list[str]:
    try:
        return [x for x in os.listdir(p) if os.path.isdir(os.path.join(p, x))]
    except OSError:
        return []


def dates(roots, known=None) -> list[str]:
    """所有号的日期文件夹合起来有哪些日子(按日子排)。"""
    ds = set()
    for folder in (f for fs in account_folder_list(roots, known).values() for f in fs):
        for x in _subdirs(folder):
            k = date_key(x)
            if k:
                ds.add(k)
    return sorted(ds, key=lambda d: tuple(int(x) for x in d.split(".")))


def videos(roots, date: str, known=None, picked=None) -> list[ApiVideo]:
    """这一天每个号要发的视频(号的文件夹下,日期开头是这一天的那些文件夹里的视频;不往更深里找)。
    picked = {号: 文件夹}:手动给号选了文件夹的(像旧软件的「选择」),这个号就只发那个文件夹里的,不自动找。"""
    picked = {k: v for k, v in (picked or {}).items() if v}
    out = []
    for nick, folders in account_folder_list(roots, known).items():
        if nick in picked:
            continue
        for folder in folders:
            for x in sorted(_subdirs(folder)):
                if date_key(x) == date:
                    out += _videos_in(os.path.join(folder, x), nick, date)
    for nick, d in picked.items():
        out += _videos_in(d, nick, date)
    return out


def _videos_in(d: str, nick: str, date: str) -> list[ApiVideo]:
    try:
        names = sorted(os.listdir(d), key=natural_key)
    except OSError:
        return []
    out = []
    for n in names:
        stem, ext = os.path.splitext(n)
        if ext.lower() in VIDEO_EXTS and not n.startswith("_处理中_") and os.path.isfile(os.path.join(d, n)):
            out.append(ApiVideo(path=os.path.join(d, n), title=stem, account=nick, date=date, folder=d))
    return out


def pub_day() -> str:
    """今天(北京时间)= 发出去的那天,「10.17」这样。"""
    from .config import bj_now
    n = bj_now()
    return f"{n.month}.{n.day}"


def archive_dir(st, date: str = "", acc: dict | None = None) -> str:
    """发完挪到哪:企鹅号软件发布 / 发出去的日期(北京时间,用户 2026-10-17:「…/企鹅号软件发布/日期/各个账号/视频和封面」)
    / 游戏名(设置里勾了「按游戏分子文件夹」,默认勾)。{month} 也按发出去的那天算。
    date = 按哪天算(不给就是今天);设置里自己写了 {date} 的,就不再多加一层日期。"""
    day = date or pub_day()
    month = day.split(".")[0] if day else "?"
    tpl = str(st.get("api_archive") or DEFAULT_ARCHIVE)
    d = tpl.replace("{month}", month).replace("{date}", day)
    if "{date}" not in tpl:
        d = os.path.join(d, day)
    if acc is not None and st.get("api_archive_by_game", True):
        d = os.path.join(d, game_folder(acc))
    return d


def game_folder(acc: dict) -> str:
    """号的游戏名文件夹 = 旧软件「账号」那一栏(CSGO / DNF / 光与夜之恋 / 暗区突围 …,
    和用户在「企鹅号软件发布」下面自己建的子文件夹一样,2026-10-15 对过)。"""
    name = str(acc.get("source_name") or acc.get("nick") or "其它").strip()
    return re.sub(r'[<>:"/\\|?*]', "", name) or "其它"


def move_published(path: str, dest_dir: str) -> str:
    """发完把视频挪到「X月发布视频 / 企鹅号 / 企鹅号软件发布 / 日期 / 游戏名」,同名封面跟着挪(用户 2026-10-17:「视频和封面」)。
    重名加 (2)(封面跟视频用同一个新名字)。返回视频的新位置。
    走 fsops.safe_move_file:被占着就报错留在原处,不会原处和归档各一份;封面挪不动不算失败(视频已经挪了)。"""
    from .apicover import find
    from .fsops import safe_move_file, unique
    os.makedirs(dest_dir, exist_ok=True)
    cover = find(path)
    new = safe_move_file(path, unique(os.path.join(dest_dir, os.path.basename(path))))
    if cover:
        stem = os.path.splitext(os.path.basename(new))[0]
        try:
            safe_move_file(cover, unique(os.path.join(dest_dir, stem + os.path.splitext(cover)[1])))
        except Exception:
            pass
    return new