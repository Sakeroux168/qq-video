"""全自动运行留痕日志（用户 2026-11-27）：

按北京时间日期落盘到 `<数据目录>/全自动留痕/YYYY-MM-DD.log`：
  - 每条记录即时落盘刷新（即使断电/异常退出也能保留到最后一步）；
  - 统一格式：`[HH:MM:SS] [阶段] [级别] [账号] 内容`（无账号时省略账号栏）；
  - 支持筛选「只看异常 / 失败 / 跳过」、列出近 30 天日志文件、自动清理超过 30 天的旧日志；
  - 供界面「留痕日志」弹窗与 AI 助手 `read_autopilot_log` 工具直接读取。
"""
from __future__ import annotations

import os
import re
import threading
from datetime import timedelta
from pathlib import Path
from typing import Any

from .config import bj_now, data_dir

_LOCK = threading.Lock()
_LISTENERS: list = []
_KEEP_DAYS = 30
_ERR_LEVELS = frozenset({"WARN", "ERROR", "SKIP", "FAIL"})
_LINE_RE = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s+\[([^\]]+)\]\s+\[([^\]]+)\]\s*(.*)$")
_ACC_PREFIX_RE = re.compile(r"^\[([^\]]+)\]\s*(.*)$")


def parse_line(ln: str) -> dict[str, Any]:
    """把单行留痕解析成结构化字典，供彩色时间线表格展示与统计。"""
    m = _LINE_RE.match(ln or "")
    if not m:
        return {"time": "", "stage": "日志", "level": "INFO", "account": "", "message": str(ln or ""), "is_empty_tick": False}
    ts, stg, lvl, rest = m.group(1), m.group(2).strip(), m.group(3).strip().upper(), m.group(4).strip()
    acc = ""
    am = _ACC_PREFIX_RE.match(rest)
    if am:
        acc, rest = am.group(1).strip(), am.group(2).strip()
    is_empty = (stg == "值守巡检" and "无新落稳视频" in rest)
    return {"time": ts, "stage": stg, "level": lvl, "account": acc, "message": rest, "is_empty_tick": is_empty}


def summarize_and_fold(lines: list[str], *, fold_empty: bool = True) -> dict[str, Any]:
    """统计整日关键指标，并按需把连续「无新落稳视频」空巡检折叠成清爽一行。"""
    parsed = [parse_line(ln) for ln in lines if (ln or "").strip()]
    stats = {"published": 0, "processed": 0, "skipped": 0, "errors": 0}
    for r in parsed:
        lvl, stg, msg = r["level"], r["stage"], r["message"]
        if lvl == "OK" and "发布成功" in msg:
            stats["published"] += 1
        elif lvl == "OK" and ("转竖屏成功" in msg or "剪片尾成功" in msg or stg == "③改标题"):
            stats["processed"] += 1
        elif lvl == "SKIP":
            stats["skipped"] += 1
        elif lvl in ("ERROR", "FAIL", "WARN"):
            stats["errors"] += 1

    if not fold_empty:
        return {"stats": stats, "rows": parsed, "folded_count": 0}

    rows: list[dict[str, Any]] = []
    folded_total = 0
    i = 0
    n = len(parsed)
    while i < n:
        r = parsed[i]
        if not r["is_empty_tick"]:
            rows.append(r)
            i += 1
            continue
        j = i + 1
        while j < n and parsed[j]["is_empty_tick"]:
            j += 1
        cnt = j - i
        if cnt == 1:
            rows.append(r)
        else:
            t1 = parsed[i]["time"][:5] or parsed[i]["time"]
            t2 = parsed[j - 1]["time"][:5] or parsed[j - 1]["time"]
            folded_total += cnt - 1
            rows.append({
                "time": f"{t1}~{t2}" if t1 != t2 else parsed[i]["time"],
                "stage": "值守巡检",
                "level": "FOLD",
                "account": "",
                "message": f"静默巡检 {cnt} 轮（均无新落稳视频）",
                "is_empty_tick": True,
                "folded": cnt,
            })
        i = j
    return {"stats": stats, "rows": rows, "folded_count": folded_total}


def add_listener(fn) -> None:
    """注册实时日志监听函数 fn(line, stage, level, account, message)，用于前端动态卡片即时滚动。"""
    with _LOCK:
        if fn not in _LISTENERS:
            _LISTENERS.append(fn)


def remove_listener(fn) -> None:
    with _LOCK:
        if fn in _LISTENERS:
            _LISTENERS.remove(fn)


def log_dir() -> Path:
    d = data_dir() / "全自动留痕"
    d.mkdir(parents=True, exist_ok=True)
    return d


def log_path(day_iso: str = "") -> Path:
    d = (day_iso or "").strip() or bj_now().strftime("%Y-%m-%d")
    safe = re.sub(r"[^0-9\-]", "", d) or bj_now().strftime("%Y-%m-%d")
    return log_dir() / f"{safe}.log"


def prune_old(keep_days: int = _KEEP_DAYS) -> int:
    """清理超过 keep_days 天的旧留痕文件，返回删了几个。"""
    cutoff = (bj_now() - timedelta(days=max(1, int(keep_days)))).strftime("%Y-%m-%d")
    removed = 0
    try:
        for p in log_dir().glob("*.log"):
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem) and p.stem < cutoff:
                try:
                    p.unlink()
                    removed += 1
                except OSError:
                    pass
    except OSError:
        pass
    return removed


def write(
    stage: str,
    message: str,
    *,
    level: str = "INFO",
    account: str = "",
    day_iso: str = "",
) -> str:
    """追加一条留痕记录并立刻刷盘。返回写入的那一行文本。"""
    ts = bj_now().strftime("%H:%M:%S")
    lvl = (level or "INFO").strip().upper()
    stg = (stage or "系统").strip()
    acc = (account or "").strip()
    msg = str(message or "").replace("\r", " ").replace("\n", " | ").strip()
    line = f"[{ts}] [{stg}] [{lvl}] " + (f"[{acc}] " if acc else "") + msg
    p = log_path(day_iso)
    with _LOCK:
        try:
            with open(p, "a", encoding="utf-8") as f:
                f.write(line + "\n")
                f.flush()
        except OSError:
            pass
        listeners = list(_LISTENERS)
    for fn in listeners:
        try:
            fn(line, stg, lvl, acc, msg)
        except Exception:
            pass
    return line


def list_days(limit: int = 30) -> list[str]:
    """返回已有留痕文件的日期列表（最新在前），如 ['2026-11-27', '2026-11-26']。"""
    try:
        days = [p.stem for p in log_dir().glob("*.log") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem)]
    except OSError:
        return []
    days.sort(reverse=True)
    return days[:max(1, int(limit))]


def read(
    day_iso: str = "",
    *,
    errors_only: bool = False,
    account: str = "",
    limit: int = 300,
) -> dict[str, Any]:
    """读取某天留痕日志，支持只看异常/失败/跳过、按账号过滤与末尾截断。"""
    d = (day_iso or "").strip() or bj_now().strftime("%Y-%m-%d")
    p = log_path(d)
    if not p.is_file():
        return {"day": d, "path": str(p), "total_lines": 0, "matched_lines": 0, "lines": [], "text": ""}
    try:
        raw_lines = p.read_text("utf-8", errors="replace").splitlines()
    except OSError:
        raw_lines = []

    acc_q = (account or "").strip().casefold()
    out: list[str] = []
    for ln in raw_lines:
        if errors_only:
            m = _LINE_RE.match(ln)
            lvl = m.group(3).upper() if m else ""
            if lvl not in _ERR_LEVELS:
                continue
        if acc_q and acc_q not in ln.casefold():
            continue
        out.append(ln)

    lim = max(1, min(int(limit or 300), 2000))
    clipped = out[-lim:]
    return {
        "day": d,
        "path": str(p),
        "total_lines": len(raw_lines),
        "matched_lines": len(out),
        "truncated": len(out) > len(clipped),
        "lines": clipped,
        "text": "\n".join(clipped),
    }
