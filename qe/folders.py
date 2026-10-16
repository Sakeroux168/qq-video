"""素材文件夹:X:\\知乎视频\\小学生教育\\<日期>\\<号的缩写>\\<员工>\\ 里每条 同名 .mp4 + .png(无字封面,用这个)+ .jpg(原封面,带字,不能用)。
实际每个人放法都不一样 → 界面用 scan_account():号文件夹整个翻一遍,按名字配封面(见下面)。

发完一整天:把 <日期> 文件夹剪切到 X:\\知乎视频\\内容查看\\<月>月发布视频\\企鹅号\\教育\\ 下面。
"""
import os
import re
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


# ---------------- 不管怎么放都认(用户 2026-10-16:「跟他们沟通不了的」)----------------
# 每个人放法不一样,每天也不一样:卓金凤「视频\ + 封面\」、51「原\ 横\」、梁「封面\标题\横屏16x9.png」、
# 10.16 干脆没有员工这一层(视频直接在号文件夹里,封面工具的文件夹直接堆在旁边或套在「封面\」里)。
# 所以:号文件夹整个翻一遍,视频按所在的第一层「人名」文件夹分人;封面按名字在整个号文件夹里配。
SKIP_WORDS = ("已发", "不能用", "不要", "脏话", "作废", "废弃", "重复")
GENERIC_DIRS = {"视频", "原", "横", "竖", "横屏", "竖屏", "原图", "封面", "新建文件夹", "成品", "处理"}
NO_EMP = "没分人"
IMG_EXTS = (".png", ".webp", ".jpg", ".jpeg")


def _skip_dir(name: str) -> bool:
    return any(w in name for w in SKIP_WORDS)


def _generic(name: str) -> bool:
    """「视频 / 原 / 横 / 封面」这种不是人名的文件夹。纯数字不算(「51」是个人;梁的「梁/1/」第一层已经是梁了)。"""
    return name.strip() in GENERIC_DIRS


def scan_account(acc_dir: str, account: str, date: str) -> list[Video]:
    """号文件夹里所有视频(翻到底),配好封面,employee = 所在第一层不是「视频 / 原 / 横 / 1」这类的文件夹名;
    直接放在号文件夹(或只套了「视频」这种)的算「没分人」。名字带「已发 / 不能用」的文件夹不碰。"""
    vids: list[tuple[str, str]] = []                 # (视频路径, 员工)
    imgs: dict[str, list[str]] = {}                  # 名字(norm) → 同名图片
    tools: dict[str, str] = {}                       # 名字(norm) → 封面工具的文件夹(横屏16x9.png / 竖屏9x16.png)
    base = os.path.normpath(acc_dir)
    for cur, dirs, files in os.walk(base):
        dirs[:] = sorted(d for d in dirs if not _skip_dir(d))
        rel = os.path.relpath(cur, base)
        parts = [] if rel == "." else rel.split(os.sep)
        emp = next((x.strip() for x in parts if not _generic(x)), NO_EMP) if parts else NO_EMP
        if parts and any(f.startswith(("横屏", "竖屏")) for f in files):
            tools.setdefault(norm_name(parts[-1]), cur)
        for f in files:
            stem, ext = os.path.splitext(f)
            e = ext.lower()
            if e in VIDEO_EXTS:
                vids.append((os.path.join(cur, f), emp))
            elif e in IMG_EXTS and not stem.startswith(("原图", "_thumb", "横屏", "竖屏", "修改")):
                imgs.setdefault(norm_name(stem), []).append(os.path.join(cur, f))

    def nearest(cands: list[str], vpath: str) -> str:
        """同名图片好几张:同一个文件夹的优先,再是路径挨得最近的。"""
        vd = os.path.dirname(vpath)
        return min(cands, key=lambda c: (os.path.dirname(c) != vd, -len(os.path.commonpath([c, vpath])), c)) if cands else ""

    out = []
    for path, emp in vids:
        stem = os.path.splitext(os.path.basename(path))[0]
        n = norm_name(stem)
        same = imgs.get(n, [])
        png = nearest([c for c in same if c.lower().endswith((".png", ".webp"))], path)
        jpg = nearest([c for c in same if c.lower().endswith((".jpg", ".jpeg"))], path)
        vpng = ""
        if n in tools:
            h, vv = covers_from_dir(tools[n])
            png, vpng = h or png, vv
        v = Video(path=path, title=stem.strip(), account=account, employee=emp, date=date, png=png, jpg=jpg)
        v.vpng = vpng
        out.append(v)
    out.sort(key=lambda v: (v.employee, v.title, v.path))
    return out


def groups(videos: list[Video]) -> list[tuple[str, int]]:
    """一个号下面分几个人:[(员工, 条数)],「没分人」放最后。"""
    cnt: dict[str, int] = {}
    for v in videos:
        cnt[v.employee] = cnt.get(v.employee, 0) + 1
    return sorted(cnt.items(), key=lambda kv: (kv[0] == NO_EMP, kv[0]))


def emp_dir(acc_dir: str, emp: str) -> str:
    """员工文件夹(打开所在文件夹用);没分人 / 找不到就给号文件夹。"""
    if emp and emp != NO_EMP:
        for cur, dirs, _f in os.walk(acc_dir):
            for d in dirs:
                if d.strip() == emp:
                    return os.path.join(cur, d)
            break
    return acc_dir


def archive_target(st, date: str) -> str:
    root = str(st.get("archive_root") or "").replace("{month}", month_of(date) or "?")
    return os.path.join(root, date)


def move_date(st, date: str, merge: bool = False, on_file=None) -> str:
    """把整个日期文件夹剪切到归档那里。目标已经有同名文件夹:merge=False 抛 FileExistsError(界面上问人);
    merge=True 把里面的东西挪进去(同名文件不覆盖,改名加 (2))。返回目标路径。
    一个文件一个文件挪(qe/fsops.move_tree):被占着的留在原处、报出来,不会两边各一份;关掉占用的再点一次接着挪。"""
    from .fsops import MoveError, move_tree
    src = os.path.join(st["material_root"], date)
    if not month_of(date):
        raise MoveError(f"「{date}」这个文件夹名认不出月份(要像 10.15 这样),没挪")
    if not str(st.get("archive_root") or "").strip():
        raise MoveError("设置里「发完挪到」是空的,先填好再挪")
    dst = archive_target(st, date)
    if not os.path.isdir(src):
        raise FileNotFoundError(src)
    if os.path.exists(dst) and not merge:
        raise FileExistsError(dst)
    n, errs = move_tree(src, dst, on_file=on_file)
    if errs:
        nl = "\n"
        raise MoveError(f"挪了 {n} 个文件,还有 {len(errs)} 个挪不动(留在原处,没有重复):{nl}" + nl.join(errs[:5]) +
                        (f"{nl}…" if len(errs) > 5 else "") + f"{nl}{nl}关掉占着的程序后再点一次「挪走」,会接着挪剩下的。")
    return dst