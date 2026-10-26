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
# 用户 2026-10-26 当天核对:定时还没到点的,企鹅号给的状态是个代号「10」,原来当成了「没发上」默认打勾(差点拎回来重发)。
# 现在只有明确失败的(打回 / 删了 / 发布失败)才算没发上;别的(定时没到点、审核中、认不出的代号)都算在企鹅号上、等着发
BAD_FLAGS = ("审核不通过", "审核未通过", "未通过", "未发布", "发布失败", "已下线", "已删除")


def _on(p: dict) -> bool:
    """这篇在企鹅号上(发了 / 审核中 / 定时没到点…),不算没发上。状态是空的不算(认不出,让人看一眼;审查 2026-10-26)。"""
    return not p.get("deleted") and bool(p.get("flag")) and p.get("flag") not in BAD_FLAGS


def _bad_kind(p: dict) -> str:
    """不在线的这篇是怎么回事:「删了」/「没发上」(未发布、发布失败)/「打回」/「认不出」(状态是空的)。"""
    if p.get("deleted"):
        return "删了"
    if p.get("flag") in ("未发布", "发布失败"):
        return "没发上"
    return "打回" if p.get("flag") else "认不出"


def _wait(p: dict) -> bool:
    """在企鹅号上,但还没真正发出去(审核中 / 定时没到点 / 认不出的状态)。"""
    return _on(p) and p.get("flag") not in ("发布成功", "已发布")


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
        # 同一个视频只算一次:同一个文件,或者同一天同一个标题(用户 2026-10-26:找视频重发 / 标成已发来回点,
        # 一条视频记了两条,后台只有一条,另一条被当成「没发上」)
        seen, uniq = set(), []
        for r in rows:
            ks = {r.get("pkey") or r["path"], "t:" + _tkey(r["title"])}
            if not (ks & seen):
                seen |= ks
                uniq.append(r)
        rows = uniq
    for r in rows:
        r["aid"], r["vid"] = _aid_of(r.get("note")), _vid_of(r.get("note"))
    return rows


def _tkey(t: str) -> str:
    from .folders import norm_name
    return norm_name(t)


def _redone(k: str, later: list[tuple[str, str, str]]) -> tuple[str, str]:
    """later 里有标题一样 / 很像的(相似度 ≥ 0.85,而且里面的数字一样 ——「第12期」「第13期」不算)→ (那条的日期 10-23, 那条的标题);
    没有 → ("", "")。审查 2026-10-26:原来 0.75 会把同一系列的不同期认成「已经补发过了」。"""
    from difflib import SequenceMatcher
    nums = re.findall(r"\d+", k)
    for lk, when, title in later:
        if lk == k or (min(len(k), len(lk)) >= 6 and re.findall(r"\d+", lk) == nums
                       and SequenceMatcher(None, k, lk).ratio() >= 0.85):
            return when, title
    return "", ""


def _later_rows(rec, nick: str, r: dict) -> list[tuple[str, str, str]]:
    """这个号在这条之后(按发布时间,同一天晚些时候也算)又发过的:[(标题 key, 日期, 标题)]。不管是接口发的还是罐头发的。"""
    t0 = str(r.get("published_at") or "")
    return [(_tkey(x["title"]), str(x["published_at"])[5:10], x["title"]) for x in rec.rows(account=nick)
            if x["status"] == "已发" and x["id"] != r.get("id") and str(x.get("published_at") or "") > t0]


def _settle(rec, nick: str, missing: list[dict], live: list[dict], near: list[dict]) -> list[dict]:
    """没对上的最后过一遍(审查 2026-10-26:只有确定没发上的才打勾,别让人把发上去的视频再发一遍):
    ① 这天 / 前后一天企鹅号上有同标题在线的 → 不算没发上(跨半夜 / 编号对不上 / 删掉的是重复的那条)
    ② 后来又发过同样 / 很像标题的 → 已经补发过了,不打勾
    ③ 打回 / 删了的 → 列出来,不打勾(打回的再发多半还会被打回;删的多半是人自己删的)
    sure=None(还没定的)→ 按调用方传进来的定。"""
    on_titles = {_tkey(p["title"]): p for p in live + [p for p in near if _on(p)]}
    out = []
    for m in missing:
        k = _tkey(m["title"])
        same = on_titles.get(k)
        if same is not None and same in near:
            continue                                         # 前后一天有(跨半夜):就是发上了
        if same is not None:
            m["why"], m["sure"] = f"企鹅号这天已经有同标题的一条在线了({same['time'][5:16]}),不用补", False
        else:
            when, title = _redone(k, _later_rows(rec, nick, m))
            if when:
                m["why"], m["sure"], m["redone"] = f"这天没发上,但 {when} 已经补发过了(「{title[:24]}」),不用再拎回来", False, True
            elif m.get("bad") == "删了":
                m["why"], m["sure"] = "在企鹅号上被删了(多半是人自己删的:重复的 / 横屏的…);真要补就自己勾上", False
            elif m.get("bad") == "认不出":
                m["why"], m["sure"] = "企鹅号上这条的状态是空的 / 认不出,看一眼再决定", False
            elif m.get("bad") == "打回":
                m["why"], m["sure"] = (f"被审核打回了(企鹅号上是「{m.get('flag')}」;再发多半还会被打回,换一条补更好;"
                                       "真要重发就自己勾上)"), False
        out.append(m)
    return out


def check_edu(cl, rec, nick: str, day: str, plat: list[dict] | None = None, near: list[dict] | None = None) -> dict:
    """教育号(用户 2026-10-26:钥匙只用来查,发布照旧走罐头):罐头发的记录没有文章编号,按标题对。
    先对完全一样的(去掉空格标点),再对一个是另一个开头的(企鹅号可能把长标题截短)。
    plat = 这天的后台列表,near = 前后一天的(跨半夜用);不给就自己去读。"""
    if plat is None:
        plat, near = _day_and_near(cl, day)
    near = near or []
    ours = ours_on(rec, nick, day, edu=True)
    live = [p for p in plat if _on(p)]
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
        bad = next((p for p in plat + near if _tkey(p["title"]) == k and not _on(p)), None)
        if bad is not None:
            kind = _bad_kind(bad)
            if kind == "没发上":
                missing.append(dict(r, why=f"企鹅号上是「{bad['flag']}」—— 没发上", sure=True))
            else:
                missing.append(dict(r, why="", sure=None, bad=kind, flag=bad["flag"]))
        else:
            missing.append(dict(r, why="", sure=None))
    missing = _settle(rec, nick, missing, live, near)
    # 用户 2026-10-26:标题找不到,而这天后台也没有多出来、软件没记的 → 不可能是改了标题发的,就是没发上(打勾);
    # 这天后台有多出来的 → 可能是改了标题发的,不打勾,提示看一眼
    for m in missing:
        if m["sure"] is None:
            if left:
                m["why"], m["sure"] = (f"企鹅号这天没找到这个标题;这天后台有 {len(left)} 条软件没记的,"
                                       "可能是在罐头里改了标题发的,看一眼再决定"), False
            else:
                m["why"], m["sure"] = "企鹅号这天和前后一天都没有这个标题,这天后台也没有别的多出来 —— 没发上", True
    return {"nick": nick, "ours": len(ours), "live": len(live), "ok": sum(1 for p in live if not _wait(p)),
            "review": sum(1 for p in live if _wait(p)), "missing": missing, "extra": left, "edu": True}


def _shift(day: str, n: int) -> str:
    from datetime import date, timedelta
    return (date.fromisoformat(day) + timedelta(days=n)).isoformat()


def _day_and_near(cl, day: str, stopped=None) -> tuple[list[dict], list[dict]]:
    """读这天 + 前后一天的后台列表(一遍):返回 (这天的, 前后一天的)。"""
    allp = platform_between(cl, _shift(day, -1), _shift(day, 1), stopped=stopped)
    return [p for p in allp if p["time"][:10] == day], [p for p in allp if p["time"][:10] != day]


def platform_on(cl, day: str, max_pages: int = 2000) -> list[dict]:
    """企鹅号上这个号这天发的(按发布时间):[{aid, vid, title, flag, deleted, time}]。新的在前,翻到比这天早就停。"""
    return platform_between(cl, day, day, max_pages)


class ListTooLong(RuntimeError):
    """翻到页数上限还没翻到要查的日子以前:列表没读全,不能当成查完了(审查 2026-10-26)。"""


def platform_between(cl, start: str, end: str, max_pages: int = 2000, stopped=None) -> list[dict]:
    """企鹅号上这个号 start~end(含,2026-10-10 ~ 2026-10-25)发的(按发布时间)。一页 10 条,新的在前,
    连着 3 页都比 start 早才停(用户 2026-10-24:列表不一定严格按时间排,一页就停会漏)。
    用户 2026-10-26「批量查询,从 10 号查到 25 号」:一个号只翻一遍,不用一天一天地翻。stopped() 返回 True 就停。
    翻页要好几分钟,中间有新文章进来整张表会往下挪,同一篇会读到两次 → 按文章编号(没有就按视频编号)去重(审查 2026-10-26)。
    翻满 max_pages 还没翻到 start 以前 → 抛 ListTooLong(查不了),不当成读完了。"""
    out, seen = [], set()
    old_pages = 0
    done = False
    for page in range(1, max_pages + 1):
        if stopped and stopped():
            done = True
            break
        d = cl.list_articles(page, 10)
        items = d.get("articles") or []
        if not items:
            done = True
            break
        older = 0
        for a in items:
            t = str(a.get("article_pub_time") or "")
            if start <= t[:10] <= end:
                vi = a.get("article_video_info") or {}
                p = {"aid": _aid_of_item(a), "vid": str(vi.get("vid") or ""), "title": str(a.get("article_title") or ""),
                     "flag": str(a.get("article_pub_flag") or ""), "deleted": str(a.get("article_del_flag") or "") == "已删除",
                     "time": t}
                key = p["aid"] or (("v:" + p["vid"]) if p["vid"] else "")
                if key and key in seen:
                    continue
                if key:
                    seen.add(key)
                out.append(p)
            elif t and t[:10] < start:
                older += 1
        old_pages = old_pages + 1 if older == len(items) else 0
        if old_pages >= 3:
            done = True
            break
        try:
            if page * 10 >= int(d.get("total") or 0):
                done = True
                break
        except (TypeError, ValueError):
            pass
    if not done:
        raise ListTooLong(f"后台列表翻了 {max_pages} 页还没翻到 {start[5:]} 以前,没读全,这个号这次查不了")
    return out


def check_range(cl, rec, nick: str, days: list[str], edu: bool = False, stopped=None) -> dict:
    """一段日子(批量查询):这个号的后台列表只读一遍(多读前后各一天,跨半夜用),再一天一天对。
    返回 {day: check_account / check_edu 的结果}。"""
    plat = platform_between(cl, _shift(days[0], -1), _shift(days[-1], 1), stopped=stopped)
    out = {}
    for d in days:
        if stopped and stopped():
            break
        near_days = (_shift(d, -1), _shift(d, 1))
        one = [p for p in plat if p["time"][:10] == d]
        near = [p for p in plat if p["time"][:10] in near_days]
        out[d] = (check_edu(cl, rec, nick, d, plat=one, near=near) if edu
                  else check_account(cl, rec, nick, d, plat=one, near=near))
    return out


def check_account(cl, rec, nick: str, day: str, plat: list[dict] | None = None, near: list[dict] | None = None) -> dict:
    """一个号:{nick, ours, ok, review, missing:[记录+why], extra:[企鹅号上的]}。
    plat = 已经读好的这天的后台列表、near = 前后一天的(批量查询用);不给就自己去读。"""
    if plat is None:
        plat, near = _day_and_near(cl, day)
    near = near or []
    ours = ours_on(rec, nick, day)
    live = [p for p in plat if _on(p)]
    aids = {p["aid"] for p in live if p["aid"]}
    vids = {p["vid"] for p in live if p["vid"]}
    near_ids = {p["aid"] for p in near if _on(p) and p["aid"]} | {p["vid"] for p in near if _on(p) and p["vid"]}
    missing = []
    found = []                                             # 列表里没读到、单查是这天发布成功的:算对上(也算进实发)
    for r in ours:
        if (r["aid"] and r["aid"] in aids) or (r["vid"] and r["vid"] in vids):
            continue
        if (r["aid"] and r["aid"] in near_ids) or (r["vid"] and r["vid"] in near_ids):
            continue                                       # 前后一天在线(跨半夜):发上了
        p0 = next((p for p in plat + near if r["aid"] and p["aid"] == r["aid"]), None)
        if p0 is not None:                                 # 列表里有这篇,但不在线
            kind = _bad_kind(p0)
            if kind == "没发上":
                missing.append(dict(r, why=f"企鹅号上是「{p0['flag']}」—— 没发上", sure=True))
            else:
                missing.append(dict(r, why="", sure=None, bad=kind, flag=p0["flag"]))
            continue
        # 用户 2026-10-24:软件记 50、企鹅号上 49,原来单查说「发布成功」就放过了,看不出是哪条 →
        # 这天的列表里没有的都列出来;只有单查明确说「未发布 / 发布失败」的才打勾,
        # 单查出错 / 回空 / 认不出的都让人看一眼(审查 2026-10-26:原来网一抖就默认打勾)
        if r["aid"]:
            try:
                info = (cl.article_info(r["aid"]) or {}).get("article_info") or {}
                flag, dele = str(info.get("article_pub_flag") or ""), str(info.get("article_del_flag") or "") == "已删除"
                t = str(info.get("article_pub_time") or "")
                if flag and flag not in BAD_FLAGS and not dele and t[:10] == day:
                    found.append({"aid": r["aid"], "flag": flag})   # 用户 2026-10-24:后台一搜就在,这天发的 → 就是发上了
                    continue
                if dele:
                    missing.append(dict(r, why="", sure=None, bad="删了", flag=flag))
                elif flag in ("未发布", "发布失败"):
                    missing.append(dict(r, why=f"企鹅号上是「{flag}」—— 没发上", sure=True))
                elif flag in BAD_FLAGS:
                    missing.append(dict(r, why="", sure=None, bad="打回", flag=flag))
                elif flag:
                    missing.append(dict(r, why=f"单查是「{flag}」,但发布时间是 {t[5:16] or '?'}(不是这天),看一眼再决定", sure=False))
                else:
                    missing.append(dict(r, why="企鹅号这天的列表里没有这条,单查也没查出状态,看一眼再决定", sure=False))
            except Exception as e:
                missing.append(dict(r, why=f"企鹅号这天的列表里没有这条,单查又没查成({str(e)[:40]}),看一眼再决定", sure=False))
        else:
            missing.append(dict(r, why="软件没记下文章编号,企鹅号这天的列表里也没有,看一眼再决定", sure=False))
    our_aids = {r["aid"] for r in ours if r["aid"]}
    our_vids = {r["vid"] for r in ours if r["vid"]}
    extra = [p for p in live if not ((p["aid"] and p["aid"] in our_aids) or (p["vid"] and p["vid"] in our_vids))]
    # 编号对不上的,按标题再认一遍(用户 2026-10-26 批量查询:10.17 那批记录没存下文章编号 / 编号变了,后台其实有同标题的)
    for m in list(missing):
        k = _tkey(m["title"])
        hit = next((p for p in extra if _tkey(p["title"]) == k), None)
        if hit is not None:
            extra.remove(hit)
            missing.remove(m)                                 # 就是这条(已经算在实发里了)
    missing = _settle(rec, nick, missing, live, near)
    for m in missing:
        if m["sure"] is None:
            m["why"], m["sure"] = "企鹅号这天的列表里没有这条,看一眼再决定", False
    every = live + found
    return {"nick": nick, "ours": len(ours), "live": len(every), "ok": sum(1 for p in every if not _wait(p)),
            "review": sum(1 for p in every if _wait(p)), "missing": missing, "extra": extra}


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
    gray = PatternFill("solid", fgColor="E7E6E6")
    unchecked = []
    for cat, nick, q, a, total in rows:
        vals = [cat, nick, q, a]
        for c, val in enumerate(vals, 1):
            x = ws.cell(r, c, val)
            x.alignment, x.border = mid, box
            x.font = Font(bold=True) if total else blue if c <= 2 else Font()
        res = results.get(nick) or {}
        if nick and not ("live" in res and not res.get("error")):   # 这个号没查成 / 没查:用的软件记录,标灰(审查 2026-10-26)
            ws.cell(r, 4).fill = gray
            unchecked.append(nick)
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
    ws.cell(r + 1, 1, "说明:去企鹅号核对出来的实发条数(按真正发出去的时间,审核不通过、删掉的不算)" +
            (f";标灰的 {len(unchecked)} 个号没查成 / 没查({'、'.join(unchecked[:6])}{'…' if len(unchecked) > 6 else ''}),"
             "用的软件记录,要核实再查一次。" if unchecked else "。")).font = Font(color="6B7280")
    for col, w in (("A", 16), ("B", 18), ("C", 14), ("D", 12)):
        ws.column_dimensions[col].width = w
    wb.save(path)
    return path


def export_range_xlsx(path: str, st, rec, days: list[str], by_day: dict) -> str:
    """批量查询导出(用户 2026-10-26:「从 10 号查到 25 号,然后导出成表格看」)。
    第一页照企业微信那张:品类 / 账号名称 / 规定视频条数 / 每天一列(企鹅号上核实的实发;没查到的号用软件记录,标灰);
    比规定少标红、多标黄,每个品类一行小计,最后总发布量。第二页:这段日子没发上的视频(哪天、哪个号、标题、原因、要不要补)。
    by_day = {号: {day: 结果}}。"""
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from . import plan
    thin = Side(style="thin", color="D0D4DA")
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    mid = Alignment(horizontal="center", vertical="center", wrap_text=True)
    red, yel = PatternFill("solid", fgColor="FFC7CE"), PatternFill("solid", fgColor="FFEB9C")
    gray = PatternFill("solid", fgColor="E7E6E6")
    sent = {d: rec.sent_on(d) for d in days}
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "企鹅号每日发文情况"
    head = ["品类", "账号名称", "规定视频条数"] + [f"{int(d[5:7])}月{int(d[8:10])}日" for d in days]
    for c, h in enumerate(head, 1):
        x = ws.cell(1, c, h)
        x.font, x.alignment, x.border = Font(bold=True), mid, box
    r = 2
    grand = [0] * len(days)
    gq = 0
    for g in plan.plan(st):
        tot = [0] * len(days)
        cq = 0
        first = r
        for nick, q in (g.get("accounts") or {}).items():
            cat = ACC_CAT.get(nick) or CAT_NAME.get(g.get("cat"), g.get("cat") or "")
            vals = [cat, nick, q]
            for c, v in enumerate(vals, 1):
                x = ws.cell(r, c, v)
                x.alignment, x.border = mid, box
                x.font = Font(color="1F3A8A", bold=True) if c <= 2 else Font()
            for k, d in enumerate(days):
                res = (by_day.get(nick) or {}).get(d) or {}
                ok = "live" in res and not res.get("error")
                a = res["live"] if ok else sent[d].get(nick, 0)
                x = ws.cell(r, 4 + k, a)
                x.alignment, x.border = mid, box
                qd = plan.quota_on(st, nick, d) if q else 0
                if not ok:
                    x.fill = gray
                elif qd and a < qd:
                    x.fill = red
                elif qd and a > qd:
                    x.fill = yel
                tot[k] += a
            cq += q or 0
            r += 1
        k = first                                          # 只合并相邻、品类一样的(审查:游戏 12 个号的品类各不相同)
        while k < r:
            j = k
            while j + 1 < r and ws.cell(j + 1, 1).value == ws.cell(k, 1).value:
                j += 1
            if j > k:
                ws.merge_cells(start_row=k, start_column=1, end_row=j, end_column=1)
            k = j + 1
        for c, v in enumerate([g.get("label") or f"{g.get('cat')}总发布量", "", cq] + tot, 1):
            x = ws.cell(r, c, v)
            x.font, x.alignment, x.border = Font(bold=True), mid, box
        grand = [a + b for a, b in zip(grand, tot)]
        gq += cq
        r += 1
    for c, v in enumerate(["总发布量", "", gq] + grand, 1):
        x = ws.cell(r, c, v)
        x.font, x.alignment, x.border = Font(bold=True), mid, box
    ws.cell(r, 1).fill = PatternFill("solid", fgColor="8DD8F8")
    ws.cell(r + 2, 1, "说明:企鹅号上核实的实发条数(按真正发出去的时间,审核不通过、删掉的不算);红 = 比规定少,黄 = 比规定多,"
                      "灰 = 这个号没查(没钥匙 / 查不了),用的软件记录。规定条数按现在设置里的算。").font = Font(color="6B7280")
    for col, w in (("A", 16), ("B", 18), ("C", 14)):
        ws.column_dimensions[col].width = w
    # 第二页:没发上的
    w2 = wb.create_sheet("没发上的视频")
    for c, h in enumerate(["日期", "账号", "标题", "原因", "要不要补"], 1):
        x = w2.cell(1, c, h)
        x.font, x.alignment, x.border = Font(bold=True), mid, box
    k = 2
    for d in days:
        for nick, per in by_day.items():
            for m in (per.get(d) or {}).get("missing") or []:
                need = "已经补发过了" if m.get("redone") else ("要补" if m.get("sure", True) else "看一眼再决定")
                for c, v in enumerate([f"{int(d[5:7])}.{int(d[8:10])}", nick, m.get("title") or "", m.get("why") or "", need], 1):
                    x = w2.cell(k, c, v)
                    x.border = box
                if need == "要补":
                    w2.cell(k, 5).fill = red
                k += 1
    if k == 2:
        w2.cell(2, 1, "这段日子软件记的已发,企鹅号上都有 ✓")
    for col, w in (("A", 8), ("B", 16), ("C", 46), ("D", 46), ("E", 14)):
        w2.column_dimensions[col].width = w
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
