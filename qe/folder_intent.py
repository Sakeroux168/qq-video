"""文件夹备注理解引擎 + 文件落稳检测（用户 2026-11-27）：

让全天值守能读懂同事给文件夹写的各种备注：
  - 固定词库秒判（0 延迟、0 费用）：
      * ignore（永久忽略）：已发 / 不能用 / 脏话 / 不行 / 废片 / 重复删除 / 打回 / 原片
      * wait（先别动，继续巡检等删备注）：正在处理 / 处理中 / 整理中 / 剪辑中 / 上传中 / 制作中 / 下载中 / 未完 / 别动 / 先别发 / 待核对 / 待审核 / 缺封面 …
      * ready（可以动手）：未改比例（标记含横屏待转）/ 已改比例 / 星期X / 第N批 / 补发 / 重发 / 可发 …
      * 数量标注：(15) / （15） / 15条 / 共15条 -> expected_count = 15
  - 新奇备注（固定词库不认识的）：
      * 自动问一次 AI（按备注原文持久化缓存到 文件夹备注判断.json，不重复花钱）；
      * 无 Key / 断网 / AI 拿不准 → 保守判 wait（绝不擅自乱发）。
  - 落稳检测：
      * 存在 .part / .tmp / .crdownload / ._ / _处理中_ 等写入中临时文件，或任意视频 mtime 不满 min_age_sec（默认 30 秒）→ 未落稳，跳过等下轮。
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from typing import Any, Callable

from . import aiconf, apisrc
from .config import data_dir

# 宽容日期前缀匹配：只要文件夹名以「月.日」开头（后面可以跟任意备注，如「11.27（正在处理）」「11.27(15)」「11.27 缺封面先别动」）
_LOOSE_DATE_RE = re.compile(r"^\s*(\d{1,2})\s*[.．\-_月]\s*(\d{1,2})(?![\d.．])日?(.*)$")

IGNORE_WORDS = (
    "已发", "不能用", "脏话", "不行", "废片", "重复删除", "打回", "横屏原片",
    "结尾原片", "水印原片", "广告原片", "原片", "不要", "作废", "不用",
)
WAIT_WORDS = (
    "正在处理", "处理中", "整理中", "剪辑中", "上传中", "制作中", "下载中", "转码中",
    "未完", "未完成", "还没完", "没弄完", "还没好", "未好",
    "别动", "先别动", "不要动", "别发", "先别发", "不要发", "暂不发", "暂停",
    "待核对", "待审核", "等审核", "待检查", "待修改", "等改", "待补", "缺封面", "无封面", "没封面",
)
READY_WORDS = (
    "未改比例", "未改", "已改比例", "已改", "已核对", "已检查", "可发", "能发", "好了", "改好了", "处理好了", "已处理",
    "补发", "重发", "加更", "存货", "竖屏", "横屏",
    "星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日", "星期天",
    "周一", "周二", "周三", "周四", "周五", "周六", "周日", "周天", "周末",
)
_BATCH_RE = re.compile(r"第\s*[一二三四五六七八九十\d]+\s*[批波轮次]")
# 数量标注：括号里的纯数字 (15) / （15条） 或 独立的「共15条 / 15条 / 15个」
_PAREN_COUNT_RE = re.compile(r"[（(]\s*(?:共|补|约|先发)?\s*(\d{1,3})\s*(?:条|个|集|视频)?\s*[）)]")
_BARE_COUNT_RE = re.compile(r"(?:共|补)\s*(\d{1,3})\s*(?:条|个|集)?|(?<!\d)(\d{1,3})\s*(?:条|个视频)")

_TEMP_SUFFIXES = (".part", ".tmp", ".crdownload", ".downloading", ".aria2")
_LOCK = threading.Lock()


def parse_date_and_remark(folder_name: str) -> tuple[str, str]:
    """返回 (date_md, remark_tail)。例：'11.27（正在处理）' -> ('11.27', '（正在处理）')。无日期前缀返回 ('', folder_name)。"""
    s = (folder_name or "").strip()
    m = _LOOSE_DATE_RE.match(s)
    if not m:
        return "", s
    mon, day = int(m.group(1)), int(m.group(2))
    if not (1 <= mon <= 12 and 1 <= day <= 31):
        return "", s
    return f"{mon}.{day}", (m.group(3) or "").strip()


def extract_expected_count(remark: str) -> int | None:
    """从备注中提取目标视频条数，如 '(15)' / '（15条）' / '共20条' -> 15 / 20；没有返回 None。"""
    s = (remark or "").strip()
    if not s:
        return None
    m = _PAREN_COUNT_RE.search(s)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 500:
            return n
    m2 = _BARE_COUNT_RE.search(s)
    if m2:
        raw = m2.group(1) or m2.group(2)
        if raw:
            n = int(raw)
            if 1 <= n <= 500:
                return n
    return None


def _strip_known_ready_tokens(remark: str) -> str:
    """把已经认识的『数量标注』『括号』『常规就绪词』『第X批』剥掉，看还剩没有不认识的词。"""
    s = _PAREN_COUNT_RE.sub(" ", remark or "")
    s = _BARE_COUNT_RE.sub(" ", s)
    s = _BATCH_RE.sub(" ", s)
    for w in sorted(READY_WORDS, key=len, reverse=True):
        s = s.replace(w, " ")
    # 去掉标点、空格、空括号
    s = re.sub(r"[\s()（）【】\[\]\-_,，。、·+~!?！？]+", "", s)
    return s


class RemarkCache:
    """持久化缓存 AI 判断过的新备注，同一个备注不重复问 AI。"""

    def __init__(self, path=None):
        self.path = str(path or (data_dir() / "文件夹备注判断.json"))
        self._data: dict[str, dict] = {}
        self.reload()

    def reload(self):
        with _LOCK:
            try:
                raw = json.loads(open(self.path, encoding="utf-8").read())
                self._data = raw if isinstance(raw, dict) else {}
            except (OSError, ValueError):
                self._data = {}

    def get(self, key: str) -> dict | None:
        with _LOCK:
            v = self._data.get(key)
            return dict(v) if isinstance(v, dict) else None

    def put(self, key: str, val: dict) -> None:
        with _LOCK:
            self._data[key] = dict(val)
            tmp = self.path + ".tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, ensure_ascii=False, indent=1)
                os.replace(tmp, self.path)
            except OSError:
                pass


_CACHE: RemarkCache | None = None
_CACHE_ENV = ""


def cache() -> RemarkCache:
    global _CACHE, _CACHE_ENV
    from . import config as _cfg
    env = str(getattr(_cfg._LOCAL_CTX, "data_dir", "") or "").strip() or os.environ.get("QE_DATA_DIR", "").strip()
    if _CACHE is None or _CACHE_ENV != env:
        _CACHE = RemarkCache()
        _CACHE_ENV = env
    return _CACHE


def _ask_ai_remark(folder_name: str, remark: str, ai: aiconf.AI) -> dict[str, Any]:
    """问一次 AI 理解新奇文件夹备注：返回 {'action': 'ready'|'wait'|'ignore', 'reason': str}。"""
    prompt = (
        f"运营同事在视频素材文件夹上起名为：「{folder_name}」（其中备注部分为「{remark}」）。\n"
        "请判断自动发布助手现在应该怎么对待这个文件夹，只从下面 3 种动作里选一个：\n"
        "- ready：说明素材已准备好可以处理发布（如只是标注日期、批次、未改比例、补发、说明来源等）；\n"
        "- wait：说明同事还在处理 / 等审核 / 缺东西 / 明确叫先别动，需要继续等待；\n"
        "- ignore：说明这是废片 / 已发 / 不能用 / 脏话等，永远不要发。\n"
        "如果拿不准，一律选 wait（宁可等也别误发）。\n"
        '只输出 JSON，不要其他文字：{"action":"ready|wait|ignore","reason":"一句话原因"}'
    )
    raw = aiconf._post(ai, prompt, max_tokens=160, timeout=30)
    m = re.search(r"\{[\s\S]*\}", raw or "")
    j = json.loads(m.group(0) if m else (raw or "{}"))
    act = str(j.get("action") or "wait").strip().lower()
    if act not in ("ready", "wait", "ignore"):
        act = "wait"
    return {"action": act, "reason": str(j.get("reason") or f"AI 判定：{act}")[:60]}


def interpret_folder(
    folder_name: str,
    st=None,
    ask_fn: Callable[[str, str], dict] | None = None,
) -> dict[str, Any]:
    """理解一个文件夹名：
    返回 {
        'date_md': str,
        'remark': str,
        'action': 'ready' | 'wait' | 'ignore',
        'expected_count': int | None,
        'needs_vertical_hint': bool,
        'reason': str,
        'source': 'rule' | 'cache' | 'ai' | 'fallback',
    }
    """
    md, remark = parse_date_and_remark(folder_name)
    exp = extract_expected_count(remark)
    needs_vert = ("未改比例" in remark) or ("横屏" in remark and "原片" not in remark)

    # 0) 纯日期（无备注）
    if not remark:
        return {
            "date_md": md, "remark": "", "action": "ready", "expected_count": None,
            "needs_vertical_hint": False, "reason": "标准日期文件夹", "source": "rule",
        }

    # 1) 固定词库优先：先判 ignore，再判 wait（注意：先判「已处理/处理好了」免得被「处理」误伤；WAIT_WORDS 里是精确词「正在处理/处理中」）
    for w in IGNORE_WORDS:
        if w in remark:
            return {
                "date_md": md, "remark": remark, "action": "ignore", "expected_count": exp,
                "needs_vertical_hint": needs_vert, "reason": f"备注含「{w}」，忽略不发", "source": "rule",
            }
    for w in WAIT_WORDS:
        if w in remark:
            return {
                "date_md": md, "remark": remark, "action": "wait", "expected_count": exp,
                "needs_vertical_hint": needs_vert, "reason": f"备注含「{w}」，先不动继续等", "source": "rule",
            }

    # 2) 剥掉所有已知就绪词与数量标注后，如果已经为空 -> 直接 ready（0 费用）
    leftover = _strip_known_ready_tokens(remark)
    if not leftover:
        hint = []
        if needs_vert:
            hint.append("含待转竖屏提示")
        if exp is not None:
            hint.append(f"标明 {exp} 条")
        return {
            "date_md": md, "remark": remark, "action": "ready", "expected_count": exp,
            "needs_vertical_hint": needs_vert, "reason": "、".join(hint) or "常规备注，可处理", "source": "rule",
        }

    # 3) 遇到不认识的新奇备注：先查本地缓存，再问一次 AI（拿不准保守判 wait）
    ck = leftover.casefold()
    hit = cache().get(ck)
    if hit and hit.get("action") in ("ready", "wait", "ignore"):
        return {
            "date_md": md, "remark": remark, "action": hit["action"], "expected_count": exp,
            "needs_vertical_hint": needs_vert, "reason": hit.get("reason") or f"缓存判定({hit['action']})", "source": "cache",
        }

    try:
        if ask_fn is not None:
            got = ask_fn(folder_name, remark)
        elif st is not None:
            ai = aiconf.text(st, str(st.get("topic_model") or aiconf.TEXT_MODEL))
            if not ai.key:
                raise RuntimeError("未配 AI Key")
            got = _ask_ai_remark(folder_name, remark, ai)
        else:
            raise RuntimeError("无配置")
        act = str((got or {}).get("action") or "wait").strip().lower()
        if act not in ("ready", "wait", "ignore"):
            act = "wait"
        rsn = str((got or {}).get("reason") or f"AI 判定：{act}")[:80]
        cache().put(ck, {"action": act, "reason": rsn, "remark": remark})
        return {
            "date_md": md, "remark": remark, "action": act, "expected_count": exp,
            "needs_vertical_hint": needs_vert, "reason": rsn, "source": "ai",
        }
    except Exception:
        return {
            "date_md": md, "remark": remark, "action": "wait", "expected_count": exp,
            "needs_vertical_hint": needs_vert,
            "reason": f"不认识的备注「{remark}」，保守先不动等你确认",
            "source": "fallback",
        }


def check_folder_stability(
    folder: str,
    min_age_sec: float = 30.0,
    now: float | None = None,
) -> dict[str, Any]:
    """检查文件夹是否已落稳（同事拷完 / 下载器写完）：
    返回 {'stable': bool, 'reason': str, 'video_paths': list[str], 'video_count': int, 'latest_mtime': float}。"""
    now_ts = time.time() if now is None else float(now)
    try:
        names = sorted(os.listdir(folder), key=apisrc.natural_key)
    except OSError as e:
        return {"stable": False, "reason": f"文件夹打不开:{e}", "video_paths": [], "video_count": 0, "latest_mtime": 0.0}

    videos: list[str] = []
    latest_mtime = 0.0
    for n in names:
        fp = os.path.join(folder, n)
        if not os.path.isfile(fp):
            continue
        low = n.lower()
        if low.startswith("_处理中_") or low.endswith(_TEMP_SUFFIXES):
            return {"stable": False, "reason": f"检测到正在写入的临时文件（{n}），等下轮", "video_paths": [], "video_count": 0, "latest_mtime": now_ts}
        _, ext = os.path.splitext(n)
        if ext.lower() in apisrc.VIDEO_EXTS:
            try:
                st_f = os.stat(fp)
            except OSError:
                return {"stable": False, "reason": f"文件「{n}」正在占用中，等下轮", "video_paths": [], "video_count": 0, "latest_mtime": now_ts}
            if st_f.st_size == 0:
                return {"stable": False, "reason": f"文件「{n}」目前 0 字节（可能还在拷），等下轮", "video_paths": [], "video_count": 0, "latest_mtime": now_ts}
            latest_mtime = max(latest_mtime, st_f.st_mtime)
            videos.append(fp)

    if not videos:
        return {"stable": True, "reason": "", "video_paths": [], "video_count": 0, "latest_mtime": latest_mtime}

    age = now_ts - latest_mtime
    if min_age_sec > 0 and age < min_age_sec:
        wait_s = max(1, int(min_age_sec - age))
        return {
            "stable": False,
            "reason": f"刚有视频写入（还差约 {wait_s} 秒落稳），等下轮再动手",
            "video_paths": videos,
            "video_count": len(videos),
            "latest_mtime": latest_mtime,
        }
    return {"stable": True, "reason": "", "video_paths": videos, "video_count": len(videos), "latest_mtime": latest_mtime}
