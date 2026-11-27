"""内置 AI 助手后端(用户 2026-11-26):
用设置里已经配好的 AI(本机填了「自己的模型」就用自己的,没填就用阿里百炼),
给 AI 挂 6 个只读/受控工具:
  1. check_today_plan        —— 查今天(或指定日期)各号规定条数 vs 软件记录已发条数
  2. verify_backend          —— 去企鹅号真实后台查实发条数、漏发(没发上)、多发、重复
  3. check_black_covers      —— 扫描后台黑封面 / 模糊封面,可选顺手截清晰封面
  4. find_archived_videos    —— 搜索发布记录并定位本地 / 归档视频位置
  5. pull_back_for_republish —— 把确定没发上(或用户指定)的已归档视频连封面拎回今天待发目录,记录改回没发
  6. open_in_czgt            —— 去创作罐头切到该账号「作品管理」并搜出该视频

安全红线(代码层硬拦 + 系统提示词双保险):
  - 绝不提供自动发布接口,绝不提供删除企鹅号线上作品接口;
  - 批量拎回时默认只拎回「确定没发上(sure=True)」的条目,不确定/打回/删了/延迟/审核中的绝不自动挪动;
  - 只做「查一下」时,界面附带可点击的一键按钮,由用户决定是否执行。
"""
from __future__ import annotations

import json
import os
import re
from datetime import timedelta
from typing import Any, Callable

from . import aiconf, aierr, blackcover, config, plan, redo, verify

MAX_ROUNDS = 6

SYSTEM_PROMPT = """你是「企鹅号发布助手」内置的 AI 助手，用简洁、接地气的大白话帮运营同学查进度、查后台漏发、查黑封面、找回视频准备重发。

你可以调用的工具：
1. check_today_plan：查软件记录里某天（默认今天）各号规定条数、已发条数、还差多少。
2. verify_backend：去企鹅号真实后台核对某天（默认今天）实发条数、漏发（确定没发上 / 不确定）、后台多出来的视频。
3. check_black_covers：扫描企鹅号后台某天（默认今天）有没有黑封面或模糊封面，必要时可把 auto_export 设为 true 顺手截清晰封面。
4. find_archived_videos：按关键词、账号或日期搜索发布记录，查视频现在在归档还是待发目录。
5. pull_back_for_republish：把没发上但挪到归档里的视频（连同封面）拎回今天待发目录，并把记录改回没发。
6. open_in_czgt：在创作罐头里切到对应账号的「作品管理」并搜出该视频。

必须遵守的安全规则：
- 你绝对不能自动发布视频，也绝对不能删除企鹅号线上已发作品（也没有这两个能力）。
- 当用户只是让你「查一下 / 看看今天发完没 / 有没有黑封面 / 有没有漏发」时，只调用查询工具，不要擅自调用 pull_back_for_republish；查完清楚汇报结果即可（界面会自动给出操作按钮）。
- 当用户明确下达执行指令（如「把今天没发上但挪到已发里的都拿出来重发」「帮我把《xxx》拎回来重发」「顺手截清晰封面」）时，可以直接调用对应工具：
  * 批量拎回时保持 confirmed_only=true，只自动挪「确定没发上」的视频；把「审核打回 / 被删 / 延迟 / 审核中 / 不确定」的单独列出来，绝不自动挪。
  * 挪完后逐条写清楚挪了哪条、挪到了哪个文件夹、有没有跳过或失败的，并提醒用户去对应页面核对后再手动发布。
- 回答尽量简明清晰，先说结论，再列关键清单（账号、条数、标题、原因），不要编造工具里没返回的数据。"""

TOOLS_SCHEMA: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "check_today_plan",
            "description": "查看某天（默认今天）各品类与各账号的规定条数、软件记录已发条数、还差几条的账号列表。",
            "parameters": {
                "type": "object",
                "properties": {
                    "day": {"type": "string", "description": "日期，如 '2026-11-26'、'11.26'、'今天'、'昨天'；留空默认今天。"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_backend",
            "description": "去企鹅号真实后台核对某天（默认今天）的实际发布条数、漏发（软件记已发但后台没发上）和后台多出的视频。",
            "parameters": {
                "type": "object",
                "properties": {
                    "day": {"type": "string", "description": "日期，如 '2026-11-26'、'11.26'、'今天'、'昨天'；留空默认今天。"},
                    "accounts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "只查指定账号名列表（支持简称/部分匹配）；留空查全部已授权账号。",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_black_covers",
            "description": "扫描企鹅号后台某天（默认今天）已发视频有没有黑封面或模糊封面。",
            "parameters": {
                "type": "object",
                "properties": {
                    "day": {"type": "string", "description": "日期，留空默认今天。"},
                    "accounts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "只查指定账号名列表；留空查全部账号。",
                    },
                    "auto_export": {
                        "type": "boolean",
                        "description": "是否顺手从原视频截清晰替代封面导出到封面目录，默认 false。",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_archived_videos",
            "description": "在软件发布记录里搜索视频，并查看视频文件目前在归档目录还是待发目录、能否拎回重发。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "标题关键词，可留空按账号或日期查。"},
                    "account": {"type": "string", "description": "账号名（支持部分匹配），可留空。"},
                    "day": {"type": "string", "description": "发布日期（如今天/昨天/2026-11-26/11.26），可留空。"},
                    "status": {"type": "string", "description": "状态过滤，如 '已发'、'没发成'，可留空。"},
                    "limit": {"type": "integer", "description": "最多返回条数，默认 30。"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pull_back_for_republish",
            "description": "把没发上但已归档（或用户明确指定）的视频连同封面挪回今天待发目录，并把记录改回没发。绝不自动发布。",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "description": "要拎回的视频列表，每项提供 row_id（优先）或 account + title。",
                        "items": {
                            "type": "object",
                            "properties": {
                                "row_id": {"type": "integer"},
                                "account": {"type": "string"},
                                "title": {"type": "string"},
                            },
                        },
                    },
                    "target_day": {"type": "string", "description": "目标日期文件夹，如 '11.26'；留空默认今天。"},
                    "confirmed_only": {
                        "type": "boolean",
                        "description": "是否只允许拎回后台核实确定没发上(sure=True)的条目。批量补发请保持 true；用户点名指定某条时可设为 false。",
                    },
                },
                "required": ["items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_in_czgt",
            "description": "在创作罐头里切到对应账号的「作品管理」并搜索该视频标题，方便人工处理。",
            "parameters": {
                "type": "object",
                "properties": {
                    "account": {"type": "string", "description": "账号全称。"},
                    "title": {"type": "string", "description": "视频标题。"},
                    "day": {"type": "string", "description": "发布日期（YYYY-MM-DD），可留空。"},
                },
                "required": ["account", "title"],
            },
        },
    },
]

QUICK_PROMPTS = [
    ("plan", "查今天发完没", "帮我查一下今天各号发完没，哪些号还差多少条？"),
    ("verify", "去后台查漏发", "去企鹅号后台核对一下今天发的视频，看看有没有软件记已发但后台没发上的。"),
    ("black", "查今天黑封面", "帮我扫描一下今天企鹅号后台有没有黑封面或模糊封面。"),
    ("archived", "查没发但已归档", "去后台查一下今天有没有没发上但已经挪到归档里的视频，列出来看看，先别挪。"),
]


def parse_day(text: str, today_fn: Callable[[], str] | None = None) -> str:
    """把「今天 / 昨天 / 11.26 / 2026-11-26」规范成 YYYY-MM-DD。"""
    t = (text or "").strip()
    today_s = (today_fn or plan.today)()
    if not t or t in ("今天", "今日", "today"):
        return today_s
    if t in ("昨天", "昨日", "yesterday"):
        now = config.bj_now()
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    if t in ("前天",):
        now = config.bj_now()
        return (now - timedelta(days=2)).strftime("%Y-%m-%d")
    m = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$", t)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m2 = re.match(r"^(\d{1,2})[.\-/月](\d{1,2})日?$", t)
    if m2:
        d = plan.md_to_day(f"{int(m2.group(1))}.{int(m2.group(2))}")
        if d:
            return d
    return today_s


def day_to_md(day: str) -> str:
    """'2026-11-26' -> '11.26'。"""
    m = re.match(r"^\d{4}-(\d{1,2})-(\d{1,2})$", (day or "").strip())
    if m:
        return f"{int(m.group(1))}.{int(m.group(2))}"
    now = config.bj_now()
    return f"{now.month}.{now.day}"


def _match_accounts(all_accs: list[dict], wanted: list[str] | None) -> list[dict]:
    if not wanted:
        return list(all_accs)
    ws = [str(w or "").strip() for w in wanted if str(w or "").strip()]
    if not ws:
        return list(all_accs)
    out = []
    for a in all_accs:
        nick = str(a.get("nick") or "")
        nl = nick.casefold()
        if any(w.casefold() in nl or nl in w.casefold() for w in ws):
            out.append(a)
    return out


def _in_archive(st, row: dict, loc: str) -> bool:
    """判断找到的文件是否已经挪进了归档（与原 path 不同，或位于归档根目录内）。"""
    if not loc:
        return False
    orig = row.get("path") or ""
    if orig and os.path.normcase(os.path.normpath(loc)) != os.path.normcase(os.path.normpath(orig)):
        return True
    for key in ("archive_root", "api_archive"):
        ar = str((st.get(key) if st else "") or "").strip()
        if ar and os.path.normcase(os.path.normpath(loc)).startswith(os.path.normcase(os.path.normpath(ar))):
            return True
    return False


def _chat_request(ai: aiconf.AI, messages: list[dict], tools: list[dict] | None, timeout: int = 90) -> dict:
    """调用 OpenAI 兼容 /chat/completions(支持 function calling)。"""
    import requests
    body: dict[str, Any] = {
        "model": ai.model,
        "temperature": 0.2,
        "max_tokens": aiconf.tokens(ai, 1200),
        "messages": messages,
        **ai.extra(),
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    try:
        r = requests.post(
            ai.url(),
            json=body,
            headers={"Authorization": f"Bearer {ai.key}", "Content-Type": "application/json"},
            timeout=timeout,
        )
    except UnicodeError:
        raise RuntimeError(f"{ai.who}的 Key 里有中文 / 全角字符，请检查设置")
    except (requests.RequestException, ValueError) as e:
        raise RuntimeError(f"连不上{ai.who}（地址对吗？服务开着吗？{type(e).__name__}）")
    try:
        j = r.json()
        msg = j["choices"][0]["message"]
        if not isinstance(msg, dict):
            raise ValueError("bad message")
        return msg
    except Exception:
        raise RuntimeError(aierr.why(r, ai.who) or f"{ai.who}没回话(HTTP {r.status_code}){r.text[:120]}")


class AssistantAgent:
    """维护一次对话上下文、缓存最近一次核对结论、执行工具调用与一键动作。"""

    def __init__(self, st, rec, chat_fn: Callable | None = None, deps: dict | None = None):
        self.st = st
        self.rec = rec
        self.chat_fn = chat_fn or _chat_request
        self.deps = dict(deps or {})
        self.history: list[dict[str, Any]] = []
        # 缓存最近一次后台核对每条记录的 sure 判定：{row_id: {"sure": bool, "why": str, "redone": bool, ...}}
        self._last_verify_map: dict[int, dict[str, Any]] = {}

    def reset(self) -> None:
        self.history.clear()
        self._last_verify_map.clear()

    def ai_config(self) -> aiconf.AI:
        model = str(self.st.get("topic_model") or aiconf.TEXT_MODEL)
        return aiconf.text(self.st, model)

    # ---------------- 6 个核心工具实现 ----------------

    def tool_check_today_plan(self, day: str = "") -> dict[str, Any]:
        d = parse_day(day, self.deps.get("today_fn"))
        s = plan.summary(self.rec, self.st, d)
        shorts = plan.short_list(s)
        free_set = set(s.get("free") or [])
        done, over = [], []
        for cat, nick, tgt, got in s["accounts"]:
            if nick in free_set:
                continue
            if tgt and got == tgt:
                done.append({"cat": cat, "account": nick, "quota": tgt, "sent": got})
            elif tgt and got > tgt:
                over.append({"cat": cat, "account": nick, "quota": tgt, "sent": got, "over": got - tgt})
        tq, ta = s["total"]
        return {
            "day": d,
            "total_quota": tq,
            "total_sent": ta,
            "all_done": len(shorts) == 0,
            "categories": [{"label": lab, "quota": q, "sent": a} for lab, q, a in s["rows"]],
            "short_accounts": [{"account": n, "quota": q, "sent": a, "left": q - a} for n, q, a in shorts],
            "done_count": len(done),
            "over_accounts": over,
            "free_accounts": [{"account": n, "sent": a} for _c, n, _q, a in s["accounts"] if n in free_set],
        }

    def _get_accounts_with_kind(self) -> list[tuple[dict, bool]]:
        """返回 [(account_dict, is_edu), ...]。"""
        if "accounts_fn" in self.deps:
            raw = self.deps["accounts_fn"]()
            out = []
            for item in raw:
                if isinstance(item, tuple):
                    out.append((item[0], bool(item[1])))
                else:
                    out.append((item, bool(item.get("_edu"))))
            return out
        from . import apiacc
        api_list = [a for a in apiacc.load() if a.get("client_id") and a.get("secret")]
        have = {a.get("nick") for a in api_list}
        q_list = [a for a in apiacc.qload() if a.get("nick") not in have and a.get("client_id") and a.get("secret")]
        return [(a, False) for a in api_list] + [(a, True) for a in q_list]

    def _make_client(self, acc: dict):
        if "make_client" in self.deps:
            return self.deps["make_client"](acc)
        from . import apiacc, omapi
        return omapi.Client(acc["client_id"], apiacc.unseal(acc["secret"]))

    def tool_verify_backend(
        self,
        day: str = "",
        accounts: list[str] | None = None,
        on_progress: Callable[[str], None] | None = None,
        stopped: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        d = parse_day(day, self.deps.get("today_fn"))
        all_pairs = self._get_accounts_with_kind()
        if accounts:
            matched_nicks = {a.get("nick") for a in _match_accounts([p[0] for p in all_pairs], accounts)}
            pairs = [p for p in all_pairs if p[0].get("nick") in matched_nicks]
        else:
            pairs = all_pairs
        if not pairs:
            return {
                "day": d,
                "checked_accounts": 0,
                "error": "没有找到已授权可核对的账号（请先在软件里搬账号或「登录取钥匙」）。",
                "per_account": [],
                "confirmed_missing": [],
                "uncertain_missing": [],
                "extras": [],
            }

        check_api_fn = self.deps.get("check_account_fn", verify.check_account)
        check_edu_fn = self.deps.get("check_edu_fn", verify.check_edu)
        per_acc, confirmed, uncertain, extras = [], [], [], []
        for idx, (acc, is_edu) in enumerate(pairs, 1):
            if stopped and stopped():
                break
            nick = str(acc.get("nick") or "")
            if on_progress:
                on_progress(f"正在核对企鹅号后台（{idx}/{len(pairs)}）：{nick}…")
            try:
                cl = self._make_client(acc)
                res = check_edu_fn(cl, self.rec, nick, d) if is_edu else check_api_fn(cl, self.rec, nick, d)
            except Exception as e:
                per_acc.append({"account": nick, "error": str(e)[:120]})
                continue
            m_sure, m_unsure = 0, 0
            for m in res.get("missing") or []:
                rid = m.get("id")
                loc = redo.locate(self.st, m)
                why_no = redo.why_not_movable(m)
                item = {
                    "row_id": rid,
                    "account": nick,
                    "title": m.get("title") or "",
                    "day": d,
                    "why": m.get("why") or "",
                    "sure": bool(m.get("sure")),
                    "redone": bool(m.get("redone")),
                    "located": loc,
                    "in_archive": _in_archive(self.st, m, loc),
                    "can_pull_back": bool(loc and not why_no),
                    "why_not_movable": why_no,
                }
                if rid is not None:
                    self._last_verify_map[int(rid)] = item
                if item["sure"] and not item["redone"]:
                    m_sure += 1
                    confirmed.append(item)
                else:
                    m_unsure += 1
                    uncertain.append(item)
            for ex in res.get("extra") or []:
                extras.append({
                    "account": nick,
                    "title": ex.get("title") or "",
                    "time": ex.get("time") or "",
                    "flag": ex.get("flag") or "",
                })
            per_acc.append({
                "account": nick,
                "ours": int(res.get("ours") or 0),
                "live": int(res.get("live") or 0),
                "ok": int(res.get("ok") or 0),
                "review": int(res.get("review") or 0),
                "missing_sure": m_sure,
                "missing_unsure": m_unsure,
                "extra_count": len(res.get("extra") or []),
            })
        return {
            "day": d,
            "checked_accounts": len(per_acc),
            "per_account": per_acc,
            "confirmed_missing": confirmed,
            "uncertain_missing": uncertain,
            "extras": extras[:30],
            "extras_total": len(extras),
        }

    def tool_check_black_covers(
        self,
        day: str = "",
        accounts: list[str] | None = None,
        auto_export: bool = False,
        on_progress: Callable[[str], None] | None = None,
        stopped: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        d = parse_day(day, self.deps.get("today_fn"))
        all_accs = [p[0] for p in self._get_accounts_with_kind()]
        accs = _match_accounts(all_accs, accounts)
        if not accs:
            return {"day": d, "checked_accounts": 0, "total_found": 0, "items": [], "error": "没有找到可查封面的账号。"}
        scan_fn = self.deps.get("scan_one_fn", blackcover.scan_one)
        export_fn = self.deps.get("export_covers_fn", blackcover.export_covers)
        found, bad_imgs, pending, errs = [], 0, 0, []
        for idx, acc in enumerate(accs, 1):
            if stopped and stopped():
                break
            nick = str(acc.get("nick") or "")
            if on_progress:
                on_progress(f"正在扫描封面（{idx}/{len(accs)}）：{nick}…")
            stats: dict[str, int] = {}
            try:
                kw: dict[str, Any] = {"stopped": stopped, "stats": stats}
                if "make_client" in self.deps:
                    kw["make_client"] = self.deps["make_client"]
                if "fetch_fn" in self.deps:
                    kw["fetch"] = self.deps["fetch_fn"]
                items, bad = scan_fn(acc, d, d, **kw)
                found.extend(items)
                bad_imgs += int(bad or 0)
                pending += int(stats.get("pending") or 0)
            except Exception as e:
                errs.append({"account": nick, "error": str(e)[:100]})
        exported = 0
        if auto_export and found and not (stopped and stopped()):
            if on_progress:
                on_progress(f"正在给 {len(found)} 条问题封面截取清晰封面…")
            exported = export_fn(found, self.st, rec=self.rec, stopped=stopped, step=on_progress)
        if not accounts and not (stopped and stopped()):
            try:
                blackcover.save(d, found)
            except Exception:
                pass
        return {
            "day": d,
            "checked_accounts": len(accs),
            "total_found": len(found),
            "summary": blackcover.summary_text(found) or "没有黑封面或模糊封面",
            "items": [
                {
                    "account": x.get("nick") or "",
                    "title": x.get("title") or "",
                    "time": x.get("time") or "",
                    "kind": x.get("kind") or "黑封面",
                    "aid": x.get("aid") or "",
                    "cover_file": x.get("cover_file") or "",
                }
                for x in found
            ],
            "failed_images": bad_imgs,
            "pending": pending,
            "exported_count": exported,
            "errors": errs,
        }

    def tool_find_archived_videos(
        self,
        keyword: str = "",
        account: str = "",
        day: str = "",
        status: str = "",
        limit: int = 30,
    ) -> dict[str, Any]:
        kw = (keyword or "").strip()
        acc_kw = (account or "").strip().casefold()
        day_norm = parse_day(day, self.deps.get("today_fn")) if (day or "").strip() else ""
        lim = max(1, min(int(limit or 30), 80))
        if kw:
            rows = redo.search(self.rec, kw, limit=lim * 3)
        else:
            rows = self.rec.rows()
        out = []
        for r in rows:
            r_acc = str(r.get("account") or "")
            if acc_kw and acc_kw not in r_acc.casefold():
                continue
            if status and str(r.get("status") or "") != status.strip():
                continue
            if day_norm:
                pub_d = str(r.get("published_at") or "")[:10]
                date_d = plan.md_to_day(str(r.get("date") or "")) if r.get("date") else ""
                if pub_d != day_norm and date_d != day_norm:
                    continue
            loc = redo.locate(self.st, r)
            why_no = redo.why_not_movable(r)
            out.append({
                "row_id": r["id"],
                "account": r_acc,
                "title": r.get("title") or "",
                "status": r.get("status") or "",
                "date": r.get("date") or "",
                "published_at": r.get("published_at") or "",
                "located": loc,
                "in_archive": _in_archive(self.st, r, loc),
                "movable": bool(loc and not why_no),
                "why_not_movable": why_no or ("" if loc else "找不到这个视频文件（归档里也没有）"),
            })
            if len(out) >= lim:
                break
        return {"count": len(out), "items": out}

    def _resolve_row(self, spec: dict[str, Any]) -> dict[str, Any] | None:
        rid = spec.get("row_id")
        if rid is not None:
            try:
                rid_int = int(rid)
                for r in self.rec.rows():
                    if int(r["id"]) == rid_int:
                        return r
            except (TypeError, ValueError):
                pass
        acc = str(spec.get("account") or "").strip()
        title = str(spec.get("title") or "").strip()
        if title:
            cands = redo.search(self.rec, title, limit=30)
            for r in cands:
                if (not acc or acc.casefold() in str(r.get("account") or "").casefold()) and str(r.get("title") or "").strip() == title:
                    return r
            for r in cands:
                if not acc or acc.casefold() in str(r.get("account") or "").casefold():
                    return r
        return None

    def tool_pull_back_for_republish(
        self,
        items: list[dict[str, Any]],
        target_day: str = "",
        confirmed_only: bool = True,
        on_progress: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        d = parse_day(target_day, self.deps.get("today_fn")) if (target_day or "").strip() else (self.deps.get("today_fn") or plan.today)()
        md = day_to_md(d)
        moved, skipped, failed = [], [], []
        seen_ids: set[int] = set()
        for idx, spec in enumerate(items or [], 1):
            if not isinstance(spec, dict):
                continue
            row = self._resolve_row(spec)
            if row is None:
                failed.append({
                    "row_id": spec.get("row_id"),
                    "account": spec.get("account") or "",
                    "title": spec.get("title") or "",
                    "error": "在发布记录里找不到这条视频",
                })
                continue
            rid = int(row["id"])
            if rid in seen_ids:
                continue
            seen_ids.add(rid)
            nick = str(row.get("account") or "")
            title = str(row.get("title") or "")
            if confirmed_only:
                vinfo = self._last_verify_map.get(rid)
                if vinfo is not None and (not vinfo.get("sure") or vinfo.get("redone")):
                    skipped.append({
                        "row_id": rid,
                        "account": nick,
                        "title": title,
                        "reason": vinfo.get("why") or "不是「确定没发上」，按安全规则不自动挪动",
                    })
                    continue
            if on_progress:
                on_progress(f"正在拎回视频（{idx}/{len(items)}）：{title[:22]}…")
            info: dict[str, Any] = {}
            new_path, err = redo.pull_back(self.st, self.rec, row, md, out=info)
            if err:
                failed.append({"row_id": rid, "account": nick, "title": title, "error": err})
            else:
                moved.append({
                    "row_id": rid,
                    "account": nick,
                    "title": title,
                    "new_path": new_path,
                    "room_added": int(info.get("room") or 0),
                    "warn": list(info.get("warn") or []),
                })
        return {
            "target_md": md,
            "moved_count": len(moved),
            "skipped_count": len(skipped),
            "failed_count": len(failed),
            "moved": moved,
            "skipped": skipped,
            "failed": failed,
        }

    def tool_open_in_czgt(self, account: str, title: str, day: str = "") -> dict[str, Any]:
        fn = self.deps.get("open_czgt_fn", blackcover.open_in_czgt)
        d = parse_day(day, self.deps.get("today_fn")) if (day or "").strip() else ""
        try:
            msg = fn(account, title, day=d)
            return {"ok": True, "message": msg or f"已在创作罐头切到「{account}」并搜索《{title[:24]}》"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ---------------- 工具分发 + 动作按钮提取 ----------------

    def _dispatch_tool(
        self,
        name: str,
        args: dict[str, Any],
        on_progress: Callable[[str], None] | None,
        stopped: Callable[[], bool] | None,
    ) -> dict[str, Any]:
        if name == "check_today_plan":
            return self.tool_check_today_plan(day=str(args.get("day") or ""))
        if name == "verify_backend":
            return self.tool_verify_backend(
                day=str(args.get("day") or ""),
                accounts=args.get("accounts"),
                on_progress=on_progress,
                stopped=stopped,
            )
        if name == "check_black_covers":
            return self.tool_check_black_covers(
                day=str(args.get("day") or ""),
                accounts=args.get("accounts"),
                auto_export=bool(args.get("auto_export", False)),
                on_progress=on_progress,
                stopped=stopped,
            )
        if name == "find_archived_videos":
            return self.tool_find_archived_videos(
                keyword=str(args.get("keyword") or ""),
                account=str(args.get("account") or ""),
                day=str(args.get("day") or ""),
                status=str(args.get("status") or ""),
                limit=int(args.get("limit") or 30),
            )
        if name == "pull_back_for_republish":
            return self.tool_pull_back_for_republish(
                items=list(args.get("items") or []),
                target_day=str(args.get("target_day") or ""),
                confirmed_only=bool(args.get("confirmed_only", True)),
                on_progress=on_progress,
            )
        if name == "open_in_czgt":
            return self.tool_open_in_czgt(
                account=str(args.get("account") or ""),
                title=str(args.get("title") or ""),
                day=str(args.get("day") or ""),
            )
        return {"error": f"不支持的工具：{name}（安全策略不允许执行发布或删除操作）"}

    def _build_actions(self, trace: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
        """根据本轮调用过的查询工具结果，生成附带在回复下方的可点击快捷动作按钮。"""
        actions: list[dict[str, Any]] = []
        pulled_ids: set[int] = set()
        exported_cover = False
        for name, res in trace:
            if name == "pull_back_for_republish":
                for m in res.get("moved") or []:
                    if m.get("row_id") is not None:
                        pulled_ids.add(int(m["row_id"]))
            elif name == "check_black_covers" and int(res.get("exported_count") or 0) > 0:
                exported_cover = True

        for name, res in trace:
            if name == "verify_backend":
                cand = [
                    x for x in (res.get("confirmed_missing") or [])
                    if x.get("can_pull_back") and x.get("row_id") is not None and int(x["row_id"]) not in pulled_ids
                ]
                if cand:
                    actions.append({
                        "label": f"一键拎回这 {len(cand)} 条准备重发",
                        "kind": "pull_back",
                        "tone": "primary",
                        "payload": {
                            "items": [{"row_id": x["row_id"], "account": x["account"], "title": x["title"]} for x in cand],
                            "confirmed_only": True,
                        },
                    })
            elif name == "check_black_covers":
                items = list(res.get("items") or [])
                if items and not exported_cover:
                    actions.append({
                        "label": f"给这 {len(items)} 条截清晰封面",
                        "kind": "export_covers",
                        "tone": "primary",
                        "payload": {
                            "day": res.get("day") or "",
                            "items": [
                                {"nick": x["account"], "title": x["title"], "time": x["time"],
                                 "kind": x["kind"], "aid": x["aid"]}
                                for x in items
                            ],
                        },
                    })
                for x in items[:5]:
                    t_short = (x["title"][:12] + "…") if len(x["title"]) > 12 else x["title"]
                    actions.append({
                        "label": f"去罐头定位：{x['account']}《{t_short}》",
                        "kind": "open_czgt",
                        "tone": "normal",
                        "payload": {"account": x["account"], "title": x["title"], "day": res.get("day") or ""},
                    })
            elif name == "find_archived_videos":
                cand = [
                    x for x in (res.get("items") or [])
                    if x.get("movable") and x.get("in_archive") and x.get("row_id") is not None and int(x["row_id"]) not in pulled_ids
                ]
                if cand:
                    label = (
                        f"拎回「{cand[0]['title'][:14]}」准备重发"
                        if len(cand) == 1
                        else f"拎回这 {len(cand)} 条归档视频准备重发"
                    )
                    actions.append({
                        "label": label,
                        "kind": "pull_back",
                        "tone": "normal",
                        "payload": {
                            "items": [{"row_id": x["row_id"], "account": x["account"], "title": x["title"]} for x in cand[:20]],
                            "confirmed_only": False,
                        },
                    })
        return actions

    # ---------------- 主对话入口 ----------------

    def ask(
        self,
        user_text: str,
        on_progress: Callable[[str], None] | None = None,
        stopped: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        """执行一轮对话（含多轮工具调用），返回 {'reply': str, 'actions': list, 'mutated': bool}。"""
        text = (user_text or "").strip()
        if not text:
            return {"reply": "", "actions": [], "mutated": False}
        ai = self.ai_config()
        if not ai.key and self.chat_fn is _chat_request:
            return {
                "reply": "还没有配置 AI Key：点左下角「设置」，在「AI(两边共用)」里填阿里百炼 Key 或你自己的模型后就能用对话助手了（上面的 4 个快捷按钮无需 Key 也能直接点）。",
                "actions": [],
                "mutated": False,
            }
        today_s = (self.deps.get("today_fn") or plan.today)()
        sys_msg = {"role": "system", "content": SYSTEM_PROMPT + f"\n\n当前北京时间日期：{today_s}。"}
        # 只保留最近 20 条历史，避免上下文过长
        work_msgs: list[dict[str, Any]] = [sys_msg] + self.history[-20:] + [{"role": "user", "content": text}]
        trace: list[tuple[str, dict[str, Any]]] = []
        mutated = False
        reply = ""

        for round_i in range(MAX_ROUNDS):
            if stopped and stopped():
                reply = "已停止。"
                break
            if on_progress:
                on_progress(f"正在思考并调用工具（第 {round_i + 1} 步）…" if round_i else "正在请 AI 分析你的问题…")
            msg = self.chat_fn(ai, work_msgs, TOOLS_SCHEMA, 90)
            tool_calls = msg.get("tool_calls") or []
            content = aiconf.clean(msg.get("content") or "")
            if not tool_calls:
                reply = content or "查完了，没有补充内容。"
                break
            work_msgs.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": tool_calls})
            for tc in tool_calls:
                if stopped and stopped():
                    break
                fn_info = tc.get("function") or {}
                fn_name = str(fn_info.get("name") or "")
                raw_args = fn_info.get("arguments") or "{}"
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                except Exception:
                    args = {}
                if on_progress:
                    label_map = {
                        "check_today_plan": "正在核对今日发布进度…",
                        "verify_backend": "正在去企鹅号后台核对实发与漏发…",
                        "check_black_covers": "正在扫描企鹅号后台封面…",
                        "find_archived_videos": "正在搜索本地与归档视频…",
                        "pull_back_for_republish": "正在把视频连封面拎回今天待发目录…",
                        "open_in_czgt": "正在打开创作罐头定位视频…",
                    }
                    on_progress(label_map.get(fn_name, f"正在执行 {fn_name}…"))
                res = self._dispatch_tool(fn_name, args, on_progress, stopped)
                trace.append((fn_name, res))
                if fn_name == "pull_back_for_republish" and int(res.get("moved_count") or 0) > 0:
                    mutated = True
                work_msgs.append({
                    "role": "tool",
                    "tool_call_id": str(tc.get("id") or fn_name),
                    "name": fn_name,
                    "content": json.dumps(res, ensure_ascii=False),
                })
        else:
            reply = "工具调用轮次已达上限，请缩小范围后再试一次。"

        self.history.append({"role": "user", "content": text})
        self.history.append({"role": "assistant", "content": reply})
        if len(self.history) > 30:
            self.history = self.history[-30:]
        actions = self._build_actions(trace)
        return {"reply": reply, "actions": actions, "mutated": mutated}

    # ---------------- 无需额外大模型往返的快捷操作 & 内联按钮执行 ----------------

    def run_quick(
        self,
        kind: str,
        on_progress: Callable[[str], None] | None = None,
        stopped: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        """4 个顶部快捷按钮：直接调用对应本地/后台工具并整理成清晰可读的中文报告（不依赖 Key，也更快）。"""
        if kind == "plan":
            if on_progress:
                on_progress("正在核对今日各号发布进度…")
            r = self.tool_check_today_plan()
            lines = [f"【{r['day']} 发布进度】总共已发 {r['total_sent']} / 规定 {r['total_quota']} 条。"]
            for c in r["categories"]:
                lines.append(f"· {c['label']}：{c['sent']} / {c['quota']}")
            if r["short_accounts"]:
                lines.append("\n还没发够的账号：")
                for x in r["short_accounts"]:
                    lines.append(f"  - {x['account']}：已发 {x['sent']} / 规定 {x['quota']}（还差 {x['left']} 条）")
            else:
                lines.append("\n所有有规定条数的账号都已发够 ✓")
            if r["over_accounts"]:
                lines.append("\n超出规定条数：")
                for x in r["over_accounts"]:
                    lines.append(f"  - {x['account']}：已发 {x['sent']} / 规定 {x['quota']}（多 {x['over']} 条）")
            reply = "\n".join(lines)
            self.history.extend([{"role": "user", "content": "查今天发完没"}, {"role": "assistant", "content": reply}])
            return {"reply": reply, "actions": [], "mutated": False}

        if kind in ("verify", "archived"):
            r = self.tool_verify_backend(on_progress=on_progress, stopped=stopped)
            if r.get("error"):
                return {"reply": r["error"], "actions": [], "mutated": False}
            conf = r["confirmed_missing"]
            unc = r["uncertain_missing"]
            lines = [f"【{r['day']} 企鹅号后台核对】共核对 {r['checked_accounts']} 个账号："]
            if conf:
                lines.append(f"\n确定没发上（共 {len(conf)} 条）：")
                for x in conf[:20]:
                    loc_s = "在归档，可拎回" if (x["in_archive"] and x["can_pull_back"]) else (
                        "在本地，可拎回" if x["can_pull_back"] else f"无法自动拎回：{x['why_not_movable'] or '找不到文件'}"
                    )
                    lines.append(f"  - [{x['account']}] 《{x['title']}》—— {x['why']}（{loc_s}）")
            else:
                lines.append("\n没有发现「确定没发上」的视频 ✓")
            if unc:
                lines.append(f"\n需人工看一眼（共 {len(unc)} 条，不会自动挪）：")
                for x in unc[:15]:
                    lines.append(f"  - [{x['account']}] 《{x['title']}》—— {x['why']}")
            errs = [a for a in r["per_account"] if a.get("error")]
            if errs:
                lines.append("\n查失败的账号：" + "、".join(f"{a['account']}({a['error'][:30]})" for a in errs))
            reply = "\n".join(lines)
            prompt_txt = "查没发但已归档" if kind == "archived" else "去后台查漏发"
            self.history.extend([{"role": "user", "content": prompt_txt}, {"role": "assistant", "content": reply}])
            return {"reply": reply, "actions": self._build_actions([("verify_backend", r)]), "mutated": False}

        if kind == "black":
            r = self.tool_check_black_covers(on_progress=on_progress, stopped=stopped)
            if r.get("error"):
                return {"reply": r["error"], "actions": [], "mutated": False}
            items = r["items"]
            lines = [f"【{r['day']} 封面扫描】共查 {r['checked_accounts']} 个账号：{r['summary']}。"]
            for x in items[:20]:
                lines.append(f"  - [{x['account']}] {x['kind']}：《{x['title']}》（{x['time'][5:16]}）")
            if r.get("pending"):
                lines.append(f"另有 {r['pending']} 条还在处理/审核中，暂时没有封面图。")
            reply = "\n".join(lines)
            self.history.extend([{"role": "user", "content": "查今天黑封面"}, {"role": "assistant", "content": reply}])
            return {"reply": reply, "actions": self._build_actions([("check_black_covers", r)]), "mutated": False}

        return self.ask(kind, on_progress=on_progress, stopped=stopped)

    def execute_action(
        self,
        action: dict[str, Any],
        on_progress: Callable[[str], None] | None = None,
        stopped: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        """点击消息下方附带的一键按钮后直接执行动作，返回 {'reply': str, 'actions': list, 'mutated': bool}。"""
        kind = str(action.get("kind") or "")
        payload = dict(action.get("payload") or {})

        if kind == "pull_back":
            res = self.tool_pull_back_for_republish(
                items=list(payload.get("items") or []),
                target_day=str(payload.get("target_day") or ""),
                confirmed_only=bool(payload.get("confirmed_only", True)),
                on_progress=on_progress,
            )
            lines = [f"拎回完成（目标目录：{res['target_md']}）：成功 {res['moved_count']} 条，跳过 {res['skipped_count']} 条，失败 {res['failed_count']} 条。"]
            for m in res["moved"]:
                lines.append(f"  ✓ [{m['account']}] 《{m['title']}》 → {m['new_path']}")
                for w in m.get("warn") or []:
                    lines.append(f"     提醒：{w}")
            for s in res["skipped"]:
                lines.append(f"  - 跳过 [{s['account']}] 《{s['title']}》：{s['reason']}")
            for f in res["failed"]:
                lines.append(f"  ✗ 失败 [{f['account']}] 《{f['title']}》：{f['error']}")
            if res["moved_count"] > 0:
                lines.append("\n已把视频放回待发目录并改回「没发」，请到对应发布页刷新后人工确认再发布。")
            reply = "\n".join(lines)
            self.history.append({"role": "assistant", "content": reply})
            return {"reply": reply, "actions": [], "mutated": res["moved_count"] > 0}

        if kind == "export_covers":
            items = list(payload.get("items") or [])
            export_fn = self.deps.get("export_covers_fn", blackcover.export_covers)
            if on_progress:
                on_progress(f"正在给 {len(items)} 条问题封面截取清晰封面…")
            n = export_fn(items, self.st, rec=self.rec, stopped=stopped, step=on_progress)
            out_dir = str(self.st.get("bad_cover_dir") or r"E:\图片\企鹅号")
            reply = f"已截取清晰封面：{n} / {len(items)} 条（保存目录：{out_dir}）。"
            self.history.append({"role": "assistant", "content": reply})
            return {"reply": reply, "actions": [], "mutated": False}

        if kind == "open_czgt":
            res = self.tool_open_in_czgt(
                account=str(payload.get("account") or ""),
                title=str(payload.get("title") or ""),
                day=str(payload.get("day") or ""),
            )
            reply = res["message"] if res.get("ok") else f"没打开成功：{res.get('error')}"
            self.history.append({"role": "assistant", "content": reply})
            return {"reply": reply, "actions": [], "mutated": False}

        return {"reply": f"不支持的操作：{kind}", "actions": [], "mutated": False}
