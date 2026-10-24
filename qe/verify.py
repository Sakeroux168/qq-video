"""去企鹅号核对:软件记的「已发」,企鹅号上到底有没有(用户 2026-10-23:「发完后要去企鹅号查这个号今天到底是不是发了这么多」
「看到底是哪个视频没发、但是在软件里面显示已经发了,给他拎回来重发」)。

只读:/article/clientlist(这个号的文章,一页 10 条,新的在前)+ /article/infoclient(单篇的状态)。不发、不删。
- 软件记的已发,企鹅号上「发布成功 / 审核中」且没删 → 对上了
- 企鹅号上没有 / 未发布 / 已删除 → 「没发上」,能「拎回来重发」:视频(和同名封面)从发布归档挪回原来的文件夹,记录改成「没发成」
- 企鹅号上今天有、软件没记的 → 「软件没记的」(手动发的 / 别的软件发的),只列出来
教育号走创作罐头,不走接口,查不了。
"""
import os
import re

OK_FLAGS = ("发布成功", "已发布", "审核中")


def _aid_of(note: str) -> str:
    m = re.search(r"article_id=(\w+)", note or "")
    return m.group(1) if m else ""


def _vid_of(note: str) -> str:
    m = re.search(r"vid=(\w+)", note or "")
    return m.group(1) if m else ""


def _aid_of_item(a: dict) -> str:
    """列表里的一篇:有 article_id 用它;没有就从快报链接里拆(…/s/20170314A06ARB00 → 20170314A06ARB)。"""
    aid = str(a.get("article_id") or "")
    if aid:
        return aid
    m = re.search(r"/s/(\w+)", str(a.get("article_url") or ""))
    if not m:
        return ""
    s = m.group(1)
    return s[:-2] if len(s) > 14 and s.endswith("00") else s


def ours_on(rec, nick: str, day: str) -> list[dict]:
    """软件记的:这个号这天(2026-10-23)用接口发出去的「已发」。"""
    rows = [r for r in rec.rows(account=nick) if r["status"] == "已发" and r["employee"] == "接口"
            and str(r.get("published_at") or "").startswith(day)]
    for r in rows:
        r["aid"], r["vid"] = _aid_of(r.get("note")), _vid_of(r.get("note"))
    return rows


def platform_on(cl, day: str, max_pages: int = 60) -> list[dict]:
    """企鹅号上这个号这天发的(按发布时间):[{aid, vid, title, flag, deleted, time}]。新的在前,翻到比这天早就停。"""
    out = []
    old_pages = 0
    for page in range(1, max_pages + 1):
        d = cl.list_articles(page, 10)
        items = d.get("articles") or []
        if not items:
            break
        older = 0
        for a in items:
            t = str(a.get("article_pub_time") or "")
            if t[:10] == day:
                vi = a.get("article_video_info") or {}
                out.append({"aid": _aid_of_item(a), "vid": str(vi.get("vid") or ""), "title": str(a.get("article_title") or ""),
                            "flag": str(a.get("article_pub_flag") or ""), "deleted": str(a.get("article_del_flag") or "") == "已删除",
                            "time": t})
            elif t and t[:10] < day:
                older += 1
        # 连着 3 页都比这天早才停(用户 2026-10-24:企鹅号上今天 51 条,软件只读到 49 条 —— 列表不一定严格按时间排,一页就停会漏)
        old_pages = old_pages + 1 if older == len(items) else 0
        if old_pages >= 3:
            break
        try:
            if page * 10 >= int(d.get("total") or 0):
                break
        except (TypeError, ValueError):
            pass
    return out


def check_account(cl, rec, nick: str, day: str) -> dict:
    """一个号:{nick, ours, ok, review, missing:[记录+why], extra:[企鹅号上的]}。"""
    ours = ours_on(rec, nick, day)
    plat = platform_on(cl, day)
    live = [p for p in plat if p["flag"] in OK_FLAGS and not p["deleted"]]
    aids = {p["aid"] for p in live if p["aid"]}
    vids = {p["vid"] for p in live if p["vid"]}
    missing = []
    found = []                                             # 列表里没读到、单查是这天发布成功的:算对上(也算进实发)
    for r in ours:
        if (r["aid"] and r["aid"] in aids) or (r["vid"] and r["vid"] in vids):
            continue
        # 用户 2026-10-24:软件记 50、企鹅号上 49,原来单查说「发布成功」就放过了,看不出是哪条 →
        # 今天的列表里没有的都列出来;单查说发布成功的标「可疑」(不默认打勾),没发布 / 删了 / 查不到的默认打勾
        why, sure = "企鹅号今天的列表里没有这条", True
        if r["aid"]:
            try:
                info = (cl.article_info(r["aid"]) or {}).get("article_info") or {}
                flag, dele = str(info.get("article_pub_flag") or ""), str(info.get("article_del_flag") or "") == "已删除"
                t = str(info.get("article_pub_time") or "")
                if flag in OK_FLAGS and not dele and t[:10] == day:
                    found.append({"aid": r["aid"], "flag": flag})   # 用户 2026-10-24:后台一搜就在,这天发的 → 就是发上了
                    continue
                if flag in OK_FLAGS and not dele:
                    why, sure = f"单查是「{flag}」,但发布时间是 {t[5:16] or '?'}(不是这天),看一眼再决定", False
                else:
                    why = "已删除" if dele else (f"企鹅号上是「{flag}」" if flag else why)
            except Exception as e:
                why = f"查不到这篇({str(e)[:40]})"
        else:
            why = "软件没记下文章编号,企鹅号今天的列表里也没有"
        missing.append(dict(r, why=why, sure=sure))
    our_aids = {r["aid"] for r in ours if r["aid"]}
    our_vids = {r["vid"] for r in ours if r["vid"]}
    extra = [p for p in live if not ((p["aid"] and p["aid"] in our_aids) or (p["vid"] and p["vid"] in our_vids))]
    every = live + found
    return {"nick": nick, "ours": len(ours), "live": len(every), "ok": sum(1 for p in every if p["flag"] != "审核中"),
            "review": sum(1 for p in every if p["flag"] == "审核中"), "missing": missing, "extra": extra}


def _real_path(p: str) -> str:
    """记录里挪走后的位置是小写的(pkey);找回文件夹里真的那个文件名(原来那次大小写不对,G镇→g镇)。"""
    d = os.path.dirname(p)
    try:
        for n in os.listdir(d):
            if os.path.normcase(n) == os.path.normcase(os.path.basename(p)):
                return os.path.join(d, n)
    except OSError:
        pass
    return ""


def unsend(rec, row: dict, why: str = "人手动改回没发") -> str:
    """人手动把一条「已发」改回没发(用户 2026-10-24:「已发的视频不能手动改回来,应该加个按钮」):
    能找到视频就挪回原来的文件夹(和拎回来重发一样);找不到视频也把记录改成没发成(要重发得自己把视频放回去)。
    返回 ""(好了)或者一句提醒。"""
    msg = pull_back(rec, dict(row, why=why))
    if msg and msg.startswith("发布归档里找不到"):
        rec.mark_unsent(row["id"], f"({why};视频没找到,要重发得自己放回原来的文件夹)")
        return "记录改成没发了,但视频没找到(要重发得自己把视频放回原来的文件夹)"
    return msg


def pull_back(rec, row: dict) -> str:
    """拎回来重发:视频(和同名封面)从发布归档挪回原来的文件夹(原名;文件夹没了就建),记录改成「没发成」。
    返回 ""(好了)或者为什么不行。"""
    from .apicover import find
    from .plan import move_noclobber
    src = _real_path(row.get("moved_pkey") or "") if row.get("moved_pkey") else ""
    if not src and os.path.isfile(row.get("path") or ""):
        src = row["path"]                                  # 没挪走(还在原处)
    if not src:
        return "发布归档里找不到这个视频了(被挪走 / 删了?)"
    dst_dir = os.path.dirname(row["path"])
    try:
        cover = find(src)
        if os.path.normcase(src) != os.path.normcase(row["path"]):
            os.makedirs(dst_dir, exist_ok=True)
            want = os.path.join(dst_dir, os.path.basename(row["path"]))
            if os.path.exists(want):
                move_noclobber(src, dst_dir)
            else:
                os.replace(src, want)
            if cover:
                cstem, cext = os.path.splitext(os.path.basename(row["path"]))[0], os.path.splitext(cover)[1]
                cwant = os.path.join(dst_dir, cstem + cext)
                if os.path.exists(cwant):
                    move_noclobber(cover, dst_dir)
                else:
                    os.replace(cover, cwant)
    except OSError as e:
        return f"挪不回去:{e.strerror or e}"
    rec.mark_unsent(row["id"], f"(去企鹅号核对:{row.get('why') or '企鹅号上没有'},拎回来重发)")
    return ""
