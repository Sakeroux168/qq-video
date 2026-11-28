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
import shutil
from datetime import timedelta
from typing import Any, Callable

from . import aiconf, aierr, apicover, apisrc, aplog, autopilot, blackcover, config, folders, plan, redo, verify
from .records import pkey

MAX_ROUNDS = 6

SYSTEM_PROMPT = """你是「企鹅号发布助手」内置的 AI 助手，用简洁、接地气的大白话帮运营同学查进度、查后台漏发、查黑封面、找回视频重发、清理过期文件夹，以及发起「16 个号今日全自动」。

你可以调用的工具：
1. check_today_plan：查软件记录里某天（默认今天）各号规定条数、已发条数、还差多少。
2. verify_backend：去企鹅号真实后台核对某天（默认今天）实发条数、漏发（确定没发上 / 不确定）、后台多出来的视频。
3. check_black_covers：扫描企鹅号后台某天或某日期段（day ~ end_day）有没有黑封面或模糊封面，必要时可把 auto_export 设为 true 顺手截清晰封面。
4. find_archived_videos：按关键词、账号或日期搜索发布记录，查视频现在在归档还是待发目录。
5. pull_back_for_republish：把没发上但挪到归档里的视频（连同封面）拎回今天待发目录，并把记录改回没发。
6. open_in_czgt：在创作罐头里切到对应账号的「作品管理」并搜出该视频。
7. scan_old_folders：扫描软件配置的游戏视频 / 动漫视频目录里某个日期及以前的旧日期文件夹，检查里面是否有未发视频、已发残留视频、残留封面、原片备份夹或 .meowload / Thumbs.db 等垃圾文件。
8. clean_old_folders：安全清理过期/残留日期文件夹——已发过的视频归档或去重删除、残留封面挪进归档、清掉 .meowload / Thumbs.db / 结尾原片等残留后删空目录；绝不删未发过的视频。
9. prepare_autopilot：当用户想让你帮他全自动处理并发布今天的 16 个号（游戏 / 动漫）时调用，生成一份简洁的「今日全自动确认卡片」（不会直接发，等用户在卡片上点一次「确认启动全自动」才会真正执行，卡片上支持一键勾选「全天每 10 分钟值守巡检」）。
10. manage_watch：全天值守运行期间，响应用户一句话动态调整值守规则——如查询当前值守状态（status）、临时跳过某个号（skip_account）、取消跳过（unskip_account）、把某个无日期夹加入今天值守（add_folder）、修改巡检间隔分钟数（set_interval）、修改晚上收工时间（set_cutoff）、结束今天值守（stop）。
11. read_autopilot_log：查看某天（默认今天）全自动与全天值守的完整留痕日志，可筛选只看异常/失败/跳过或按账号过滤，用于复盘今天全自动都做了什么、具体哪一步出了错。

必须遵守的安全规则：
- 你绝对不能绕过确认卡片直接发布视频，也绝对不能删除企鹅号线上已发作品，也绝对不能删除任何未发过的视频文件。
- 当用户让你「全自动跑今天 16 个号 / 自动处理并发布」时，调用 prepare_autopilot，然后用 1~2 句简短的话提醒用户在下方卡片点「确认启动全自动」即可，不要重复把长列表再写一遍。
- 当用户只是让你「查一下 / 列出来看看」时，只调用查询工具，不要擅自调用清理或拎回工具；查完清楚汇报结果即可（界面会自动附带一键操作按钮）。
- 当用户明确下达执行指令（如「把这些过期残留文件夹清理掉」「把今天没发上但挪到已发里的都拿出来重发」「顺手截清晰封面」）时，可以直接调用对应执行工具，并逐条汇报结果。
- 当用户说「某某号可以了 / 可以发了 / 放行某某 / 发某某的某某夹」时（通常指该号有备注等待中的目录或刚发现的无日期目录），先调 `manage_watch(action="status")` 查看 `waiting` 和 `undated` 列表，确认该号对应的文件夹后调 `manage_watch(action="add_folder", account=..., folder=...)` 放行并立刻触发巡检。
- 回答尽量简明清晰，先说结论，再列关键清单，不要编造工具里没返回的数据。"""

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
            "description": "扫描企鹅号后台某天或某日期段（day ~ end_day）已发视频有没有黑封面或模糊封面。",
            "parameters": {
                "type": "object",
                "properties": {
                    "day": {"type": "string", "description": "开始日期（或单天日期），留空默认今天。"},
                    "end_day": {"type": "string", "description": "结束日期（查多天时填，如 '11.26'）；留空只查 day 那一天。"},
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
    {
        "type": "function",
        "function": {
            "name": "scan_old_folders",
            "description": "扫描软件配置的素材目录（游戏视频 / 动漫视频）下某个日期及以前的旧日期文件夹，检查里面是否有未发视频、已发残留视频、残留封面、原片备份夹或 .meowload / Thumbs.db 等垃圾文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "before_day": {"type": "string", "description": "截止日期（含当天，如 '11.25'、'2026-11-25'、'昨天'）；留空默认昨天及以前。"},
                    "root_filter": {"type": "string", "description": "按根目录筛选，如 '游戏'、'动漫' 或完整路径；留空扫描全部配置目录。"},
                    "accounts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "只看指定账号列表（支持简称）；留空看全部账号。",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clean_old_folders",
            "description": "安全清理过期/残留日期文件夹：已发视频归档或去重删除、残留封面挪进归档、清掉 .meowload / Thumbs.db / 结尾原片等残留并删空文件夹；绝对保留未发过的视频。",
            "parameters": {
                "type": "object",
                "properties": {
                    "folders": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要清理的文件夹完整路径列表（来自 scan_old_folders）；留空按 before_day / root_filter 清理全部可清理项。",
                    },
                    "before_day": {"type": "string", "description": "截止日期（含当天），留空默认昨天及以前。"},
                    "root_filter": {"type": "string", "description": "按根目录筛选，如 '游戏'、'动漫'；留空全部。"},
                    "accounts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "只清理指定账号列表；留空全部。",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_autopilot",
            "description": "准备「16 个号（游戏 / 动漫）全自动」执行计划并在界面弹出一次性确认卡片（只读扫描，不直接发布；等用户在卡片点确认启动后才会自动执行转竖屏、整理标题、发布、清残留、查漏补发与扫黑封面，支持开启全天值守巡检）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "day": {"type": "string", "description": "要发布的日期，如 '今天'、'11.27'；留空默认今天。"},
                    "accounts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "只跑指定账号名列表（支持简称）；留空跑全部今日有文件夹的 16 个号。",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_watch",
            "description": "查看或动态调整正在进行的全天值守：查状态、临时跳过/恢复某账号、把指定子文件夹加入今天值守、修改巡检间隔或收工时间、结束值守。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["status", "skip_account", "unskip_account", "add_folder", "set_interval", "set_cutoff", "stop"],
                        "description": "要执行的值守控制动作。",
                    },
                    "account": {"type": "string", "description": "账号名（支持简称），用于 skip_account / unskip_account / add_folder。"},
                    "folder": {"type": "string", "description": "子文件夹名（如 '周末存货'）或完整路径，用于 add_folder。"},
                    "interval_min": {"type": "integer", "description": "巡检间隔（分钟，1~60），用于 set_interval。"},
                    "cutoff_hm": {"type": "string", "description": "晚上自动收工时间（如 '22:30'），用于 set_cutoff。"},
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_autopilot_log",
            "description": "查看某天（默认今天）全自动与全天值守的留痕执行日志，定位今天每一步干了什么以及具体出错/跳过原因。",
            "parameters": {
                "type": "object",
                "properties": {
                    "day": {"type": "string", "description": "日期，如 '今天'、'昨天'、'11.27'；留空默认今天。"},
                    "errors_only": {"type": "boolean", "description": "是否只看异常/失败/跳过记录，默认 false。"},
                    "account": {"type": "string", "description": "按账号名过滤，可留空。"},
                    "limit": {"type": "integer", "description": "最多返回最近多少行，默认 120。"},
                },
            },
        },
    },
]

QUICK_PROMPTS = [
    ("autopilot", "🚀 今日全自动", "准备今天 16 个号的全自动发布计划，弹出确认卡片。"),
    ("plan", "查今天发完没", "帮我查一下今天各号发完没，哪些号还差多少条？"),
    ("verify", "去后台查漏发", "去企鹅号后台核对一下今天发的视频，看看有没有软件记已发但后台没发上的。"),
    ("black", "查今天黑封面", "帮我扫描一下今天企鹅号后台有没有黑封面或模糊封面。"),
    ("archived", "查没发但已归档", "去后台查一下今天有没有没发上但已经挪到归档里的视频，列出来看看，先别挪。"),
    ("old_folders", "查过期/残留文件夹", "帮我扫描游戏和动漫素材目录里的过期日期文件夹，看看里面有没有残留或未发视频。"),
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
        self.watch: autopilot.WatchState | None = None

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
        end_day: str = "",
        accounts: list[str] | None = None,
        auto_export: bool = False,
        on_progress: Callable[[str], None] | None = None,
        stopped: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        d = parse_day(day, self.deps.get("today_fn"))
        d2 = parse_day(end_day, self.deps.get("today_fn")) if (end_day or "").strip() else d
        if d2 < d:
            d, d2 = d2, d
        all_accs = [p[0] for p in self._get_accounts_with_kind()]
        accs = _match_accounts(all_accs, accounts)
        if not accs:
            return {"day": d, "end_day": d2, "checked_accounts": 0, "total_found": 0, "items": [], "error": "没有找到可查封面的账号。"}
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
                items, bad = scan_fn(acc, d, d2, **kw)
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

    # ---------------- 过期 / 残留日期文件夹扫描与安全清理 ----------------

    def _yesterday_iso(self) -> str:
        from datetime import datetime
        t_s = (self.deps.get("today_fn") or plan.today)()
        try:
            return (datetime.strptime(t_s, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        except ValueError:
            return (config.bj_now() - timedelta(days=1)).strftime("%Y-%m-%d")

    def _filtered_api_roots(self, root_filter: str = "") -> list[str]:
        roots = [str(r) for r in (self.st.get("api_roots") or apisrc.DEFAULT_ROOTS) if str(r or "").strip()]
        rf = (root_filter or "").strip()
        if not rf:
            return roots
        rfl = rf.casefold()
        matched = [r for r in roots if rfl in r.casefold() or r.casefold() in rfl]
        return matched or roots

    def tool_scan_old_folders(
        self,
        before_day: str = "",
        root_filter: str = "",
        accounts: list[str] | None = None,
        on_progress: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        cutoff = parse_day(before_day, self.deps.get("today_fn")) if (before_day or "").strip() else self._yesterday_iso()
        roots = self._filtered_api_roots(root_filter)
        from . import apiacc
        known = set(apiacc.nicks()) or None
        acc_map = apisrc.account_folder_list(roots, known) if known else {}
        # 补充未被 known 收录但目录里确实有日期子夹的账号文件夹（防漏）
        raw_map = apisrc.account_folder_list(roots, None)
        seen_acc_dirs = {os.path.normcase(os.path.abspath(p)) for ps in acc_map.values() for p in ps}
        for nick, ps in raw_map.items():
            for p in ps:
                if os.path.normcase(os.path.abspath(p)) not in seen_acc_dirs:
                    acc_map.setdefault(nick, []).append(p)
                    seen_acc_dirs.add(os.path.normcase(os.path.abspath(p)))

        want_accs = [str(a or "").strip().casefold() for a in (accounts or []) if str(a or "").strip()]
        # 预先建立「已发」索引（按路径 pkey + 按 (账号, 规范标题)）
        sent_by_pkey: dict[str, dict] = {}
        sent_by_acc_title: dict[tuple[str, str], dict] = {}
        for r in self.rec.rows():
            if r.get("status") != "已发":
                continue
            for k in (r.get("pkey"), pkey(r.get("path") or ""), r.get("moved_pkey")):
                if k:
                    sent_by_pkey.setdefault(k, r)
            nt = folders.norm_name(r.get("title") or "")
            ra = str(r.get("account") or "").strip().casefold()
            if nt and ra:
                sent_by_acc_title.setdefault((ra, nt), r)

        found_folders: list[dict[str, Any]] = []
        acc_items = sorted(acc_map.items())
        for idx, (nick, dirs) in enumerate(acc_items, 1):
            if want_accs and not any(w in nick.casefold() or any(w in os.path.basename(d).casefold() for d in dirs) for w in want_accs):
                continue
            if on_progress:
                on_progress(f"正在扫描旧日期文件夹（{idx}/{len(acc_items)}）：{nick}…")
            for acc_dir in dirs:
                if not os.path.isdir(acc_dir):
                    continue
                alt_nick = apisrc.nick_of_folder(os.path.basename(acc_dir)).casefold()
                for sub in sorted(apisrc._subdirs(acc_dir)):
                    md = apisrc.date_key(sub)
                    if not md:
                        continue
                    d_iso = plan.md_to_day(md)
                    if not d_iso or d_iso > cutoff:
                        continue
                    sp = os.path.join(acc_dir, sub)
                    try:
                        entries = sorted(os.listdir(sp))
                    except OSError as e:
                        found_folders.append({
                            "account": nick, "folder_name": sub, "date_md": md, "date_iso": d_iso,
                            "path": sp, "status": "error", "can_clean": False, "error": str(e),
                        })
                        continue
                    sent_vids, unsent_vids = [], []
                    cover_files, junk_files, other_files = [], [], []
                    backup_dirs, junk_dirs, empty_dirs, other_dirs = [], [], [], []
                    for name in entries:
                        fp = os.path.join(sp, name)
                        if os.path.isdir(fp):
                            try:
                                sub_n = len(os.listdir(fp))
                            except OSError:
                                sub_n = -1
                            if name in apisrc.BACKUP_DIR_NAMES:
                                backup_dirs.append({"name": name, "file_count": sub_n})
                            elif apisrc.is_removable_subdir(name):
                                junk_dirs.append({"name": name, "file_count": sub_n})
                            elif sub_n == 0:
                                empty_dirs.append({"name": name, "file_count": 0})
                            else:
                                other_dirs.append({"name": name, "file_count": sub_n})
                            continue
                        if not os.path.isfile(fp):
                            continue
                        stem, ext = os.path.splitext(name)
                        ext_l = ext.lower()
                        if ext_l in apisrc.VIDEO_EXTS:
                            nt = folders.norm_name(stem)
                            row = (
                                sent_by_pkey.get(pkey(fp))
                                or sent_by_acc_title.get((nick.casefold(), nt))
                                or sent_by_acc_title.get((alt_nick, nt))
                            )
                            if row is not None:
                                archived_copy = ""
                                mp = row.get("moved_pkey") or ""
                                if mp:
                                    q = redo._real(mp) or (mp if os.path.isfile(mp) else "")
                                    if q and os.path.isfile(q) and os.path.normcase(os.path.abspath(q)) != os.path.normcase(os.path.abspath(fp)):
                                        archived_copy = q
                                if not archived_copy:
                                    loc = redo.locate(self.st, row)
                                    if loc and os.path.isfile(loc) and os.path.normcase(os.path.abspath(loc)) != os.path.normcase(os.path.abspath(fp)):
                                        archived_copy = loc
                                sent_vids.append({"name": name, "path": fp, "archived_copy": archived_copy})
                            else:
                                unsent_vids.append({"name": name, "path": fp})
                        elif apisrc.is_junk_file(name):
                            junk_files.append(name)
                        elif ext_l in apicover.IMG_EXT:
                            cover_files.append(name)
                        else:
                            other_files.append(name)

                    has_unsent = bool(unsent_vids)
                    has_unknown_sub = bool(other_dirs)
                    if not sent_vids and not has_unsent and not has_unknown_sub:
                        status, can_clean = "empty_or_leftover", True
                    elif sent_vids and not has_unsent and not has_unknown_sub:
                        status, can_clean = "all_sent", True
                    elif sent_vids:
                        status, can_clean = "partial_sent", True
                    else:
                        status, can_clean = "has_unsent", False

                    found_folders.append({
                        "account": nick,
                        "account_folder": os.path.basename(acc_dir),
                        "folder_name": sub,
                        "date_md": md,
                        "date_iso": d_iso,
                        "path": sp,
                        "status": status,
                        "can_clean": can_clean,
                        "sent_videos": sent_vids,
                        "unsent_videos": unsent_vids,
                        "cover_files": cover_files,
                        "junk_files": junk_files,
                        "other_files": other_files,
                        "backup_dirs": backup_dirs,
                        "junk_dirs": junk_dirs,
                        "empty_dirs": empty_dirs,
                        "other_dirs": other_dirs,
                    })

        found_folders.sort(key=lambda x: (x.get("date_iso") or "", x.get("account") or "", x.get("folder_name") or ""))
        return {
            "before_day": cutoff,
            "roots_scanned": roots,
            "total_folders": len(found_folders),
            "cleanable_count": sum(1 for f in found_folders if f.get("can_clean")),
            "has_unsent_count": sum(1 for f in found_folders if f.get("unsent_videos")),
            "folders": found_folders,
        }

    def _resolve_api_nick(self, query: str) -> str:
        q = (query or "").strip().casefold()
        if not q:
            return ""
        accs = autopilot._load_enabled_api_accounts(self.deps)
        for a in accs:
            nk = str(a.get("nick") or "")
            if nk.casefold() == q:
                return nk
        for a in accs:
            nk = str(a.get("nick") or "")
            if q in nk.casefold() or nk.casefold() in q:
                return nk
        return query.strip()

    def _resolve_account_subfolder(self, nick: str, folder: str) -> str:
        """把用户说的子文件夹名（如 '周末存货'）或完整路径解析为该账号目录下的真实存在路径（防越权）。"""
        f = (folder or "").strip()
        if not f:
            return ""
        roots = list(self.st.get("api_roots") or apisrc.DEFAULT_ROOTS)
        acc_dirs = apisrc.account_folder_list(roots, {nick}).get(nick) or apisrc.account_folder_list(roots, None).get(nick) or []
        if os.path.isabs(f) and os.path.isdir(f):
            nf = os.path.normcase(os.path.abspath(f))
            for ad in acc_dirs:
                nad = os.path.normcase(os.path.abspath(ad))
                if nf == nad or nf.startswith(nad + os.sep):
                    return os.path.normpath(f)
            return ""
        for ad in acc_dirs:
            cand = os.path.join(ad, f)
            if os.path.isdir(cand):
                return os.path.normpath(cand)
            for sub in apisrc._subdirs(ad):
                if f.casefold() in sub.casefold():
                    return os.path.normpath(os.path.join(ad, sub))
        return ""

    def tool_manage_watch(
        self,
        action: str,
        account: str = "",
        folder: str = "",
        interval_min: int = 0,
        cutoff_hm: str = "",
    ) -> dict[str, Any]:
        act = (action or "").strip().lower()
        w = self.watch
        if act == "status":
            if w is None or not w.active:
                return {"active": False, "message": "当前没有正在运行的全天值守。点「🚀 今日全自动」并勾选全天值守即可启动。"}
            return {"active": True, **w.snapshot(self.st, self.rec)}

        if w is None or not w.active:
            return {"ok": False, "error": "当前没有开启全天值守，请先通过「🚀 今日全自动」卡片启动值守。"}

        if act in ("skip_account", "unskip_account"):
            nk = self._resolve_api_nick(account)
            if not nk:
                return {"ok": False, "error": "请说明要跳过或恢复的账号名。"}
            w.skip_account(nk, on=(act == "skip_account"))
            msg = f"已临时跳过「{nk}」，今天值守不再发它。" if act == "skip_account" else f"已恢复「{nk}」，下轮巡检会继续处理它。"
            aplog.write("中途指挥", msg, level="INFO", account=nk, day_iso=w.day_iso)
            return {"ok": True, "message": msg, "watch_changed": True, "snapshot": w.snapshot(self.st, self.rec)}

        if act == "add_folder":
            nk = self._resolve_api_nick(account)
            if not nk:
                return {"ok": False, "error": "请说明要把文件夹加到哪个账号名下。"}
            real_p = self._resolve_account_subfolder(nk, folder) if (folder or "").strip() else ""
            if not real_p and not (folder or "").strip():
                # 没指定子夹名（如用户只说「国漫解说可以了」）：自动从该号的等待中 / 无日期发现目录里挑唯一候选
                cands = [x for x in (w.waiting_summary + w.undated_summary) if x.get("account") == nk and x.get("path")]
                uniq = []
                seen_p = set()
                for c in cands:
                    pk_c = os.path.normcase(os.path.abspath(c["path"]))
                    if pk_c not in seen_p and os.path.isdir(c["path"]):
                        seen_p.add(pk_c)
                        uniq.append(c)
                if len(uniq) == 1:
                    real_p = uniq[0]["path"]
                elif len(uniq) > 1:
                    names = "、".join(c.get("folder_name") or os.path.basename(c["path"]) for c in uniq)
                    return {"ok": False, "error": f"「{nk}」下有多个待确认目录（{names}），请说明要放行哪一个。"}
            if not real_p:
                return {"ok": False, "error": f"在「{nk}」的素材目录下找不到「{folder or '待放行'}」这个文件夹。"}
            added = w.add_extra_folder(nk, real_p)
            w.skip_account(nk, on=False)
            fk_ok = os.path.normcase(os.path.abspath(real_p))
            w.waiting_summary = [x for x in w.waiting_summary if os.path.normcase(os.path.abspath(x.get("path") or "")) != fk_ok]
            w.undated_summary = [x for x in w.undated_summary if os.path.normcase(os.path.abspath(x.get("path") or "")) != fk_ok]
            msg = f"已把「{nk}/{os.path.basename(real_p)}」加入今天的值守范围，马上开始处理。" if added else f"「{nk}/{os.path.basename(real_p)}」已经在今日值守范围里了，马上巡检。"
            aplog.write("中途指挥", msg, level="INFO", account=nk, day_iso=w.day_iso)
            return {
                "ok": True, "message": msg, "path": real_p,
                "watch_changed": True, "trigger_tick": True, "snapshot": w.snapshot(self.st, self.rec),
            }

        if act == "set_interval":
            if int(interval_min or 0) <= 0:
                return {"ok": False, "error": "请提供 1~60 之间的分钟数。"}
            m = w.set_interval(int(interval_min))
            msg = f"已把值守巡检间隔调整为每 {m} 分钟一次。"
            aplog.write("中途指挥", msg, level="INFO", day_iso=w.day_iso)
            return {"ok": True, "message": msg, "watch_changed": True, "snapshot": w.snapshot(self.st, self.rec)}

        if act == "set_cutoff":
            hm = (cutoff_hm or "").strip()
            if not re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", hm):
                return {"ok": False, "error": "收工时间格式不对，请用 24 小时制如 22:30。"}
            w.cutoff_hm = hm
            msg = f"已把今晚自动收工时间改为 {hm}。"
            aplog.write("中途指挥", msg, level="INFO", day_iso=w.day_iso)
            return {"ok": True, "message": msg, "watch_changed": True, "snapshot": w.snapshot(self.st, self.rec)}

        if act == "stop":
            w.active = False
            aplog.write("中途指挥", "用户手动结束今日全天值守", level="INFO", day_iso=w.day_iso)
            return {"ok": True, "message": "已结束今日全天值守。", "watch_changed": True, "snapshot": w.snapshot(self.st, self.rec)}

        return {"ok": False, "error": f"不支持的值守控制动作：{action}"}

    def tool_read_autopilot_log(
        self,
        day: str = "",
        errors_only: bool = False,
        account: str = "",
        limit: int = 120,
    ) -> dict[str, Any]:
        d = parse_day(day, self.deps.get("today_fn")) if (day or "").strip() else (self.deps.get("today_fn") or plan.today)()
        return aplog.read(d, errors_only=bool(errors_only), account=account, limit=int(limit or 120))

    def tool_clean_old_folders(
        self,
        folders_list: list[str] | None = None,
        before_day: str = "",
        root_filter: str = "",
        accounts: list[str] | None = None,
        on_progress: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """安全清理过期/残留日期文件夹：绝不碰配置目录外的路径，绝不删未发视频。"""
        from . import apiacc
        today_s = (self.deps.get("today_fn") or plan.today)()
        # 若显式传入路径清单，则用截止今天的全量扫描做白名单校验，防止越权删非素材目录
        scan = self.tool_scan_old_folders(
            before_day=(today_s if folders_list else before_day),
            root_filter=("" if folders_list else root_filter),
            accounts=(None if folders_list else accounts),
        )
        all_scanned = scan["folders"]
        if folders_list:
            want = {os.path.normcase(os.path.abspath(p)) for p in folders_list if p}
            targets = [f for f in all_scanned if os.path.normcase(os.path.abspath(f["path"])) in want]
        else:
            targets = [f for f in all_scanned if f.get("can_clean")]

        acc_by_nick = {str(a.get("nick") or ""): a for a in apiacc.load()}
        removed_dirs, archived_sent, deleted_dup_sent = [], [], []
        moved_leftovers, deleted_junk_or_backups, kept_unsent, errors = [], [], [], []

        for idx, f in enumerate(targets, 1):
            sp = f["path"]
            nick = f["account"]
            acc_dict = acc_by_nick.get(nick) or {"nick": nick, "source_name": f.get("account_folder") or nick}
            dest = apisrc.archive_dir(self.st, f.get("date_md") or "", acc_dict)
            if on_progress:
                on_progress(f"正在清理（{idx}/{len(targets)}）：{nick}/{f['folder_name']}…")
            if not os.path.isdir(sp):
                continue

            # 1) 已发过的视频：归档里已有副本就删重复；没归档就挪进归档
            for sv in f.get("sent_videos") or []:
                vp = sv["path"]
                if not os.path.isfile(vp):
                    continue
                try:
                    if sv.get("archived_copy") and os.path.isfile(sv["archived_copy"]):
                        for cov in apicover.find_all(vp):
                            try:
                                os.remove(cov)
                            except OSError:
                                pass
                        os.remove(vp)
                        deleted_dup_sent.append({"account": nick, "name": sv["name"], "archived_copy": sv["archived_copy"]})
                    else:
                        new_p = apisrc.move_published(vp, dest)
                        archived_sent.append({"account": nick, "name": sv["name"], "to": new_p})
                except OSError as e:
                    errors.append({"path": vp, "error": str(e)})

            # 2) 如果该目录还有未发视频或未知子目录：严格保留目录和未发视频不动
            if f.get("unsent_videos") or f.get("other_dirs"):
                kept_unsent.append({
                    "account": nick,
                    "folder": sp,
                    "unsent_count": len(f.get("unsent_videos") or []),
                    "unsent_samples": [x["name"] for x in (f.get("unsent_videos") or [])[:5]],
                    "other_dirs": [x["name"] for x in (f.get("other_dirs") or [])],
                })
                continue

            # 3) 已无未发视频：残留封面/文件挪进归档，清掉垃圾文件与原片/.meowload 子夹，删空目录
            try:
                for entry in list(os.listdir(sp)):
                    fp = os.path.join(sp, entry)
                    if os.path.isdir(fp):
                        if apisrc.is_removable_subdir(entry) or not os.listdir(fp):
                            shutil.rmtree(fp)
                            deleted_junk_or_backups.append(os.path.join(f["folder_name"], entry))
                    elif os.path.isfile(fp):
                        if apisrc.is_junk_file(entry):
                            os.remove(fp)
                            deleted_junk_or_backups.append(os.path.join(f["folder_name"], entry))
                        else:
                            plan.move_noclobber(fp, dest)
                            moved_leftovers.append({"account": nick, "name": entry, "to": dest})
                if not os.listdir(sp):
                    os.rmdir(sp)
                    removed_dirs.append({"account": nick, "folder_name": f["folder_name"], "path": sp})
            except OSError as e:
                errors.append({"path": sp, "error": str(e)})

        return {
            "removed_dirs_count": len(removed_dirs),
            "archived_sent_count": len(archived_sent),
            "deleted_dup_sent_count": len(deleted_dup_sent),
            "moved_leftovers_count": len(moved_leftovers),
            "deleted_junk_or_backups_count": len(deleted_junk_or_backups),
            "kept_unsent_count": len(kept_unsent),
            "removed_dirs": removed_dirs,
            "archived_sent": archived_sent,
            "deleted_dup_sent": deleted_dup_sent,
            "moved_leftovers": moved_leftovers,
            "deleted_junk_or_backups": deleted_junk_or_backups,
            "kept_unsent": kept_unsent,
            "errors": errors,
        }

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
                end_day=str(args.get("end_day") or ""),
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
        if name == "scan_old_folders":
            return self.tool_scan_old_folders(
                before_day=str(args.get("before_day") or ""),
                root_filter=str(args.get("root_filter") or ""),
                accounts=args.get("accounts"),
                on_progress=on_progress,
            )
        if name == "clean_old_folders":
            return self.tool_clean_old_folders(
                folders_list=args.get("folders"),
                before_day=str(args.get("before_day") or ""),
                root_filter=str(args.get("root_filter") or ""),
                accounts=args.get("accounts"),
                on_progress=on_progress,
            )
        if name == "prepare_autopilot":
            return autopilot.prepare(
                self.st, self.rec,
                day=str(args.get("day") or ""),
                accounts=args.get("accounts"),
                deps=self.deps,
            )
        if name == "manage_watch":
            return self.tool_manage_watch(
                action=str(args.get("action") or "status"),
                account=str(args.get("account") or ""),
                folder=str(args.get("folder") or ""),
                interval_min=int(args.get("interval_min") or 0),
                cutoff_hm=str(args.get("cutoff_hm") or ""),
            )
        if name == "read_autopilot_log":
            return self.tool_read_autopilot_log(
                day=str(args.get("day") or ""),
                errors_only=bool(args.get("errors_only", False)),
                account=str(args.get("account") or ""),
                limit=int(args.get("limit") or 120),
            )
        return {"error": f"不支持的工具：{name}（安全策略不允许绕过确认直接发布或删除线上作品）"}

    def _build_actions(self, trace: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
        """根据本轮调用过的查询工具结果，生成附带在回复下方的可点击快捷动作按钮。"""
        actions: list[dict[str, Any]] = []
        pulled_ids: set[int] = set()
        exported_cover = False
        cleaned_paths: set[str] = set()
        for name, res in trace:
            if name == "pull_back_for_republish":
                for m in res.get("moved") or []:
                    if m.get("row_id") is not None:
                        pulled_ids.add(int(m["row_id"]))
            elif name == "check_black_covers" and int(res.get("exported_count") or 0) > 0:
                exported_cover = True
            elif name == "clean_old_folders":
                for d in res.get("removed_dirs") or []:
                    if d.get("path"):
                        cleaned_paths.add(os.path.normcase(os.path.abspath(d["path"])))

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
            elif name == "scan_old_folders":
                cands = [
                    x for x in (res.get("folders") or [])
                    if x.get("can_clean") and os.path.normcase(os.path.abspath(x["path"])) not in cleaned_paths
                ]
                if cands:
                    actions.append({
                        "label": f"一键清理这 {len(cands)} 个过期/残留文件夹",
                        "kind": "clean_old_folders",
                        "tone": "primary",
                        "payload": {
                            "folders": [x["path"] for x in cands],
                            "before_day": res.get("before_day") or "",
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
                        "scan_old_folders": "正在扫描过期日期文件夹与残留文件…",
                        "clean_old_folders": "正在安全清理过期/残留文件夹…",
                        "prepare_autopilot": "正在生成今日 16 个号全自动计划…",
                        "manage_watch": "正在读取/调整全天值守状态…",
                        "read_autopilot_log": "正在读取今日全自动留痕日志…",
                    }
                    on_progress(label_map.get(fn_name, f"正在执行 {fn_name}…"))
                res = self._dispatch_tool(fn_name, args, on_progress, stopped)
                trace.append((fn_name, res))
                if fn_name == "pull_back_for_republish" and int(res.get("moved_count") or 0) > 0:
                    mutated = True
                if fn_name == "clean_old_folders" and (
                    int(res.get("removed_dirs_count") or 0) > 0
                    or int(res.get("archived_sent_count") or 0) > 0
                    or int(res.get("deleted_dup_sent_count") or 0) > 0
                ):
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
        card = None
        watch_changed = False
        trigger_tick = False
        for name, res in reversed(trace):
            if name == "prepare_autopilot" and card is None:
                card = {"kind": "autopilot_confirm", "plan": res}
            if name == "manage_watch" and res.get("watch_changed"):
                watch_changed = True
            if name == "manage_watch" and res.get("trigger_tick"):
                trigger_tick = True
        return {
            "reply": reply, "actions": actions, "card": card,
            "watch_changed": watch_changed, "trigger_tick": trigger_tick, "mutated": mutated,
        }

    # ---------------- 无需额外大模型往返的快捷操作 & 内联按钮执行 ----------------

    def run_quick(
        self,
        kind: str,
        on_progress: Callable[[str], None] | None = None,
        stopped: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        """4 个顶部快捷按钮：直接调用对应本地/后台工具并整理成清晰可读的中文报告（不依赖 Key，也更快）。"""
        if kind == "autopilot":
            if on_progress:
                on_progress("正在扫描今日 16 个号目录与规定条数…")
            prep = autopilot.prepare(self.st, self.rec, deps=self.deps)
            reply = (
                f"已为你整理好 {prep['md']} 的 16 个号全自动计划，确认无误点下方「确认启动全自动」即可。"
                if prep["can_start"]
                else (prep.get("reason_cannot_start") or "今天暂无可自动发布的 16 个号视频。")
            )
            self.history.extend([{"role": "user", "content": "今日全自动"}, {"role": "assistant", "content": reply}])
            return {"reply": reply, "actions": [], "card": {"kind": "autopilot_confirm", "plan": prep}, "mutated": False}

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

        if kind == "old_folders":
            r = self.tool_scan_old_folders(on_progress=on_progress)
            fs = r["folders"]
            lines = [f"【过期/残留日期文件夹扫描（≤ {r['before_day']}）】共找到 {len(fs)} 个旧日期文件夹："]
            if not fs:
                lines.append("没有找到过期或残留的日期文件夹 ✓")
            for x in fs:
                parts = []
                if x.get("unsent_videos"):
                    parts.append(f"⚠ {len(x['unsent_videos'])} 条未发视频（保留不动）")
                if x.get("sent_videos"):
                    parts.append(f"{len(x['sent_videos'])} 条已发视频")
                if x.get("cover_files"):
                    parts.append(f"{len(x['cover_files'])} 张残留封面")
                if x.get("backup_dirs"):
                    parts.append("备份夹：" + "、".join(f"{b['name']}({b['file_count']})" for b in x["backup_dirs"]))
                if x.get("junk_dirs") or x.get("junk_files"):
                    jnames = [d["name"] for d in (x.get("junk_dirs") or [])] + list(x.get("junk_files") or [])
                    parts.append("残留：" + "、".join(jnames[:4]))
                if x.get("other_dirs"):
                    parts.append("其他子夹：" + "、".join(d["name"] for d in x["other_dirs"]))
                detail = "；".join(parts) or "空文件夹"
                lines.append(f"  - [{x['account']}] {x['folder_name']}：{detail}")
            reply = "\n".join(lines)
            self.history.extend([{"role": "user", "content": "查过期/残留文件夹"}, {"role": "assistant", "content": reply}])
            return {"reply": reply, "actions": self._build_actions([("scan_old_folders", r)]), "mutated": False}

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

        if kind == "clean_old_folders":
            res = self.tool_clean_old_folders(
                folders_list=payload.get("folders"),
                before_day=str(payload.get("before_day") or ""),
                on_progress=on_progress,
            )
            lines = [
                f"清理完成：删除空/残留目录 {res['removed_dirs_count']} 个，"
                f"归档已发视频 {res['archived_sent_count']} 条，"
                f"删除已归档重复视频 {res['deleted_dup_sent_count']} 条，"
                f"挪走残留封面/文件 {res['moved_leftovers_count']} 个，"
                f"清掉垃圾/原片备份 {res['deleted_junk_or_backups_count']} 项。"
            ]
            for d in res["removed_dirs"]:
                lines.append(f"  ✓ 已删目录：[{d['account']}] {d['folder_name']}")
            for s in res["archived_sent"]:
                lines.append(f"  ✓ 已归档：[{s['account']}] {s['name']} → {s['to']}")
            for s in res["deleted_dup_sent"]:
                lines.append(f"  ✓ 已删重复已发：[{s['account']}] {s['name']}（归档已有副本）")
            for k in res["kept_unsent"]:
                lines.append(f"  ⚠ 已保留未发：[{k['account']}] {os.path.basename(k['folder'])}（含 {k['unsent_count']} 条未发视频）")
            for e in res["errors"]:
                lines.append(f"  ✗ 出错：{e['path']} — {e['error']}")
            reply = "\n".join(lines)
            self.history.append({"role": "assistant", "content": reply})
            mutated = bool(res["removed_dirs_count"] or res["archived_sent_count"] or res["deleted_dup_sent_count"])
            return {"reply": reply, "actions": [], "mutated": mutated}

        if kind == "run_autopilot":
            use_watch = bool(payload.get("watch", False))
            day_arg = str(payload.get("day") or "")
            accs_arg = list(payload.get("accounts") or [])
            if use_watch:
                d_iso = parse_day(day_arg, self.deps.get("today_fn"))
                self.watch = autopilot.WatchState(
                    day_iso=d_iso,
                    md=day_to_md(d_iso),
                    interval_min=max(1, int(payload.get("interval_min") or 10)),
                    cutoff_hm=str(payload.get("cutoff_hm") or "22:30"),
                    accounts_filter=accs_arg,
                )
                aplog.write(
                    "值守启动",
                    f"用户确认启动全天值守（{self.watch.md}，每 {self.watch.interval_min} 分钟巡检，收工 {self.watch.cutoff_hm}）",
                    level="INFO", day_iso=d_iso,
                )
                return self.run_watch_tick_result(on_progress=on_progress, stopped=stopped, is_first=True)
            rep = autopilot.run(
                self.st, self.rec,
                day=day_arg,
                accounts=accs_arg,
                on_progress=on_progress,
                stopped=stopped,
                deps=self.deps,
            )
            return self._wrap_autopilot_report(rep)

        if kind == "watch_tick":
            return self.run_watch_tick_result(on_progress=on_progress, stopped=stopped, is_first=False)

        if kind == "add_watch_folder":
            nk = str(payload.get("account") or "")
            fp = str(payload.get("path") or "")
            if self.watch is not None and self.watch.active:
                res = self.tool_manage_watch("add_folder", account=nk, folder=fp)
                msg = res.get("message") if res.get("ok") else f"没加上：{res.get('error')}"
                self.history.append({"role": "assistant", "content": msg})
                return {"reply": msg, "actions": [], "watch_changed": bool(res.get("ok")), "trigger_tick": bool(res.get("ok")), "mutated": False}
            return {"reply": "当前没有开启全天值守，请先点「🚀 今日全自动」启动值守。", "actions": [], "mutated": False}

        return {"reply": f"不支持的操作：{kind}", "actions": [], "mutated": False}

    def _wrap_autopilot_report(
        self,
        rep: dict[str, Any],
        extra_actions: list[dict[str, Any]] | None = None,
        watch_changed: bool = False,
        ended_msg: str = "",
    ) -> dict[str, Any]:
        acts: list[dict[str, Any]] = list(extra_actions or [])
        acts.append({"label": "查看留痕日志", "kind": "open_aplog", "tone": "normal", "payload": {"day": rep["day_iso"]}})
        if rep.get("skipped_items") or rep.get("missing_accounts"):
            acts.append({"label": "去「游戏 / 动漫」页查看", "kind": "goto_page", "tone": "normal", "payload": {"page": "api"}})
        for x in (rep.get("black_covers") or [])[:4]:
            ts = (x["title"][:12] + "…") if len(x["title"]) > 12 else x["title"]
            acts.append({
                "label": f"去罐头定位：{x['account']}《{ts}》",
                "kind": "open_czgt",
                "tone": "normal",
                "payload": {"account": x["account"], "title": x["title"], "day": rep["day_iso"]},
            })
        reply = (rep["summary"] + (f"\n{ended_msg}" if ended_msg else "")).strip()
        self.history.append({"role": "assistant", "content": reply})
        mutated = bool(rep["published_count"] or rep["retried_count"] or rep["cleaned_dirs_count"] or rep["renamed_count"])
        return {
            "reply": reply,
            "actions": acts,
            "card": {"kind": "autopilot_report", "report": rep},
            "key_errors": list(rep.get("key_errors") or []),
            "watch_changed": watch_changed,
            "mutated": mutated,
        }

    def run_watch_tick_result(
        self,
        on_progress: Callable[[str], None] | None = None,
        stopped: Callable[[], bool] | None = None,
        is_first: bool = False,
    ) -> dict[str, Any]:
        """执行一轮全天值守巡检，按「极致安静、仅密钥失效强提醒」规则包装返回结果。"""
        if self.watch is None or not self.watch.active:
            return {"quiet": True, "reply": "", "actions": [], "watch_changed": True, "mutated": False}
        tk = autopilot.run_watch_tick(self.st, self.rec, self.watch, on_progress=on_progress, stopped=stopped, deps=self.deps)

        undated_acts = []
        for u in tk.get("undated_discovered") or []:
            undated_acts.append({
                "label": f"加入值守：{u['account']}/{u['folder_name']}({u['video_count']}条)",
                "kind": "add_watch_folder",
                "tone": "normal",
                "payload": {"account": u["account"], "path": u["path"]},
            })

        if tk.get("has_work") and tk.get("report"):
            res = self._wrap_autopilot_report(
                tk["report"],
                extra_actions=undated_acts,
                watch_changed=True,
                ended_msg=tk.get("end_reason") or "",
            )
            res["key_errors"] = list(tk.get("key_errors") or [])
            return res

        # 没新片可发：如果已自动收工，发一条全天总战报摘要；否则仅在首次启动或发现无日期新夹时静默记一条
        if tk.get("ended"):
            snap = tk.get("snapshot") or {}
            reply = (
                f"【全天值守已自动收工】{tk.get('end_reason') or ''}\n"
                f"今日累计巡检 {snap.get('rounds', 0)} 轮，自动发布 {snap.get('total_published', 0)} 条"
                + (f"（含补发 {snap.get('total_retried', 0)} 条）" if snap.get("total_retried") else "")
                + f"，拦下异常 {snap.get('total_skipped', 0)} 条。"
            )
            self.history.append({"role": "assistant", "content": reply})
            return {"reply": reply, "actions": [], "watch_changed": True, "mutated": False}

        if undated_acts:
            lines = ["发现以下无日期文件夹今天新进了未发视频（按规则未擅自发布，需要就点下方按钮加入今天值守）："]
            for u in tk.get("undated_discovered") or []:
                lines.append(f"  · [{u['account']}] {u['folder_name']}（{u['video_count']} 条未发）")
            reply = "\n".join(lines)
            self.history.append({"role": "assistant", "content": reply})
            return {"reply": reply, "actions": undated_acts, "watch_changed": True, "mutated": False}

        if is_first:
            waits = tk.get("waiting_folders") or []
            note = (
                f"已开启全天值守（每 {self.watch.interval_min} 分钟巡检一次，发满或 {self.watch.cutoff_hm} 自动收工）。"
                + (f"\n当前有 {len(waits)} 个文件夹正在等待（如「{waits[0]['folder_name']}」：{waits[0]['reason']}），落稳/改完备注后自动接手。"
                   if waits else "\n目前盘里暂无新落稳视频，同事放好视频后会自动处理。")
            )
            self.history.append({"role": "assistant", "content": note})
            return {"reply": note, "actions": [], "watch_changed": True, "mutated": False}

        # 平时空巡检：绝对安静，不往聊天里发废话气泡
        return {"quiet": True, "reply": "", "actions": [], "watch_changed": True, "mutated": False}
