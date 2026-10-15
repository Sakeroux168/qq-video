"""接口发的 16 个号(游戏 / 动漫)的素材在哪(2026-10-15 用户说的 + 实地看过):

    X:\\知乎视频\\游戏视频\\<游戏名>--<号的昵称>\\<日期文件夹>\\*.mp4
    X:\\知乎视频\\动漫视频\\<号的昵称>\\<日期文件夹>\\*.mp4

- 日期文件夹叫法很杂:「10.14（星期三）」「10.15」「10.15(20)」「10.15（20）」 —— 只认开头的「月.日」。
- 号的文件夹里还有「不能用」「脏话」「不行」「已发」「游戏资讯」「1」之类,一概不碰(不是日期开头的都不碰)。
- 「2电竞赛事（腾讯系相关游戏赛事）」= 电竞情报馆,视频直接放在最外面(没有日期文件夹)—— 先不管,等用户说。
- 发完挪到 X:\\知乎视频\\内容查看\\<月>月发布视频\\企鹅号\\<月.日>已发布\\(平铺,照搬旧软件「企鹅号批量发布」的设置)。
"""
import os
import re
from dataclasses import dataclass, field

DATE_RE = re.compile(r"^\s*(\d{1,2})\s*[.．]\s*(\d{1,2})")
VIDEO_EXTS = (".mp4", ".mov", ".m4v", ".avi", ".mkv", ".flv", ".wmv")

DEFAULT_ROOTS = [r"X:\知乎视频\游戏视频", r"X:\知乎视频\动漫视频"]
DEFAULT_ARCHIVE = r"X:\知乎视频\内容查看\{month}月发布视频\企鹅号\{date}已发布"


@dataclass
class ApiVideo:
    path: str
    title: str                  # = 文件名(不带后缀),旧软件就是这么发的(标题、简介都用它)
    account: str                # 号的昵称
    date: str                   # 「10.15」
    folder: str                 # 日期文件夹
    checks: dict = field(default_factory=dict)   # 发前检查的结果(checks.py 填)


def date_key(name: str) -> str:
    """「10.14（星期三）」→「10.14」;不是日期开头的返回 ""。"""
    m = DATE_RE.match(name or "")
    return f"{int(m.group(1))}.{int(m.group(2))}" if m else ""


def nick_of_folder(name: str) -> str:
    """「CSGO--CSGO战神君」→「CSGO战神君」;「国漫解说馆z」→ 原样。"""
    return name.split("--")[-1].strip() if "--" in name else name.strip()


def account_folders(roots, known=None) -> dict[str, str]:
    """{号的昵称: 号的文件夹}。根目录下名字带「--」的、或者下面有日期文件夹的,算一个号。
    known = 搬过来的号的昵称:给了就只认这些(「1疑似脏话」这种不是号的文件夹就不会混进来)。"""
    out = {}
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
                    out[nick] = p
            elif "--" in n or any(date_key(x) for x in _subdirs(p)):
                out[nick] = p
    return out


def _subdirs(p: str) -> list[str]:
    try:
        return [x for x in os.listdir(p) if os.path.isdir(os.path.join(p, x))]
    except OSError:
        return []


def dates(roots, known=None) -> list[str]:
    """所有号的日期文件夹合起来有哪些日子(按日子排)。"""
    ds = set()
    for folder in account_folders(roots, known).values():
        for x in _subdirs(folder):
            k = date_key(x)
            if k:
                ds.add(k)
    return sorted(ds, key=lambda d: tuple(int(x) for x in d.split(".")))


def videos(roots, date: str, known=None) -> list[ApiVideo]:
    """这一天每个号要发的视频(号的文件夹下,日期开头是这一天的那些文件夹里的视频;不往更深里找)。"""
    out = []
    for nick, folder in account_folders(roots, known).items():
        for x in sorted(_subdirs(folder)):
            if date_key(x) != date:
                continue
            d = os.path.join(folder, x)
            try:
                names = sorted(os.listdir(d))
            except OSError:
                continue
            for n in names:
                stem, ext = os.path.splitext(n)
                if ext.lower() in VIDEO_EXTS and not n.startswith("_处理中_"):
                    out.append(ApiVideo(path=os.path.join(d, n), title=stem, account=nick, date=date, folder=d))
    return out


def archive_dir(st, date: str) -> str:
    month = date.split(".")[0] if date else "?"
    return str(st.get("api_archive") or DEFAULT_ARCHIVE).replace("{month}", month).replace("{date}", date)


def move_published(path: str, dest_dir: str) -> str:
    """发完把视频挪到「X月发布视频 / 企鹅号 / X.X已发布」(平铺,和旧软件一样只挪视频)。重名加 (2)。返回新位置。"""
    import shutil
    os.makedirs(dest_dir, exist_ok=True)
    stem, ext = os.path.splitext(os.path.basename(path))
    dst = os.path.join(dest_dir, stem + ext)
    k = 2
    while os.path.exists(dst):
        dst = os.path.join(dest_dir, f"{stem} ({k}){ext}")
        k += 1
    shutil.move(path, dst)
    return dst
