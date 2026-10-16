"""素材文件夹:X:\\知乎视频\\小学生教育\\<日期>\\<号的缩写>\\<员工>\\ 里每条 同名 .mp4 + .png(无字封面,用这个)+ .jpg(原封面,带字,不能用)。
实际每个人放法都不一样 → 界面用 scan_account():号文件夹整个翻一遍,按名字配封面(见下面)。

发完一整天:把 <日期> 文件夹剪切到 X:\\知乎视频\\内容查看\\<月>月发布视频\\企鹅号\\教育\\ 下面。
"""
import os
import re
import unicodedata
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
    skip: str = ""             # 不摆它的原因(同号同名只发一条 / 0 字节 / 打不开 / 这个号发过同名的);空 = 正常


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


def _subdirs(d: str) -> list[str]:
    """d 下面的文件夹名(按名字排)。用 scandir 认:名字末尾带空格的(苹果电脑建的)os.path.isdir 认不出,会悄悄漏掉。"""
    with os.scandir(d) as it:
        return sorted(e.name for e in it if e.is_dir())


def _match_dirs(root: str, date: str, st) -> tuple[dict[str, list[str]] | None, list[str]]:
    """日期下面的文件夹分给各个号。返回 ({号: [号文件夹]}, [不认识的])。日期文件夹打不开 → (None, [])。
    ① 名字(去掉前后空格)正好是号名 / 缩写的,归那个号;
    ② 不是正好,但名字里含某个号的缩写(「研习空间2」「小天地（补）」),而且只含一个号的,也归它;
       名字带「已发 / 不要…」的不这么猜;一个文件夹两个号都像的,不分(算不认识,免得发错号);
    ③ 日期里又套了一层同名日期(归档里见过 10.15\\10.15\\研习空间),里面那层也照样认。"""
    base = os.path.join(root, date)
    try:
        subs = _subdirs(base)
    except OSError:
        return None, []
    alias: dict[str, set] = {}                       # 缩写 → 哪些号
    for name in st.account_names():
        for a in st.aliases_of(name):
            if a.strip():
                alias.setdefault(a.strip(), set()).add(name)
    out: dict[str, list[str]] = {name: [] for name in st.account_names()}
    unknown: list[str] = []
    places = [(base, s) for s in subs if s.strip() != date.strip()]
    for s in subs:                                   # ③ 套了一层同名日期
        if s.strip() == date.strip():
            try:
                inner = os.path.join(base, s)
                places += [(inner, x) for x in _subdirs(inner)]
            except OSError:
                unknown.append(s)
    for b, s in places:
        hits = alias.get(s.strip(), set())
        if not hits and not _skip_dir(s):            # ② 名字里含缩写(缩写至少两个字,免得一个字到处都像)
            hits = {n for a, ns in alias.items() if len(a) >= 2 and a in s for n in ns}
        if len(hits) == 1:
            out[next(iter(hits))].append(os.path.join(b, s))
        else:
            unknown.append(os.path.relpath(os.path.join(b, s), base))
    return out, unknown


def account_dirs(root: str, date: str, st) -> dict[str, list[str]]:
    """这一天每个号对应的缩写文件夹(可能有好几个)。认不出的缩写不要(见 _match_dirs)。"""
    out, _unk = _match_dirs(root, date, st)
    return out if out is not None else {}


def unknown_dirs(root: str, date: str, st) -> list[str]:
    """这一天里不认识的缩写文件夹(提醒去设置里加)。"""
    return _match_dirs(root, date, st)[1]


def employees(account_dir: str) -> list[str]:
    try:
        return sorted(n for n in os.listdir(account_dir) if os.path.isdir(os.path.join(account_dir, n)))
    except OSError:
        return []


COVER_DIR = "封面"


def norm_name(s: str) -> str:
    """对名字用:去掉空格、下划线、标点(「C 位」和「C_位」、全角半角冒号、「１２」和「12」算一样)。
    全是符号 / 表情的名字(去完啥也不剩)就用原样,免得「🔥🔥」和「❤❤」互相配上。"""
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"[\W_]+", "", s).lower() or s.strip().lower()


def _loose(s: str) -> str:
    """比 norm_name 严:只把空格和 Windows 文件名里不能有的字(封面工具建文件夹时换成 _)当成一样,标点要一样。
    「三个方法，」和「三个方法。」norm 后一样,这里不一样 —— 同名分不清的时候靠它认准是哪条。"""
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r'[\s<>:"/\\|?*_]+', "_", s).strip(" ._").lower()


def _landscape(path: str) -> bool:
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size[0] >= im.size[1]
    except Exception:
        return False


def covers_from_dir(d: str) -> tuple[str, str]:
    """员工「梁」的放法:<员工>/封面/<视频标题>/ 里 横屏16x9.png / 竖屏9x16.png / 修改 (1).png 是他改过的无字版,
    原图.png 带字不要,_thumb.jpg 是缩略图不要。返回 (横的, 竖的),没有的给 ""。
    好几张横的(真实素材见过:工具跑了几遍「横屏16x9 (2).png」「(3)」,第一遍的 AI 扩图凭空多出个人 / 一面墙;
    他自己改的「修改 (1).png」比「横屏16x9.png」晚)→ 用最后改的那张(文件修改时间最新)。
    别的图只认 .png / .webp 横的(.jpg 在这些放法里都是带字的)。"""
    try:
        files = sorted(os.listdir(d))
    except OSError:
        return "", ""
    imgs = [f for f in files if os.path.splitext(f)[1].lower() in (".png", ".jpg", ".jpeg", ".webp")
            and not f.startswith(("原图", "_thumb", ".", "~$"))]

    def newest(fs):
        def key(f):
            try:
                t = os.path.getmtime(os.path.join(d, f))
            except OSError:
                t = 0
            return t, f.startswith("修改"), f
        return max(fs, key=key) if fs else ""
    fix = [f for f in imgs if f.startswith("修改")]
    fix_h = [f for f in fix if _landscape(os.path.join(d, f))]
    hs = [f for f in imgs if f.startswith("横屏")] + fix_h
    vs = [f for f in imgs if f.startswith("竖屏")] + [f for f in fix if f not in fix_h]
    if not hs:                                  # 没有「横屏 / 修改」:别的横的 png
        hs = [f for f in imgs if f not in vs and os.path.splitext(f)[1].lower() in (".png", ".webp")
              and _landscape(os.path.join(d, f))]
    h, v = newest(hs), newest(vs)
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
_WEAK_WORDS = ("不要", "重复")                       # 标题里也常有(「告知孩子不要随意踩踏井盖」「一周早餐不重复」)
_NEG_RE = re.compile(r"(没|无|未|非|不|不含|不是)$")    # 「没脏话 / 不重复」(脏话检测工具分出来的,正是要发的)
GENERIC_DIRS = {"视频", "原", "横", "竖", "横屏", "竖屏", "原图", "封面", "新建文件夹", "成品", "处理", "已改封面"}
NO_EMP = "没分人"
IMG_EXTS = (".png", ".webp", ".jpg", ".jpeg")
JUNK_PREFIX = ("._", "~$")                           # 苹果电脑 / Office 留下的小垃圾文件(「._xxx.mp4」不是视频)


def _has_word(name: str, words) -> bool:
    """名字里有这些字,而且前面不是「没 / 无 / 不含」。"""
    for w in words:
        i = name.find(w)
        while i >= 0:
            if not _NEG_RE.search(name[:i]):
                return True
            i = name.find(w, i + 1)
    return False


def _titleish(name: str) -> bool:
    """像一句视频标题(有逗号冒号、字多),不像「31条（已发）」「不要的」这种记号。"""
    return len(norm_name(name)) >= 12 and any(c in name for c in "，,：:！!？?、")


def _skip_dir(name: str, path: str = "") -> bool:
    """名字带「已发 / 不能用 / 脏话 / 作废 / 废弃 / 不要 / 重复」的文件夹整个不碰。但这些不算(真实素材里见过):
    ①「没脏话 / 无重复」:前面是「没 / 无 / 不含」;
    ②「不要 / 重复」在一句标题里(封面工具按标题建的文件夹:「理性规划课外培训，家长不要盲目给孩子报…」);
    ③ 给了 path 时看一眼里面:有 横屏 / 竖屏 / 原图(封面工具的标题文件夹),或者有和文件夹同名的视频 → 是标题文件夹,不跳
       (「孩子已发烧三天…」这种标题里带「已发」的也认得出)。"""
    if not _has_word(name, SKIP_WORDS):
        return False
    if not _has_word(name, tuple(w for w in SKIP_WORDS if w not in _WEAK_WORDS)) and _titleish(name):
        return False
    if path:
        try:
            files = os.listdir(path)
        except OSError:
            files = []
        n = norm_name(name)
        for f in files:
            stem, ext = os.path.splitext(f)
            if f.startswith(("横屏", "竖屏", "原图")) or (ext.lower() in VIDEO_EXTS and n and norm_name(stem) == n):
                return False
    return True


def _generic(name: str) -> bool:
    """「视频 / 原 / 横 / 封面」这种不是人名的文件夹。纯数字不算(「51」是个人;梁的「梁/1/」第一层已经是梁了)。"""
    return name.strip() in GENERIC_DIRS


def _emp_of(parts: list[str], stem: str) -> str:
    """视频归谁:路径里第一层不是「视频 / 原 / 封面」、不是日期(号文件夹里又套了「10.16」)、
    也不是这条视频自己的标题文件夹(<号>\\<标题>\\<标题>.mp4)的文件夹名;都不是就「没分人」。"""
    n = norm_name(stem)
    for x in parts:
        if _generic(x) or _DATE_RE.match(x.strip()) or (n and norm_name(x) == n):
            continue
        return x.strip()
    return NO_EMP


# 封面工具出的文件:横屏16x9.png、横屏16x9 (2).png、竖屏9x16.png、横屏.png、修改 (1).png、原图.png、_thumb.jpg
_TOOL_FILE = re.compile(r"^(横屏|竖屏|修改|原图)\s*(\d+\s*[x×X:：]\s*\d+)?\s*([(（]\s*\d+\s*[)）])?$|^_thumb$")


def _is_tool_dir(files: list[str]) -> bool:
    """封面工具按标题建的文件夹:里面有 横屏 / 竖屏 / 修改 / 原图 这些图,或者 质检报告.json。
    (只有「修改 (1).png + 原图.png」没有横屏竖屏的也算 —— 真实素材里梁有 9 条是这样,原来认不出,封面就丢了)"""
    for f in files:
        stem, ext = os.path.splitext(f)
        if f == "质检报告.json" or (ext.lower() in IMG_EXTS and _TOOL_FILE.match(stem)):
            return True
    return False


def _pick(cands: list[tuple], vpath: str, stem: str, emp: str, crowded: bool):
    """同名的封面(图片 / 封面工具的文件夹)好几个,挑给这条视频的那个;挑不准就不给 —— 宁可没封面让人看一眼,也不能配错。
    cands = [(路径, 员工, 原名)];返回挑中的那个,没有给 None。
    ① 只要本人文件夹里的;本人那里没有,才要「没分人」的(号文件夹里直接放的、号\\封面\\ 里的);别的员工的一律不要
       (乙的视频不能拿甲的同名封面:可能是两个人起了一样名字的两条视频);
    ② 名字原样对得上的优先(只差空格 / 下划线 / 文件名不能有的字也算原样,见 _loose);
    ③ 这个号里有好几条视频去掉标点后同名(「三个方法，」和「三个方法。」):只认原样对得上的,对不上就不给;
    ④ 还剩好几个:同一个文件夹的优先,再是路径挨得最近的。"""
    pool = [c for c in cands if c[1] == emp] or ([c for c in cands if c[1] == NO_EMP] if emp != NO_EMP else [])
    exact = [c for c in pool if _loose(c[2]) == _loose(stem)]
    if exact:
        pool = exact
    elif crowded:
        return None
    if not pool:
        return None
    vd = os.path.dirname(vpath)
    return min(pool, key=lambda c: (os.path.dirname(c[0]) != vd, -len(os.path.commonpath([c[0], vpath])), c[0]))


def _count_videos(d: str) -> int:
    n = 0
    for _c, _ds, fs in os.walk(d):
        n += sum(1 for f in fs if os.path.splitext(f)[1].lower() in VIDEO_EXTS and not f.startswith(JUNK_PREFIX))
    return n


def scan_account(acc_dir: str, account: str, date: str, report: list | None = None) -> list[Video]:
    """号文件夹里所有视频(翻到底),配好封面,employee = 所在第一层不是「视频 / 原 / 横 / 1」这类的文件夹名;
    直接放在号文件夹(或只套了「视频」这种)的算「没分人」。名字带「已发 / 不能用」的文件夹不碰(见 _skip_dir)。
    report:给了就往里记「跳过了哪个文件夹几条」「哪个文件夹打不开」,界面上说给人听(不悄悄漏掉)。
    0 字节 / 打不开(路径太长)的视频照样列出来,skip 里写原因,不摆。"""
    vids: list[tuple[str, str]] = []                 # (视频路径, 员工)
    imgs: dict[str, list[tuple]] = {}                # 名字(norm) → [(同名图片, 员工, 原名)]
    tools: dict[str, list[tuple]] = {}               # 名字(norm) → [(封面工具的文件夹, 员工, 文件夹名)](横屏16x9.png / 竖屏9x16.png / 修改 (1).png)
    base = os.path.normpath(acc_dir)
    rep = report if report is not None else []
    for cur, dirs, files in os.walk(base, onerror=lambda e: rep.append(("打不开", getattr(e, "filename", "") or str(e), 0))):
        keep = []
        for d in sorted(dirs):
            if _skip_dir(d, os.path.join(cur, d)):
                rep.append(("跳过", os.path.join(cur, d), _count_videos(os.path.join(cur, d))))
            else:
                keep.append(d)
        dirs[:] = keep
        rel = os.path.relpath(cur, base)
        parts = [] if rel == "." else rel.split(os.sep)
        tool = bool(parts) and _is_tool_dir(files)
        if tool:                                     # 封面工具的文件夹:文件夹名 = 标题;归谁看它上面几层(不算它自己)
            tools.setdefault(norm_name(parts[-1]), []).append((cur, _emp_of(parts[:-1], parts[-1]), parts[-1]))
        for f in files:
            stem, ext = os.path.splitext(f)
            e = ext.lower()
            if f.startswith(JUNK_PREFIX):
                continue
            if e in VIDEO_EXTS:
                vids.append((os.path.join(cur, f), _emp_of(parts, stem)))
            elif e in IMG_EXTS and not _TOOL_FILE.match(stem) and not (tool and stem.startswith(("原图", "_thumb", "横屏", "竖屏", "修改"))):
                imgs.setdefault(norm_name(stem), []).append((os.path.join(cur, f), _emp_of(parts, stem), stem))

    crowd: dict[str, int] = {}                       # 这个号里 norm 后同名的视频有几条
    for path, _e in vids:
        k = norm_name(os.path.splitext(os.path.basename(path))[0])
        crowd[k] = crowd.get(k, 0) + 1

    out = []
    for path, emp in vids:
        stem = os.path.splitext(os.path.basename(path))[0]
        n = norm_name(stem)
        same = imgs.get(n, [])
        crowded = crowd.get(n, 0) > 1
        p = _pick([c for c in same if c[0].lower().endswith((".png", ".webp"))], path, stem, emp, crowded)
        j = _pick([c for c in same if c[0].lower().endswith((".jpg", ".jpeg"))], path, stem, emp, crowded)
        t = _pick(tools.get(n, []), path, stem, emp, crowded)
        png, jpg, vpng = (p[0] if p else ""), (j[0] if j else ""), ""
        if t and not (p and p[1] == emp and t[1] != emp):      # 工具文件夹优先;但它是别处(没分人)的、同名 png 就在本人这里,用本人的
            h, vv = covers_from_dir(t[0])
            png, vpng = h or png, vv
        v = Video(path=path, title=stem.strip(), account=account, employee=emp, date=date, png=png, jpg=jpg)
        v.vpng = vpng
        try:                                         # 0 字节(没拷完 / 坏的)、打不开(路径超过 260 字)的不摆
            if os.stat(path).st_size == 0:
                v.skip = "0 字节,视频是坏的(没拷完?),让员工重新放"
        except OSError:
            v.skip = "软件打不开这个文件(路径太长?),让员工把文件夹名 / 文件名改短"
        out.append(v)
    out.sort(key=lambda v: (v.employee, v.title, v.path))
    return out


def dup_key(v: Video) -> tuple[str, str]:
    """同号同名的判断:号 + 标题(去掉空格标点;全是表情去光了就用原标题)。"""
    return v.account, (norm_name(v.title) or v.title)


def mark_dups(videos: list[Video], prefer=None) -> int:
    """同一个号里标题一样的视频(员工放了两份:卓金凤13\\ 和 卓金凤14\\ 各一条、原\\ 和 横\\ 各一条…)只发一条,
    别的写上 skip。留哪条:prefer(v) 为真的(已经发了 / 摆了的)优先,再是有人名的、按人名和路径排第一的。
    已经有 skip 的(0 字节)不算数,免得坏的那条把好的挤掉。返回标了几条。"""
    first: dict = {}
    n = 0
    for v in sorted(videos, key=lambda v: (not (prefer and prefer(v)), v.employee == NO_EMP, v.employee, v.path)):
        if v.skip:
            continue
        k = dup_key(v)
        if k in first:
            f = first[k]
            v.skip = f"和「{f.employee}」里那条同名,同一个号只发一条(两条都要发就让员工改个名)"
            n += 1
        else:
            first[k] = v
    return n


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