"""素材文件夹:X:\\知乎视频\\小学生教育\\<日期>\\<号的缩写>\\<员工>\\ 里每条 同名 .mp4 + .png(无字封面,用这个)+ .jpg(原封面,带字,不能用)。

发完一整天:把 <日期> 文件夹剪切到 X:\\知乎视频\\内容查看\\<月>月发布视频\\企鹅号\\教育\\ 下面。
"""
import os
import re
import shutil
from dataclasses import dataclass, field

VIDEO_EXTS = (".mp4", ".mov", ".m4v", ".avi", ".mkv", ".flv", ".wmv")
_DATE_RE = re.compile(r"^(\d{1,2})[.\-_月](\d{1,2})日?$")


@dataclass
class Video:
    path: str                  # 视频文件
    title: str                 # 发出去的标题 = 文件名(不带后缀),企鹅号自己也是这么填的
    account: str               # 发到哪个号
    employee: str              # 哪个员工整理的(员工文件夹名)
    date: str                  # 日期文件夹名,如 10.15
    png: str = ""              # 无字封面(用这个)
    vpng: str = ""             # 无字竖封面(员工「梁」的 竖屏9x16.png;有的话将来可以给竖的比例用)
    jpg: str = ""              # 原封面(带字,不用;只是认出来提醒)
    cover: str = ""            # 这次用哪张(cover.decide 填)
    cover_kind: str = ""       # 横 / 竖
    cover_why: str = ""        # 为什么这么选(给人看)
    plan: dict = field(default_factory=dict)   # 裁剪要对准哪(cover.decide 填)
    vcover: str = ""           # 竖的比例(3:4、9:16)改用这张竖图(几个人分得开、横图裁会切掉人时,用无字的 竖屏9x16.png)
    vplan: dict = field(default_factory=dict)  # 竖图上的裁剪对准哪
    warn: bool = False         # 要人看一眼(没认出人 / 缺封面)


def list_dates(root: str) -> list[str]:
    """素材根目录下的日期文件夹(按日期排,新的在后)。"""
    try:
        names = [n for n in os.listdir(root) if os.path.isdir(os.path.join(root, n))]
    except OSError:
        return []

    def key(n):
        m = _DATE_RE.match(n.strip())
        return (0, int(m.group(1)), int(m.group(2))) if m else (1, 0, 0)
    return sorted(names, key=lambda n: (key(n), n))


def month_of(date: str) -> str:
    m = _DATE_RE.match(date.strip())
    return str(int(m.group(1))) if m else ""


def account_dirs(root: str, date: str, st) -> dict[str, list[str]]:
    """这一天每个号对应的缩写文件夹(可能有好几个)。认不出的缩写不要。"""
    base = os.path.join(root, date)
    try:
        subs = [n for n in os.listdir(base) if os.path.isdir(os.path.join(base, n))]
    except OSError:
        return {}
    out: dict[str, list[str]] = {}
    for name in st.account_names():
        als = st.aliases_of(name)
        out[name] = [os.path.join(base, s) for s in sorted(subs) if s.strip() in als]
    return out


def unknown_dirs(root: str, date: str, st) -> list[str]:
    """这一天里不认识的缩写文件夹(提醒去设置里加)。"""
    base = os.path.join(root, date)
    try:
        subs = [n for n in os.listdir(base) if os.path.isdir(os.path.join(base, n))]
    except OSError:
        return []
    known = {a for n in st.account_names() for a in st.aliases_of(n)}
    return [s for s in sorted(subs) if s.strip() not in known]


def employees(account_dir: str) -> list[str]:
    try:
        return sorted(n for n in os.listdir(account_dir) if os.path.isdir(os.path.join(account_dir, n)))
    except OSError:
        return []


COVER_DIR = "封面"


def norm_name(s: str) -> str:
    """对名字用:去掉空格、下划线、标点(「C 位」和「C_位」、全角半角冒号算一样)。"""
    return re.sub(r"[\W_]+", "", s or "").lower()


def _landscape(path: str) -> bool:
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size[0] >= im.size[1]
    except Exception:
        return False


def covers_from_dir(d: str) -> tuple[str, str]:
    """员工「梁」的放法:<员工>/封面/<视频标题>/ 里 横屏16x9.png / 竖屏9x16.png / 修改 (1).png 是他改过的无字版,
    原图.png 带字不要,_thumb.jpg 是缩略图不要。返回 (横的, 竖的),没有的给 ""。"""
    try:
        files = sorted(os.listdir(d))
    except OSError:
        return "", ""
    imgs = [f for f in files if os.path.splitext(f)[1].lower() in (".png", ".jpg", ".jpeg", ".webp")
            and not f.startswith("原图") and not f.startswith("_thumb")]
    h = next((f for f in imgs if f.startswith("横屏")), "")
    v = next((f for f in imgs if f.startswith("竖屏")), "")
    if not h:                                   # 没有「横屏」:「修改 (1).png」这类,横的那张
        h = next((f for f in imgs if f != v and _landscape(os.path.join(d, f))), "")
    return (os.path.join(d, h) if h else ""), (os.path.join(d, v) if v else "")


def videos_in(emp_dir: str, account: str, date: str) -> list[Video]:
    """员工文件夹里的视频,带上无字封面。按文件名排。封面两种放法:
    ① 视频旁边同名的 .png(.jpg 是带字的原封面,不用);
    ② <员工>/封面/<视频标题>/横屏16x9.png 等(员工「梁」,标题里空格 / 下划线 / 标点对不齐也认)。"""
    try:
        names = sorted(os.listdir(emp_dir))
    except OSError:
        return []
    by_stem: dict[str, dict] = {}
    for n in names:
        stem, ext = os.path.splitext(n)
        by_stem.setdefault(stem, {})[ext.lower()] = os.path.join(emp_dir, n)
    cdir = os.path.join(emp_dir, COVER_DIR)
    sub = {}
    if os.path.isdir(cdir):
        try:
            sub = {norm_name(d): os.path.join(cdir, d) for d in os.listdir(cdir) if os.path.isdir(os.path.join(cdir, d))}
        except OSError:
            sub = {}
    out = []
    emp = os.path.basename(emp_dir.rstrip("\\/"))
    for stem in sorted(by_stem):
        d = by_stem[stem]
        vid = next((d[e] for e in VIDEO_EXTS if e in d), "")
        if not vid:
            continue
        png, vpng = d.get(".png", ""), ""
        if norm_name(stem) in sub:
            h, vv = covers_from_dir(sub[norm_name(stem)])
            png, vpng = h or png, vv
        v = Video(path=vid, title=stem.strip(), account=account, employee=emp, date=date,
                  png=png, jpg=d.get(".jpg", "") or d.get(".jpeg", ""))
        v.vpng = vpng
        out.append(v)
    return out


def archive_target(st, date: str) -> str:
    root = str(st.get("archive_root") or "").replace("{month}", month_of(date) or "?")
    return os.path.join(root, date)


def move_date(st, date: str, merge: bool = False) -> str:
    """把整个日期文件夹剪切到归档那里。目标已经有同名文件夹:merge=False 抛 FileExistsError(界面上问人);
    merge=True 把里面的东西挪进去(同名文件不覆盖,改名加 (2))。返回目标路径。"""
    src = os.path.join(st["material_root"], date)
    dst = archive_target(st, date)
    if not os.path.isdir(src):
        raise FileNotFoundError(src)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if not os.path.exists(dst):
        shutil.move(src, dst)
        return dst
    if not merge:
        raise FileExistsError(dst)
    _merge(src, dst)
    try:
        shutil.rmtree(src) if not _has_files(src) else None
    except OSError:
        pass
    return dst


def _has_files(d: str) -> bool:
    return any(files for _r, _d, files in os.walk(d))


def _merge(src: str, dst: str):
    os.makedirs(dst, exist_ok=True)
    for n in os.listdir(src):
        s, t = os.path.join(src, n), os.path.join(dst, n)
        if os.path.isdir(s):
            _merge(s, t)
            continue
        if os.path.exists(t):
            stem, ext = os.path.splitext(n)
            k = 2
            while os.path.exists(t):
                t = os.path.join(dst, f"{stem} ({k}){ext}")
                k += 1
        shutil.move(s, t)
