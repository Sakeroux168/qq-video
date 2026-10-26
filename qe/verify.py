"""去企鹅号核对:软件记的「已发」,企鹅号上到底有没有(用户 2026-10-23:「发完后要去企鹅号查这个号今天到底是不是发了这么多」
「看到底是哪个视频没发、但是在软件里面显示已经发了,给他拎回来重发」)。

只读:/article/clientlist(这个号的文章,一页 10 条,新的在前)+ /article/infoclient(单篇的状态)。不发、不删。
- 软件记的已发,企鹅号上「发布成功 / 审核中」且没删 → 对上了
- 企鹅号上没有 / 未发布 / 已删除 → 「没发上」,能「拎回来重发」:视频(和同名封面)从发布归档挪回原来的文件夹,记录改成「没发成」
- 企鹅号上今天有、软件没记的 → 「软件没记的」(手动发的 / 别的软件发的),只列出来
教育号:发布走创作罐头;在「登录取钥匙」里取了钥匙(只查不发,存在 只查账号.json)的,也能查,按标题对(check_edu)。
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


def ours_on(rec, nick: str, day: str, edu: bool = False) -> list[dict]:
    """软件记的:这个号这天(2026-10-23)发出去的「已发」。16 个号 = 接口发的;edu = 教育号(罐头发的,同一个视频只算一次)。"""
    rows = [r for r in rec.rows(account=nick) if r["status"] == "已发" and ((r["employee"] != "接口") if edu else (r["employee"] == "接口"))
            and str(r.get("published_at") or "").startswith(day)]
    if edu:
        seen, uniq = set(), []
        for r in rows:
            k = r.get("pkey") or r["path"]
            if k not in seen:
                seen.add(k)
                uniq.append(r)
        rows = uniq
    for r in rows:
        r["aid"], r["vid"] = _aid_of(r.get("note")), _vid_of(r.get("note"))
    return rows


def _tkey(t: str) -> str:
    from .folders import norm_name
    return norm_name(t)


def _redone(k: str, later: list[tuple[str, str]]) -> str:
    """later 里有标题一样 / 很像(相似度 ≥ 0.75)的 → 返回那条的日期(10-23),没有 → ""。"""
    from difflib import SequenceMatcher
    for lk, when in later:
        if lk == k or (min(len(k), len(lk)) >= 6 and SequenceMatcher(None, k, lk).ratio() >= 0.75):
            return when
    return ""


def check_edu(cl, rec, nick: str, day: str) -> dict:
    """教育号(用户 2026-10-26:钥匙只用来查,发布照旧走罐头):罐头发的记录没有文章编号,按标题对。
    先对完全一样的(去掉空格标点),再对一个是另一个开头的(企鹅号可能把长标题截短)。
    企鹅号上同标题是「审核不通过 / 已删除」的 → 没发上(打勾);标题哪儿都找不到的 → 也列出来,但不打勾(可能是标题对不上,看一眼再决定)。"""
    ours = ours_on(rec, nick, day, edu=True)
    plat = platform_on(cl, day)
    live = [p for p in plat if p["flag"] in OK_FLAGS and not p["deleted"]]
    left = list(live)
    todo = []
    for r in ours:                                            # 第一遍:标题完全一样
        k = _tkey(r["title"])
        hit = next((p for p in left if _tkey(p["title"]) == k), None)
        if hit is not None:
            left.remove(hit)
        else:
            todo.append(r)
    missing = []
    for r in todo:                                            # 第二遍:一个是另一个的开头(至少 8 个字)
        k = _tkey(r["title"])
        hit = next((p for p in left if min(len(k), len(_tkey(p["title"]))) >= 8
                    and (k.startswith(_tkey(p["title"])) or _tkey(p["title"]).startswith(k))), None)
        if hit is not None:
            left.remove(hit)
            continue
        bad = next((p for p in plat if _tkey(p["title"]) == k and p not in live), None)
        if bad is not None:
            why, sure = ("已删除" if bad["deleted"] else f"企鹅号上是「{bad['flag']}」"), True
        else:
            why, sure = "", None                              # 标题哪儿都找不到:看这天后台有没有多出来的(下面定)
        missing.append(dict(r, why=why, sure=sure))
    # 用户 2026-10-26:标题找不到,而这天后台也没有多出来、软件没记的 → 不可能是在罐头里改了标题发的,就是没发上(打勾);
    # 这天后台有多出来的 → 可能是改了标题发的,不打勾,提示看一眼
    # 同一个号、后来又发过同样 / 差不多标题的(补发过了):别再拎回来,不然重复发。
    # 用户 2026-10-23 的「精选8条视频」就是 19~22 号没发上的,标题为了躲查重稍微改过(三项→三种、参考→攻略):按相似度认
    later = [(_tkey(x["title"]), str(x["published_at"])[5:10]) for x in rec.rows(account=nick)
             if x["status"] == "已发" and str(x.get("published_at") or "")[:10] > day]
    for m in missing:
        again = _redone(_tkey(m["title"]), later)
        if again:
            m["why"], m["sure"] = f"这天没发上,但 {again} 已经补发过了,不用再拎回来", False
            m["redone"] = True
        elif m["sure"] is None:
            if left:
                m["why"], m["sure"] = (f"企鹅号这天没找到这个标题;这天后台有 {len(left)} 条软件没记的,"
                                       "可能是在罐头里改了标题发的,看一眼再决定"), False
            else:
                m["why"], m["sure"] = "企鹅号这天没有这个标题,这天后台也没有别的多出来 —— 没发上", True
    return {"nick": nick, "ours": len(ours), "live": len(live), "ok": sum(1 for p in live if p["flag"] != "审核中"),
            "review": sum(1 for p in live if p["flag"] == "审核中"), "missing": missing, "extra": left, "edu": True}


def platform_on(cl, day: str, max_pages: int = 400) -> list[dict]:
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


# 导出表格的「品类」(照用户企业微信表「企鹅号每日发文情况」那页,2026-10-25 截图)
ACC_CAT = {"PUBG突围君": "PUBG", "和平精英上分君": "和平精英", "CSGO战神君": "CSGO", "DNF连招档案馆": "地下城与勇士",
           "QQ飞车漂移课堂": "QQ飞车", "LOLM峡谷日常": "LOL手游", "LOL玩家聚集地": "LOL端游", "三角洲密探君": "三角洲行动",
           "云顶上分情报局": "云顶之弈", "暗区突围情报局": "暗区突围", "光与夜心动剧场": "光与夜之恋", "电竞情报馆": "亚运会电竞赛事"}
CAT_NAME = {"教育": "小学生家长教育", "动漫": "动漫"}


def table_rows(st, rec, day: str, results: dict) -> list[tuple]:
    """导出用的行:[(品类, 号, 规定, 实发, 是不是小计)]。实发:16 个号用核对出来的(企鹅号上实发),
    没查到的(教育号没取钥匙的)用软件记录。"""
    from . import plan
    sent = rec.sent_on(day)
    out, tq, ta = [], 0, 0
    for g in plan.plan(st):
        cq = ca = 0
        for nick, q in (g.get("accounts") or {}).items():
            q = plan.quota_on(st, nick, day) if q else 0
            r = results.get(nick) or {}
            a = r["live"] if ("live" in r and not r.get("error")) else sent.get(nick, 0)
            cat = ACC_CAT.get(nick) or CAT_NAME.get(g.get("cat"), g.get("cat") or "")
            out.append((cat, nick, q, a, False))
            cq, ca = cq + q, ca + a
        out.append((g.get("label") or f"{g.get('cat')}总发布量", "", cq, ca, True))
        tq, ta = tq + cq, ta + ca
    out.append(("总发布量", "", tq, ta, True))
    return out


def export_xlsx(path: str, st, rec, day: str, results: dict) -> str:
    """导出成企业微信表那个样子:品类 / 账号名称 / 规定视频条数 / 10月25日(实发)。教育、动漫的品类格子合并。返回文件路径。"""
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    rows = table_rows(st, rec, day, results)
    y, m, d = (int(x) for x in day.split("-"))
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "企鹅号每日发文情况"
    thin = Side(style="thin", color="D0D4DA")
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    mid = Alignment(horizontal="center", vertical="center", wrap_text=True)
    blue = Font(color="1F3A8A", bold=True)
    for c, h in enumerate(["品类", "账号名称", "规定视频条数", f"{m}月{d}日"], 1):
        x = ws.cell(1, c, h)
        x.font, x.alignment, x.border = Font(bold=True), mid, box
    r = 2
    for cat, nick, q, a, total in rows:
        vals = [cat, nick, q, a]
        for c, val in enumerate(vals, 1):
            x = ws.cell(r, c, val)
            x.alignment, x.border = mid, box
            x.font = Font(bold=True) if total else blue if c <= 2 else Font()
        if cat == "总发布量":
            ws.cell(r, 1).fill = PatternFill("solid", fgColor="8DD8F8")
        r += 1
    # 教育、动漫:同一个品类连着好几行的,品类格子合并
    k = 2
    while k < r:
        j = k
        while j + 1 < r and ws.cell(j + 1, 1).value == ws.cell(k, 1).value and ws.cell(k, 2).value and ws.cell(j + 1, 2).value:
            j += 1
        if j > k:
            ws.merge_cells(start_row=k, start_column=1, end_row=j, end_column=1)
        k = j + 1
    edu_ok = any((results.get(n) or {}).get("edu") and not (results.get(n) or {}).get("error") for n in results)
    ws.cell(r + 1, 1, "说明:去企鹅号核对出来的实发条数(按真正发出去的时间,审核不通过、删掉的不算)" +
            ("。" if edu_ok else ";教育号还没取钥匙的,按软件记录。")).font = Font(color="6B7280")
    for col, w in (("A", 16), ("B", 18), ("C", 14), ("D", 12)):
        ws.column_dimensions[col].width = w
    wb.save(path)
    return path


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
