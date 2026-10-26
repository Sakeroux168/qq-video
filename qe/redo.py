"""找视频重发(用户 2026-10-25:「我找到一个横屏的,要删了重发,但是过程繁琐:要去内容查看里找 24 号发布的研习社,
把视频和封面找到,再放到共享盘的小学生教育,建 10.xx 的文件夹,再建家长研习社,再把视频放进去」)。

输入标题里的几个字 → 从发布记录里找出来 → 算出视频现在在哪(教育号:整天挪去了「内容查看\\X月发布视频\\企鹅号\\教育\\那天」,
结构不变;16 个号:发完挪去的位置记录里有)→「挪回去重发」:视频连封面(同名图、封面工具按标题建的文件夹)
挪回素材盘今天 / 明天的日期文件夹,里面的结构照原样,记录改成没发成;16 个号还能在企鹅号上删掉那条。
"""
import os

from . import folders as F
from .plan import move_noclobber

IMG = (".jpg", ".jpeg", ".png", ".webp")


def search(rec, kw: str, limit: int = 60) -> list[dict]:
    """标题里有这几个字的记录(新的在前;作废的不要)。同一条视频只留最新那条记录。"""
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
        k = r.get("pkey") or r["path"]
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
        if len(out) >= limit:
            break
    return out


def is_api(row: dict) -> bool:
    return row.get("employee") == "接口"


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
        root, date = st["material_root"], row.get("date") or ""
        try:
            rel = os.path.relpath(p, os.path.join(root, date))
        except ValueError:
            rel = ""
        if rel and not rel.startswith(".."):
            q = os.path.join(F.archive_target(st, date), rel)
            if os.path.isfile(q):
                return q
    return ""


def extras(video: str) -> list[str]:
    """跟着视频一起挪的:同名的图、封面工具按标题建的文件夹(名字对得上的)。"""
    d, stem = os.path.dirname(video), os.path.splitext(os.path.basename(video))[0]
    n = F.norm_name(stem)
    out = []
    try:
        for x in os.listdir(d):
            p = os.path.join(d, x)
            s, e = os.path.splitext(x)
            if os.path.isfile(p) and e.lower() in IMG and s.strip() == stem.strip():
                out.append(p)
            elif os.path.isdir(p) and F.norm_name(x) == n:
                out.append(p)
    except OSError:
        pass
    return out


def target_dir(st, row: dict, md: str) -> str:
    """挪回哪:教育号 = 素材盘\\<那天>\\<原来日期文件夹下面那几层>;16 个号 = 号的文件夹\\<那天>。
    那天的日期文件夹已经有了(哪怕叫「10.25(星期六)」)就用它,没有就建「10.25」。"""
    if is_api(row):
        from . import apiacc, apisrc
        orig = os.path.dirname(row["path"])
        acc_dir = os.path.dirname(orig) if apisrc.date_key(os.path.basename(orig)) else ""
        if not acc_dir or not os.path.isdir(acc_dir):
            known = set(apiacc.nicks()) or None
            lst = apisrc.account_folder_list(list(st.get("api_roots") or apisrc.DEFAULT_ROOTS), known).get(row["account"], [])
            acc_dir = lst[0] if lst else ""
        if not acc_dir:
            return ""
        return os.path.join(_day_dir(acc_dir, md))
    root, date = st["material_root"], row.get("date") or ""
    rel = os.path.relpath(os.path.dirname(row["path"]), os.path.join(root, date))
    if rel.startswith(".."):
        rel = ""
    return os.path.normpath(os.path.join(_day_dir(root, md), rel))


def _day_dir(parent: str, md: str) -> str:
    try:
        for x in os.listdir(parent):
            if F.day_of(x) == md and os.path.isdir(os.path.join(parent, x)):
                return os.path.join(parent, x)
    except OSError:
        pass
    return os.path.join(parent, md)


def pull_back(st, rec, row: dict, md: str) -> tuple[str, str]:
    """挪回 md(「10.25」)那天的文件夹重发:视频 + 封面挪过去,记录改成没发成。返回 (新位置, "") 或 ("", 为什么不行)。"""
    src = locate(st, row)
    if not src:
        return "", "找不到这个视频了(发布归档里也没有)"
    dst = target_dir(st, row, md)
    if not dst:
        return "", "找不到这个号的素材文件夹"
    if os.path.normcase(os.path.normpath(os.path.dirname(src))) == os.path.normcase(os.path.normpath(dst)):
        rec.mark_unsent(row["id"], f"(找视频重发:就在 {md} 的文件夹里,没挪)")   # 还没挪去归档、就在那天的文件夹:不挪(免得变成「(2)」)
        return src, ""
    try:
        os.makedirs(dst, exist_ok=True)
        moved = [p for p in extras(src)]
        new = move_noclobber(src, dst)
        for p in moved:
            if os.path.isdir(p):
                tgt = os.path.join(dst, os.path.basename(p))
                if not os.path.exists(tgt):
                    os.replace(p, tgt)
            else:
                move_noclobber(p, dst)
    except OSError as e:
        return "", f"挪不过去:{e.strerror or e}"
    rec.mark_unsent(row["id"], f"(找视频重发:挪回 {md} 重发)")
    return new, ""


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
