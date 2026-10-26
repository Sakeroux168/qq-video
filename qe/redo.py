"""找视频重发(用户 2026-10-25:「我找到一个横屏的,要删了重发,但是过程繁琐:要去内容查看里找 24 号发布的研习社,
把视频和封面找到,再放到共享盘的小学生教育,建 10.xx 的文件夹,再建家长研习社,再把视频放进去」)。

输入标题里的几个字 → 从发布记录里找出来 → 算出视频现在在哪(教育号:整天挪去了「内容查看\\X月发布视频\\企鹅号\\教育\\那天」,
结构不变;16 个号:发完挪去的位置记录里有)→「挪回去重发」:视频连封面(同名图、封面工具按标题建的文件夹、「封面」文件夹里配它的)
挪回素材盘今天 / 明天该发的文件夹,里面的结构照原样,记录改成没发成;16 个号还能在企鹅号上删掉那条。
「去企鹅号核对」的「拎回来重发」、数据记录 / 16 个号页的「改回没发」也都走这里(用户 2026-10-26)。

审查 2026-10-26(子 agent 找出来的,都改了):
- 挪文件走 fsops.safe_move_file(不用 shutil.move:被占着 / 跨盘时两边各一份,再点一次变「(2)」重复发);目标有同名的停下来,不加 (2)
- 挪回来用原来的文件名(归档里撞名存成了「xxx (2)」的改回原名,不然「(2)」会当标题发出去,还躲过查重)
- 认那天的文件夹用和发布页一样的认法(「10.26 脏话」「10.26不能用」「10.26已发」不算)
- 只有「已发 / 没发成」的能挪(「不确定发没发 / 摆好」的挪了会把防重发的保护拆掉)
- 视频挪成了就马上改记录、记下新位置(封面挪不动只提醒);同一个视频的几条记录一起改;补发额度只加一次
"""
import os

from . import folders as F

IMG = (".jpg", ".jpeg", ".png", ".webp")
MOVABLE = ("已发", "没发成")


def search(rec, kw: str, limit: int = 60) -> list[dict]:
    """标题里有这几个字的记录(新的在前;作废的不要)。同一条视频(同一个文件、同一个文章编号)只留最新那条记录;
    文章编号不一样的分开列(审查:同一个位置发过两次,只留最新的会让人删错那条)。"""
    import re
    kw = (kw or "").strip()
    if not kw:
        return []
    rec._fill()
    with rec.conn:
        rows = [dict(r) for r in rec.conn.execute(
            "SELECT * FROM posts WHERE title LIKE ? AND status IN ('已发','摆好','结果不明','发布中','没发成') ORDER BY id DESC LIMIT 400",
            (f"%{kw}%",))]
    seen, out = set(), []
    for r in rows:
        m = re.search(r"article_id=(\w+)", r.get("note") or "")
        k = (r.get("pkey") or r["path"], m.group(1) if m else "")
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
        if len(out) >= limit:
            break
    return out


def is_api(row: dict) -> bool:
    return row.get("employee") == "接口"


def why_not_movable(row: dict) -> str:
    """不能挪回去的原因;能挪给 ""。"""
    s = row.get("status")
    if s in MOVABLE:
        return ""
    if s in ("结果不明", "发布中"):
        return "这条「不确定发没发」:先去企鹅号后台看一眼,在「数据记录」里标成已发 / 没发出去,再决定要不要重发"
    if s == "摆好":
        return "这条在罐头里摆好了、还没确认发没发:先把那批处理完(发好了点「这批发好了」)再说"
    return f"这条记录是「{s}」,不能挪"


def _real(p: str) -> str:
    """记录里挪走后的位置是小写的:找回真名字。"""
    d = os.path.dirname(p or "")
    try:
        for n in os.listdir(d):
            if os.path.normcase(n) == os.path.normcase(os.path.basename(p)):
                return os.path.join(d, n)
    except OSError:
        pass
    return ""


def _rel_in_day(st, row: dict) -> str:
    """教育号:视频在那天的日期文件夹下面的哪几层(「家长研习空间\\小王」);认不出给 ""。"""
    root, date = st.get("material_root") or "", row.get("date") or ""
    try:
        rel = os.path.relpath(os.path.dirname(row.get("path") or ""), os.path.join(root, date))
    except ValueError:                                       # 不在一个盘(换过盘符)
        return ""
    return "" if rel in (".", "") or rel.startswith("..") else rel


def locate(st, row: dict) -> str:
    """这条视频现在在哪;找不到给 ""。"""
    p = row.get("path") or ""
    if p and os.path.isfile(p):
        return p
    if row.get("moved_pkey"):
        q = _real(row["moved_pkey"])
        if q:
            return q
    if not is_api(row):                                    # 教育号:整天挪去了归档,结构不变
        rel = _rel_in_day(st, row)
        date = row.get("date") or ""
        if date:
            q = os.path.join(F.archive_target(st, date), rel, os.path.basename(p)) if rel else \
                os.path.join(F.archive_target(st, date), os.path.basename(p))
            if os.path.isfile(q):
                return q
    return ""


def _same_title(a: str, b: str) -> bool:
    """封面文件夹 / 图的名字是不是这条视频的:先比「只把空格和文件名里不能有的字当一样」(标点要一样),
    审查:「三个方法,…」和「三个方法。…」去掉标点后一样,会把另一条的封面拿走。"""
    return F._loose(a) == F._loose(b)


def extras(video: str, up: int = 0) -> list[tuple[str, int, str]]:
    """跟着视频一起挪的:[(位置, 往上几层, 在那一层下面的相对路径)]。
    - 同一个文件夹:同名的图、封面工具按标题建的文件夹;
    - up > 0(教育号):往上 up 层里叫「封面」的文件夹,里面配这条的图(「_标题.jpg」也算)/ 标题文件夹
      (folders.py 里写过的放法:「梁\\封面\\<标题>\\横屏16x9.png」「卓金凤\\视频\\ + 卓金凤\\封面\\」)。"""
    d, stem = os.path.dirname(video), os.path.splitext(os.path.basename(video))[0]
    out = []

    def scan(folder: str, k: int, prefix: str, allow_under: bool):
        try:
            names = os.listdir(folder)
        except OSError:
            return
        for x in names:
            p = os.path.join(folder, x)
            s, e = os.path.splitext(x)
            if os.path.isfile(p) and e.lower() in IMG and (s.strip() == stem.strip() or (allow_under and _same_title(s.lstrip("_"), stem))):
                out.append((p, k, os.path.join(prefix, x)))
            elif os.path.isdir(p) and _same_title(x, stem):
                out.append((p, k, os.path.join(prefix, x)))

    scan(d, 0, "", False)
    a = d
    for k in range(1, up + 1):
        a = os.path.dirname(a)
        try:
            cov = [x for x in os.listdir(a) if x.strip() == "封面" and os.path.isdir(os.path.join(a, x))]
        except OSError:
            cov = []
        for c in cov:
            scan(os.path.join(a, c), k, c, True)
    return out


def _date_name(x: str, md: str, api: bool) -> bool:
    if api:
        from . import apisrc
        return apisrc.date_key(x) == md                   # 和 16 个号页一样严(「10.26 脏话」不算)
    return F.day_of(x) == md and not F._skip_dir(x)


def _day_dir(parent: str, md: str, api: bool = False) -> str:
    """parent 下面 md 那天的日期文件夹:已经有(哪怕叫「10.25(星期六)」)就用它,好几个优先名字正好是「10.25」的;没有就「10.25」。
    用 scandir 认文件夹(名字末尾带空格的 os.path.isdir 认不出,会另建一个)。"""
    try:
        with os.scandir(parent) as it:
            cands = sorted(e.name for e in it if e.is_dir() and _date_name(e.name, md, api))
    except OSError:
        cands = []
    if cands:
        exact = [x for x in cands if x.strip() == md]
        return os.path.join(parent, (exact or cands)[0])
    return os.path.join(parent, md)


def target_dir(st, row: dict, md: str) -> str:
    """挪回哪:教育号 = 素材盘\\<那天>\\<原来日期文件夹下面那几层>;16 个号 = 那天给这个号手选的文件夹,没手选就是号的文件夹\\<那天>。"""
    if is_api(row):
        from . import apiacc, apisrc
        # 那天这个号手选过文件夹(「给号选文件夹」)的,16 个号页那天只看那个文件夹 → 就放那儿(用户 2026-10-26:
        # 「核查后把视频挪回来了,但是为啥没视频给我发」—— 原来挪回了老的日期文件夹,今天的页面看不到)
        pk = ((st.get("api_picked") or {}).get(md) or {}).get(row.get("account") or "")
        if pk:
            return pk
        orig = os.path.dirname(row.get("path") or "")
        acc_dir = os.path.dirname(orig) if apisrc.date_key(os.path.basename(orig)) else ""
        if not acc_dir or not os.path.isdir(acc_dir):
            known = set(apiacc.nicks()) or None
            lst = apisrc.account_folder_list(list(st.get("api_roots") or apisrc.DEFAULT_ROOTS), known).get(row.get("account") or "", [])
            acc_dir = lst[0] if lst else ""
        if not acc_dir:
            # 号的视频直接放在号文件夹里、没有日期文件夹的(电竞情报馆那种):挪回原来的文件夹(审查:原来直接报找不到)
            return orig if orig and os.path.isdir(orig) else ""
        return _day_dir(acc_dir, md, api=True)
    rel = _rel_in_day(st, row)
    parts = rel.split(os.sep) if rel else []
    if parts and F.day_of(parts[0]):                         # 原来是「10.15\\10.15\\家长研习空间」这种套了一层同名日期的:去掉那层
        parts = parts[1:]
    return os.path.normpath(os.path.join(_day_dir(st["material_root"], md), *parts))


def pull_back(st, rec, row: dict, md: str, out: dict | None = None) -> tuple[str, str]:
    """挪回 md(「10.25」)那天的文件夹重发:视频(用原来的文件名)+ 封面挪过去,记录改成没发成、记下新位置,
    补发以前哪天的给 md 那天加 1 条额度(plan.room_for_redo)。返回 (新位置, "") 或 ("", 为什么不行)。
    out(给了的话)填上 room = 加了几条额度、warn = [封面没挪成之类的提醒]。"""
    from . import fsops, plan
    out = out if out is not None else {}
    out.setdefault("room", 0)
    out.setdefault("warn", [])
    cur = rec.conn.execute("SELECT status FROM posts WHERE id=?", (row["id"],)).fetchone()
    status = cur[0] if cur else row.get("status")
    why = why_not_movable(dict(row, status=status))
    if why:
        return "", why
    src = locate(st, row)
    if not src:
        return "", "找不到这个视频了(发布归档里也没有)"
    dst = target_dir(st, row, md)
    if not dst:
        return "", "找不到这个号的素材文件夹"
    name = os.path.basename(row.get("path") or "") or os.path.basename(src)    # 原来的文件名(归档里可能被改成「xxx (2)」)
    src_stem, new_stem = os.path.splitext(os.path.basename(src))[0], os.path.splitext(name)[0]
    same_dir = os.path.normcase(os.path.normpath(os.path.dirname(src))) == os.path.normcase(os.path.normpath(dst))
    if same_dir and os.path.normcase(os.path.basename(src)) == os.path.normcase(name):
        new = src                                            # 还没挪去归档、就在那天的文件夹:不挪(免得变成「(2)」)
        note = f"(找视频重发:就在 {md} 的文件夹里,没挪)"
    else:
        tgt = os.path.join(dst, name)
        if os.path.exists(tgt):
            return "", f"{md} 的文件夹里已经有「{name}」了(是不是已经挪回来过 / 员工又放了一份?),没挪"
        try:
            new = fsops.safe_move_file(src, tgt)
        except OSError as e:
            return "", f"挪不过去:{e}"
        note = f"(找视频重发:挪回 {md} 重发)"
    # 视频挪成了:马上改记录(同一个视频的几条「已发 / 没发成」一起改),记下新位置
    _relink_all(rec, row, src, new, note)
    if plan.room_for_redo(st, dict(row, status=status), plan.md_to_day(md)):
        out["room"] = 1
    if new == src:
        return new, ""
    # 封面跟着挪(挪不动的只提醒,不算整条失败)
    up = 0 if is_api(row) else len(_rel_in_day(st, row).split(os.sep)) if _rel_in_day(st, row) else 0
    for p, k, rel in extras(src, up):
        base = dst
        for _ in range(k):
            base = os.path.dirname(base)
        head, tail = os.path.split(rel)
        root = os.path.normcase(os.path.normpath(st.get("material_root") or ""))
        if k and not (root and os.path.normcase(base).startswith(root) and os.path.normcase(base) != root):
            out["warn"].append(f"封面「{tail}」没挪(放的位置对不上,还在 {os.path.dirname(p)})")
            continue
        s, e = os.path.splitext(tail)
        if k == 0 and src_stem != new_stem and s.strip() == src_stem.strip():
            tail = new_stem + (e if os.path.isfile(p) else s[len(src_stem):] + e)      # 同名图跟着改回原名
        t = os.path.join(base, head, tail)
        try:
            if os.path.exists(t):
                out["warn"].append(f"封面「{tail}」那边已经有了,没挪(还在 {os.path.dirname(p)})")
            elif os.path.isdir(p):
                n, errs = fsops.move_tree(p, t)
                if errs:
                    out["warn"].append(f"封面文件夹「{tail}」没挪全:{errs[0]}")
            else:
                fsops.safe_move_file(p, t)
        except OSError as e:
            out["warn"].append(f"封面「{tail}」没挪成:{e}")
    return new, ""


def _relink_all(rec, row: dict, src: str, new: str, note: str) -> None:
    """这条视频的记录(同一个文件 / 挪走后同一个位置的「已发 / 没发成」)都改成没发成,位置改成新的(之后按路径认得出,
    重发成了以后「没发成」也不会一直挂着;审查 2026-10-26)。"""
    from .records import pkey
    keys = {pkey(row.get("path") or ""), pkey(src)}
    if row.get("moved_pkey"):
        keys.add(row["moved_pkey"])
    with rec.conn:
        ids = [r[0] for r in rec.conn.execute(
            f"SELECT id FROM posts WHERE status IN ('已发','没发成') AND (pkey IN ({','.join('?' * len(keys))}) "
            f"OR moved_pkey IN ({','.join('?' * len(keys))}))", (*keys, *keys))]
    ids = sorted(set(ids) | {row["id"]})
    for rid in ids:
        rec.mark_unsent(rid, note)
        rec.repath(rid, new)


def delete_on_platform(row: dict) -> str:
    """16 个号:在企鹅号上删掉这条(删了找不回)。返回 ""(删了)或者为什么不行。"""
    import re
    from . import apiacc, omapi
    m = re.search(r"article_id=(\w+)", row.get("note") or "")
    if not m:
        return "软件没记下这条的文章编号,删不了(去后台手动删)"
    acc = next((a for a in apiacc.load() if a.get("nick") == row.get("account")), None)
    if not acc:
        return "这个号没在软件里搬账号,删不了"
    try:
        omapi.Client(acc["client_id"], apiacc.unseal(acc["secret"])).delete_article(m.group(1))
    except Exception as e:
        return f"企鹅号没删成:{str(e)[:60]}"
    return ""


def busy_reason(widget) -> str:
    """软件那边正在发(16 个号)/ 正在罐头里摆(教育号)的时候别挪视频(审查 2026-10-26):返回原因,不忙给 ""。"""
    w = widget.parent() if widget is not None else None
    while w is not None and not hasattr(w, "api_tab"):
        w = w.parent()
    if w is None:
        return ""
    try:
        if w.api_tab.busy() and not getattr(w.api_tab, "_quiet", False):
            return "16 个号那边正在发 / 处理,发完再挪"
        wk = getattr(w, "worker", None)
        if wk is not None and wk.isRunning():
            return "教育号那边正在罐头里摆 / 处理,弄完再挪"
    except Exception:
        return ""
    return ""
